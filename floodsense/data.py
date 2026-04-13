import streamlit as st
import pandas as pd
import geopandas as gpd
import joblib
from pathlib import Path

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
        
        capacity_map = {
            "school": 500,
            "townhall": 300,
            "church": 200,
            "social_facility": 250,
        }
        
        gdf["capacity"] = gdf["amenity"].map(capacity_map)
        gdf["capacity"] = gdf["capacity"].fillna(150)
        
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
        
        gdf_merged = pd.concat(gdf_list, ignore_index=True)
        
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
        
        ncr_boundaries = []
        
        for city in ncr_cities:
            city_match = gdf_merged[gdf_merged["ADM3_EN"] == city]
            
            if city == "Manila" and city_match.empty:
                manila_barangays = ["Binondo", "Ermita", "Intramuros", "Malate", "Paco", 
                                   "Pandacan", "Port Area", "Quiapo", "Sampaloc", "San Miguel", 
                                   "San Nicolas", "Santa Ana", "Santa Cruz", "Tondo I / II"]
                manila_data = gdf_merged[gdf_merged["ADM3_EN"].isin(manila_barangays)]
                if not manila_data.empty:
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