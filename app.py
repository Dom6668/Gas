import streamlit as st
import pandas as pd
import requests
import unicodedata
import urllib.parse
import math
import re
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

# Cache the geocoder so it doesn't spam the free API
@st.cache_data(ttl=3600)
def get_coordinates(query):
    geolocator = Nominatim(user_agent="qc_gas_tracker_app")
    
    # 1. Clean the input and check if it looks like a Canadian postal code
    query = query.strip()
    pc_pattern = re.compile(r'^([A-Za-z]\d[A-Za-z])[ -]?(\d[A-Za-z]\d)$')
    match = pc_pattern.match(query)
    
    try:
        if match:
            # 2. If it IS a postal code, only use the first 3 characters (the FSA)
            fsa = match.group(1).upper()
            loc = geolocator.geocode(f"{fsa}, Quebec, Canada")
        else:
            # 3. Otherwise, search the city or street name as normal
            loc = geolocator.geocode(f"{query}, Quebec, Canada")
            
        if loc: 
            return loc.latitude, loc.longitude
        return None, None
    except:
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
    results = results.sort_values(by=['Distance', 'Price']) if has_distance else results.sort_values(by='Price')
    st.success(f"Found {len(results)} stations")
    
    # ✅ THE FIX: Use the official Google Maps Search API
    # We include 'Quebec' and the Brand to make the search pinpoint accurate
    results['Map_URL'] = results.apply(
        lambda x: f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(x['brand'] + ' ' + x['Address'] + ', Quebec')}", 
        axis=1
    )
    
    # Select columns (Map_URL must be included for the LinkColumn to work)
    display_df = results[['Price', 'Distance', 'Address', 'brand', 'Map_URL']].copy()
    
    st.dataframe(
        display_df,
        column_config={
           "Price": st.column_config.NumberColumn("Price (¢)", format="%.1f"),
           "Distance": st.column_config.NumberColumn("Away (km)", format="%.1f"),
           
           # ✅ LinkColumn configuration
           "Address": st.column_config.LinkColumn(
               "Station Address", 
               # This tells Streamlit to use the Map_URL column as the target
               display_text=None 
           ),
           
           "brand": "Brand",
           "Map_URL": None # Hide the raw URL from the user
        },
        hide_index=True,
        use_container_width=True
    )
    
    st.caption("📍 Click an address to open navigation in a new tab.")
else:
    st.warning("No stations found. Adjust your filters or increase your search radius.")
