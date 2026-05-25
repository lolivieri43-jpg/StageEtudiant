import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Badge } from "../components/ui/badge";
import { Search, MapPin, Building2, Hash, Globe, Plus, ExternalLink, Loader2 } from "lucide-react";
import { toast } from "sonner";
import AISearchBar from "../components/AISearchBar";

const REGIONS = [
  { code: "11", name: "Île-de-France" }, { code: "84", name: "Auvergne-Rhône-Alpes" },
  { code: "93", name: "Provence-Alpes-Côte d'Azur" }, { code: "76", name: "Occitanie" },
  { code: "75", name: "Nouvelle-Aquitaine" }, { code: "32", name: "Hauts-de-France" },
  { code: "44", name: "Grand Est" }, { code: "52", name: "Pays de la Loire" },
  { code: "53", name: "Bretagne" }, { code: "28", name: "Normandie" },
  { code: "27", name: "Bourgogne-Franche-Comté" }, { code: "24", name: "Centre-Val de Loire" },
  { code: "94", name: "Corse" },
];

export default function CompanyDirectoryPage() {
  const { user } = useAuth();
  const [q, setQ] = useState("");
  const [cp, setCp] = useState("");
  const [dep, setDep] = useState("");
  const [region, setRegion] = useState("");
  const [naf, setNaf] = useState("");
  const [results, setResults] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [cacheHit, setCacheHit] = useState(false);
  const [page, setPage] = useState(1);

  const submit = async (e, pageOverride) => {
    if (e?.preventDefault) e.preventDefault();
    const p = pageOverride ?? 1;
    setPage(p);
    if (!q && !cp && !dep && !region && !naf) {
      toast.error("Saisissez au moins un critère");
      return;
    }
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (q) params.set("q", q);
      if (cp) params.set("code_postal", cp);
      if (dep) params.set("departement", dep);
      if (region) params.set("region", region);
      if (naf) params.set("activite_principale", naf);
      params.set("page", p);
      params.set("per_page", 12);
      const { data } = await api.get(`/companies/search?${params.toString()}`);
      setResults(data.results || []);
      setTotal(data.total || 0);
      setCacheHit(!!data.cache_hit);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erreur de recherche");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen pt-20 pb-12 bg-slate-50">
      <div className="max-w-6xl mx-auto px-6">
        <div className="mb-8">
          <h1 className="text-3xl font-black tracking-tight text-slate-900">Trouver des entreprises</h1>
          <p className="text-slate-500 mt-1">Recherchez parmi toutes les entreprises françaises (données officielles INSEE — Annuaire des Entreprises).</p>
        </div>

        <AISearchBar onCriteria={(c, originalQuery) => {
          if (c?.city) setQ(c.city);
          if (c?.naf_code) setNaf(c.naf_code);
          if (c?.keywords && !c?.city) setQ(c.keywords);
        }} />

        <form onSubmit={submit} className="card-soft p-6 mb-6" data-testid="company-search-form">
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            <div>
              <Label>Nom, SIREN, SIRET ou activité</Label>
              <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="ex: Décathlon, 552120222..." className="rounded-xl mt-1" data-testid="cs-q" />
            </div>
            <div>
              <Label>Code postal</Label>
              <Input value={cp} onChange={(e) => setCp(e.target.value)} placeholder="69003" maxLength={5} className="rounded-xl mt-1" data-testid="cs-cp" />
            </div>
            <div>
              <Label>Département</Label>
              <Input value={dep} onChange={(e) => setDep(e.target.value)} placeholder="69" maxLength={3} className="rounded-xl mt-1" data-testid="cs-dep" />
            </div>
            <div>
              <Label>Région</Label>
              <select value={region} onChange={(e) => setRegion(e.target.value)} className="w-full rounded-xl border border-slate-200 h-10 px-3 mt-1 bg-white" data-testid="cs-region">
                <option value="">Toutes</option>
                {REGIONS.map(r => <option key={r.code} value={r.code}>{r.name}</option>)}
              </select>
            </div>
            <div>
              <Label>Code NAF / APE</Label>
              <Input value={naf} onChange={(e) => setNaf(e.target.value)} placeholder="62.01Z" className="rounded-xl mt-1" data-testid="cs-naf" />
            </div>
            <div className="flex items-end">
              <Button type="submit" disabled={loading} className="w-full rounded-full bg-blue-600 hover:bg-blue-700" data-testid="cs-submit">
                {loading ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Search className="w-4 h-4 mr-1" />}
                {loading ? "Recherche..." : "Rechercher"}
              </Button>
            </div>
          </div>
        </form>

        {total > 0 && (
          <div className="flex items-center justify-between mb-4 text-sm text-slate-500">
            <div data-testid="cs-results-count">
              {total.toLocaleString("fr-FR")} entreprise{total > 1 ? "s" : ""} trouvée{total > 1 ? "s" : ""}
              {cacheHit && <Badge className="ml-2 rounded-full bg-emerald-50 text-emerald-700 border-0 text-[10px]">Cache</Badge>}
            </div>
            <div className="text-xs">Page {page}</div>
          </div>
        )}

        <div className="grid sm:grid-cols-2 gap-4" data-testid="cs-results">
          {results.map((c) => (
            <ExternalCompanyCard key={c.siret || c.siren} company={c} canSave={!!user && user.role === "candidate"} />
          ))}
        </div>

        {results.length === 0 && !loading && (
          <div className="card-soft p-12 text-center text-slate-400">
            <Building2 className="w-10 h-10 mx-auto mb-3 text-slate-300" />
            <div>Lancez une recherche pour découvrir des entreprises</div>
          </div>
        )}

        {results.length > 0 && results.length === 12 && (
          <div className="flex justify-center gap-2 mt-6">
            {page > 1 && <Button variant="outline" onClick={() => submit(null, page - 1)} className="rounded-full">Précédent</Button>}
            <Button onClick={() => submit(null, page + 1)} className="rounded-full bg-blue-600 hover:bg-blue-700">Suivant</Button>
          </div>
        )}
      </div>
    </div>
  );
}

