import streamlit as st
import pandas as pd
import requests
import unicodedata
import urllib.parse

# --- 1. APP CONFIG ---
st.set_page_config(page_title="Gas Tracker", page_icon="⛽")

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
    df['Station_Address'] = df['brand'] + " (" + df['Address'] + ")"
    return df

# Load Data Early for Header
df = fetch_data()

# --- 3. UI HEADER ---
col_title, col_metric = st.columns([4, 2])

with col_title:
    st.markdown("## ⛽ Live Gas Prices")

with col_metric:
    if not df.empty:
        mtl_search = simplify("Montreal")
        mtl_stations = df[df['Address'].apply(simplify).str.contains(mtl_search)]
        if not mtl_stations['Price'].empty:
            mtl_avg = mtl_stations['Price'].mean()
            st.metric("MTL Average", f"{mtl_avg:.1f}¢")

st.markdown('<div style="margin-top: -25px;"></div>', unsafe_allow_html=True)

# --- 4. SIDEBAR SETUP ---
st.sidebar.header("Search Filters")
city_query = st.sidebar.text_input("Enter City", value="Montreal")

show_selected_brands_only = st.sidebar.toggle("Show Brands", value=True)
show_favs_only = st.sidebar.toggle("Show Favorite", value=True)

brand_list = sorted(df['brand'].dropna().unique().tolist())
selected_brands = st.sidebar.multiselect(
    "Select Brands", 
    options=brand_list,
    default=["Esso", "Couche-Tard"]
)

all_station_addresses = sorted(df['Station_Address'].dropna().unique().tolist())

# --- USER CUSTOMIZATION ---
my_target_stations = [
    "Esso (2495 ch. Rockland, Mont-Royal)",
    "Esso (180 boul. Crémazie ouest, Montréal)",
    "Esso (790 boul. Crémazie est, Montréal)",
    "Esso (7635 boul. Lacordaire, Montréal)",
    "Esso (4225 rue Jarry est, Montréal)",
    "Esso (8380 boul. Langelier, Montréal)"
]
safe_defaults = [s for s in my_target_stations if s in all_station_addresses]

my_fav_stations = st.sidebar.multiselect(
    "Select Favorites", 
    options=all_station_addresses,
    default=safe_defaults
)

# --- 5. FILTERING LOGIC ---
results = df.copy()

if show_favs_only and my_fav_stations:
    results = results[results['Station_Address'].isin(my_fav_stations)]
else:
    if show_selected_brands_only and selected_brands:
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
        
    # 1. Calculate average for comparison
    current_avg = results['Price'].mean()
    
    # 2. Prepare Display Data
    display_df = results[['Price', 'Address', 'brand']].copy()
    
    def make_clickable_price(row):
        addr_encoded = urllib.parse.quote(f"{row['Address']}, Quebec")
        url = f"https://www.google.com/maps/search/?api=1&query={addr_encoded}"
        price_val = row['Price']
        if price_val < current_avg:
            indicator = "🟢"  # Below average
        elif price_val == current_avg:
            indicator = "⚪"  # Exactly average
        else:
            indicator = "🔴"  # Above average
            
        return f"{indicator} **[{price_val:.1f}¢]({url})**"

    display_df['Price (¢)'] = display_df.apply(make_clickable_price, axis=1)
    final_table = display_df[['Price (¢)', 'Address', 'brand']]
    final_table.columns = ['Price (¢)', 'Address', 'Brand']
    
    # --- CSS TO CENTRE ONLY THE FIRST ROW (HEADER) ---
    st.markdown("""
        <style>
            table {
                width: 100% !important;
                max-width: 400px !important;
                margin-left: 0;
                border-collapse: collapse;
            }
            /* Target ONLY the header row */
            th {
                text-align: center !important;
                padding: 8px !important;
                border-bottom: 2px solid #f0f2f6;
            }
            /* Target all data rows (aligned left) */
            td {
                text-align: center !important;
                padding: 8px !important;
                border-bottom: 1px solid #f0f2f6;
            }
            /* Keep columns compact */
            td:nth-child(1), td:nth-child(3) {
                width: 1% !important;
                white-space: nowrap !important;
            }
            /* Address column wrapping */
            td:nth-child(2) {
                white-space: normal !important;
                word-wrap: break-word;
            }
        </style>
    """, unsafe_allow_html=True)

    # 3. Display the table
    st.markdown(final_table.to_markdown(index=False))
else:
    st.warning("No stations found. Adjust your filters or toggles.")
