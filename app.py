import re
import streamlit as st
import pandas as pd
import requests
import unicodedata
import urllib.parse
import math
from geopy.geocoders import Nominatim

# --- 1. APP CONFIG ---
st.set_page_config(page_title="Quebec Gas Tracker", page_icon="⛽", layout="wide")

# --- 2. THE LOGIC ---
def simplify(text):
    if not isinstance(text, str): return ""
    return "".join([c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c)]).lower()

def get_price(price_list):
    if not isinstance(price_list, list): return None
    for item in price_list:
        if item.get('GasType') == 'Régulier' and item.get('IsAvailable'):
            try: return float(item.get('Price', '').replace('¢', ''))
            except: return None
    return None

# Math formula to calculate distance between two GPS coordinates
def calculate_distance(lat1, lon1, lat2, lon2):
    if pd.isna(lat1) or pd.isna(lat2): return float('inf')
    R = 6371.0 # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# Cache the geocoding results to stay within free usage limits
@st.cache_data(ttl=3600)
def get_coordinates(query):
    # Use a unique user agent to avoid being throttled
    geolocator = Nominatim(user_agent="quebec_gas_finder_v3")
    
    # 1. Clean the input
    clean_query = query.strip().upper()
    
    # Regex to extract the first 3 characters of a Canadian postal code
    pc_match = re.search(r'([A-Z]\d[A-Z])', clean_query)
    
    try:
        # Strategy A: Try the full query first with a strict Quebec filter
        loc = geolocator.geocode(f"{clean_query}, Quebec, Canada", timeout=10)
        
        # Strategy B: If that fails and it looks like a postal code, try just the FSA (first 3 digits)
        if not loc and pc_match:
            fsa = pc_match.group(1)
            # We use a structured query here which is more reliable for postal codes
            loc = geolocator.geocode(
                query={
                    "postalcode": fsa,
                    "state": "Quebec",
                    "country": "Canada"
                },
                timeout=10
            )
        
        if loc:
            return loc.latitude, loc.longitude
        
        # Strategy C: Final "Hail Mary" - search just the first 3 characters as a plain string
        if pc_match:
            loc = geolocator.geocode(f"{pc_match.group(1)}, Quebec, Canada", timeout=10)
            if loc: return loc.latitude, loc.longitude

        return None, None
    except Exception:
        return None, None

@st.cache_data(ttl=300) 
def fetch_data():
    url = "https://regieessencequebec.ca/stations.geojson.gz"
    resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    
    # Extract properties AND coordinates
    data = []
    for f in resp.json()['features']:
        props = f['properties']
        # Grab GPS coordinates if they exist in the file
        if f.get('geometry') and f['geometry'].get('coordinates'):
            props['Lon'] = f['geometry']['coordinates'][0]
            props['Lat'] = f['geometry']['coordinates'][1]
        else:
            props['Lon'], props['Lat'] = None, None
        data.append(props)

    df = pd.DataFrame(data)
    df['Price'] = df['Prices'].apply(get_price)
    df['Station_Address'] = df['brand'] + " (" + df['Address'] + ")"
    return df

# Load Data Early
df = fetch_data()

# --- 3. UI HEADER ---
col_title, col_metric = st.columns([4, 2])

with col_title:
    st.markdown("## ⛽ Live Gas Prices")

with col_metric:
    if not df.empty:
        mtl_search = simplify("Montreal")
        mtl_stations = df[df['Address'].apply(simplify).str.contains(mtl_search)]
        if not mtl_stations['Price'].empty:
            mtl_avg = mtl_stations['Price'].mean()
            st.metric("MTL Average", f"{mtl_avg:.1f}¢")

st.markdown('<div style="margin-top: -25px;"></div>', unsafe_allow_html=True)
st.divider()

# --- 4. SIDEBAR SETUP ---
st.sidebar.header("Search Filters")

# ✅ NEW: Dropdown for City Selection
city_list = ["Montreal", "Quebec", "Laval"]
selected_city = st.sidebar.selectbox("Select City", options=city_list, index=0)

# ✅ NEW: Optional Postal Code / Specific Address Input
postal_query = st.sidebar.text_input("Postal Code or Street (Optional)", value="")

