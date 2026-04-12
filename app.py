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
    # Use a clear, unique user agent to avoid being blocked
    geolocator = Nominatim(user_agent="quebec_gas_app_v2")
    
    query = query.strip().upper()
    
    # Check if it looks like a Canadian postal code
    pc_pattern = re.compile(r'^([A-Z]\d[A-Z])[ -]?(\d[A-Z]\d)?$')
    match = pc_pattern.match(query)
    
    try:
        if match:
            # ✅ IMPROVEMENT: Use a structured query
            # We only use the first 3 digits (FSA) as it's far more reliable
            fsa = match.group(1)
            loc = geolocator.geocode(
                query={
                    "postalcode": fsa,
                    "country": "Canada",
                    "state": "Quebec"
                }
            )
        else:
            # Standard search for city or street names
            loc = geolocator.geocode(f"{query}, Quebec, Canada")
            
        if loc: 
            return loc.latitude, loc.longitude
        return None, None
    except Exception as e:
        # If the API times out, try one more time with a simple string
        try:
            loc = geolocator.geocode(f"{query[:3]}, Quebec, Canada")
            if loc: return loc.latitude, loc.longitude
        except:
            return None, None
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
st.sidebar.header("📍 Location Search")
location_query = st.sidebar.text_input("Enter Postal Code, Address, or City", value="Montreal")
search_radius = st.sidebar.slider("Search Radius (km)", 1, 50, 5) # Default 5km radius

st.sidebar.divider()
# --- BRAND CONTROLS ---
show_selected_brands_only = st.sidebar.toggle("Show ONLY selected brands", value=False)
show_favs_only = st.sidebar.toggle("Show ONLY my favorite stations", value=False)

brand_list = sorted(df['brand'].dropna().unique().tolist())
selected_brands = st.sidebar.multiselect(
    "Select Brands:", 
    options=brand_list,
    default=["Esso", "Couche-Tard"]
)

st.sidebar.divider()
# --- FAVORITES SELECTION ---
all_station_addresses = sorted(df['Station_Address'].dropna().unique().tolist())

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

# --- 5. FILTERING LOGIC ---
results = df.copy()
has_distance = False

if show_favs_only and my_fav_stations:
    results = results[results['Station_Address'].isin(my_fav_stations)]
else:
    if show_selected_brands_only and selected_brands:
        results = results[results['brand'].isin(selected_brands)]
    
    # NEW: Geospatial Location Search
    if location_query:
        user_lat, user_lon = get_coordinates(location_query)
        
        if user_lat and user_lon:
            # Calculate distance for every station
            results['Distance'] = results.apply(
                lambda row: calculate_distance(user_lat, user_lon, row['Lat'], row['Lon']), axis=1
            )
            # Filter by the radius slider
            results = results[results['Distance'] <= search_radius]
            has_distance = True
        else:
            st.sidebar.error("Could not find that location. Please try a different postal code or city.")

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
