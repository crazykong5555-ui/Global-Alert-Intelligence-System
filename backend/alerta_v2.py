#!/usr/bin/env python3
"""
alerta_v2
La Fabrica Del Software.
Aplicación unificada: analiza feeds RSS, genera alerts.geojson/alerts.csv y las muestra
en una UI moderna (ttkbootstrap cuando esté disponible). Los iconos son generados
 dinámicamente (colores) para no requerir archivos adicionales.
"""

import os
import json
import hashlib
import re
from datetime import datetime, timezone
from typing import List, Dict, Any

import feedparser
import requests
import csv


def append_to_csv(alerts: List[Dict[str, Any]]):
    """Append alerts to a CSV file using the standard csv module.
    Creates the file with a header if it does not exist.
    """
    if not alerts:
        return
    fieldnames = list(alerts[0].keys())
    file_exists = os.path.isfile(OUT_CSV)
    try:
        with open(OUT_CSV, "a", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            for alert in alerts:
                writer.writerow(alert)
    except Exception as e:
        # Log silently; UI will handle errors elsewhere
        print(f"Failed to write CSV: {e}")


import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import webbrowser

# -----------------------------
# MODELO NLP (with fallback)
# -----------------------------
try:
    import spacy
    # Try to load the model
    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        # Model not found - try to download it
        import subprocess
        import sys
        subprocess.check_call([sys.executable, "-m", "spacy", "download", "en_core_web_sm"])
        nlp = spacy.load("en_core_web_sm")
except Exception as e:
    # Final fallback: disable NLP features
    print(f"Warning: spaCy initialization failed: {e}")
    nlp = None

GEOCODE_CACHE = {}
# Intentar usar ttkbootstrap para interfaz moderna; si no está, caerá a ttk estándar.
try:
    import ttkbootstrap as tb
    from ttkbootstrap.constants import *
    TB_AVAILABLE = True
except Exception:
    TB_AVAILABLE = False

# -----------------------------
# CONFIG / FEEDS / KEYWORDS
# -----------------------------
FEEDS = [
    "https://feeds.reuters.com/reuters/worldNews",
    "http://feeds.bbci.co.uk/news/world/rss.xml",
    "http://rss.cnn.com/rss/edition_world.rss",
    "https://apnews.com/rss",
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://www.theguardian.com/world/rss",
    "https://www.france24.com/en/rss",
    "https://www.dw.com/atom/rss-en-all",
    "https://www.hrw.org/rss.xml",
    "https://reliefweb.int/updates?format=rss",
    # Colombia
    "https://www.eltiempo.com/rss/colombia.xml",
    "https://www.elespectador.com/feed/",
    "https://www.semana.com/rss/",
    "https://caracol.com.co/rss/colombia/",
    "https://www.rcnradio.com/rss/colombia",
    "https://www.elcolombiano.com/rss",
    "https://www.lafm.com.co/rss.xml",
    "https://www.vanguardia.com/rss",
    "https://www.elheraldo.co/rss",
    "https://www.publimetro.co/rss/colombia",
]

KEYWORDS = [
    "conflict", "war", "attack", "strike", "explosion", "border",
    "tension", "military", "missile", "drone", "nuclear",
    "venezuela", "colombia", "usa", "russia", "ukraine", "middle east",
    "migration", "refugees", "displaced", "guerrilla", "eln", "farc",
    "narcotrafico", "tren de aragua", "gaitanistas", "epl",
    "terroristas", "cartel de los soles", "lanza del sur", "south spears"
]
KEYWORDS = [k.lower() for k in KEYWORDS]

SEVERITY_KEYWORDS = [
    "attack", "explosion", "killed", "strike", "war",
    "invasion", "massacre", "terrorist"
]

OUT_CSV = "alerts.csv"
OUT_GEOJSON = "alerts.geojson"
DUP_HASH_FILE = ".seen_unified_hashes"

# -----------------------------
# LÓGICA DE PROCESAMIENTO
# -----------------------------
def hash_item(title: str, link: str) -> str:
    return hashlib.sha256((title + link).encode("utf-8")).hexdigest()


def matches_keywords(text: str, keywords: List[str]) -> bool:
    t = text.lower()
    return any(k in t for k in keywords)


def severity_from_text(text: str) -> int:
    t = text.lower()
    score = sum(2 for k in SEVERITY_KEYWORDS if k in t)
    return min(score, 10)


def extract_places_regex(text: str) -> List[str]:
    """Fallback place extraction using regex patterns"""
    # Common patterns for place names (simplified)
    patterns = [
        r'\\b[A-Z][a-z]+(?:\\s+[A-Z][a-z]+)*\\b',  # Capitalized words
        r'\\b[A-Z]{2,}\\b',  # Acronyms like USA, UK
    ]

    places = set()
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            # Filter out common false positives
            if match not in ['The', 'And', 'Or', 'But', 'In', 'On', 'At', 'To', 'For', 'Of', 'With', 'By']:
                places.add(match)
    return list(places)[:5]  # Limit to 5 places


def extract_places(text: str) -> List[str]:
    if nlp is not None:
        try:
            doc = nlp(text)
            places = []
            for ent in doc.ents:
                if ent.label_ in ("GPE", "LOC", "FAC"):
                    if ent.text not in places:
                        places.append(ent.text)
            return places
        except Exception:
            # Fall back to regex if spaCy processing fails
            pass
    # Use regex fallback
    return extract_places_regex(text)


def geocode_place(place: str):
    if not place:
        return None

    if place in GEOCODE_CACHE:
        return GEOCODE_CACHE[place]

    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": place,
                "format": "jsonv2",
                "limit": 1,
                "addressdetails": 1
            },
            headers={
                "User-Agent": "AlertApp/2.0"
            },
            timeout=10
        )

        data = r.json()

        if data:
            coords = [
                float(data[0]["lon"]),
                float(data[0]["lat"])
            ]
            GEOCODE_CACHE[place] = coords
            return coords

    except Exception:
        pass

    return None


