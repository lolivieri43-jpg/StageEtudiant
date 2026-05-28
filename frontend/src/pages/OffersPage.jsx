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
import { Search, Filter, X, Map as MapIcon, List, Loader2, RotateCcw } from "lucide-react";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Checkbox } from "../components/ui/checkbox";

const SOURCES = [
  { id: "StageConnect", label: "StageEtudiant" },
  { id: "La Bonne Alternance", label: "La Bonne Alternance ★" },
  { id: "FranceTravail", label: "France Travail ✓" },
  { id: "Adzuna", label: "Adzuna" },
  { id: "EURES", label: "EURES (UE)" },
  { id: "Ashby", label: "Ashby" },
  { id: "Arbeitnow", label: "Arbeitnow" },
  { id: "Remotive", label: "Remotive" },
  { id: "RemoteOK", label: "RemoteOK" },
  { id: "Jobicy", label: "Jobicy" },
  { id: "Greenhouse", label: "Greenhouse" },
];

// ---- URL <-> draft helpers ----------------------------------------------
const FILTER_KEYS = [
  "q", "region", "city", "contract_type", "domain", "level",
  "remote", "source", "near_city", "distance_km", "lba",
  "company", "country", "european",
];

function readFromParams(params) {
  return {
    q: params.get("q") || "",
    region: params.get("region") || "",
    city: params.get("city") || "",
    contract_type: params.get("contract_type") || "",
    domain: params.get("domain") || "",
    level: params.get("level") || "",
    remote: params.get("remote") === "true",
    source: params.get("source") || "",
    near_city: params.get("near_city") || "",
    distance_km: params.get("distance_km") || "50",
    lba: params.get("lba") !== "0",     // default true
    company: params.get("company") || "",
    country: params.get("country") || "",
    european: params.get("european") === "1",
  };
}

function writeToParams(draft) {
  const p = new URLSearchParams();
  if (draft.q) p.set("q", draft.q);
  if (draft.region) p.set("region", draft.region);
  if (draft.city) p.set("city", draft.city);
  if (draft.contract_type) p.set("contract_type", draft.contract_type);
  if (draft.domain) p.set("domain", draft.domain);
  if (draft.level) p.set("level", draft.level);
  if (draft.remote) p.set("remote", "true");
  if (draft.source) p.set("source", draft.source);
  if (draft.near_city) p.set("near_city", draft.near_city);
  if (draft.near_city && draft.distance_km) p.set("distance_km", draft.distance_km);
  if (draft.lba === false) p.set("lba", "0");
  if (draft.company) p.set("company", draft.company);
  if (draft.country) p.set("country", draft.country);
  if (draft.european) p.set("european", "1");
  return p;
}

