# ============================================================================
# FLOODSENSE - Flood Risk Decision-Support System for Metro Manila
# ============================================================================

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import warnings

from floodsense.config import CONFIG, validate_city_name, validate_numeric_input, log_security_event
from floodsense.data import load_model, load_evacuation_centers, load_flood_data, load_city_boundaries
from floodsense.weather import check_api_status, get_weather_data
from floodsense.models import predict_risk
from floodsense.maps import create_base_map, add_city_boundaries, add_evacuation_markers, add_flood_risk_points
from floodsense.simulation import simulate_evacuation_capacity, generate_recommendation

warnings.filterwarnings('ignore')

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

def main():
    st.title("🌊 FloodSense: Flood Risk Decision-Support System")
    st.markdown("### Metro Manila Real-Time Prediction & Evacuation Planning")
    
    with st.spinner("Loading data and model..."):
        model = load_model()
        evac_centers = load_evacuation_centers()
        flood_data = load_flood_data()
        city_boundaries = load_city_boundaries()
    
    if model is None or evac_centers is None or flood_data is None or city_boundaries is None:
        st.error("❌ Failed to load required data. Please check file paths.")
        st.stop()
    
    cities_list = sorted(city_boundaries["ADM3_EN"].unique())
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("###  CONTROL PANEL")
    
    weather_api_key = CONFIG["weather_api_key"]
    api_working, api_status = check_api_status(weather_api_key)
    
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
    
    rainfall_mm = 10.0
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
    
    refresh_weather = st.sidebar.button("= Refresh Weather =")
    
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
    
    temperature_c = 28.0
    humidity = 70
    
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
    
    tab_map, tab_analysis, tab_capacity = st.tabs([" Interactive Map", " Analysis", " Evacuation Capacity"])
    
    with tab_map:
        st.subheader(f"Flood Risk Map - {selected_city}")
        
        m = create_base_map(selected_city)
        add_city_boundaries(m, city_boundaries, selected_city)
        add_evacuation_markers(m, evac_centers, selected_city, city_boundaries)
        add_flood_risk_points(m, flood_data, selected_city, city_boundaries)
        
        from streamlit_folium import st_folium
        st_folium(m, width=1400, height=600)
        
        st.info(
            "🟢 Low Risk | 🟠 Medium Risk | 🔴 High Risk | 🟢 Evacuation Centers",
            icon="ℹ️"
        )
    
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
        
        st.subheader(" City Characteristics: ")
        char_col1, char_col2 = st.columns(2)
        
        with char_col1:
            st.metric("Average Elevation", f"{avg_elevation:.1f} m")
        with char_col2:
            st.metric("Avg Distance to River", f"{avg_distance_to_river:.0f} m")
        
        st.markdown("---")
        
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
    
    with tab_capacity:
        st.subheader(f"Evacuation Capacity Simulation - {selected_city}")
        st.markdown(f"**Evacuees to Accommodate:** {evacuees_count:,} persons")
        
        capacity_df = simulate_evacuation_capacity(
            evac_centers, evacuees_count, selected_city, city_boundaries
        )
        
        if capacity_df is not None and not capacity_df.empty:
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
    
    st.markdown("---")
    st.markdown("""
    **FloodSense** | Flood Risk Decision-Support System for National Capital Region (NCR), Philippines
    
    - Data sources: GIS boundaries, Weather API, ML model predictions
    - **For emergency use only** | Always follow official government guidance
    """)

if __name__ == "__main__":
    main()