function ExternalCompanyCard({ company: c, canSave }) {
  const [added, setAdded] = useState(false);
  const addToList = async () => {
    try {
      await api.post("/me/companies", c);
      setAdded(true);
      toast.success("Ajoutée à votre liste");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erreur");
    }
  };
  const addr = [c.address, c.postal_code, c.city].filter(Boolean).join(", ");
  return (
    <div className="card-soft p-5 hover-lift" data-testid={`cs-card-${c.siret}`}>
      <div className="flex items-start gap-3 mb-2">
        <div className="w-10 h-10 rounded-xl bg-blue-50 grid place-items-center shrink-0">
          <Building2 className="w-5 h-5 text-blue-600" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="font-bold text-slate-900 truncate" title={c.name}>{c.name}</div>
          {c.region && <div className="text-xs text-slate-500 truncate">{c.region}</div>}
        </div>
        {c.active === false && <Badge className="rounded-full bg-rose-50 text-rose-700 border-0 text-[10px]">Fermée</Badge>}
        {c.active && <Badge className="rounded-full bg-emerald-50 text-emerald-700 border-0 text-[10px]">Active</Badge>}
      </div>
      <div className="text-sm space-y-1 mb-3">
        {addr && <div className="flex items-start gap-2 text-slate-700"><MapPin className="w-3.5 h-3.5 mt-0.5 text-slate-400 shrink-0" />{addr}</div>}
        {c.naf_code && <div className="flex items-center gap-2 text-slate-500 text-xs"><Hash className="w-3.5 h-3.5" />NAF {c.naf_code}</div>}
        {c.siret && <div className="text-xs text-slate-400">SIRET {c.siret}</div>}
      </div>
      <div className="flex flex-wrap gap-2">
        {canSave && !added && (
          <Button size="sm" onClick={addToList} className="rounded-full bg-blue-600 hover:bg-blue-700" data-testid={`cs-save-${c.siret}`}>
            <Plus className="w-3.5 h-3.5 mr-1" />Ajouter à ma liste
          </Button>
        )}
        {added && <Badge className="rounded-full bg-emerald-50 text-emerald-700 border-0">✓ Dans ma liste</Badge>}
        {c.siret && (
          <a href={`https://annuaire-entreprises.data.gouv.fr/entreprise/${c.siret}`} target="_blank" rel="noopener" className="inline-flex items-center text-xs text-slate-500 hover:text-blue-600 gap-1" data-testid={`cs-ext-${c.siret}`}>
            <Globe className="w-3 h-3" />Voir sur l'Annuaire <ExternalLink className="w-2.5 h-2.5" />
          </a>
        )}
      </div>
    </div>
  );
}
