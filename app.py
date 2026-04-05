import streamlit as st
import pandas as pd
import requests
import unicodedata
import urllib.parse

# --- 1. APP CONFIG ---
st.set_page_config(page_title="Quebec Gas Tracker", page_icon="⛽")

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

# --- 3. UI HEADER ---
col_title, col_btn = st.columns([5, 2])
with col_title:
    st.markdown("## ⛽ Live Gas Prices")
with col_btn:
    st.write(" ") 
    if st.button("🔄 Refresh"):
        fetch_data.clear()
        st.rerun()

st.markdown("Find the cheapest gas near you. Data updates every 5 minutes.")
st.divider()

# Load Data
df = fetch_data()

# --- 4. SIDEBAR SETUP ---
st.sidebar.header("Search Filters")

# 🏙️ City Search
city_query = st.sidebar.text_input("Enter City", value="Montreal")

# 🏷️ Brand Filter
brand_list = sorted(df['brand'].dropna().unique().tolist())
selected_brands = st.sidebar.multiselect(
    "Filter by Brand", 
    options=brand_list,
    default=["Esso", "Couche-Tard"]
)

st.sidebar.divider()

# ⭐ ENHANCED FAVORITES SECTION
st.sidebar.subheader("⭐ My Favorite Stations")

# 1. Search Box to find specific addresses quickly
fav_search = st.sidebar.text_input("🔍 Search Address to Favorite", placeholder="e.g. 123 Sherbrooke")

# 2. Filter the options list based on the search box to make selection easier
if fav_search:
    search_term = simplify(fav_search)
    filtered_options = [s for s in df['Station_Address'].dropna().unique() if search_term in simplify(s)]
else:
    filtered_options = sorted(df['Station_Address'].dropna().unique().tolist())

# 3. The actual Favorite Selection
my_fav_stations = st.sidebar.multiselect(
    "Select your usual stops:", 
    options=filtered_options,
    help="Type in the search box above to find your station faster."
)

# 4. Master Toggle
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

# Priority 1: Favorites Toggle
if show_favs_only and my_fav_stations:
    results = results[results['Station_Address'].isin(my_fav_stations)]
else:
    # Priority 2: Standard Filters
    if selected_brands:
        results = results[results['brand'].isin(selected_brands)]
    
    if city_query:
        term = simplify(city_query)
        results = results[
            results['Address'].apply(simplify).str.contains(term) | 
            results['Region'].apply(simplify).str.contains(term)
        ]

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
    st.warning("No stations found. Adjust your filters or toggle off 'Favorite Stations'.")
