import React, { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import api from "../lib/api";
import OfferCard from "../components/OfferCard";
import FranceMap from "../components/FranceMap";
import { Search, Filter, X } from "lucide-react";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Checkbox } from "../components/ui/checkbox";

export default function OffersPage() {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const [offers, setOffers] = useState([]);
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(true);

  const q = params.get("q") || "";
  const region = params.get("region") || "";
  const city = params.get("city") || "";
  const ct = params.get("contract_type") || "";
  const domain = params.get("domain") || "";
  const level = params.get("level") || "";
  const remote = params.get("remote") === "true";

  useEffect(() => {
    api.get("/offers/regions").then((r) => setStats(r.data)).catch(() => {});
  }, []);

  useEffect(() => {
    setLoading(true);
    const p = new URLSearchParams();
    if (q) p.set("q", q);
    if (region) p.set("region", region);
    if (city) p.set("city", city);
    if (ct) p.set("contract_type", ct);
    if (domain) p.set("domain", domain);
    if (level) p.set("level", level);
    if (remote) p.set("remote", "true");
    api.get(`/offers?${p.toString()}`).then((r) => setOffers(r.data)).finally(() => setLoading(false));
  }, [q, region, city, ct, domain, level, remote]);

  const updateParam = (k, v) => {
    const p = new URLSearchParams(params);
    if (v) p.set(k, v); else p.delete(k);
    setParams(p);
  };

  const reset = () => setParams({});

  return (
    <div className="min-h-screen pt-20 pb-12 bg-slate-50">
      <div className="max-w-7xl mx-auto px-6">
        <h1 className="text-3xl font-black tracking-tight text-slate-900 mb-2">Offres de stage & alternance</h1>
        <p className="text-slate-500 mb-6">{offers.length} offres correspondant à votre recherche</p>

        <div className="grid lg:grid-cols-[280px_1fr] gap-6">
          {/* Sidebar Filters */}
          <aside className="card-soft p-6 h-fit sticky top-20">
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
                  {[
                    { val: "", label: "Tous" },
                    { val: "stage", label: "Stage" },
                    { val: "alternance", label: "Alternance" },
                  ].map(o => (
                    <label key={o.val} className="flex items-center gap-2 cursor-pointer text-sm" data-testid={`filter-ct-${o.val || "all"}`}>
                      <input type="radio" checked={ct === o.val} onChange={() => updateParam("contract_type", o.val)} className="accent-blue-600" />
                      {o.label}
                    </label>
                  ))}
                </div>
              </div>

              <div>
                <label className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2 block">Niveau</label>
                <select data-testid="filter-level" value={level} onChange={(e) => updateParam("level", e.target.value)} className="w-full rounded-xl border border-slate-200 px-3 h-10 text-sm bg-white">
                  <option value="">Tous</option>
                  <option value="Bac+2">Bac+2</option>
                  <option value="Bac+3">Bac+3</option>
                  <option value="Bac+5">Bac+5</option>
                </select>
              </div>

              <div>
                <label className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2 block">Domaine</label>
                <Input data-testid="filter-domain" value={domain} onChange={(e) => updateParam("domain", e.target.value)} placeholder="Informatique..." className="rounded-xl" />
              </div>

              <label className="flex items-center gap-2 cursor-pointer" data-testid="filter-remote">
                <Checkbox checked={remote} onCheckedChange={(v) => updateParam("remote", v ? "true" : "")} />
                <span className="text-sm font-medium">Télétravail possible</span>
              </label>

              {region && (
                <div className="bg-blue-50 rounded-xl p-3 flex items-center justify-between">
                  <div className="text-sm font-semibold text-blue-700">{region}</div>
                  <button onClick={() => updateParam("region", "")} data-testid="clear-region"><X className="w-4 h-4 text-blue-700" /></button>
                </div>
              )}
            </div>
          </aside>

          {/* Map + results */}
          <div>
            <div className="card-soft p-4 mb-6">
              <FranceMap stats={stats} selected={region} onSelect={(r) => updateParam("region", r)} />
            </div>

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
        </div>
      </div>
    </div>
  );
}
