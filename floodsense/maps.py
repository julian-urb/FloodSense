import folium
import geopandas as gpd
import streamlit as st

def create_base_map(selected_city=None):
    """Create Folium base map centered on NCR (Manila)."""
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
        for idx, row in city_gdf.iterrows():
            city_name = row.get("ADM3_EN", f"City {idx}")
            
            if selected_city and city_name == selected_city:
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
                except Exception:
                    pass
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
            
            if selected_city and city_gdf is not None:
                city_bounds = city_gdf[city_gdf["ADM3_EN"] == selected_city]
                if city_bounds.empty:
                    continue
                point = gpd.GeoSeries([gpd.points_from_xy([lon], [lat])[0]])[0]
                if not city_bounds.geometry.contains(point).any():
                    continue
            
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
        return "#d32f2f"
    elif elevation < 30:
        return "#f57c00"
    else:
        return "#388e3c"