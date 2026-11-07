import { useState } from "react";
import { MapContainer, TileLayer, Marker, Popup, Tooltip } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

const API_URL = (import.meta.env.VITE_API_URL || "http://127.0.0.1:5000").replace(/\/$/, "");

const alertIcon = L.icon({
  iconUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png",
  iconRetinaUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png",
  shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [0, -41],
});

function getFeatures(payload) {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.features)) return payload.features;
  if (Array.isArray(payload?.alerts)) return payload.alerts;
  return [];
}

function getCoordinates(item) {
  const geometry = item?.geometry;
  if (Array.isArray(geometry?.coordinates)) {
    // GeoJSON stores coordinates as [longitud, latitud].
    const [longitude, latitude] = geometry.coordinates;
    return [Number(latitude), Number(longitude)];
  }

  // Also accept rows returned directly by the backend table.
  const row = item?.properties || item;
  const latitude = Number(row?.latitude ?? row?.lat);
  const longitude = Number(row?.longitude ?? row?.lon ?? row?.lng);
  if (Number.isFinite(latitude) && Number.isFinite(longitude)) return [latitude, longitude];
  return null;
}

function openNews(link) {
  if (!link) return;

  try {
    const url = new URL(link);
    if (url.protocol === "http:" || url.protocol === "https:") {
      window.open(url.href, "_blank", "noopener,noreferrer");
    }
  } catch {
    // Ignore malformed links from a feed entry.
  }
}

export default function MapView() {
  const [features, setFeatures] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const loadFeed = async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${API_URL}/alerts.geojson`);
      if (!response.ok) throw new Error(`El servidor respondió HTTP ${response.status}`);
      const payload = await response.json();
      setFeatures(getFeatures(payload));
    } catch (err) {
      setError(`No se pudo cargar el feed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="feed-section">
      <div className="feed-toolbar">
        <button type="button" onClick={loadFeed} disabled={loading}>
          {loading ? "Cargando…" : "Cargar feed"}
        </button>
        <span>{features.length} alertas en el mapa</span>
      </div>
      {error && <p className="feed-error" role="alert">{error}</p>}
      <MapContainer center={[20, 0]} zoom={2} minZoom={2} scrollWheelZoom style={{ height: "70vh", minHeight: 420, width: "100%" }}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {features.map((feature, index) => {
          const position = getCoordinates(feature);
          if (!position || !position.every(Number.isFinite) || position[0] < -90 || position[0] > 90 || position[1] < -180 || position[1] > 180) return null;
          const properties = feature?.properties || feature;
          const title = properties?.title || properties?.name || "Alerta";
          const country = properties?.country;
          const link = properties?.link || properties?.url;
          return (
            <Marker
              key={feature.id ?? index}
              position={position}
              icon={alertIcon}
              eventHandlers={{ click: () => openNews(link) }}
            >
              {link && (
                <Tooltip direction="top" offset={[0, -36]}>
                  <a href={link} target="_blank" rel="noreferrer">
                    {link}
                  </a>
                </Tooltip>
              )}
              <Popup>
                {country && <><strong>{country}</strong><br /></>}
                {link ? <a href={link} target="_blank" rel="noreferrer">{title}</a> : title}
                <br />
                <small>{position[0]}, {position[1]}</small>
              </Popup>
            </Marker>
          );
        })}
      </MapContainer>
    </section>
  );
}
