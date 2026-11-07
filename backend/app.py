import os

import mysql.connector
from flask import Flask, jsonify, request
from flask_cors import CORS
from rss_monitor import get_alerts as get_rss_alerts

def get_alerts(force_refresh: bool = False):
    alerts = get_rss_alerts(force_refresh=force_refresh)
    # The RSS feed and map should remain available when the optional MySQL
    # persistence layer is down or not configured.
    if alerts:
        try:
            save_alerts(alerts)
        except Exception:
            app.logger.exception("Could not persist RSS alerts to MySQL")
    return alerts


def _mysql_config(include_database=True):
    config = {
        "host": os.getenv("MYSQL_HOST", "localhost"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", "root"),
        "password": os.getenv("MYSQL_PASSWORD", ""),
    }
    if include_database:
        config["database"] = "gais"
    return config


def save_alerts(alerts):
    """Create the GAIS schema when needed and insert/update RSS alerts."""
    connection = mysql.connector.connect(**_mysql_config(include_database=False))
    try:
        cursor = connection.cursor()
        cursor.execute("CREATE DATABASE IF NOT EXISTS gais CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        cursor.execute("USE gais")
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS rss_alerts (
                id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                title TEXT NOT NULL,
                link VARCHAR(2048) NOT NULL,
                country VARCHAR(255) NOT NULL,
                latitude DOUBLE NOT NULL,
                longitude DOUBLE NOT NULL,
                severity VARCHAR(32) NOT NULL,
                summary TEXT,
                published VARCHAR(255),
                source VARCHAR(255),
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uq_rss_alerts_link (link(512))
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"""
        )
        cursor.executemany(
            """INSERT INTO rss_alerts
                (title, link, country, latitude, longitude, severity, summary, published, source)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    title = VALUES(title), country = VALUES(country),
                    latitude = VALUES(latitude), longitude = VALUES(longitude),
                    severity = VALUES(severity), summary = VALUES(summary),
                    published = VALUES(published), source = VALUES(source)""",
            [(
                alert["title"], alert["link"], alert["country"], alert["lat"], alert["lon"],
                alert["severity"], alert.get("summary"), alert.get("published"), alert.get("source"),
            ) for alert in alerts if alert.get("link") and alert.get("lat") is not None and alert.get("lon") is not None],
        )
        connection.commit()
    finally:
        connection.close()

app = Flask(__name__)

# Enable CORS for frontend integration (React dashboard)
CORS(app, resources={r"/*": {"origins": "*"}})


@app.route("/")
def home():
    """API root health/status endpoint."""
    return jsonify({
        "status": "GAIS API running",
        "endpoints": {
            "alerts": "/alerts",
            "health": "/health"
        }
    })


@app.route("/health")
def health():
    """Service health check."""
    return jsonify({
        "status": "healthy",
        "service": "Global Alert Intelligence System Backend"
    })


@app.route("/alerts")
def alerts():
    """Returns detected geopolitical/conflict alerts with geolocation data as a plain list."""
    try:
        force_refresh = request.args.get("refresh", "false").lower() in ("true", "1")
        data = get_alerts(force_refresh=force_refresh)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/alerts.geojson")
def alerts_geojson():
    """Return alerts as a GeoJSON FeatureCollection.
    Each feature includes point geometry (lon, lat) and properties title, link, country.
    """
    try:
        force_refresh = request.args.get("refresh", "false").lower() in ("true", "1")
        alerts = get_alerts(force_refresh=force_refresh)
        # Build GeoJSON
        features = []
        for a in alerts:
            # Ensure required fields exist
            if all(k in a for k in ("lat", "lon", "title", "link", "country")):
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [a["lon"], a["lat"]]},
                    "properties": {
                        "title": a["title"],
                        "link": a["link"],
                        "country": a["country"]
                    }
                })
        geojson = {"type": "FeatureCollection", "features": features}
        return jsonify(geojson)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/sample.geojson")
def sample_geojson():
    """Return a static sample alert as GeoJSON with full data fields.
    Example payload:
    {
        "country":"Colombia",
        "department":"Antioquia",
        "city":"Medellín",
        "confidence":0.98,
        "latitude":6.244,
        "longitude":-75.581,
        "event":"Ataque",
        "actors":["ELN"],
        "risk":"HIGH"
    }
    """
    feature = {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [-75.581, 6.244]
        },
        "properties": {
            "country": "Colombia",
            "department": "Antioquia",
            "city": "Medellín",
            "confidence": 0.98,
            "event": "Ataque",
            "actors": ["ELN"],
            "risk": "HIGH"
        }
    }
    return jsonify({"type": "FeatureCollection", "features": [feature]})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
