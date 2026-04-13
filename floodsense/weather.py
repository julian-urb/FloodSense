import streamlit as st
import requests
from datetime import datetime
from floodsense.config import CONFIG, sanitize_input, generate_hmac_signature, verify_hmac_signature, log_security_event

def log_weather_request(city_name, api_key, response_data=None, error=None):
    """Log weather API requests and responses."""
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
    """Check if WeatherAPI is working."""
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

@st.cache_data(ttl=1800)
def get_weather_data(city_name, api_key):
    """Fetch real-time weather data from WeatherAPI."""
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
        
        log_weather_request(city_name, api_key, response_data=weather_result)
        
        return weather_result
    except Exception as e:
        log_weather_request(city_name, api_key, error=e)
        st.warning(f"⚠️ Could not fetch weather data: {e}. Using manual input.")
        return None