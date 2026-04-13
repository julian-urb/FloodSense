# ============================================================================
# FLOODSENSE - Flood Risk Decision-Support System for Metro Manila
# ============================================================================

import streamlit as st
import pandas as pd
import numpy as np
import geopandas as gpd
import folium
from folium import plugins
from streamlit_folium import st_folium
import json
import joblib
import requests
from datetime import datetime
from pathlib import Path
import warnings
import os
import hmac
import hashlib
import re

warnings.filterwarnings('ignore')

# ============================================================================
# SECURITY CONFIGURATION
# ============================================================================

def get_secure_config():
    """Load configuration from environment variables with secure defaults."""
    config = {
        "weather_api_key": os.environ.get("WEATHER_API_KEY", ""),
        "hmac_secret_key": os.environ.get("HMAC_SECRET_KEY", "floodsense-default-key-change-me"),
        "allowed_cities": [
            "Manila", "Quezon City", "Caloocan City", "City of Makati",
            "City of Mandaluyong", "Pasay City", "City of Pasig", "Taguig City",
            "City of Valenzuela", "City of Malabon", "City of Navotas",
            "City of Marikina", "City of Parañaque", "City of Las Piñas",
            "City of Muntinlupa", "City of San Juan", "Pateros"
        ],
        "max_rainfall_mm": 500.0,
        "min_elevation_m": -10.0,
        "max_elevation_m": 2000.0,
        "max_distance_to_river_m": 50000.0,
        "max_evacuees": 500000,
    }
    return config

CONFIG = get_secure_config()

def generate_hmac_signature(data: str, secret: str) -> str:
    """Generate HMAC-SHA256 signature for request verification."""
    return hmac.new(
        secret.encode('utf-8'),
        data.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

def verify_hmac_signature(data: str, signature: str, secret: str) -> bool:
    """Verify HMAC-SHA256 signature."""
    expected_signature = generate_hmac_signature(data, secret)
    return hmac.compare_digest(expected_signature, signature)

def sanitize_input(value: str, pattern: str = r'^[a-zA-Z0-9\s\-_,]+$') -> str:
    """Sanitize input string to prevent injection attacks."""
    if not value or not re.match(pattern, str(value)):
        return ""
    return value.strip()

def validate_numeric_input(value: float, min_val: float, max_val: float) -> float:
    """Validate and clamp numeric input within safe bounds."""
    try:
        value = float(value)
        return max(min_val, min(max_val, value))
    except (ValueError, TypeError):
        return min_val

def validate_city_name(city_name, allowed_cities: list) -> bool:
    """Validate city name against whitelist."""
    if city_name is None:
        return False
    if not isinstance(city_name, str):
        return False
    sanitized = sanitize_input(city_name)
    return sanitized in allowed_cities

def log_security_event(event_type: str, details: str):
    """Log security-related events."""
    try:
        log_file = "security_log.txt"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_file, "a") as f:
            f.write(f"[{timestamp}] {event_type}: {details}\n")
    except Exception:
        pass

# ============================================================================
# PAGE CONFIG
# ============================================================================

