import streamlit as st
import pandas as pd
import requests
import unicodedata
import urllib.parse

# --- 1. APP CONFIG ---
st.set_page_config(page_title="Quebec Gas Tracker", page_icon="⛽", layout="wide")

# --- 2. CORE FUNCTIONS ---
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
    data = resp.json()
    df = pd.DataFrame([f['properties'] for f in data['features']])
    df['Price'] = df['Prices'].apply(get_price)
    # Unique ID for favoriting specific stations
    df['Station_ID'] = df['brand'] + " (" + df['Address'] + ")"
    return df

# --- 3. DATA LOADING ---
df_raw = fetch_data()

# --- 4. SIDEBAR (The Control Center) ---
st.sidebar.header("⛽ Settings")

# A. Montreal Average (Always visible as a benchmark)
mtl_stations = df_raw[df_raw['Address'].apply(simplify).str.contains("montreal")]
if not mtl_stations.empty:
    mtl_avg = mtl_stations['Price'].mean()
    st.sidebar.metric("Montreal Average", f"{mtl_avg:.1f}¢")
    st.sidebar.divider()

# B. Favorite Stations (Address-level)
st.sidebar.subheader("⭐ My Stations")
fav_stations = st.sidebar.multiselect(
    "Star your frequent stops:",
    options=sorted(df_raw['Station_ID'].unique()),
    help="Select specific addresses to track them easily."
)
show_favs_only = st.sidebar.checkbox("Show ONLY Starred Stations", value=False)

st.sidebar.divider()

# C. General Search Filters
st.sidebar.subheader("🔍 General Search")
city_input = st.sidebar.text_input("City Search", value="Montreal")
brand_options = sorted(df_raw['brand'].dropna().unique())
selected_brands = st.sidebar.multiselect("Filter Brands", options=brand_options, default=["Esso", "Couche-Tard"])

# --- 5. FILTERING LOGIC ---
results = df_raw.copy()

if show_favs_only and fav_stations:
    # If the star toggle is ON, only show selected IDs
    results = results[results['Station_ID'].isin(fav_stations)]
else:
    # Otherwise, apply city and brand filters
    if selected_brands:
        results = results[results['brand'].isin(selected_brands)]
    
    if city_input:
        term = simplify(city_input)
        results = results[
            results['Address'].apply(simplify).str.contains(term) | 
            results['Region'].apply(simplify).str.contains(term)
        ]

# --- 6. MAIN DISPLAY ---
st.title("Live Gas Prices")

if not results.empty:
    results = results.sort_values('Price')
    
    # Summary stats
    col1, col2 = st.columns(2)
    col1.success(f"Found {len(results)} stations")
    
    # Prepare Table
    display_df = results[['brand', 'Address', 'Price']].copy()
    display_df['Map'] = results['Address'].apply(
        lambda x: f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(x + ', Quebec')}"
    )

    st.dataframe(
        display_df,
        column_config={
            "brand": "Brand",
            "Address": "Address",
            "Price": st.column_config.NumberColumn("Price (¢)", format="%.1f"),
            "Map": st.column_config.LinkColumn("Directions", display_text="Open Map")
        },
        hide_index=True,
        use_container_width=True
    )
else:
    st.warning("No stations found. Try unchecking 'Starred Stations' or changing your city search.")

if st.button("🔄 Refresh Data"):
    fetch_data.clear()
    st.rerun()st.sidebar.divider()

# ⭐ FAVORITE STATIONS (Address-based)
st.sidebar.subheader("⭐ Favorite Stations")
all_stations = sorted(df['Station_Label'].dropna().unique().tolist())
my_fav_stations = st.sidebar.multiselect(
    "Select your usual stops:", 
    options=all_stations
)
show_favs_only = st.sidebar.toggle("Show ONLY my favorite stations", value=False)

# 📊 MONTREAL AVERAGE
if not df.empty:
    st.sidebar.divider()
    mtl_search = simplify("Montreal")
    mtl_stations = df[df['Address'].apply(simplify).str.contains(mtl_search)]
    ifst.sidebar.divider()

# ⭐ FAVORITE ADDRESSES SECTION
st.sidebar.subheader("⭐ Favorite Stations")
# This list pulls every unique address in the dataset
all_stations = sorted(df['Station_Label'].dropna().unique().tolist())
my_fav_stations = st.sidebar.multiselect(
    "Select your usual stops:", 
    options=all_stations,
    help="Search and select the specific addresses you visit most."
)
show_favs_only = st.sidebar.toggle("Show ONLY my favorite stations", value=False)

