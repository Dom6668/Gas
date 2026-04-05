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

# ⭐ FAVORITE ADDRESSES
st.sidebar.subheader("⭐ Favorite Stations")
all_station_addresses = sorted(df['Station_Address'].dropna().unique().tolist())

# SET YOUR DEFAULT STATIONS HERE
my_target_stations = [
    "Costco (300 Rue Bridge)", 
    "Esso (123 Rue Sherbrooke)"
]
safe_defaults = [s for s in my_target_stations if s in all_station_addresses]

my_fav_stations = st.sidebar.multiselect(
    "Select your usual stops:", 
    options=all_station_addresses,
    default=safe_defaults
)

# Set the toggle to be ON by default as requested
show_favs_only = st.sidebar.toggle("Show ONLY my favorite stations", value=True)

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

if show_favs_only and my_fav_stations:
    results = results[results['Station_Address'].isin(my_fav_stations)]
else:
    if selected_brands:
        results = results[results['brand'].isin(selected_brands)]
    
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
    
    # We create a column for the URL but we will hide it from view
    results['Map_URL'] = results['Address'].apply(
        lambda x: f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(x + ', Quebec')}"
    )
    
    # Select only the columns you want to see, in your preferred order
    display_df = results[['Price', 'Address', 'brand', 'Map_URL']].copy()
    
    st.dataframe(
        display_df,
        column_config={
           # This makes the Price column a clickable link using the Map_URL data
           "Price": st.column_config.LinkColumn(
               "Price (¢)", 
               display_text=r"^(\d+\.\d+)$", # Uses a regex to keep the number visible
               validate=None
           ),
           "Address": "Station Address",
           "brand": "Brand",
           "Map_URL": None # This hides the URL column from the user
        },
        hide_index=True,
        use_container_width=True
    )
else:
    st.warning("No stations found. Adjust your filters or toggle off 'Favorite Stations'.")
