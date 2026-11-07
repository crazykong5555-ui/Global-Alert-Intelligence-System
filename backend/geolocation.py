import re
from geopy.geocoders import Nominatim

# In-memory cache to prevent repetitive network requests and avoid Nominatim rate limits
_GEO_CACHE = {}

# Pre-seeded coordinates for common countries and conflict hotspots
KNOWN_LOCATIONS = {
    "afghanistan": {"name": "Afghanistan", "lat": 33.93911, "lon": 67.709953},
    "algeria": {"name": "Algeria", "lat": 28.033886, "lon": 1.659626},
    "armenia": {"name": "Armenia", "lat": 40.069099, "lon": 45.038189},
    "azerbaijan": {"name": "Azerbaijan", "lat": 40.143105, "lon": 47.576927},
    "belarus": {"name": "Belarus", "lat": 53.709807, "lon": 27.953389},
    "china": {"name": "China", "lat": 35.86166, "lon": 104.195397},
    "colombia": {"name": "Colombia", "lat": 4.570868, "lon": -74.297333},
    "egypt": {"name": "Egypt", "lat": 26.820553, "lon": 30.802498},
    "france": {"name": "France", "lat": 46.227638, "lon": 2.213749},
    "gaza": {"name": "Gaza Strip", "lat": 31.354676, "lon": 34.308825},
    "germany": {"name": "Germany", "lat": 51.165691, "lon": 10.451526},
    "india": {"name": "India", "lat": 20.593684, "lon": 78.96288},
    "iran": {"name": "Iran", "lat": 32.427908, "lon": 53.688046},
    "iraq": {"name": "Iraq", "lat": 33.223191, "lon": 43.679291},
    "ireland": {"name": "Ireland", "lat": 53.41291, "lon": -8.24389},
    "israel": {"name": "Israel", "lat": 31.046051, "lon": 34.851612},
    "italy": {"name": "Italy", "lat": 41.87194, "lon": 12.56738},
    "japan": {"name": "Japan", "lat": 36.204824, "lon": 138.252924},
    "jordan": {"name": "Jordan", "lat": 30.585164, "lon": 36.238414},
    "lebanon": {"name": "Lebanon", "lat": 33.854721, "lon": 35.862285},
    "libya": {"name": "Libya", "lat": 26.3351, "lon": 17.228331},
    "mexico": {"name": "Mexico", "lat": 23.634501, "lon": -102.552784},
    "myanmar": {"name": "Myanmar", "lat": 21.916221, "lon": 95.956005},
    "nigeria": {"name": "Nigeria", "lat": 9.081999, "lon": 8.675277},
    "north korea": {"name": "North Korea", "lat": 40.339852, "lon": 127.510093},
    "pakistan": {"name": "Pakistan", "lat": 30.375321, "lon": 69.345116},
    "palestine": {"name": "Palestine", "lat": 31.952162, "lon": 35.233154},
    "philippines": {"name": "Philippines", "lat": 12.879721, "lon": 121.774017},
    "poland": {"name": "Poland", "lat": 51.919438, "lon": 19.145136},
    "russia": {"name": "Russia", "lat": 61.52401, "lon": 105.318756},
    "saudi arabia": {"name": "Saudi Arabia", "lat": 23.885942, "lon": 45.079162},
    "somalia": {"name": "Somalia", "lat": 5.152149, "lon": 46.199616},
    "south korea": {"name": "South Korea", "lat": 35.907757, "lon": 127.766922},
    "spain": {"name": "Spain", "lat": 40.463667, "lon": -3.74922},
    "sudan": {"name": "Sudan", "lat": 12.862807, "lon": 30.217636},
    "syria": {"name": "Syria", "lat": 34.802075, "lon": 38.996815},
    "taiwan": {"name": "Taiwan", "lat": 23.69781, "lon": 120.960515},
    "turkey": {"name": "Turkey", "lat": 38.963745, "lon": 35.243322},
    "ukraine": {"name": "Ukraine", "lat": 48.379433, "lon": 31.16558},
    "united kingdom": {"name": "United Kingdom", "lat": 55.378051, "lon": -3.435973},
    "uk": {"name": "United Kingdom", "lat": 55.378051, "lon": -3.435973},
    "united states": {"name": "United States", "lat": 37.09024, "lon": -95.712891},
    "us": {"name": "United States", "lat": 37.09024, "lon": -95.712891},
    "usa": {"name": "United States", "lat": 37.09024, "lon": -95.712891},
    "venezuela": {"name": "Venezuela", "lat": 6.42375, "lon": -66.58973},
    "yemen": {"name": "Yemen", "lat": 15.552727, "lon": 48.516388},
}

# Safely initialize spaCy NLP model
try:
    import spacy
    try:
        nlp = spacy.load("en_core_web_sm")
    except Exception:
        nlp = None
except Exception:
    nlp = None

# Geocoder instance with dedicated user-agent and timeout
geolocator = Nominatim(user_agent="gais_global_alert_intelligence_system/1.0", timeout=5)


def _lookup_location(name):
    """Resolve location using known dictionary, cache, or geocoder."""
    clean_name = name.strip().strip(".,;:\"'()[]{}")
    if not clean_name or len(clean_name) < 2:
        return None

    lower = clean_name.lower()

    # 1. Built-in instant dictionary
    if lower in KNOWN_LOCATIONS:
        return KNOWN_LOCATIONS[lower]

    # 2. In-memory cache
    if lower in _GEO_CACHE:
        return _GEO_CACHE[lower]

    # 3. Remote geocoding
    try:
        location = geolocator.geocode(clean_name, language="en")
        if location:
            result = {
                "name": clean_name,
                "lat": location.latitude,
                "lon": location.longitude
            }
            _GEO_CACHE[lower] = result
            return result
        else:
            _GEO_CACHE[lower] = None
    except Exception:
        pass

    return None


def extract_location(text):
    """
    Extracts geographical location from text using spaCy NER,
    with fallback to regex matching against known locations.
    """
    if not text:
        return None

    # First attempt: NLP entity recognition
    if nlp is not None:
        try:
            doc = nlp(text)
            for ent in doc.ents:
                if ent.label_ in ["GPE", "LOC"]:
                    loc = _lookup_location(ent.text)
                    if loc:
                        return loc
        except Exception:
            pass

    # Fallback attempt: keyword matching against known hotspots
    lower_text = text.lower()
    for key, loc_data in KNOWN_LOCATIONS.items():
        # Match as whole word/phrase
        pattern = r"\b" + re.escape(key) + r"\b"
        if re.search(pattern, lower_text):
            return loc_data

    return None
