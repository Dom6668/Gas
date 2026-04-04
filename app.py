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
# We use a 2-column layout to force them onto the same line
col_title, col_btn = st.columns([5, 2])

with col_title:
    # Using a markdown header instead of st.title to keep the line height slim
    st.markdown("## ⛽ Live Gas Prices")

with col_btn:
    # A tiny bit of top padding to center the button vertically with the text
    st.write(" ") 
    if st.button("🔄 Refresh"):
        fetch_data.clear()
        st.rerun()

st.markdown("Find the cheapest gas near you. Data updates every 5 minutes.")
st.divider()

# Load Data
df = fetch_data()

# Load Data
df = fetch_data()

# --- 4. SIDEBAR SETUP ---
st.sidebar.header("Search Filters")

city_query = st.sidebar.text_input("Enter City (e.g. Montreal)", "")

brand_list = df['brand'].dropna().unique().tolist()
all_brands = sorted([str(b) for b in brand_list])
selected_brands = st.sidebar.multiselect("Filter by Brand", all_brands)

# Provincial Average Metric
if not df['Price'].empty:
    st.sidebar.divider()
    st.sidebar.metric("Provincial Average", f"{df['Price'].mean():.1f}¢")

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
        
        display_df = results[['Name', 'brand', 'Address', 'Price']].copy()
        display_df['Map'] = display_df['Address'].apply(
            lambda x: f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(x + ', Quebec')}"
        )
        
        st.dataframe(
            display_df,
            column_config={
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
