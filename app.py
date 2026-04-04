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

# City Search - Default Montreal
city_query = st.sidebar.text_input("Enter City (e.g. Montreal)", value="Montreal")

# Brand Filter - Default Esso and Couche-Tard
brand_list = df['brand'].dropna().unique().tolist()
all_brands = sorted([str(b) for b in brand_list])
selected_brands = st.sidebar.multiselect(
    "Filter by Brand", 
    options=all_brands,
    default=["Esso", "Couche-Tard"]

# ... (keep your existing city_query and selected_brands code) ...

st.sidebar.divider()
show_favorites = st.sidebar.checkbox("⭐ Show Only My Favorites", value=True)

# Define what "Favorites" means to you
my_favorite_brands = ["Esso", "Couche-Tard"]
)

# --- NEW: MONTREAL AVERAGE CALCULATION ---
if not df.empty:
    st.sidebar.divider()
    # Filter full dataset for Montreal stations to get the average
    mtl_data = df[df['Address'].apply(simplify).str.contains("montreal")]
    if not mtl_data['Price'].empty:
        mtl_avg = mtl_data['Price'].mean()
        st.sidebar.metric("Montreal Average", f"{mtl_avg:.1f}¢")

# --- 5. FILTERING LOGIC ---
results = df.copy()

if city_query:
    search_term = simplify(city_query)
    # Filter based on address or region
    results = results[
        results['Address'].apply(simplify).str.contains(search_term) | 
        results['Region'].apply(simplify).str.contains(search_term)
    ]

if selected_brands:
    results = results[results['brand'].isin(selected_brands)]

# --- 6. DISPLAY RESULTS ---
if city_query or selected_brands:
    results = results.sort_values(by='Price')

    if not results.empty:
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
        st.error("No stations found. Try broadening your search!")
else:
    st.info("👈 Search by City or Brand in the sidebar to begin.")
