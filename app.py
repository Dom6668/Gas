import streamlit as st
import pandas as pd
import requests
import pgeocode
import urllib.parse

# --- 1. SETUP GEODATA ---
# 'CA' tells the library to use the Canadian postal code database
dist_calc = pgeocode.GeoDistance('CA')
nomi = pgeocode.Nominatim('CA')

@st.cache_data(ttl=300)
def fetch_data():
    url = "https://regieessencequebec.ca/stations.geojson.gz"
    resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    features = resp.json()['features']
    
    stations = []
    for f in features:
        # Merge the properties (name/brand) with the geometry (GPS)
        data = f['properties']
        data['lon'] = f['geometry']['coordinates'][0]
        data['lat'] = f['geometry']['coordinates'][1]
        stations.append(data)
        
    df = pd.DataFrame(stations)
    # Re-using your price extraction logic
    def get_price(price_list):
        for item in price_list:
            if item.get('GasType') == 'Régulier' and item.get('IsAvailable'):
                try: return float(item.get('Price', '').replace('¢', ''))
                except: return None
        return None
    
    df['Price'] = df['Prices'].apply(get_price)
    return df

# --- 2. USER INTERFACE ---
st.title("⛽ Quebec Gas Proximity Finder")
df = fetch_data()

st.sidebar.header("📍 Find by Distance")
user_pc = st.sidebar.text_input("Enter Postal Code (e.g., H3B 1A1)").upper().replace(" ", "")
search_radius = st.sidebar.slider("Distance (km)", 1, 50, 10)

# --- 3. FILTERING LOGIC ---
results = df.copy()

# A. Handle Postal Code (Proximity)
if user_pc and len(user_pc) >= 3:
    user_location = nomi.query_postal_code(user_pc)
    if not pd.isna(user_location.latitude):
        # Calculate distance
        results['Dist_km'] = dist_calc.query_postal_code(
            [user_pc] * len(results), 
            results['lat'], 
            results['lon']
        )
        results = results[results['Dist_km'] <= search_radius]
        results = results.sort_values('Dist_km')
    else:
        st.sidebar.error("Postal code not recognized.")

# B. Handle City Search (Optional - if you still have city_query in your sidebar)
# Note: Ensure city_query is defined in your sidebar section!
if 'city_query' in locals() and city_query:
    search_term = simplify(city_query)
    results = results[results['Address'].apply(simplify).str.contains(search_term)]

# --- 4. DISPLAY RESULTS ---
if (user_pc and len(user_pc) >= 3) or ( 'city_query' in locals() and city_query):
    if not results.empty:
        # Create Map Links
        results['Map'] = results['Address'].apply(
            lambda x: f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(x + ', Quebec')}"
        )
        
        # Build Table
        st.dataframe(
            results[['Name', 'brand', 'Address', 'Price', 'Dist_km', 'Map']],
            column_config={
                "Map": st.column_config.LinkColumn("View on Map", display_text="Click to View"),
                "Price": st.column_config.NumberColumn("Price (¢)", format="%.1f"),
                "Dist_km": st.column_config.NumberColumn("Distance (km)", format="%.1f")
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.warning("No stations found matching those filters.")
else:
    st.info("👈 Use the sidebar to search by Postal Code or City.")

# Apply Brand Filter
if selected_brands:
    results = results[results['brand'].isin(selected_brands)]

# --- 5. DISPLAY RESULTS ---
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
                    display_text="Click to View on Map"  # <--- This is the magic line
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
# Summary Stat
if not df['Price'].empty:
    st.sidebar.divider()
    st.sidebar.metric("Provincial Average", f"{df['Price'].mean():.1f}¢")