st.sidebar.divider()
show_selected_brands_only = st.sidebar.toggle("Show ONLY selected brands", value=True)
brand_list = sorted(df['brand'].dropna().unique().tolist())
selected_brands = st.sidebar.multiselect(
    "Select Brands:", 
    options=brand_list,
    default=["Esso", "Couche-Tard"]
)

st.sidebar.divider()
all_station_addresses = sorted(df['Station_Address'].dropna().unique().tolist())

# --- USER CUSTOMIZATION ---
my_target_stations = [
    "Esso (2495 ch. Rockland, Mont-Royal)",
    "Esso (180 boul. Crémazie ouest, Montréal)",
    "Esso (790 boul. Crémazie est, Montréal)",
    "Esso (7635 boul. Lacordaire, Montréal)",
    "Esso (4225 rue Jarry est, Montréal)"
]
safe_defaults = [s for s in my_target_stations if s in all_station_addresses]

my_fav_stations = st.sidebar.multiselect(
    "Select your usual stops:", 
    options=all_station_addresses,
    default=safe_defaults
)
show_favs_only = st.sidebar.toggle("Show ONLY my favorite stations", value=True)

# --- 5. FILTERING LOGIC ---
results = df.copy()
has_distance = False  # ✅ ADD THIS LINE HERE to initialize the variable

if show_favs_only and my_fav_stations:
    results = results[results['Station_Address'].isin(my_fav_stations)]
else:
    if show_selected_brands_only and selected_brands:
        results = results[results['brand'].isin(selected_brands)]
    
    # Improved filtering logic with City and Postal Code
    city_term = simplify(selected_city)
    postal_term = simplify(postal_query)
    
    # Filter by selected city first
    results = results[
        results['Address'].apply(simplify).str.contains(city_term) | 
        results['Region'].apply(simplify).str.contains(city_term)
    ]
    
    # If a postal code or specific address is entered, calculate distance
    if postal_term:
        user_lat, user_lon = get_coordinates(postal_query) # Uses your improved get_coordinates
        
        if user_lat and user_lon:
            results['Distance'] = results.apply(
                lambda row: calculate_distance(user_lat, user_lon, row['Lat'], row['Lon']), axis=1
            )
            # Only show stations within the slider radius
            results = results[results['Distance'] <= search_radius]
            has_distance = True # ✅ This now updates the initialized variable

# --- 6. DISPLAY RESULTS ---
if not results.empty:
    # ✅ SORTING LOGIC: 
    # If we have distance, we sort by Price first, then Distance.
    # This ensures the cheapest stations are at the top.
    if has_distance:
        results = results.sort_values(by=['Price', 'Distance'])
    else:
        results = results.sort_values(by='Price')
        
    st.success(f"Found {len(results)} stations")

    # ✅ TOP RECOMMENDATIONS (The Cheapest Stations)
     
    # Take the top 3 after the sort
    top_3 = results.head(3)
    cols = st.columns(3)
    
    for i, (idx, row) in enumerate(top_3.iterrows()):
        # Use official Google Maps search format to avoid Streamlit redirect loop
        addr_url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(row['brand'] + ' ' + row['Address'] + ', Quebec')}"
        
        with cols[i]:
            # Large, clickable headers for the cheapest prices
            st.markdown(f"### {row['Price']:.1f}¢")
            st.markdown(f"**{row['brand']}**")
            if has_distance:
                st.markdown(f"📍 {row['Distance']:.1f} km away")
            st.markdown(f"[{row['Address']}]({addr_url})")

    st.divider()

    # --- FULL DATA TABLE ---
    st.markdown("#### All Results")
    
    # Prepare display dataframe (excluding Map_URL to avoid messy table)
    cols_to_show = ['Price']
    if has_distance: cols_to_show.append('Distance')
    cols_to_show.extend(['brand', 'Address'])
    
    display_df = results[cols_to_show].copy()
    
    st.dataframe(
        display_df,
        column_config={
           "Price": st.column_config.NumberColumn("Price (¢)", format="%.1f"),
           "Distance": st.column_config.NumberColumn("Away (km)", format="%.1f"),
           "brand": "Brand",
           "Address": "Station Address"
        },
        hide_index=True,
        use_container_width=True
    )
    
else:
    st.warning("No stations found. Adjust your filters or increase your search radius.")
