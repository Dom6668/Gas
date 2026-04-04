import streamlit as st
import pandas as pd
import requests
import unicodedata
import urllib.parse

# --- 1. APP CONFIG ---
st.set_page_config(page_title="Quebec Gas Tracker", page_icon="⛽")
st.title("⛽ Live Quebec Gas Prices")
st.markdown("Find the cheapest gas near you. Data updates every 5 minutes.")

# --- 2. THE LOGIC (Same as your Colab) ---
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

@st.cache_data(ttl=300) # This keeps the app fast by caching data for 5 mins
def fetch_data():
    url = "https://regieessencequebec.ca/stations.geojson.gz"
    resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    df = pd.DataFrame([f['properties'] for f in resp.json()['features']])
    df['Price'] = df['Prices'].apply(get_price)
    return df

# --- 3. THE USER INTERFACE ---
df = fetch_data()

# Sidebar Search
st.sidebar.header("Search Filters")
city_query = st.sidebar.text_input("Enter City (e.g. Montreal)", "")

if city_query:
    search_term = simplify(city_query)
    df['s_addr'] = df['Address'].apply(simplify)
    df['s_reg'] = df['Region'].apply(simplify)
    
    results = df[df['s_addr'].str.contains(search_term) | df['s_reg'].str.contains(search_term)].copy()
    results = results.sort_values(by='Price')

    if not results.empty:
        st.success(f"Found {len(results)} stations in {city_query}")
        
        # Create a display-friendly version
        display_df = results[['Name', 'brand', 'Address', 'Price']].copy()
        
        # Add a "Map" column that creates a link
        display_df['Map'] = display_df['Address'].apply(
            lambda x: f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(x + ', Quebec')}"
        )
        
        # Display the table with clickable links
        st.dataframe(
            display_df,
            column_config={
                "Map": st.column_config.LinkColumn("View on Map"),
                "Price": st.column_config.NumberColumn("Price (¢)", format="%.1f")
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.error("No stations found for that city.")
else:
    st.info("👈 Enter a city in the sidebar to see local prices.")

# Summary Stat
if not df['Price'].empty:
    st.sidebar.divider()
    st.sidebar.metric("Provincial Average", f"{df['Price'].mean():.1f}¢")
