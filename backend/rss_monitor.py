import re
import time
import feedparser
from geolocation import extract_location

# Reliable, active international news feeds
FEEDS = [
    {"name": "BBC News", "url": "https://feeds.bbci.co.uk/news/world/rss.xml"},
    {"name": "CNN World", "url": "http://rss.cnn.com/rss/edition_world.rss"},
    {"name": "NYT World", "url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"},
    {"name": "Al Jazeera", "url": "https://www.aljazeera.com/xml/rss/all.xml"},
    {"name": "The Guardian", "url": "https://www.theguardian.com/world/rss"},
    
    # ==========================================================
# LATINOAMERICA
# ==========================================================

{"name": "BBC Mundo Latinoamerica",
 "url": "https://feeds.bbci.co.uk/mundo/america_latina/rss.xml"},

{"name": "BBC Latin America",
 "url": "https://feeds.bbci.co.uk/news/world/latin_america/rss.xml"},

{"name": "France 24 Americas",
 "url": "https://www.france24.com/en/americas/rss"},

{"name": "France 24 Español",
 "url": "https://www.france24.com/es/rss"},

{"name": "El Pais America",
 "url": "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada"},

{"name": "Infobae",
 "url": "https://www.infobae.com/arc/outboundfeeds/rss/"},

# COLOMBIA
{"name": "El Tiempo Latinoamerica",
 "url": "https://www.eltiempo.com/rss/mundo_latinoamerica.xml"},

{"name": "La Silla Vacia",
 "url": "https://www.lasillavacia.com/rss"},

# ARGENTINA
{"name": "La Nacion Argentina",
 "url": "https://www.lanacion.com.ar/arc/outboundfeeds/rss/"},

{"name": "Clarin Argentina",
 "url": "https://www.clarin.com/rss/lo-ultimo/"},

# BRASIL
{"name": "Folha de Sao Paulo",
 "url": "https://feeds.folha.uol.com.br/emcimadahora/rss091.xml"},

{"name": "G1 Globo Brasil",
 "url": "https://g1.globo.com/rss/g1/"},

# ECUADOR
{"name": "Primicias Ecuador",
 "url": "https://www.primicias.ec/feed/"},

{"name": "El Universo Ecuador",
 "url": "https://www.eluniverso.com/arc/outboundfeeds/rss/category/noticias/?outputType=xml"},
]

# Keywords grouped by severity
CRITICAL_KEYWORDS = [
    "nuclear", "missile", "war", "airstrike", "air strike",
    "explosion", "bomb", "bombing", "terror", "terrorist", "massacre"
]

HIGH_KEYWORDS = [
    "attack", "killed", "combat", "troops", "hostage", "clash",
    "invasion", "invaded", "shelling", "casualties", "deadly"
]

MEDIUM_KEYWORDS = [
    "military", "drone", "conflict", "strike", "rebel",
    "offensive", "artillery", "ambush", "gunfire"
]

LOW_KEYWORDS = [
    "threat", "warning", "crisis", "security", "sanctions",
    "tensions", "dispute", "protest"
]

ALL_KEYWORDS = CRITICAL_KEYWORDS + HIGH_KEYWORDS + MEDIUM_KEYWORDS + LOW_KEYWORDS

# Cache configuration
_ALERTS_CACHE = {
    "timestamp": 0,
    "data": []
}
CACHE_TTL_SECONDS = 180  # 3 minutes


def _classify_severity(text):
    """Determine alert severity based on keyword presence."""
    lower = text.lower()
    for kw in CRITICAL_KEYWORDS:
        if kw in lower:
            return "critical"
    for kw in HIGH_KEYWORDS:
        if kw in lower:
            return "high"
    for kw in MEDIUM_KEYWORDS:
        if kw in lower:
            return "medium"
    return "low"


def _clean_html(raw_html):
    """Remove HTML tags and normalize whitespace."""
    if not raw_html:
        return ""
    clean = re.sub(r"<[^>]+>", " ", raw_html)
    return " ".join(clean.split())


def get_alerts(force_refresh=False):
    """
    Crawls RSS feeds, identifies military/conflict alerts, extracts locations,
    classifies severity, and caches results.
    """
    now = time.time()
    if not force_refresh and (now - _ALERTS_CACHE["timestamp"] < CACHE_TTL_SECONDS):
        if _ALERTS_CACHE["data"]:
            return _ALERTS_CACHE["data"]

    alerts = []
    seen_links = set()
    seen_titles = set()

    for feed_info in FEEDS:
        feed_url = feed_info["url"]
        source_name = feed_info["name"]

        try:
            feed_data = feedparser.parse(feed_url)

            for entry in feed_data.entries:
                title = entry.get("title", "").strip()
                summary = _clean_html(entry.get("summary", ""))
                link = entry.get("link", "").strip()
                published = entry.get("published", "")

                if not title:
                    continue

                # Deduplication check
                norm_title = title.lower()[:60]
                if link in seen_links or norm_title in seen_titles:
                    continue

                full_text = f"{title}. {summary}"
                lower_text = full_text.lower()

                # Check for relevant intelligence keywords
                matched = any(k in lower_text for k in ALL_KEYWORDS)
                if not matched:
                    continue

                # Geolocation extraction
                location = extract_location(full_text)
                if location:
                    severity = _classify_severity(full_text)

                    alerts.append({
                        "title": title,
                        "link": link,
                        "country": location["name"],
                        "lat": location["lat"],
                        "lon": location["lon"],
                        "severity": severity,
                        "summary": summary,
                        "published": published,
                        "source": source_name
                    })

                    seen_links.add(link)
                    seen_titles.add(norm_title)

        except Exception:
            continue

    if alerts:
        _ALERTS_CACHE["data"] = alerts
        _ALERTS_CACHE["timestamp"] = now

    return alerts if alerts else _ALERTS_CACHE["data"]
