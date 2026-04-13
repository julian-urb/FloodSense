import numpy as np

def prepare_feature_vector(rainfall_mm, elevation_m, distance_to_river_m):
    """Prepare feature vector for model prediction with all 13 engineered features."""
    
    elevation_orig = elevation_m
    precipitat_orig = rainfall_mm
    distance_to_river_m_orig = distance_to_river_m
    
    distance_to_river_log = np.log1p(distance_to_river_m)
    
    elevation_precipitation = elevation_orig * precipitat_orig
    
    elev_highland = 1 if elevation_orig >= 100 else 0
    elev_lowland = 1 if elevation_orig < 10 else 0
    elev_plain = 1 if 10 <= elevation_orig < 50 else 0
    elev_upland = 1 if 50 <= elevation_orig < 100 else 0
    
    dist_very_close = 1 if distance_to_river_m < 500 else 0
    dist_close = 1 if 500 <= distance_to_river_m < 1500 else 0
    dist_moderate = 1 if 1500 <= distance_to_river_m < 3500 else 0
    dist_far = 1 if distance_to_river_m >= 3500 else 0
    
    features = np.array([[
        elevation_orig,
        precipitat_orig,
        distance_to_river_m_orig,
        distance_to_river_log,
        elevation_precipitation,
        elev_highland,
        elev_lowland,
        elev_plain,
        elev_upland,
        dist_close,
        dist_far,
        dist_moderate,
        dist_very_close
    ]])
    
    return features

def predict_risk(model, rainfall_mm, elevation_m, distance_to_river_m, threshold=0.35):
    """Predict flood risk. Returns: (risk_level, risk_score, color)"""
    try:
        features = prepare_feature_vector(rainfall_mm, elevation_m, distance_to_river_m)
        
        proba = model.predict_proba(features)[0]
        
        risk_score = proba[-1]
        
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
        return "UNKNOWN", 0.0, "#9e9e9e"