export default function OffersPage() {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const [offers, setOffers] = useState([]);
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(true);
  const [mobileView, setMobileView] = useState("list");
  const [showFilters, setShowFilters] = useState(true);
  const [cityList, setCityList] = useState([]);

  // Draft state — only applied on explicit submit
  const [draft, setDraft] = useState(() => readFromParams(params));

  // Active filters = those currently encoded in the URL (the ones used for the API call)
  const active = readFromParams(params);

  useEffect(() => {
    api.get("/offers/regions").then((r) => setStats(r.data)).catch(() => {});
    api.get("/cities").then((r) => setCityList(r.data.cities)).catch(() => {});
  }, []);

  // Re-sync draft when URL changes externally (e.g. AI search, region chip, browser back)
  useEffect(() => {
    setDraft(readFromParams(params));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.toString()]);

  // ---- Data fetching driven by URL params (not draft) ----
  useEffect(() => {
    setLoading(true);
    const a = active;
    const lbaOnly = a.source === "La Bonne Alternance";
    const ftOnly  = a.source === "FranceTravail";
    const fetchLba = async () => {
      if (ftOnly) return [];
      if (!a.lba && !lbaOnly) return [];
      if (!lbaOnly && a.contract_type && a.contract_type !== "alternance") return [];
      try {
        const lbaCity = a.near_city || a.city;
        // For LBA-only OR when a company keyword is set, allow fetching without geo hint
        if (!lbaOnly && !a.company && !lbaCity && !a.region) return [];
        const lp = new URLSearchParams();
        if (lbaCity) lp.set("city", lbaCity);
        if (a.company) lp.set("romes", a.company); // LBA uses "romes" param; reusing for keyword passthrough
        lp.set("radius", a.near_city ? a.distance_km : "30");
        lp.set("per_page", lbaOnly ? "60" : "30");
        const { data } = await api.get(`/lba/search?${lp.toString()}`);
        return data.results || [];
      } catch { return []; }
    };
    const fetchFt = async () => {
      // ALSO trigger France Travail when the user types a company name (so Sofratom etc. is found)
      const shouldFetchFt = ftOnly || (a.company && !lbaOnly);
      if (!shouldFetchFt) return [];
      try {
        const fp = new URLSearchParams();
        if (a.city) fp.set("city", a.city);
        if (a.region) fp.set("region", a.region);
        if (a.q) fp.set("q", a.q);
        if (a.company) fp.set("q", a.company);   // company name as keyword
        if (a.domain) fp.set("domain", a.domain);
        fp.set("per_page", "50");
        const { data } = await api.get(`/francetravail/search?${fp.toString()}`);
        return data.results || [];
      } catch { return []; }
    };
    const fetchInternal = async () => {
      if (lbaOnly || ftOnly) return [];
      if (a.near_city) {
        const p = new URLSearchParams();
        p.set("city", a.near_city);
        p.set("distance_km", a.distance_km);
        if (a.contract_type) p.set("contract_type", a.contract_type);
        if (a.source) p.set("source", a.source);
        p.set("limit", "200");
        const r = await api.get(`/offers-nearby?${p.toString()}`);
        return r.data;
      }
      const p = new URLSearchParams();
      if (a.q) p.set("q", a.q);
      if (a.region) p.set("region", a.region);
      if (a.city) p.set("city", a.city);
      if (a.contract_type) p.set("contract_type", a.contract_type);
      if (a.domain) p.set("domain", a.domain);
      if (a.level) p.set("level", a.level);
      if (a.remote) p.set("remote", "true");
      if (a.source) p.set("source", a.source);
      if (a.company) p.set("company", a.company);
      if (a.country) p.set("country", a.country);
      if (a.european) p.set("european_only", "true");
      p.set("limit", "300");
      const r = await api.get(`/offers?${p.toString()}`);
      return r.data;
    };
    const fetchKeyless = async () => {
      const EXT = new Set(["Adzuna","Jooble","EURES","Ashby","Arbeitnow","Remotive","RemoteOK","Jobicy","Greenhouse"]);
      if (lbaOnly || ftOnly) return [];
      if (a.source && !EXT.has(a.source)) return [];
      try {
        const ep = new URLSearchParams();
        if (a.company) ep.set("company", a.company);
        if (a.near_city) { ep.set("city", a.near_city); ep.set("radius_km", a.distance_km); }
        else if (a.city) ep.set("city", a.city);
        if (a.country) ep.set("country", a.country);
        if (a.european) ep.set("european_only", "true");
        const { data } = await api.get(`/external-offers/all?${ep.toString()}`);
        const all = data.results || [];
        return a.source ? all.filter(o => o.source === a.source) : all;
      } catch { return []; }
    };
    Promise.all([fetchInternal(), fetchLba(), fetchFt(), fetchKeyless()])
      .then(([internal, lba, ft, keyless]) => {
        const seen = new Set();
        const merged = [];
        for (const o of [...internal, ...lba, ...ft, ...keyless]) {
          const k = o.external_url || o.offer_id || o.siret;
          if (k && seen.has(k)) continue;
          seen.add(k);
          merged.push(o);
        }
        // Apply company strict-ish filter on the merged set when set, in case FT
        // returned tangentially-related results (keyword in description, not company).
        let final = merged;
        if (a.company) {
          const term = a.company
            .toLowerCase()
            .normalize("NFD").replace(/\p{Diacritic}/gu, "")
            .trim();
          final = merged.filter(o => {
            const name = (o.company_name || "").toLowerCase().normalize("NFD").replace(/\p{Diacritic}/gu, "");
            return name.includes(term);
          });
        }
        setOffers(final);
      })
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.toString()]);

  // ---- Draft helpers ----
  const setDraftKey = (k, v) => setDraft(d => ({ ...d, [k]: v }));
  const applyFilters = (e) => {
    if (e?.preventDefault) e.preventDefault();
    setParams(writeToParams(draft));
  };
  const resetFilters = () => {
    const blank = readFromParams(new URLSearchParams());
    setDraft(blank);
    setParams(new URLSearchParams());
  };

  // ---- Sidebar (no auto-apply) ----
  const Sidebar = () => (
    <aside className="card-soft p-6 h-fit lg:sticky lg:top-20" data-testid="filters-sidebar">
      <form onSubmit={applyFilters} className="space-y-5">
        <div className="flex items-center justify-between">
          <h2 className="font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <Filter className="w-4 h-4" />Filtres
          </h2>
          <button type="button" onClick={resetFilters} className="text-xs text-blue-600 font-semibold inline-flex items-center gap-1" data-testid="filters-reset">
            <RotateCcw className="w-3 h-3" />Réinitialiser
          </button>
        </div>

        <div>
          <label className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2 block">Recherche</label>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <Input data-testid="filter-query" value={draft.q} onChange={(e) => setDraftKey("q", e.target.value)} placeholder="Métier, mot-clé..." className="rounded-xl pl-9" />
          </div>
        </div>
        <div>
          <label className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2 block">Ville</label>
          <Input data-testid="filter-city" value={draft.city} onChange={(e) => setDraftKey("city", e.target.value)} placeholder="Paris, Lyon..." className="rounded-xl" />
        </div>
        <div>
          <label className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2 block">Entreprise précise</label>
          <Input data-testid="filter-company" value={draft.company} onChange={(e) => setDraftKey("company", e.target.value)} placeholder="Ex: Sofratom, EDF, SNCF…" className="rounded-xl" />
          <div className="text-[10px] text-slate-500 mt-1">
            {draft.company
              ? "Filtre strict (accents/majuscules ignorés). Cherche dans toutes les sources."
              : "Tapez le nom d'une entreprise pour voir uniquement ses offres"}
          </div>
        </div>
        <div>
          <label className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2 block">Type de contrat</label>
          <div className="space-y-2">
            {[{ val: "", label: "Tous" }, { val: "stage", label: "Stage" }, { val: "alternance", label: "Alternance" }].map(o => (
              <label key={o.val} className="flex items-center gap-2 cursor-pointer text-sm" data-testid={`filter-ct-${o.val || "all"}`}>
                <input type="radio" name="contract_type" checked={draft.contract_type === o.val} onChange={() => setDraftKey("contract_type", o.val)} className="accent-blue-600" />{o.label}
              </label>
            ))}
          </div>
        </div>
        <div>
          <label className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2 block">Niveau</label>
          <select data-testid="filter-level" value={draft.level} onChange={(e) => setDraftKey("level", e.target.value)} className="w-full rounded-xl border border-slate-200 dark:border-slate-700 px-3 h-10 text-sm bg-white dark:bg-slate-800">
            <option value="">Tous niveaux</option>
            {DIPLOMA_LEVELS.map(d => <option key={d} value={d}>{d}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2 block">Domaine / secteur</label>
          <Input data-testid="filter-domain" value={draft.domain} onChange={(e) => setDraftKey("domain", e.target.value)} placeholder="Informatique..." className="rounded-xl" />
        </div>
        <div>
          <label className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2 block">Source</label>
          <select data-testid="filter-source" value={draft.source} onChange={(e) => setDraftKey("source", e.target.value)} className="w-full rounded-xl border border-slate-200 dark:border-slate-700 px-3 h-10 text-sm bg-white dark:bg-slate-800">
            <option value="">Toutes</option>
            {SOURCES.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
          </select>
        </div>

        {/* Europe */}
        <div className="bg-gradient-to-br from-emerald-50 to-blue-50 dark:from-emerald-950/30 dark:to-blue-950/30 rounded-xl p-4 -mx-2" data-testid="europe-section">
          <label className="text-xs font-bold uppercase tracking-wider text-emerald-700 dark:text-emerald-300 mb-2 block flex items-center gap-1">
            🇪🇺 Pays européens
          </label>
          <label className="flex items-center gap-2 cursor-pointer text-sm" data-testid="filter-european-only">
            <input type="checkbox" checked={draft.european}
                   onChange={(e) => setDraft(d => ({ ...d, european: e.target.checked, country: e.target.checked ? d.country : "" }))}
                   className="accent-emerald-600" />
            <span>Voir uniquement les offres hors France</span>
          </label>
          {draft.european && (
            <div className="mt-2">
              <select value={draft.country} onChange={(e) => setDraftKey("country", e.target.value)}
                      className="w-full rounded-xl border-0 bg-white dark:bg-slate-800 px-3 h-9 text-sm"
                      data-testid="filter-country">
                <option value="">Tous les pays UE</option>
                <option value="Belgique">Belgique</option>
                <option value="Suisse">Suisse</option>
                <option value="Luxembourg">Luxembourg</option>
                <option value="Allemagne">Allemagne / Germany</option>
                <option value="Espagne">Espagne / Spain</option>
                <option value="Italie">Italie / Italy</option>
                <option value="Royaume-Uni">Royaume-Uni / UK</option>
                <option value="Pays-Bas">Pays-Bas / Netherlands</option>
                <option value="Portugal">Portugal</option>
                <option value="Irlande">Irlande / Ireland</option>
                <option value="Autriche">Autriche / Austria</option>
                <option value="Pologne">Pologne / Poland</option>
              </select>
            </div>
          )}
          {!draft.european && (
            <div className="text-[10px] text-emerald-700 dark:text-emerald-300 mt-2 leading-snug">
              ✓ Par défaut, seules les offres en <b>France</b> sont affichées
            </div>
          )}
        </div>

        {/* Rayon */}
        <div className="bg-gradient-to-br from-blue-50 to-violet-50 dark:from-blue-950/30 dark:to-violet-950/30 rounded-xl p-4 -mx-2">
          <label className="text-xs font-bold uppercase tracking-wider text-violet-700 dark:text-violet-300 mb-2 block">Rayon autour d&apos;une ville</label>
          <select value={draft.near_city} onChange={(e) => setDraftKey("near_city", e.target.value)} className="w-full rounded-xl border-0 bg-white dark:bg-slate-800 px-3 h-10 text-sm" data-testid="filter-near-city">
            <option value="">Aucun</option>
            {cityList.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
          {draft.near_city && (
            <div className="mt-2">
              <label className="text-[10px] font-semibold text-slate-500">Distance: {draft.distance_km} km</label>
              <input type="range" min="10" max="300" step="10" value={draft.distance_km} onChange={(e) => setDraftKey("distance_km", e.target.value)} className="w-full accent-violet-600" data-testid="filter-distance" />
            </div>
          )}
        </div>

        <label className="flex items-center gap-2 cursor-pointer bg-amber-50 dark:bg-amber-950/30 -mx-2 px-3 py-2 rounded-xl" data-testid="filter-lba">
          <input type="checkbox" checked={draft.lba} onChange={(e) => setDraftKey("lba", e.target.checked)} className="accent-amber-600" />
          <div>
            <div className="text-sm font-bold text-amber-900 dark:text-amber-200">Inclure La Bonne Alternance</div>
            <div className="text-[10px] text-amber-700 dark:text-amber-300">Offres officielles gouv (alternance)</div>
          </div>
        </label>
        <label className="flex items-center gap-2 cursor-pointer" data-testid="filter-remote">
          <Checkbox checked={draft.remote} onCheckedChange={(v) => setDraftKey("remote", !!v)} />
          <span className="text-sm font-medium">Télétravail possible</span>
        </label>

        {/* Submit / Reset buttons */}
        <div className="sticky bottom-0 -mx-6 -mb-6 px-6 py-4 bg-white/95 dark:bg-slate-900/95 border-t border-slate-100 dark:border-slate-800 backdrop-blur rounded-b-2xl">
          <div className="flex gap-2">
            <Button type="submit" disabled={loading} className="rounded-full bg-blue-600 hover:bg-blue-700 text-white flex-1 h-11" data-testid="apply-filters-btn">
              {loading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Search className="w-4 h-4 mr-2" />}
              Rechercher
            </Button>
            <Button type="button" variant="outline" onClick={resetFilters} className="rounded-full h-11" data-testid="reset-filters-btn">
              <RotateCcw className="w-4 h-4" />
            </Button>
          </div>
          <div className="text-[11px] text-slate-500 mt-2 text-center" data-testid="filters-hint">
            Sélectionnez vos critères puis cliquez sur <b>Rechercher</b>
          </div>
        </div>

        {active.region && (
          <div className="bg-blue-50 dark:bg-blue-950/30 rounded-xl p-3 flex items-center justify-between">
            <div className="text-sm font-semibold text-blue-700 dark:text-blue-300 truncate">{active.region}</div>
            <button type="button" onClick={() => { const p = new URLSearchParams(params); p.delete("region"); setParams(p); }} data-testid="clear-region"><X className="w-4 h-4 text-blue-700" /></button>
          </div>
        )}
      </form>
    </aside>
  );

  const Map = () => (
    <div className="card-soft p-5 mb-6">
      <h3 className="font-bold text-slate-900 dark:text-slate-100 mb-3">Filtrer par région</h3>
      <div className="flex flex-wrap gap-2">
        {REGIONS_LIST.map(r => (
          <button
            key={r}
            onClick={() => {
              const p = new URLSearchParams(params);
              if (active.region === r) p.delete("region"); else p.set("region", r);
              setParams(p);
            }}
            className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-all ${active.region === r ? "bg-blue-600 text-white" : "bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700"}`}
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
        <div className="text-center py-12 text-slate-400 flex flex-col items-center gap-2" data-testid="results-loading">
          <Loader2 className="w-6 h-6 animate-spin" />
          Recherche en cours…
        </div>
      ) : offers.length === 0 ? (
        <div className="card-soft p-12 text-center" data-testid="results-empty">
          <div className="text-slate-400 mb-2">Aucune offre trouvée</div>
          <p className="text-xs text-slate-500 mb-3">Essayez d&apos;élargir le rayon ou de retirer un filtre.</p>
          <Button variant="outline" onClick={resetFilters} className="rounded-full mt-2">Réinitialiser les filtres</Button>
        </div>
      ) : (
        <div className="grid sm:grid-cols-2 gap-4">
          {offers.map(o => <OfferCard key={o.offer_id} offer={o} />)}
        </div>
      )}
    </div>
  );

  return (
    <div className="min-h-screen pt-20 pb-12 bg-slate-50 dark:bg-slate-900">
      <div className="max-w-7xl mx-auto px-4 sm:px-6">
        <h1 className="text-3xl font-black tracking-tight text-slate-900 dark:text-slate-100 mb-2">Offres de stage & alternance</h1>
        <p className="text-slate-500 mb-4" data-testid="results-count">
          {loading ? "Chargement…" : (
            <><b className="text-slate-700 dark:text-slate-300">{offers.length}</b> offre{offers.length > 1 ? "s" : ""} trouvée{offers.length > 1 ? "s" : ""} · Sources multiples agrégées</>
          )}
        </p>

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
