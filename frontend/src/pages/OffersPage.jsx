import React, { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import api from "../lib/api";
import OfferCard from "../components/OfferCard";
import AISearchBar from "../components/AISearchBar";
import { DIPLOMA_LEVELS } from "../lib/diplomas";
import FranceMap from "../components/FranceMap"; // kept import for backward compat; not rendered
const REGIONS_LIST = [
  "Île-de-France", "Auvergne-Rhône-Alpes", "Nouvelle-Aquitaine", "Occitanie", "Hauts-de-France",
  "Provence-Alpes-Côte d'Azur", "Grand Est", "Pays de la Loire", "Bretagne", "Normandie",
  "Bourgogne-Franche-Comté", "Centre-Val de Loire", "Corse",
];
import { Search, Filter, X, ChevronDown, ChevronUp, Map as MapIcon, List } from "lucide-react";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Checkbox } from "../components/ui/checkbox";
import { Badge } from "../components/ui/badge";

const SOURCES = [
  { id: "StageConnect", label: "StageEtudiant" },
  { id: "La Bonne Alternance", label: "La Bonne Alternance ★" },
  { id: "FranceTravail", label: "France Travail ✓" },
  { id: "Ashby", label: "Ashby" },
  { id: "Arbeitnow", label: "Arbeitnow" },
  { id: "Remotive", label: "Remotive" },
  { id: "RemoteOK", label: "RemoteOK" },
  { id: "Jobicy", label: "Jobicy" },
  { id: "Greenhouse", label: "Greenhouse" },
];

