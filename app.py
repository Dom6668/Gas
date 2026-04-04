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

# --- 3. PROXIMITY LOGIC ---
results = df.copy()

if len(user_pc) >= 3:
    # Get the lat/lon for the typed postal code
    user_location = nomi.query_postal_code(user_pc)
    
    if not pd.isna(user_location.latitude):
        # Calculate distance for every station in the list
        # We compare user lat/lon vs station lat/lon
        results['Dist_km'] = dist_calc.query_postal_code(
            [user_pc] * len(results), 
            results['lat'], 
            results['lon']
        )
        
        # Filter by your selected distance
        results = results[results['Dist_km'] <= search_radius]
        results = results.sort_values('Dist_km')
        
        st.success(f"Showing stations within {search_radius}km of {user_pc}")
    else:
        st.sidebar.error("Postal code not recognized.")

# --- 4. DISPLAY ---
if not results.empty:
    # Add the Map Link
    results['Map'] = results['Address'].apply(
        lambda x: f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(x + ', Quebec')}"
    )
    
    # Final Table
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
    st.info("Enter a postal code in the sidebar to find gas near you.")    search_term = simplify(city_query)
    df['s_addr'] = df['Address'].apply(simplify)
    df['s_reg'] = df['Region'].apply(simplify)
    results = results[df['s_addr'].str.contains(search_term) | df['s_reg'].str.contains(search_term)]

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