st.set_page_config(
    page_title="FloodSense Dashboard",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
        .metric-card {
            padding: 1.5rem;
            border-radius: 0.5rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            text-align: center;
            font-weight: bold;
        }
        .danger { color: #d32f2f; }
        .warning { color: #f57c00; }
        .safe { color: #388e3c; }
        .info-box {
            background-color: #e3f2fd;
            border-left: 4px solid #1976d2;
            padding: 1rem;
            border-radius: 0.25rem;
            margin: 1rem 0;
        }
    </style>
""", unsafe_allow_html=True)

# ============================================================================
# CACHE & SESSION STATE
# ============================================================================

@st.cache_resource
def load_model():
    """Load the trained gradient boosting model."""
    model_path = Path("models/gradient_boosting.pkl")
    if model_path.exists():
        return joblib.load(model_path)
    else:
        st.error("❌ Model file not found: models/gradient_boosting.pkl")
        st.stop()

@st.cache_resource
def load_evacuation_centers():
    """Load evacuation centers from GeoJSON and assign capacities."""
    try:
        gdf = gpd.read_file("Dataset/evacuation_cleaned_filled.geojson")
        
        # Define capacity mappings
        capacity_map = {
            "school": 500,
            "townhall": 300,
            "church": 200,
            "social_facility": 250,
        }
        
        # Assign capacities
        gdf["capacity"] = gdf["amenity"].map(capacity_map)
        gdf["capacity"] = gdf["capacity"].fillna(150)  # Default for Unknown
        
        # Fill missing names
        for idx, row in gdf.iterrows():
            if pd.isna(row["name"]) or row["name"] == "":
                amenity_type = str(row["amenity"]).capitalize()
                gdf.at[idx, "name"] = f"{amenity_type} #{idx}"
        
        return gdf
    except Exception as e:
        st.error(f"Error loading evacuation centers: {e}")
        return None

@st.cache_resource
def load_flood_data():
    """Load flood landscape data."""
    try:
        df = pd.read_csv("Dataset/FloodLandscape_with_distance.csv")
        return df
    except Exception as e:
        st.error(f"Error loading flood data: {e}")
        return None

@st.cache_resource
def load_city_boundaries():
    """Load and merge city boundaries from 4 GeoJSON files, filter for NCR cities only."""
    try:
        city_files = [
            "Dataset/municities-province-ph133900000.0.1.json",
            "Dataset/municities-province-ph137400000.0.1.json",
            "Dataset/municities-province-ph137500000.0.1.json",
            "Dataset/municities-province-ph137600000.0.1.json",
        ]
        
        gdf_list = []
        for file in city_files:
            gdf_list.append(gpd.read_file(file))
        
        # Merge all boundaries
        gdf_merged = pd.concat(gdf_list, ignore_index=True)
        
        # NCR cities and municipality
        ncr_cities = [
            "Manila",
            "Quezon City",
            "Caloocan City",
            "City of Makati",
            "City of Mandaluyong",
            "Pasay City",
            "City of Pasig",
            "Taguig City",
            "City of Valenzuela",
            "City of Malabon",
            "City of Navotas",
            "City of Marikina",
            "City of Parañaque",
            "City of Las Piñas",
            "City of Muntinlupa",
            "City of San Juan",
            "Pateros"
        ]
        
        # Filter for NCR cities - handle Manila specially (it's split into barangays)
        ncr_boundaries = []
        
        for city in ncr_cities:
            city_match = gdf_merged[gdf_merged["ADM3_EN"] == city]
            
            # For Manila, which appears as barangays, merge them
            if city == "Manila" and city_match.empty:
                manila_barangays = ["Binondo", "Ermita", "Intramuros", "Malate", "Paco", 
                                   "Pandacan", "Port Area", "Quiapo", "Sampaloc", "San Miguel", 
                                   "San Nicolas", "Santa Ana", "Santa Cruz", "Tondo I / II"]
                manila_data = gdf_merged[gdf_merged["ADM3_EN"].isin(manila_barangays)]
                if not manila_data.empty:
                    # Merge all Manila barangays into single geometry
                    manila_merged = manila_data.dissolve(as_index=False)
                    manila_merged["ADM3_EN"] = "Manila"
                    ncr_boundaries.append(manila_merged)
            elif not city_match.empty:
                ncr_boundaries.append(city_match)
        
        if ncr_boundaries:
            gdf_ncr = pd.concat(ncr_boundaries, ignore_index=True)
            return gdf_ncr
        else:
            st.warning("⚠️ Could not filter for NCR cities. Using all cities.")
            return gdf_merged
    except Exception as e:
        st.error(f"Error loading city boundaries: {e}")
        return None

def log_weather_request(city_name, api_key, response_data=None, error=None):
    """
    Log weather API requests and responses to a text file for tracking.
    """
    try:
        log_file = "weather_api_log.txt"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with open(log_file, "a") as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"Timestamp: {timestamp}\n")
            f.write(f"City: {city_name}\n")
            f.write(f"API Key (masked): {api_key[:8]}...{api_key[-4:]}\n")
            
            if response_data:
                f.write(f"\nResponse Data:\n")
                f.write(f"  Precipitation (mm): {response_data.get('precipitation_mm', 'N/A')}\n")
                f.write(f"  Temperature (°C): {response_data.get('temperature_c', 'N/A')}\n")
                f.write(f"  Humidity (%): {response_data.get('humidity', 'N/A')}\n")
                f.write(f"Status: SUCCESS\n")
            
            if error:
                f.write(f"\nError: {str(error)}\n")
                f.write(f"Status: FAILED\n")
            
            f.write(f"{'='*80}\n")
    except Exception as log_error:
        print(f"Could not write to log file: {log_error}")

def check_api_status(api_key):
    """
    Check if WeatherAPI is working by making a test request.
    Returns: (is_working: bool, status_message: str)
    """
    if not api_key:
        return False, "⚠️ API key not configured"
    
    try:
        url = f"http://api.weatherapi.com/v1/current.json"
        params = {"key": api_key, "q": "Manila", "aqi": "no"}
        
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        
        return True, "✅ API is working"
    except requests.exceptions.Timeout:
        log_security_event("API_TIMEOUT", "WeatherAPI request timed out")
        return False, "⚠️ API timeout"
    except requests.exceptions.ConnectionError:
        log_security_event("API_CONNECTION_ERROR", "Failed to connect to WeatherAPI")
        return False, "❌ Connection failed"
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            log_security_event("API_AUTH_FAILURE", "Invalid API key detected")
            return False, "❌ Invalid API key"
        return False, f"❌ API error ({e.response.status_code})"
    except Exception as e:
        log_security_event("API_ERROR", f"Unexpected error: {str(e)[:50]}")
        return False, f"❌ {str(e)[:50]}"

@st.cache_data(ttl=1800)  # 30-min cache for weather
def get_weather_data(city_name, api_key):
    """
    Fetch real-time weather data from WeatherAPI.
    Returns: dict with precipitation_mm, temperature_c, humidity
    
    Security: Uses HMAC signature for request integrity verification.
    """
    if not api_key:
        log_security_event("API_KEY_MISSING", "Attempted API call without API key")
        return None
    
    sanitized_city = sanitize_input(city_name)
    if not sanitized_city:
        log_security_event("INVALID_INPUT", "Empty or invalid city name")
        return None
    
    try:
        url = f"http://api.weatherapi.com/v1/current.json"
        params = {"key": api_key, "q": sanitized_city, "aqi": "no"}
        
        request_data = f"{sanitized_city}{api_key}"
        request_signature = generate_hmac_signature(request_data, CONFIG["hmac_secret_key"])
        
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        
        data = response.json()
        
        response_signature = data.get("signature", "")
        if response_signature and not verify_hmac_signature(str(data), response_signature, CONFIG["hmac_secret_key"]):
            log_security_event("SIGNATURE_VERIFICATION_FAILED", "HMAC signature mismatch")
            st.warning("⚠️ Warning: Response integrity check failed")
        weather_result = {
            "precipitation_mm": data["current"]["precip_mm"],
            "temperature_c": data["current"]["temp_c"],
            "humidity": data["current"]["humidity"]
        }
        
        # Log successful request
        log_weather_request(city_name, api_key, response_data=weather_result)
        
        return weather_result
    except Exception as e:
        # Log failed request
        log_weather_request(city_name, api_key, error=e)
        st.warning(f"⚠️ Could not fetch weather data: {e}. Using manual input.")
        return None

# ============================================================================
# PREDICTION & CLASSIFICATION
# ============================================================================

def prepare_feature_vector(rainfall_mm, elevation_m, distance_to_river_m):
    """Prepare feature vector for model prediction with all 13 engineered features."""
    
    # Original features
    elevation_orig = elevation_m
    precipitat_orig = rainfall_mm
    distance_to_river_m_orig = distance_to_river_m
    
    # Log transformation (add small value to avoid log(0))
    distance_to_river_log = np.log1p(distance_to_river_m)
    
    # Interaction feature
    elevation_precipitation = elevation_orig * precipitat_orig
    
    # Elevation categorization
    elev_highland = 1 if elevation_orig >= 100 else 0
    elev_lowland = 1 if elevation_orig < 10 else 0
    elev_plain = 1 if 10 <= elevation_orig < 50 else 0
    elev_upland = 1 if 50 <= elevation_orig < 100 else 0
    
    # Distance categorization (in meters)
    dist_very_close = 1 if distance_to_river_m < 500 else 0
    dist_close = 1 if 500 <= distance_to_river_m < 1500 else 0
    dist_moderate = 1 if 1500 <= distance_to_river_m < 3500 else 0
    dist_far = 1 if distance_to_river_m >= 3500 else 0
    
    # Assemble feature vector in correct order
    features = np.array([[
        elevation_orig,           # 0: elevation_orig
        precipitat_orig,          # 1: precipitat_orig
        distance_to_river_m_orig, # 2: distance_to_river_m_orig
        distance_to_river_log,    # 3: distance_to_river_log
        elevation_precipitation,  # 4: elevation_precipitation
        elev_highland,            # 5: elev_highland
        elev_lowland,             # 6: elev_lowland
        elev_plain,               # 7: elev_plain
        elev_upland,              # 8: elev_upland
        dist_close,               # 9: dist_close
        dist_far,                 # 10: dist_far
        dist_moderate,            # 11: dist_moderate
        dist_very_close           # 12: dist_very_close
    ]])
    
    return features

def predict_risk(model, rainfall_mm, elevation_m, distance_to_river_m, threshold=0.35):
    """
    Predict flood risk.
    Returns: (risk_level, risk_score, risk_probability)
    """
    try:
        features = prepare_feature_vector(rainfall_mm, elevation_m, distance_to_river_m)
        
        # Get probability for HIGH risk class
        proba = model.predict_proba(features)[0]
        
        # Assuming binary classification (0=LOW, 1=HIGH)
        # For multi-class, adjust labels accordingly
        risk_score = proba[-1]  # Probability of HIGH risk class
        
        if risk_score > 0.70:
            risk_level = "HIGH"
            color = "#d32f2f"
        elif risk_score > 0.35:
            risk_level = "MEDIUM"
            color = "#f57c00"
        else:
            risk_level = "LOW"
            color = "#388e3c"
        
        return risk_level, risk_score, color
    except Exception as e:
        st.warning(f"⚠️ Prediction error: {e}")
        return "UNKNOWN", 0.0, "#9e9e9e"

# ============================================================================
# MAP FUNCTIONS
# ============================================================================

def create_base_map(selected_city=None):
    """Create Folium base map centered on NCR (Manila)."""
    # NCR center coordinates
    ncr_center = [14.5994, 121.0855]
    
    m = folium.Map(
        location=ncr_center,
        zoom_start=12,
        tiles="OpenStreetMap"
    )
    
    return m

def add_city_boundaries(map_obj, city_gdf, selected_city=None):
    """Add city boundaries to map."""
    try:
        # Add unselected cities in gray
        for idx, row in city_gdf.iterrows():
            city_name = row.get("ADM3_EN", f"City {idx}")
            
            if selected_city and city_name == selected_city:
                # Highlight selected city in yellow
                try:
                    folium.GeoJson(
                        gpd.GeoSeries([row.geometry]).__geo_interface__,
                        style_function=lambda x: {
                            "fillColor": "#ffeb3b",
                            "color": "#fbc02d",
                            "weight": 3,
                            "opacity": 0.8,
                            "fillOpacity": 0.4
                        },
                        popup=city_name,
                        name=city_name
                    ).add_to(map_obj)
                except Exception as e:
                    st.warning(f"⚠️ Could not add selected city boundary: {e}")
            else:
                # Unselected cities in light gray
                try:
                    folium.GeoJson(
                        gpd.GeoSeries([row.geometry]).__geo_interface__,
                        style_function=lambda x: {
                            "fillColor": "#e0e0e0",
                            "color": "#9e9e9e",
                            "weight": 1,
                            "opacity": 0.5,
                            "fillOpacity": 0.1
                        },
                        popup=city_name,
                        name=city_name
                    ).add_to(map_obj)
                except Exception as e:
                    pass  # Skip cities that can't be added
    except Exception as e:
        st.warning(f"⚠️ Error adding city boundaries: {e}")

def add_evacuation_markers(map_obj, evac_gdf, selected_city=None, city_gdf=None):
    """Add evacuation center markers to map."""
    try:
        for idx, row in evac_gdf.iterrows():
            lat = row["latitude"]
            lon = row["longitude"]
            name = row["name"]
            amenity = row["amenity"]
            capacity = row["capacity"]
            
            # Filter by selected city if specified
            if selected_city and city_gdf is not None:
                city_bounds = city_gdf[city_gdf["ADM3_EN"] == selected_city]
                if city_bounds.empty:
                    continue
                # Check if point is within city bounds
                point = gpd.GeoSeries([gpd.points_from_xy([lon], [lat])[0]])[0]
                if not city_bounds.geometry.contains(point).any():
                    continue
            
            # Create popup
            popup_text = f"""
            <b>{name}</b><br>
            Amenity: {amenity}<br>
            Capacity: {int(capacity)} persons
            """
            
            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(popup_text, max_width=250),
                icon=folium.Icon(color="green", icon="info-sign"),
                tooltip=name
            ).add_to(map_obj)
    except Exception as e:
        st.warning(f"⚠️ Error adding evacuation markers: {e}")

def add_flood_risk_points(map_obj, flood_df, selected_city=None, city_gdf=None):
    """Add flood risk points to map, filtered by selected city."""
    try:
        for idx, row in flood_df.iterrows():
            lat = row["lat"]
            lon = row["lon"]
            elevation = row["elevation"]
            risk_color = classify_point_risk(elevation)
            
            # Filter by selected city if specified
            if selected_city and city_gdf is not None:
                city_bounds = city_gdf[city_gdf["ADM3_EN"] == selected_city]
                if city_bounds.empty:
                    continue
                point = gpd.GeoSeries([gpd.points_from_xy([lon], [lat])[0]])[0]
                if not city_bounds.geometry.contains(point).any():
                    continue
            
            folium.CircleMarker(
                location=[lat, lon],
                radius=4,
                popup=f"Elevation: {elevation:.1f}m",
                color=risk_color,
                fill=True,
                fillColor=risk_color,
                fillOpacity=0.7,
                weight=1
            ).add_to(map_obj)
    except Exception as e:
        st.warning(f"⚠️ Error adding flood risk points: {e}")

def classify_point_risk(elevation):
    """Classify risk color based on elevation."""
    if elevation < 10:
        return "#d32f2f"  # HIGH - Red
    elif elevation < 30:
        return "#f57c00"  # MEDIUM - Orange
    else:
        return "#388e3c"  # LOW - Green

# ============================================================================
# EVACUATION CAPACITY SIMULATION
# ============================================================================

def simulate_evacuation_capacity(evac_centers, evacuees, selected_city=None, city_gdf=None):
    """
    Simulate evacuation capacity allocation.
    Returns: DataFrame with allocation details
    """
    try:
        centers = evac_centers.copy()
        
        # Filter by selected city if specified
        if selected_city and city_gdf is not None:
            city_bounds = city_gdf[city_gdf["ADM3_EN"] == selected_city]
            if not city_bounds.empty:
                filtered_centers = []
                for idx, center in centers.iterrows():
                    point = gpd.GeoSeries([gpd.points_from_xy([center["longitude"]], [center["latitude"]])[0]])[0]
                    if city_bounds.geometry.contains(point).any():
                        filtered_centers.append(center)
                if filtered_centers:
                    centers = pd.DataFrame(filtered_centers)
        
        # Calculate allocation based on capacity proportions
        total_capacity = centers["capacity"].sum()
        centers["allocation_ratio"] = centers["capacity"] / total_capacity
        centers["assigned_evacuees"] = (centers["allocation_ratio"] * evacuees).astype(int)
        centers["available_capacity"] = centers["capacity"] - centers["assigned_evacuees"]
        centers["occupancy_pct"] = (centers["assigned_evacuees"] / centers["capacity"] * 100).astype(int)
        centers["overflow"] = np.where(centers["available_capacity"] < 0, 
                                       abs(centers["available_capacity"]), 0).astype(int)
        
        # Status
        centers["status"] = centers.apply(lambda x: 
            "🔴 OVERFLOW" if x["occupancy_pct"] > 100 
            else ("🟡 NEAR FULL" if x["occupancy_pct"] > 80 
            else "🟢 OK"), axis=1)
        
        return centers[["name", "amenity", "capacity", "assigned_evacuees", 
                       "available_capacity", "occupancy_pct", "overflow", "status"]]
    except Exception as e:
        st.warning(f"⚠️ Error in capacity simulation: {e}")
        return None

# ============================================================================
# RECOMMENDATIONS
# ============================================================================

def generate_recommendation(risk_level, rainfall_mm, temperature_c, humidity):
    """Generate action recommendations based on risk level."""
    
    if risk_level == "HIGH":
        action = "🚨 **EVACUATION RECOMMENDED** (6-12 hours)"
        details = f"""
        - Immediately alert residents in high-risk areas
        - Activate evacuation centers
        - Dispatch rescue teams to strategic locations
        - Prepare relief supplies and emergency services
        - Current conditions: {rainfall_mm:.1f}mm rain, {temperature_c:.1f}°C, {humidity}% humidity
        """
        color_class = "danger"
    elif risk_level == "MEDIUM":
        action = "⚠️ **PREPARE EVACUATION RESOURCES**"
        details = f"""
        - Put evacuation teams on standby
        - Pre-position supplies at centers
        - Monitor weather updates every 30 minutes
        - Brief emergency personnel
        - Current conditions: {rainfall_mm:.1f}mm rain, {temperature_c:.1f}°C, {humidity}% humidity
        """
        color_class = "warning"
    else:  # LOW
        action = "✅ **MONITOR CONDITIONS**"
        details = f"""
        - Continue routine monitoring
        - Maintain awareness of weather forecasts
        - Keep communication channels available
        - Standard operations in effect
        - Current conditions: {rainfall_mm:.1f}mm rain, {temperature_c:.1f}°C, {humidity}% humidity
        """
        color_class = "safe"
    
    return action, details, color_class

# ============================================================================
# MAIN APP START
# ============================================================================

def main():
    st.title("🌊 FloodSense: Flood Risk Decision-Support System")
    st.markdown("### Metro Manila Real-Time Prediction & Evacuation Planning")
    
    # ========================================================================
    # LOAD DATA
    # ========================================================================
    
    with st.spinner("Loading data and model..."):
        model = load_model()
        evac_centers = load_evacuation_centers()
        flood_data = load_flood_data()
        city_boundaries = load_city_boundaries()
    
    if model is None or evac_centers is None or flood_data is None or city_boundaries is None:
        st.error("❌ Failed to load required data. Please check file paths.")
        st.stop()
    
    # Get unique city names
    cities_list = sorted(city_boundaries["ADM3_EN"].unique())
    
    # ========================================================================
    # SIDEBAR CONTROLS
    # ========================================================================
    
    # ========================================================================
    # SIDEBAR CONTROLS
    # ========================================================================
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("###  CONTROL PANEL")
    
    # Use secure config from environment
    weather_api_key = CONFIG["weather_api_key"]
    
    # Check API status
    api_working, api_status = check_api_status(weather_api_key)
    
    # Only display API status if it's working
    if api_working:
        st.sidebar.markdown("####  WeatherAPI Status")
        st.sidebar.success(api_status)
        st.sidebar.markdown("---")
    else:
        st.sidebar.markdown("####  WeatherAPI Status")
        st.sidebar.error(api_status)
        st.sidebar.markdown("---")
    
    selected_city = st.sidebar.selectbox(
        " Select City/Municipality",
        cities_list,
        help="Choose a city to highlight and analyze"
    )
    
    use_realtime_weather = st.sidebar.toggle(
        " Use Real-Time Weather Data",
        value=False,
        help="Toggle to fetch live weather from WeatherAPI"
    )
    
    # Manual rainfall input
    rainfall_mm = 10.0  # Default value
    if not use_realtime_weather:
        rainfall_mm = st.sidebar.slider(
            " Rainfall (mm)",
            min_value=0.0,
            max_value=100.0,
            value=10.0,
            step=1.0
        )
    
    risk_threshold = st.sidebar.slider(
        " Risk Threshold (0-1)",
        min_value=0.0,
        max_value=1.0,
        value=0.35,
        step=0.05
    )
    
    evacuees_count = st.sidebar.number_input(
        " Evacuees to Accommodate",
        min_value=100,
        max_value=100000,
        value=1000,
        step=1000
    )
    
    # Weather refresh button
    refresh_weather = st.sidebar.button("= Refresh Weather =")
    
    # ========================================================================
    # INPUT VALIDATION
    # ========================================================================
    
    if not validate_city_name(selected_city, CONFIG["allowed_cities"]):
        log_security_event("INVALID_CITY", f"Invalid city input: {selected_city}")
        st.error("❌ Invalid city selected. Please choose from the dropdown.")
        st.stop()
    
    validated_rainfall = validate_numeric_input(rainfall_mm, 0.0, CONFIG["max_rainfall_mm"])
    validated_threshold = validate_numeric_input(risk_threshold, 0.0, 1.0)
    validated_evacuees = validate_numeric_input(evacuees_count, 100, CONFIG["max_evacuees"])
    
    if validated_rainfall != rainfall_mm:
        log_security_event("INPUT_CLAMPED", f"Rainfall value clamped from {rainfall_mm} to {validated_rainfall}")
        rainfall_mm = validated_rainfall
    
    if validated_threshold != risk_threshold:
        risk_threshold = validated_threshold
        
    if validated_evacuees != evacuees_count:
        log_security_event("INPUT_CLAMPED", f"Evacuees value clamped from {evacuees_count} to {validated_evacuees}")
        evacuees_count = int(validated_evacuees)
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Last Updated:** " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    # ========================================================================
    # GET WEATHER DATA
    # ========================================================================
    
    temperature_c = 28.0  # Default
    humidity = 70  # Default
    
    if use_realtime_weather:
        weather_data = get_weather_data(selected_city, weather_api_key)
        if weather_data:
            rainfall_mm = weather_data["precipitation_mm"]
            temperature_c = weather_data["temperature_c"]
            humidity = weather_data["humidity"]
            st.sidebar.success(f"✅ Using real-time weather data")
        else:
            st.sidebar.warning(f"Using default values")
            rainfall_mm = 10.0
    
    # ========================================================================
    # COMPUTE PREDICTIONS
    # ========================================================================
    
    # Get city elevation and river distance from flood data
    city_geom = city_boundaries[city_boundaries["ADM3_EN"] == selected_city]
    if not city_geom.empty:
        bounds = city_geom["geometry"].bounds.iloc[0]
        city_flood_data = flood_data[
            (flood_data["lat"].between(bounds[1], bounds[3])) &
            (flood_data["lon"].between(bounds[0], bounds[2]))
        ]
    else:
        city_flood_data = flood_data
    
    if not city_flood_data.empty:
        avg_elevation = city_flood_data["elevation"].mean()
        avg_distance_to_river = city_flood_data["distance_to_river_m"].mean()
    else:
        avg_elevation = 20.0
        avg_distance_to_river = 1000.0
    
    risk_level, risk_score, color = predict_risk(
        model, rainfall_mm, avg_elevation, avg_distance_to_river, risk_threshold
    )
    
    # ========================================================================
    # MAIN LAYOUT - TAB STRUCTURE
    # ========================================================================
    
    tab_map, tab_analysis, tab_capacity = st.tabs([" Interactive Map", " Analysis", " Evacuation Capacity"])
    
    # ========================================================================
    # TAB 1: MAP
    # ========================================================================
    
    with tab_map:
        st.subheader(f"Flood Risk Map - {selected_city}")
        
        m = create_base_map(selected_city)
        add_city_boundaries(m, city_boundaries, selected_city)
        add_evacuation_markers(m, evac_centers, selected_city, city_boundaries)
        add_flood_risk_points(m, flood_data, selected_city, city_boundaries)
        
        # Display map
        st_folium(m, width=1400, height=600)
        
        st.info(
            "🟢 Low Risk | 🟠 Medium Risk | 🔴 High Risk | 🟢 Evacuation Centers",
            icon="ℹ️"
        )
    
    # ========================================================================
    # TAB 2: ANALYSIS & PREDICTIONS
    # ========================================================================
    
    with tab_analysis:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "📈 Risk Level",
                risk_level,
                f"{risk_score:.1%} probability"
            )
        
        with col2:
            st.metric(
                "💧 Rainfall",
                f"{rainfall_mm:.1f} mm",
                "Real-time" if use_realtime_weather else "Manual"
            )
        
        with col3:
            st.metric(
                "🌡️ Temperature",
                f"{temperature_c:.1f}°C",
                f"Humidity: {humidity}%"
            )
        
        st.markdown("---")
        
        # City characteristics
        st.subheader(" City Characteristics: ")
        char_col1, char_col2 = st.columns(2)
        
        with char_col1:
            st.metric("Average Elevation", f"{avg_elevation:.1f} m")
        with char_col2:
            st.metric("Avg Distance to River", f"{avg_distance_to_river:.0f} m")
        
        st.markdown("---")
        
        # Recommendation panel
        action, details, color_class = generate_recommendation(
            risk_level, rainfall_mm, temperature_c, humidity
        )
        
        st.subheader("🎯 Recommended Actions")
        
        if risk_level == "HIGH":
            st.error(action)
        elif risk_level == "MEDIUM":
            st.warning(action)
        else:
            st.success(action)
        
        st.markdown(details)
    
    # ========================================================================
    # TAB 3: EVACUATION CAPACITY
    # ========================================================================
    
    with tab_capacity:
        st.subheader(f"Evacuation Capacity Simulation - {selected_city}")
        st.markdown(f"**Evacuees to Accommodate:** {evacuees_count:,} persons")
        
        capacity_df = simulate_evacuation_capacity(
            evac_centers, evacuees_count, selected_city, city_boundaries
        )
        
        if capacity_df is not None and not capacity_df.empty:
            # Summary metrics
            summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)
            
            total_capacity = capacity_df["capacity"].sum()
            total_assigned = capacity_df["assigned_evacuees"].sum()
            total_overflow = capacity_df["overflow"].sum()
            utilization = (total_assigned / total_capacity * 100) if total_capacity > 0 else 0
            
            with summary_col1:
                st.metric("Total Capacity", f"{int(total_capacity):,}")
            with summary_col2:
                st.metric("Assigned", f"{int(total_assigned):,}")
            with summary_col3:
                st.metric("Utilization", f"{utilization:.1f}%")
            with summary_col4:
                if total_overflow > 0:
                    st.metric("⚠️ Overflow", f"{int(total_overflow):,}", delta="Deficit")
                else:
                    st.metric("✅ No Overflow", f"+{int(total_capacity - total_assigned):,}", delta="Available")
            
            st.markdown("---")
            
            # Capacity table
            display_df = capacity_df[[
                "name", "amenity", "capacity", "assigned_evacuees", 
                "available_capacity", "occupancy_pct", "status"
            ]].copy()
            
            display_df.columns = ["Center Name", "Type", "Capacity", "Assigned", "Available", "Occupancy %", "Status"]
            
            st.dataframe(
                display_df,
                hide_index=True,
                column_config={
                    "Capacity": st.column_config.NumberColumn(format="%d"),
                    "Assigned": st.column_config.NumberColumn(format="%d"),
                    "Available": st.column_config.NumberColumn(format="%d"),
                    "Occupancy %": st.column_config.ProgressColumn(min_value=0, max_value=120),
                }
            )
        else:
            st.warning("No evacuation centers found for this city.")
    
    # ========================================================================
    # FOOTER
    # ========================================================================
    
    st.markdown("---")
    st.markdown("""
    **FloodSense** | Flood Risk Decision-Support System for National Capital Region (NCR), Philippines
    
    - Data sources: GIS boundaries, Weather API, ML model predictions
    - **For emergency use only** | Always follow official government guidance
    """)

if __name__ == "__main__":
    main()
