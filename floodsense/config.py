import os
import hmac
import hashlib
import re
from datetime import datetime

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