export default function OffersPage() {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const [offers, setOffers] = useState([]);
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(true);
  const [mobileView, setMobileView] = useState("list"); // list | map
  const [showFilters, setShowFilters] = useState(true);

  const q = params.get("q") || "";
  const region = params.get("region") || "";
  const city = params.get("city") || "";
  const ct = params.get("contract_type") || "";
  const domain = params.get("domain") || "";
  const level = params.get("level") || "";
  const remote = params.get("remote") === "true";
  const source = params.get("source") || "";
  const nearCity = params.get("near_city") || "";
  const distanceKm = params.get("distance_km") || "50";
  const includeLba = params.get("lba") !== "0"; // include La Bonne Alternance by default
  const [cityList, setCityList] = useState([]);

  useEffect(() => {
    api.get("/offers/regions").then((r) => setStats(r.data)).catch(() => {});
    api.get("/cities").then((r) => setCityList(r.data.cities)).catch(() => {});
  }, []);

  useEffect(() => {
    setLoading(true);
    const lbaOnly = source === "La Bonne Alternance";
    const ftOnly = source === "FranceTravail";
    const fetchLba = async () => {
      if (ftOnly) return []; // do not mix LBA with FT-only
      if (!includeLba && !lbaOnly) return [];
      if (!lbaOnly && ct && ct !== "alternance") return []; // when not LBA-only, only when alternance/all
      try {
        const lbaCity = nearCity || city;
        // For LBA-only filter, always fetch (Paris default if no city); for merge mode, require a geo hint
        if (!lbaOnly && !lbaCity && !region) return [];
        const lbaParams = new URLSearchParams();
        if (lbaCity) lbaParams.set("city", lbaCity);
        lbaParams.set("radius", nearCity ? distanceKm : "30");
        lbaParams.set("per_page", lbaOnly ? "60" : "30");
        const { data } = await api.get(`/lba/search?${lbaParams.toString()}`);
        return data.results || [];
      } catch (err) {
        console.warn("LBA fetch failed", err);
        return [];
      }
    };
    const fetchFt = async () => {
      if (!ftOnly) return [];
      try {
        const ftParams = new URLSearchParams();
        if (city) ftParams.set("city", city);
        if (region) ftParams.set("region", region);
        if (q) ftParams.set("q", q);
        if (domain) ftParams.set("domain", domain);
        ftParams.set("per_page", "50");
        const { data } = await api.get(`/francetravail/search?${ftParams.toString()}`);
        return data.results || [];
      } catch (err) {
        console.warn("FT fetch failed", err);
        return [];
      }
    };
    const fetchInternal = async () => {
      if (lbaOnly || ftOnly) return []; // do not fetch internal offers when an external source is selected
      if (nearCity) {
        const p = new URLSearchParams();
        p.set("city", nearCity);
        p.set("distance_km", distanceKm);
        if (ct) p.set("contract_type", ct);
        if (source) p.set("source", source);
        p.set("limit", "200");
        const r = await api.get(`/offers-nearby?${p.toString()}`);
        return r.data;
      }
      const p = new URLSearchParams();
      if (q) p.set("q", q);
      if (region) p.set("region", region);
      if (city) p.set("city", city);
      if (ct) p.set("contract_type", ct);
      if (domain) p.set("domain", domain);
      if (level) p.set("level", level);
      if (remote) p.set("remote", "true");
      if (source) p.set("source", source);
      p.set("limit", "300");
      const r = await api.get(`/offers?${p.toString()}`);
      return r.data;
    };
    const fetchKeyless = async () => {
      // include external keyless aggregated sources when no specific source filter
      if (source || lbaOnly || ftOnly) return [];
      try {
        const { data } = await api.get('/external-offers/keyless');
        return data.results || [];
      } catch (err) {
        console.warn('Keyless fetch failed', err);
        return [];
      }
    };
    Promise.all([fetchInternal(), fetchLba(), fetchFt(), fetchKeyless()])
      .then(([internal, lba, ft, keyless]) => {
        // Merge — internal first, then LBA, then FT, then keyless. dedupe by external_url/offer_id
        const seen = new Set();
        const merged = [];
        for (const o of [...internal, ...lba, ...ft, ...keyless]) {
          const k = o.external_url || o.offer_id || o.siret;
          if (k && seen.has(k)) continue;
          seen.add(k);
          merged.push(o);
        }
        setOffers(merged);
      })
      .finally(() => setLoading(false));
  }, [q, region, city, ct, domain, level, remote, source, nearCity, distanceKm, includeLba]);

  const updateParam = (k, v) => {
    const p = new URLSearchParams(params);
    if (v) p.set(k, v); else p.delete(k);
    setParams(p);
  };
  const reset = () => setParams({});

  const Sidebar = () => (
    <aside className="card-soft p-6 h-fit lg:sticky lg:top-20">
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-bold text-slate-900 flex items-center gap-2"><Filter className="w-4 h-4" />Filtres</h2>
        <button onClick={reset} className="text-xs text-blue-600 font-semibold" data-testid="filters-reset">Réinitialiser</button>
      </div>
      <div className="space-y-5">
        <div>
          <label className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2 block">Recherche</label>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <Input data-testid="filter-query" value={q} onChange={(e) => updateParam("q", e.target.value)} placeholder="Métier, mot-clé..." className="rounded-xl pl-9" />
          </div>
        </div>
        <div>
          <label className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2 block">Ville</label>
          <Input data-testid="filter-city" value={city} onChange={(e) => updateParam("city", e.target.value)} placeholder="Paris, Lyon..." className="rounded-xl" />
        </div>
        <div>
          <label className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2 block">Type de contrat</label>
          <div className="space-y-2">
            {[{ val: "", label: "Tous" }, { val: "stage", label: "Stage" }, { val: "alternance", label: "Alternance" }].map(o => (
              <label key={o.val} className="flex items-center gap-2 cursor-pointer text-sm" data-testid={`filter-ct-${o.val || "all"}`}>
                <input type="radio" checked={ct === o.val} onChange={() => updateParam("contract_type", o.val)} className="accent-blue-600" />{o.label}
              </label>
            ))}
          </div>
        </div>
        <div>
          <label className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2 block">Niveau</label>
          <select data-testid="filter-level" value={level} onChange={(e) => updateParam("level", e.target.value)} className="w-full rounded-xl border border-slate-200 px-3 h-10 text-sm bg-white">
            <option value="">Tous niveaux</option>
            {DIPLOMA_LEVELS.map(d => <option key={d} value={d}>{d}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2 block">Domaine</label>
          <Input data-testid="filter-domain" value={domain} onChange={(e) => updateParam("domain", e.target.value)} placeholder="Informatique..." className="rounded-xl" />
        </div>
        <div>
          <label className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2 block">Source</label>
          <select data-testid="filter-source" value={source} onChange={(e) => updateParam("source", e.target.value)} className="w-full rounded-xl border border-slate-200 px-3 h-10 text-sm bg-white">
            <option value="">Toutes</option>
            {SOURCES.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
          </select>
        </div>
        <div className="bg-gradient-to-br from-blue-50 to-violet-50 rounded-xl p-4 -mx-2">
          <label className="text-xs font-bold uppercase tracking-wider text-violet-700 mb-2 block">Rayon autour d'une ville</label>
          <select value={nearCity} onChange={(e) => updateParam("near_city", e.target.value)} className="w-full rounded-xl border-0 bg-white px-3 h-10 text-sm" data-testid="filter-near-city">
            <option value="">Aucun</option>
            {cityList.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
          {nearCity && (
            <div className="mt-2">
              <label className="text-[10px] font-semibold text-slate-500">Distance: {distanceKm} km</label>
              <input type="range" min="10" max="300" step="10" value={distanceKm} onChange={(e) => updateParam("distance_km", e.target.value)} className="w-full accent-violet-600" data-testid="filter-distance" />
            </div>
          )}
        </div>
        <label className="flex items-center gap-2 cursor-pointer bg-amber-50 -mx-2 px-3 py-2 rounded-xl" data-testid="filter-lba">
          <input type="checkbox" checked={includeLba} onChange={(e) => updateParam("lba", e.target.checked ? "" : "0")} className="accent-amber-600" />
          <div>
            <div className="text-sm font-bold text-amber-900">Inclure La Bonne Alternance</div>
            <div className="text-[10px] text-amber-700">Offres officielles gouv (alternance)</div>
          </div>
        </label>
        <label className="flex items-center gap-2 cursor-pointer" data-testid="filter-remote">
          <Checkbox checked={remote} onCheckedChange={(v) => updateParam("remote", v ? "true" : "")} />
          <span className="text-sm font-medium">Télétravail possible</span>
        </label>
        {region && (
          <div className="bg-blue-50 rounded-xl p-3 flex items-center justify-between">
            <div className="text-sm font-semibold text-blue-700 truncate">{region}</div>
            <button onClick={() => updateParam("region", "")} data-testid="clear-region"><X className="w-4 h-4 text-blue-700" /></button>
          </div>
        )}
      </div>
    </aside>
  );

  const Map = () => (
    <div className="card-soft p-5 mb-6">
      <h3 className="font-bold text-slate-900 mb-3">Filtrer par région</h3>
      <div className="flex flex-wrap gap-2">
        {REGIONS_LIST.map(r => (
          <button
            key={r}
            onClick={() => updateParam("region", r === region ? "" : r)}
            className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-all ${region === r ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200"}`}
            data-testid={`region-chip-${r.replace(/\s|'|-/g, "_")}`}
          >
            {r}
            {stats.by_region?.find(s => s.region === r) && (
              <span className="ml-1.5 text-[10px] opacity-70">({stats.by_region.find(s => s.region === r).offers})</span>
            )}
          </button>
        ))}
      </div>
    </div>
  );

  const Results = () => (
    <div>
      {loading ? (
        <div className="text-center py-12 text-slate-400">Chargement...</div>
      ) : offers.length === 0 ? (
        <div className="card-soft p-12 text-center">
          <div className="text-slate-400 mb-2">Aucune offre trouvée</div>
          <Button variant="outline" onClick={reset} className="rounded-full mt-2">Réinitialiser</Button>
        </div>
      ) : (
        <div className="grid sm:grid-cols-2 gap-4">
          {offers.map(o => <OfferCard key={o.offer_id} offer={o} />)}
        </div>
      )}
    </div>
  );

  return (
    <div className="min-h-screen pt-20 pb-12 bg-slate-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6">
        <h1 className="text-3xl font-black tracking-tight text-slate-900 mb-2">Offres de stage & alternance</h1>
        <p className="text-slate-500 mb-4">{offers.length} offres · Sources multiples agrégées</p>

        <AISearchBar onCriteria={(c) => {
          const p = new URLSearchParams(params);
          if (c?.city) p.set("city", c.city);
          if (c?.contract_type) p.set("contract_type", c.contract_type);
          if (c?.keywords) p.set("q", c.keywords);
          if (c?.domain) p.set("domain", c.domain);
          setParams(p);
        }} />

        {/* Mobile toggle */}
        <div className="lg:hidden flex gap-2 mb-4">
          <Button onClick={() => setMobileView("list")} variant={mobileView === "list" ? "default" : "outline"} className="rounded-full flex-1" data-testid="mobile-list-btn"><List className="w-4 h-4 mr-1" />Liste</Button>
          <Button onClick={() => setMobileView("map")} variant={mobileView === "map" ? "default" : "outline"} className="rounded-full flex-1" data-testid="mobile-map-btn"><MapIcon className="w-4 h-4 mr-1" />Carte</Button>
          <Button onClick={() => setShowFilters(!showFilters)} variant="outline" className="rounded-full" data-testid="mobile-filters-btn">
            <Filter className="w-4 h-4 mr-1" />Filtres
          </Button>
        </div>

        {/* Mobile filters toggle visibility */}
        {showFilters && <div className="lg:hidden mb-4"><Sidebar /></div>}

        <div className="grid lg:grid-cols-[280px_1fr] gap-6">
          <div className="hidden lg:block"><Sidebar /></div>
          <div>
            <div className={`${mobileView === "map" ? "block" : "hidden"} lg:block`}><Map /></div>
            <div className={`${mobileView === "list" ? "block" : "hidden"} lg:block`}><Results /></div>
          </div>
        </div>
      </div>
    </div>
  );
}
