import streamlit as st
import pandas as pd
import requests
import unicodedata
import urllib.parse

# --- 1. APP CONFIG ---
st.set_page_config(page_title="Gas Tracker", page_icon="⛽")

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

@st.cache_data(ttl=300) 
def fetch_data():
    url = "https://regieessencequebec.ca/stations.geojson.gz"
    resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    df = pd.DataFrame([f['properties'] for f in resp.json()['features']])
    df['Price'] = df['Prices'].apply(get_price)
    # Combined label for the address-based favorites selector
    df['Station_Address'] = df['brand'] + " (" + df['Address'] + ")"
    return df

# Load Data Early to use in Header
df = fetch_data()

# --- 3. UI HEADER ---
col_title, col_metric = st.columns([5, 2])

with col_title:
    st.markdown("## ⛽ Live Gas Prices")

with col_metric:
    # 🔄 Refresh Button
    if st.button("🔄 Refresh", use_container_width=True):
        fetch_data.clear()
        st.rerun()
    
    # 📊 Montreal Average directly below the button
    if not df.empty:
        mtl_search = simplify("Montreal")
        mtl_stations = df[df['Address'].apply(simplify).str.contains(mtl_search)]
        if not mtl_stations['Price'].empty:
            mtl_avg = mtl_stations['Price'].mean()
            st.metric("MTL Average", f"{mtl_avg:.1f}¢")

st.divider()

# --- 4. SIDEBAR SETUP ---
st.sidebar.header("Search Filters")

# 🏙️ City Search
city_query = st.sidebar.text_input("Enter City", value="Montreal")

st.sidebar.divider()

# 🏷️ BRAND FILTER SECTION
st.sidebar.subheader("🏷️ Brand Filters")

# Brand Toggle - ON by default
show_selected_brands_only = st.sidebar.toggle("Show ONLY selected brands", value=True)

brand_list = sorted(df['brand'].dropna().unique().tolist())
selected_brands = st.sidebar.multiselect(
    "Select Brands:", 
    options=brand_list,
    default=["Esso", "Couche-Tard"]
)

st.sidebar.divider()

# ⭐ FAVORITE ADDRESSES
st.sidebar.subheader("⭐ Favorite Stations")
all_station_addresses = sorted(df['Station_Address'].dropna().unique().tolist())

# SET YOUR DEFAULT STATIONS HERE
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

# Set the favorites toggle to be ON by default
show_favs_only = st.sidebar.toggle("Show ONLY my favorite stations", value=True)

# --- 5. FILTERING LOGIC ---
results = df.copy()

# Priority 1: Favorites Toggle
if show_favs_only and my_fav_stations:
    results = results[results['Station_Address'].isin(my_fav_stations)]
else:
    # Priority 2: Brand Toggle Logic
    if show_selected_brands_only and selected_brands:
        results = results[results['brand'].isin(selected_brands)]
    
    # Priority 3: City Filter
    if city_query:
        search_term = simplify(city_query)
        results = results[
            results['Address'].apply(simplify).str.contains(search_term) | 
            results['Region'].apply(simplify).str.contains(search_term)
        ]

# --- 6. DISPLAY RESULTS ---
if not results.empty:
    results = results.sort_values(by='Price')
    st.success(f"Found {len(results)} stations")
    
    # Create the Map URL
    results['Map_URL'] = results['Address'].apply(
        lambda x: f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(x + ', Quebec')}"
    )
    
    # Select and order columns: Price (clickable), Address, Brand
    display_df = results[['Price', 'Address', 'brand', 'Map_URL']].copy()
    
    st.dataframe(
        display_df,
        column_config={
           "Price": st.column_config.LinkColumn(
               "Price (¢)", 
               display_text=r"^(\d+\.\d+)$", 
               validate=None
           ),
           "Address": "Station Address",
           "brand": "Brand",
           "Map_URL": None # Hide the URL column
        },
        hide_index=True,
        use_container_width=True
    )
else:
    st.warning("No stations found. Adjust your filters or toggles.")