# 📊 MONTREAL AVERAGE
if not df.empty:
    st.sidebar.divider()
    mtl_search = simplify("Montreal")
    mtl_stations = df[df['Address'].apply(simplify).str.contains(mtl_search)]
    if not mtl_stations['Price'].empty:
        mtl_avg = mtl_stations['Price'].mean()
        st.sidebar.metric("Montreal Average", f"{mtl_avg:.1f}¢")

# --- 5. FILTERING LOGIC ---
results = df.copy()

# Step 1: Handle Favorites Toggle
if show_favs_only and my_fav_stations:
    results = results[results['Station_Label'].isin(my_fav_stations)]
else:
    # Step 2: Apply standard Brand Filter if toggle is off
    if selected_brands:
        results = results[results['brand'].isin(selected_brands)]
    
    # Step 3: Apply City Filter
    if city_query:
        search_term = simplify(city_query)
        results['s_addr'] = results['Address'].apply(simplify)
        results['s_reg'] = results['Region'].apply(simplify)
        results = results[(results['s_addr'].str.contains(search_term)) | (results['s_reg'].str.contains(search_term))]

# --- 6. DISPLAY RESULTS ---
if not results.empty:
    results = results.sort_values(by='Price')
    st.success(f"Found {len(results)} stations")
    
    display_df = results[['brand', 'Address', 'Price']].copy()
    display_df['Map'] = results['Address'].apply(
        lambda x: f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(x + ', Quebec')}"
    )
    
    st.dataframe(
        display_df,
        column_config={
           "brand": "Brand",
           "Address": "Station Address",
           "Map": st.column_config.LinkColumn("View on Map", display_text="Click to View"),
           "Price": st.column_config.NumberColumn("Price (¢)", format="%.1f")
        },
        hide_index=True,
        use_container_width=True
    )
else:
    st.warning("No stations found. Adjust your filters or toggle off 'Favorites Only'.")    options=all_brands,
    default=["Esso", "Couche-Tard"]
)
use_favs = st.sidebar.toggle("Filter by Favorites Only", value=True)

st.sidebar.divider()

# 🔍 MANUAL BRAND FILTER (Independent)
# We disable this visually if Favorites is toggled 'On' to avoid confusion
manual_brands = st.sidebar.multiselect(
    "Filter by Other Brands", 
    options=all_brands,
    disabled=use_favs
)

# 📊 MONTREAL AVERAGE
if not df.empty:
    st.sidebar.divider()
    mtl_search = simplify("Montreal")
    mtl_stations = df[df['Address'].apply(simplify).str.contains(mtl_search)]
    if not mtl_stations['Price'].empty:
        mtl_avg = mtl_stations['Price'].mean()
        st.sidebar.metric("Montreal Average", f"{mtl_avg:.1f}¢")

# --- 5. FILTERING LOGIC ---
results = df.copy()

# Step 1: Filter by Brand (Priority given to Favorites Toggle)
if use_favs and my_fav_list:
    results = results[results['brand'].isin(my_fav_list)]
elif manual_brands:
    results = results[results['brand'].isin(manual_brands)]

# Step 2: Filter by City
if city_query:
    search_term = simplify(city_query)
    results['s_addr'] = results['Address'].apply(simplify)
    results['s_reg'] = results['Region'].apply(simplify)
    results = results[(results['s_addr'].str.contains(search_term)) | (results['s_reg'].str.contains(search_term))]

# --- 6. DISPLAY RESULTS ---
if not results.empty:
    results = results.sort_values(by='Price')
    st.success(f"Found {len(results)} stations")
    
    display_df = results[['brand', 'Address', 'Price']].copy()
    display_df['Map'] = results['Address'].apply(
        lambda x: f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(x + ', Quebec')}"
    )
    
    st.dataframe(
        display_df,
        column_config={
           "brand": "Brand",
           "Address": "Station Address",
           "Map": st.column_config.LinkColumn("View on Map", display_text="Click to View"),
           "Price": st.column_config.NumberColumn("Price (¢)", format="%.1f")
        },
        hide_index=True,
        use_container_width=True
    )
else:
    st.warning("No stations found. Adjust your filters or toggle off Favorites.")
