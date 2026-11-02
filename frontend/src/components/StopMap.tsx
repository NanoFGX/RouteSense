import L from "leaflet";
import { useEffect } from "react";
import { MapContainer, Marker, Polyline, TileLayer, Tooltip, useMap } from "react-leaflet";

export interface MapPoint {
  id: string;
  lat: number;
  lng: number;
  label: string;
  color: string;
  title: string;
  ring?: boolean;
}

type LatLng = [number, number];

function FitBounds({ points }: { points: LatLng[] }) {
  const map = useMap();
  const key = points.map((p) => p.join(",")).join("|");
  useEffect(() => {
    if (points.length > 1) map.fitBounds(L.latLngBounds(points), { padding: [28, 28] });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return null;
}

const pin = (p: MapPoint) =>
  L.divIcon({
    className: "",
    html: `<div class="stop-pin" style="background:${p.color};${p.ring ? "outline:3px solid #8a1538;outline-offset:1px" : ""}">${p.label}</div>`,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
  });

const hubIcon = L.divIcon({ className: "", html: `<div class="hub-pin">HUB</div>`, iconSize: [30, 30], iconAnchor: [15, 15] });

export function StopMap({
  points,
  hub,
  line,
  altLine,
  height = 300,
  onSelect,
}: {
  points: MapPoint[];
  hub: { lat: number; lng: number; label: string };
  line: LatLng[];
  altLine?: LatLng[];
  height?: number;
  onSelect?: (id: string) => void;
}) {
  const all: LatLng[] = [[hub.lat, hub.lng], ...points.map((p) => [p.lat, p.lng] as LatLng)];
  return (
    <div className="overflow-hidden rounded-2xl border border-line" style={{ height }}>
      <MapContainer center={[hub.lat, hub.lng]} zoom={12} scrollWheelZoom={false} style={{ height: "100%", width: "100%" }}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
        />
        <FitBounds points={all} />
        {altLine && altLine.length > 1 && (
          <Polyline positions={altLine} pathOptions={{ color: "#6a5f65", weight: 3, opacity: 0.55, dashArray: "6 8" }} />
        )}
        {line.length > 1 && <Polyline positions={line} pathOptions={{ color: "#8a1538", weight: 4, opacity: 0.85 }} />}
        <Marker position={[hub.lat, hub.lng]} icon={hubIcon}>
          <Tooltip direction="top" offset={[0, -14]}>{hub.label}</Tooltip>
        </Marker>
        {points.map((p) => (
          <Marker key={p.id} position={[p.lat, p.lng]} icon={pin(p)} eventHandlers={{ click: () => onSelect?.(p.id) }}>
            <Tooltip direction="top" offset={[0, -14]}>{p.title}</Tooltip>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
}
