"""
Weather Microservice
Listens on tcp://127.0.0.1:5556 for JSON requests and returns the current temperature.
"""

import json
import zmq
import requests

ENDPOINT = "tcp://127.0.0.1:5556"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT = 10


def geocode(location):
    """Return (lat, lon) for a location string, or None if not found.

    Open-Meteo's search API doesn't handle 'City, ST' format well (e.g. 'Washington, DC').
    Try the full string first; if that returns nothing, retry with just the part before the comma.
    """
    search_terms = [location]
    if "," in location:
        city_part = location.split(",")[0].strip()
        if city_part:
            search_terms.append(city_part)

    for name in search_terms:
        try:
            resp = requests.get(
                GEOCODE_URL,
                params={"name": name, "count": 1, "language": "en", "format": "json"},
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            results = resp.json().get("results")
            if results:
                return results[0]["latitude"], results[0]["longitude"]
        except Exception:
            return None

    return None


def fetch_temperature(lat, lon, unit):
    """Return the current temperature as a float, or None on failure."""
    unit_param = "fahrenheit" if unit == "F" else "celsius"
    try:
        resp = requests.get(
            FORECAST_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "current_weather": "true",
                "temperature_unit": unit_param,
            },
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()["current_weather"]["temperature"]
    except Exception:
        return None


def handle_request(raw):
    """Parse a raw ZMQ message and return a response dict."""
    try:
        req = json.loads(raw.decode("utf-8"))
    except Exception:
        return {"success": False, "error": "Request must be valid JSON."}

    if not isinstance(req, dict):
        return {"success": False, "error": "Request must be a JSON object."}

    action = req.get("action", "")
    if action != "get_temperature":
        return {"success": False, "error": f"Unknown action '{action}'."}

    location = req.get("location", "")
    if not isinstance(location, str) or not location.strip():
        return {"success": False, "error": "Location is required."}
    location = location.strip()

    unit = req.get("unit", "")
    if not isinstance(unit, str) or unit.upper() not in ("F", "C"):
        return {"success": False, "error": "Unit must be 'F' or 'C'."}
    unit = unit.upper()

    coords = geocode(location)
    if coords is None:
        return {"success": False, "error": "Location was not found."}

    temperature = fetch_temperature(coords[0], coords[1], unit)
    if temperature is None:
        return {"success": False, "error": "Weather data is unavailable right now."}

    return {"success": True, "location": location, "temperature": temperature, "unit": unit}


def main():
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.bind(ENDPOINT)
    print(f"Weather Service running on {ENDPOINT}  |  Press Ctrl-C to stop.")

    while True:
        try:
            raw = socket.recv()
            response = handle_request(raw)
            socket.send_string(json.dumps(response))
        except KeyboardInterrupt:
            print("\nStopped.")
            break

    socket.close()
    context.term()


if __name__ == "__main__":
    main()
