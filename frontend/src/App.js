import MapView from "./MapView";

const API_URL = (import.meta.env.VITE_API_URL || "http://127.0.0.1:5000").replace(/\/$/, "");

function App() {
  const exportGeoJSON = async () => {
    try {
      const response = await fetch(`${API_URL}/alerts.geojson`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "alerts.geojson";
      anchor.click();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error("No se pudo exportar el GeoJSON", error);
    }
  };

  return (
    <main className="app">
      <header className="app-header">
        <h1>Global Alert Intelligence System</h1>
        <button type="button" className="secondary-button" onClick={exportGeoJSON}>
          Exportar GeoJSON
        </button>
      </header>
      <MapView />
    </main>
  );
}

export default App;
