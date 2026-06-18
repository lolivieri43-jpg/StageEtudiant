import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { MapContainer, TileLayer, Marker, Popup, useMap } from "react-leaflet";
import MarkerClusterGroup from "react-leaflet-cluster";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "leaflet.markercluster/dist/MarkerCluster.css";
import "leaflet.markercluster/dist/MarkerCluster.Default.css";
import api from "../lib/api";
import { Search, Filter, X, Loader2, MapPin, Briefcase, Building2 } from "lucide-react";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";

// Fix default marker icons under webpack (CRA doesn't inline them)
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

// Distinct marker per contract type
const ICONS = {
  stage: new L.Icon({
    iconUrl: "https://cdn.rawgit.com/pointhi/leaflet-color-markers/master/img/marker-icon-blue.png",
    shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
    iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34], shadowSize: [41, 41],
  }),
  alternance: new L.Icon({
    iconUrl: "https://cdn.rawgit.com/pointhi/leaflet-color-markers/master/img/marker-icon-violet.png",
    shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
    iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34], shadowSize: [41, 41],
  }),
  default: new L.Icon.Default(),
};

function FitOnResults({ results }) {
  const map = useMap();
  useEffect(() => {
    if (!results || results.length === 0) return;
    if (results.length === 1) {
      map.setView([results[0].latitude, results[0].longitude], 11);
      return;
    }
    const bounds = L.latLngBounds(results.map(r => [r.latitude, r.longitude]));
    map.fitBounds(bounds, { padding: [40, 40], maxZoom: 12 });
  }, [results, map]);
  return null;
}

