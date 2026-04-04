import streamlit as st
import pandas as pd
import requests
import pgeocode
import urllib.parse
import unicodedata

# --- 1. SETTINGS & UTILITIES ---
st.set_page_config(page_title="Quebec Gas Finder", page_icon="⛽")

# Initialize the Postal Code tools
dist_calc = pgeocode.GeoDistance('CA')
nomi = pgeocode.Nominatim('CA')

def simplify(text):
    """Removes accents and makes text lowercase for easier searching"""
    if not isinstance(text, str): return ""
    return "".join([c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c)]).lower()

def get_price(price_list):
    """Extracts the 'Regular' gas price from the complex nested data"""
    if not isinstance(price_list, list): return None
    for item in price_list:
        if item.get('GasType') == 'Régulier' and item.get('IsAvailable'):
            try: return float(item.get('Price', '').replace('¢', ''))
            except: return None
    return None

@st.cache_data(ttl=300)
def fetch_data():
    """Downloads the live GeoJSON and flattens it into a Table"""
    url = "https://regieessencequebec.ca/stations.geojson.gz"
    resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    features = resp.json()['features']
    
    stations = []
    for f in features:
        data = f['properties']
        data['lon'] = f['geometry']['coordinates'][0]
        data['lat'] = f['geometry']['coordinates'][1]
        stations.append(data)
        
    df = pd.DataFrame(stations)
    df['Price'] = df['Prices'].apply(get_price)
    return df

# --- 2. SIDEBAR FILTERS ---
st.sidebar.header("🔍 Search Filters")

# City Search
city_query = st.sidebar.text_input("Search by City", "")

# Postal Code Search
st.sidebar.divider()
st.sidebar.subheader("📍 Proximity Search")
user_pc = st.sidebar.text_input("Your Postal Code (e.g. H3B 1A1)").upper().replace(" ", "")
search_radius = st.sidebar.slider("Radius (km)", 1, 50, 10)

# Refresh Button
if st.sidebar.button("🔄 Sync Live Prices"):
    fetch_data.clear()
    st.sidebar.success("Updated!")

# --- 3. FILTERING LOGIC ---
df = fetch_data()
results = df.copy()
has_searched = False

# Filter A: Postal Code Proximity
if len(user_pc) >= 3:
    has_searched = True
    user_geo = nomi.query_postal_code(user_pc)
    if not pd.isna(user_geo.latitude):
        # Calculate distance for all stations
        results['Dist_km'] = dist_calc.query_postal_code(
            [user_pc] * len(results), 
            results['lat'], 
            results['lon']
        )
        results = results[results['Dist_km'] <= search_radius]
        results = results.sort_values('Dist_km')
    else:
        st.sidebar.error("Postal code not recognized.")

# Filter B: City Search
if city_query:
    has_searched = True
    search_term = simplify(city_query)
    results['s_addr'] = results['Address'].apply(simplify)
    results['s_reg'] = results['Region'].apply(simplify)
    results = results[results['s_addr'].str.contains(search_term) | results['s_reg'].str.contains(search_term)]

# --- 4. DISPLAY ---
st.title("⛽ Quebec Gas Finder")

if has_searched:
    if not results.empty:
        st.success(f"Found {len(results)} stations matching your search.")
        
        # Build the final table
        display_df = results[['Name', 'brand', 'Address', 'Price']].copy()
        
        # Add Distance column if searching by postal code
        if 'Dist_km' in results.columns:
            display_df['Distance (km)'] = results['Dist_km']
            
        # Add Map Links
        display_df['Map'] = results['Address'].apply(
            lambda x: f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(x + ', Quebec')}"
        )
        
        st.dataframe(
            display_df,
            column_config={
                "Map": st.column_config.LinkColumn("View on Map", display_text="Click to View"),
                "Price": st.column_config.NumberColumn("Price (¢)", format="%.1f"),
                "Distance (km)": st.column_config.NumberColumn("Distance (km)", format="%.1f")
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.warning("No stations found. Try increasing the radius or checking the spelling.")
else:
    st.info("👈 Use the sidebar to search by city or enter a postal code to find gas
