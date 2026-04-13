import numpy as np
import pandas as pd
import geopandas as gpd
import streamlit as st

def simulate_evacuation_capacity(evac_centers, evacuees, selected_city=None, city_gdf=None):
    """Simulate evacuation capacity allocation."""
    try:
        centers = evac_centers.copy()
        
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
        
        total_capacity = centers["capacity"].sum()
        centers["allocation_ratio"] = centers["capacity"] / total_capacity
        centers["assigned_evacuees"] = (centers["allocation_ratio"] * evacuees).astype(int)
        centers["available_capacity"] = centers["capacity"] - centers["assigned_evacuees"]
        centers["occupancy_pct"] = (centers["assigned_evacuees"] / centers["capacity"] * 100).astype(int)
        centers["overflow"] = np.where(centers["available_capacity"] < 0, 
                                       abs(centers["available_capacity"]), 0).astype(int)
        
        centers["status"] = centers.apply(lambda x: 
            "🔴 OVERFLOW" if x["occupancy_pct"] > 100 
            else ("🟡 NEAR FULL" if x["occupancy_pct"] > 80 
            else "🟢 OK"), axis=1)
        
        return centers[["name", "amenity", "capacity", "assigned_evacuees", 
                       "available_capacity", "occupancy_pct", "overflow", "status"]]
    except Exception as e:
        st.warning(f"⚠️ Error in capacity simulation: {e}")
        return None

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
    else:
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