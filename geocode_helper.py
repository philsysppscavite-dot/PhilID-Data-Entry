"""
Verifies that a delivery rider's phone GPS reading is actually near the
resident's registered address when they resolve a delivery (mark it
delivered or returned/not-delivered).

Uses the Google Maps Geocoding API to turn addresses into coordinates:
  1. Try the resident's exact address (house/street + barangay + city).
  2. Fall back to just the barangay centroid (barangays can be large, so
     this uses a wider acceptance radius).

If no API key is configured, or the geocoding lookup fails (no network,
bad address, etc.), the raw GPS point is still saved on the record -- it's
just marked "unverified" instead of matched/unmatched, so field staff are
never blocked from completing a delivery because of this feature.
"""
import json
import math
import urllib.parse
import urllib.request

_geocode_cache = {}  # query string -> (lat, lng) or None, cached for the process lifetime


def _geocode_query(query, api_key):
    if not api_key:
        return None
    if query in _geocode_cache:
        return _geocode_cache[query]

    url = "https://maps.googleapis.com/maps/api/geocode/json?" + urllib.parse.urlencode(
        {"address": query, "key": api_key, "region": "ph"}
    )
    result = None
    try:
        with urllib.request.urlopen(url, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("status") == "OK" and data.get("results"):
            loc = data["results"][0]["geometry"]["location"]
            result = (loc["lat"], loc["lng"])
    except Exception:
        result = None

    _geocode_cache[query] = result
    return result


def _haversine_meters(lat1, lng1, lat2, lng2):
    r = 6371000  # Earth radius, meters
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def verify_delivery_location(resident, lat, lng, app_config):
    """Checks a captured (lat, lng) against the resident's address, then
    their barangay, returning a dict describing the result. Never raises."""
    api_key = app_config.get("GOOGLE_MAPS_API_KEY")
    if not api_key or lat is None or lng is None:
        return {
            "checked": False,
            "matched": None,
            "distance_m": None,
            "reference": "unverified",
            "message": "GPS not verified (no Google Maps API key configured).",
        }

    addr_radius = app_config.get("DELIVERY_GPS_ADDRESS_RADIUS_M", 300)
    brgy_radius = app_config.get("DELIVERY_GPS_BARANGAY_RADIUS_M", 4000)

    # 1) Try the exact address, if one was captured on the resident's record.
    if resident.address_line:
        address_query = ", ".join(
            filter(None, [resident.address_line, resident.barangay, resident.city_municipality, resident.province, "Philippines"])
        )
        target = _geocode_query(address_query, api_key)
        if target:
            distance = _haversine_meters(lat, lng, target[0], target[1])
            if distance <= addr_radius:
                return {
                    "checked": True,
                    "matched": True,
                    "distance_m": round(distance),
                    "reference": "address",
                    "message": f"GPS matches the resident's exact address ({round(distance)}m away).",
                }

    # 2) Fall back to the barangay centroid (wider radius).
    barangay_query = ", ".join(
        filter(None, [resident.barangay, resident.city_municipality, resident.province, "Philippines"])
    )
    target = _geocode_query(barangay_query, api_key)
    if target:
        distance = _haversine_meters(lat, lng, target[0], target[1])
        if distance <= brgy_radius:
            return {
                "checked": True,
                "matched": True,
                "distance_m": round(distance),
                "reference": "barangay",
                "message": f"GPS matches the resident's barangay ({round(distance)}m from center).",
            }
        return {
            "checked": True,
            "matched": False,
            "distance_m": round(distance),
            "reference": "barangay",
            "message": f"GPS is {round(distance)}m from the resident's barangay -- outside the expected area.",
        }

    # Couldn't geocode anything (bad address data, or the API call failed).
    return {
        "checked": False,
        "matched": None,
        "distance_m": None,
        "reference": "unverified",
        "message": "GPS not verified (could not look up the resident's address/barangay).",
    }
