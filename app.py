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
    return df

# --- 3. THE USER INTERFACE (Header & Refresh) ---
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
city_query = st.sidebar.text_input("Enter City (e.g. Montreal)", value="Montreal")

# 🏷️ All Brands List
brand_list = df['brand'].dropna().unique().tolist()
all_brands = sorted([str(b) for b in brand_list])

# ⭐ FAVORITES MANAGEMENT
st.sidebar.subheader("⭐ My Favorites")
# This lets you choose which stations are your personal favorites
my_favorites = st.sidebar.multiselect(
    "Set your Favorite Brands", 
    options=all_brands,
    default=["Esso", "Couche-Tard"]
)
show_favorites_only = st.sidebar.checkbox("Show Only My Favorites", value=True)

# 🔍 ADDITIONAL FILTERS (Only shows if favorites toggle is OFF)
selected_brands = []
if not show_favorites_only:
    st.sidebar.divider()
    selected_brands = st.sidebar.multiselect("Add Other Brands to Search", options=all_brands)

# 📊 MONTREAL AVERAGE METRIC
if not df.empty:
    st.sidebar.divider()
    mtl_search = simplify("Montreal")
    mtl_stations = df[df['Address'].apply(simplify).str.contains(mtl_search)]
    if not mtl_stations['Price'].empty:
        mtl_avg = mtl_stations['Price'].mean()
        st.sidebar.metric("Montreal Average", f"{mtl_avg:.1f}¢")

# --- 5. FILTERING LOGIC ---
results = df.copy()

# 1. Apply Brand Filtering
if show_favorites_only and my_favorites:
    results = results[results['brand'].isin(my_favorites)]
elif selected_brands:
    results = results[results['brand'].isin(selected_brands)]

# 2. Apply City Filter
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
    st.warning("No stations found. Adjust your filters in the sidebar.")