export default function MapPage() {
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(true);
  // Applied filters (used for fetch)
  const [applied, setApplied] = useState({ country: "", city: "", contract_type: "", domain: "", q: "" });
  // Draft (form values, no auto-apply)
  const [draft, setDraft] = useState({ country: "", city: "", contract_type: "", domain: "", q: "" });
  const [showFilters, setShowFilters] = useState(false);

  const fetchOffers = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      Object.entries(applied).forEach(([k, v]) => v && params.set(k, v));
      params.set("limit", "2000");
      const { data } = await api.get(`/offers-map?${params.toString()}`);
      setResults(data.results || []);
    } catch (err) {
      console.error("map load failed", err);
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchOffers(); /* eslint-disable-next-line */ }, [applied]);

  const submit = (e) => { if (e?.preventDefault) e.preventDefault(); setApplied(draft); };
  const reset = () => { setDraft({ country: "", city: "", contract_type: "", domain: "", q: "" }); setApplied({ country: "", city: "", contract_type: "", domain: "", q: "" }); };

  const counts = useMemo(() => {
    let stage = 0, alt = 0;
    for (const r of results) {
      if (r.contract_type === "stage") stage++;
      else if (r.contract_type === "alternance") alt++;
    }
    return { stage, alt, total: results.length };
  }, [results]);

  // Deferred mount — sidesteps StrictMode's "Map container is already initialized" issue
  // by only mounting MapContainer once on the next tick (StrictMode's first synchronous
  // unmount cleans up the scheduled timer before it ever fires).
  const [mapReady, setMapReady] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setMapReady(true), 0);
    return () => { clearTimeout(t); setMapReady(false); };
  }, []);

  const Sidebar = ({ className = "" }) => (
    <aside className={`card-soft p-5 ${className}`} data-testid="map-filters">
      <form onSubmit={submit} className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-bold flex items-center gap-2 text-slate-900 dark:text-slate-100"><Filter className="w-4 h-4" />Filtres</h2>
          <button type="button" onClick={reset} className="text-xs text-blue-600 font-semibold" data-testid="map-reset">Réinitialiser</button>
        </div>

        <div>
          <label className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-1 block">Recherche</label>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <Input value={draft.q} onChange={(e) => setDraft({ ...draft, q: e.target.value })} placeholder="Métier, mot-clé…" className="rounded-xl pl-9" data-testid="map-q" />
          </div>
        </div>
        <div>
          <label className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-1 block">Pays</label>
          <Input value={draft.country} onChange={(e) => setDraft({ ...draft, country: e.target.value })} placeholder="France, Belgique…" className="rounded-xl" data-testid="map-country" />
        </div>
        <div>
          <label className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-1 block">Ville</label>
          <Input value={draft.city} onChange={(e) => setDraft({ ...draft, city: e.target.value })} placeholder="Paris, Lyon…" className="rounded-xl" data-testid="map-city" />
        </div>
        <div>
          <label className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-1 block">Type de contrat</label>
          <select value={draft.contract_type} onChange={(e) => setDraft({ ...draft, contract_type: e.target.value })} className="w-full rounded-xl border border-slate-200 dark:border-slate-700 px-3 h-10 text-sm bg-white dark:bg-slate-800" data-testid="map-contract">
            <option value="">Tous</option>
            <option value="stage">Stage</option>
            <option value="alternance">Alternance</option>
          </select>
        </div>
        <div>
          <label className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-1 block">Secteur / métier</label>
          <Input value={draft.domain} onChange={(e) => setDraft({ ...draft, domain: e.target.value })} placeholder="Informatique, Marketing…" className="rounded-xl" data-testid="map-domain" />
        </div>

        <Button type="submit" disabled={loading} className="w-full rounded-full bg-blue-600 hover:bg-blue-700 h-11" data-testid="map-apply">
          {loading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Search className="w-4 h-4 mr-2" />}
          Rechercher sur la carte
        </Button>

        <div className="border-t border-slate-100 dark:border-slate-800 pt-3 mt-3 text-xs text-slate-500 space-y-1" data-testid="map-counts">
          <div className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-blue-500" />Stage : <b className="text-slate-700 dark:text-slate-300">{counts.stage}</b></div>
          <div className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-violet-500" />Alternance : <b className="text-slate-700 dark:text-slate-300">{counts.alt}</b></div>
          <div className="pt-1 border-t border-slate-100 dark:border-slate-800">Total géolocalisé : <b className="text-slate-700 dark:text-slate-300">{counts.total}</b></div>
        </div>
      </form>
    </aside>
  );

  return (
    <div className="min-h-screen pt-16 bg-slate-50 dark:bg-slate-900">
      <div className="max-w-[1600px] mx-auto px-3 sm:px-6 pt-4">
        <div className="flex items-center justify-between mb-3 gap-3">
          <div>
            <h1 className="text-2xl sm:text-3xl font-black tracking-tight text-slate-900 dark:text-slate-100">
              <MapPin className="inline w-7 h-7 text-blue-600 mr-1 -mt-1" />Carte des offres
            </h1>
            <p className="text-sm text-slate-500">{loading ? "Chargement…" : `${counts.total} offre${counts.total > 1 ? "s" : ""} géolocalisée${counts.total > 1 ? "s" : ""}`}</p>
          </div>
          <Button variant="outline" className="lg:hidden rounded-full" onClick={() => setShowFilters(!showFilters)} data-testid="map-toggle-filters">
            {showFilters ? <X className="w-4 h-4 mr-1" /> : <Filter className="w-4 h-4 mr-1" />}
            Filtres
          </Button>
        </div>

        {showFilters && <div className="lg:hidden mb-3"><Sidebar /></div>}

        <div className="grid lg:grid-cols-[300px_1fr] gap-4 pb-6">
          <div className="hidden lg:block"><Sidebar className="sticky top-20" /></div>

          <div className="rounded-2xl overflow-hidden ring-1 ring-slate-200 dark:ring-slate-800 shadow-sm bg-slate-100 dark:bg-slate-800" style={{ height: "calc(100vh - 160px)" }}>
            {!mapReady ? (
              <div className="h-full w-full flex items-center justify-center text-slate-400" data-testid="map-loading">
                <Loader2 className="w-6 h-6 animate-spin mr-2" />Préparation de la carte…
              </div>
            ) : (
            <MapContainer
              center={[46.5, 2.5]} zoom={4} minZoom={2} maxZoom={18}
              scrollWheelZoom={true}
              style={{ height: "100%", width: "100%" }}
              worldCopyJump={true}
            >
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &middot; Geocoding by <a href="https://www.geoapify.com/">Geoapify</a>'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              <FitOnResults results={results} />
              <MarkerClusterGroup chunkedLoading maxClusterRadius={50}>
                {results.map(o => (
                  <Marker
                    key={o.id || `${o.latitude}-${o.longitude}-${o.title}`}
                    position={[o.latitude, o.longitude]}
                    icon={ICONS[o.contract_type] || ICONS.default}
                  >
                    <Popup>
                      <div className="min-w-[200px]">
                        <div className="font-bold text-slate-900 mb-0.5">{o.title}</div>
                        <div className="text-xs text-slate-600 flex items-center gap-1 mb-1"><Building2 className="w-3 h-3" />{o.company}</div>
                        <div className="text-xs text-slate-500 flex items-center gap-1 mb-1"><MapPin className="w-3 h-3" />{o.city}{o.country && `, ${o.country}`}</div>
                        {o.contract_type && (
                          <div className="text-[10px] font-bold uppercase tracking-wider mb-2">
                            <Briefcase className="w-3 h-3 inline mr-1" />
                            <span className={o.contract_type === "stage" ? "text-blue-700" : "text-violet-700"}>
                              {o.contract_type === "stage" ? "Stage" : o.contract_type === "alternance" ? "Alternance" : o.contract_type}
                            </span>
                          </div>
                        )}
                        {o.is_external && o.url ? (
                          <a href={o.url} target="_blank" rel="noopener noreferrer" className="block w-full text-center bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-3 py-1.5 rounded-full mt-1" data-testid={`map-popup-link-${o.id}`}>Voir l'offre →</a>
                        ) : o.id ? (
                          <Link to={`/offers/${o.id}`} className="block w-full text-center bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-3 py-1.5 rounded-full mt-1" data-testid={`map-popup-link-${o.id}`}>Voir l'offre →</Link>
                        ) : null}
                      </div>
                    </Popup>
                  </Marker>
                ))}
              </MarkerClusterGroup>
            </MapContainer>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
