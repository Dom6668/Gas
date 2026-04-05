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
    # Create a unique ID for favoriting specific addresses
    df['Station_ID'] = df['brand'] + " (" + df['Address'] + ")"
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

# ⭐ FAVORITE STATIONS (Address-based)
st.sidebar.subheader("⭐ My Stations")
all_stations = sorted(df['Station_ID'].dropna().unique().tolist())
my_fav_stations = st.sidebar.multiselect(
    "Select your usual stops:", 
    options=all_stations,
    help="You can search and pick specific addresses here."
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

# Step 1: Favorites Toggle (Highest Priority)
if show_favs_only and my_fav_stations:
    results = results[results['Station_ID'].isin(my_fav_stations)]
else:
    # Step 2: Brand Filter
    if selected_brands:
        results = results[results['brand'].isin(selected_brands)]
    
    # Step 3: City Filter
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
    st.warning("No stations found. Try adjusting your filters or toggling off 'Favorites Only'.")

# We use the 'default' parameter to pre-select brands
selected_brands = st.sidebar.multiselect(
    "Filter by Brand", 
    options=all_brands,
    default=["Esso", "Couche-Tard"]

)

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

if city_query:
    search_term = simplify(city_query)
    # Applying simplify to the local df for filtering
    df_temp = df.copy()
    df_temp['s_addr'] = df_temp['Address'].apply(simplify)
    df_temp['s_reg'] = df_temp['Region'].apply(simplify)
    results = results[(df_temp['s_addr'].str.contains(search_term)) | (df_temp['s_reg'].str.contains(search_term))]

if selected_brands:
    results = results[results['brand'].isin(selected_brands)]

# --- 6. DISPLAY RESULTS ---
if city_query or selected_brands:
    results = results.sort_values(by='Price')

    if not results.empty:
        st.success(f"Found {len(results)} stations matching your criteria")
        
        # We REMOVED 'Name' from this list below:
        display_df = results[['brand', 'Address', 'Price']].copy()
        
        display_df['Map'] = results['Address'].apply(
            lambda x: f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(x + ', Quebec')}"
        )
        
        # Updated table with cleaner columns
        st.dataframe(
            display_df,
            column_config={
               "brand": "Brand",
               "Address": "Station Address",
               "Map": st.column_config.LinkColumn(
                    "View on Map", 
                    display_text="Click to View on Map"
                ),
                "Price": st.column_config.NumberColumn("Price (¢)", format="%.1f")
            },
            hide_index=True,
            use_container_width=True
        )
else:
    st.warning("No stations found. Try adjusting your filters or toggling off 'Favorites Only'.")