def extract_coords_from_text(text: str):
    places = extract_places(text)
    for place in places:
        coords = geocode_place(place)
        if coords:
            return coords
    return [0.0, 0.0]


def load_seen_hashes():
    if not os.path.exists(DUP_HASH_FILE):
        return set()
    try:
        with open(DUP_HASH_FILE, "r", encoding="utf-8") as f:
            return {line.strip() for line in f}
    except Exception:
        return set()


def save_seen_hashes(hashes: set):
    try:
        with open(DUP_HASH_FILE, "w", encoding="utf-8") as f:
            f.writelines(h + "\n" for h in hashes)
    except Exception:
        pass


def poll_once() -> List[Dict[str, Any]]:
    new_alerts = []
    seen = load_seen_hashes()

    for feed in FEEDS:
        try:
            d = feedparser.parse(feed)
        except Exception:
            continue

        for entry in getattr(d, "entries", []):
            title = entry.get("title", "")
            summary = entry.get("summary", entry.get("description", ""))
            link = entry.get("link", "")
            content = f"{title}\n{summary}"

            if not matches_keywords(content, KEYWORDS):
                continue

            h = hash_item(title, link)
            if h in seen:
                continue

            seen.add(h)
            coords = extract_coords_from_text(content)
            lon, lat = coords[0], coords[1]
            sev = severity_from_text(content)

            new_alerts.append({
                "id_hash": h,
                "title": title,
                "summary": summary,
                "link": link,
                "severity": sev,
                "longitude": lon,
                "latitude": lat,
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            })

    save_seen_hashes(seen)
    return new_alerts


def append_to_csv(alerts: List[Dict[str, Any]]):
    if not alerts:
        return
    df = pd.DataFrame(alerts)
    if os.path.exists(OUT_CSV):
        try:
            df_old = pd.read_csv(OUT_CSV)
            df = pd.concat([df_old, df], ignore_index=True)
        except Exception:
            pass
    df.to_csv(OUT_CSV, index=False)


def append_to_geojson(alerts: List[Dict[str, Any]]):
    features = []
    for a in alerts:
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [a["longitude"], a["latitude"]]},
            "properties": {k: v for k, v in a.items() if k not in ("longitude", "latitude")},
        })
    geojson = {"type": "FeatureCollection", "features": features}
    with open(OUT_GEOJSON, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)

# UI code follows (unchanged) ...
