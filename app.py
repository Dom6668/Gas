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

# 🏷️ Brand Filter
brand_list = df['brand'].dropna().unique().tolist()
all_brands = sorted([str(b) for b in brand_list])
selected_brands = st.sidebar.multiselect(
    "Filter by Brand", 
    options=all_brands,
    default=["Esso", "Couche-Tard"]
)

# ⭐ Favorites Toggle
st.sidebar.divider()
show_favorites = st.sidebar.checkbox("⭐ Show Only My Favorites", value=True)
my_favorites = ["Esso", "Couche-Tard"]

# 📊 Montreal Average Metric
if not df.empty:
    st.sidebar.divider()
    # We use the full 'df' here so the average is always accurate regardless of filters
    mtl_search = simplify("Montreal")
    mtl_stations = df[df['Address'].apply(simplify).str.contains(mtl_search)]
    
    if not mtl_stations['Price'].empty:
        mtl_avg = mtl_stations['Price'].mean()
        st.sidebar.metric("Montreal Average", f"{mtl_avg:.1f}¢")

# --- 5. FILTERING LOGIC ---
results = df.copy()

# 1. Apply Brand Filtering (Favorites vs Manual)
if show_favorites:
    results = results[results['brand'].isin(my_favorites)]
elif selected_brands:
    results = results[results['brand'].isin(selected_brands)]

# 2. Apply City Filter
if city_query:
    search_term = simplify(city_query)
    # Create temp columns for searching without affecting the display table
    results['s_addr'] = results['Address'].apply(simplify)
    results['s_reg'] = results['Region'].apply(simplify)
    
    results = results[(results['s_addr'].str.contains(search_term)) | (results['s_reg'].str.contains(search_term))]

# --- 6. DISPLAY RESULTS ---
if not results.empty:
    results = results.sort_values(by='Price')
    st.success(f"Found {len(results)} stations matching your criteria")
    
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
    st.error("No stations found. Try unchecking 'Favorites' or changing the city.")
# ⭐ Favorites Toggle
st.sidebar.divider()
show_favorites = st.sidebar.checkbox("Show Only My Favorites", value=True)
my_favorites = ["Esso", "Couche-Tard"]

# 📊 Montreal Average Metric
if not df.empty:
    st.sidebar.divider()
    # Logic to find Montreal stations for the benchmark
    mtl_data = df[df['Address'].apply(simplify).str.contains("montreal")]
    if not mtl_data['Price'].empty:
        mtl_avg = mtl_data['Price'].mean()
        st.sidebar.metric("Montreal Average", f"{mtl_avg:.1f}¢")

# --- 5. FILTERING LOGIC ---
results = df.copy()

# 1. Apply Favorites Toggle
if show_favorites:
    results = results[results['brand'].isin(my_favorites)]
elif selected_brands:
    results = results[results['brand'].isin(selected_brands)]

# 2. Apply City Filter
if city_query:
    search_term = simplify(city_query)
    df_temp = df.copy()
    df_temp['s_addr'] = df_temp['Address'].apply(simplify)
    df_temp['s_reg'] = df_temp['Region'].apply(simplify)
    # Ensure this bracket is closed correctly
    results = results[(df_temp['s_addr'].str.contains(search_term)) | (df_temp['s_reg'].str.contains(search_term))]

# --- 6. DISPLAY RESULTS ---
if not results.empty:
    results = results.sort_values(by='Price')
    st.success(f"Found {len(results)} stations matching your criteria")
    
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
    st.error("No stations found. Try broadening your search!")
