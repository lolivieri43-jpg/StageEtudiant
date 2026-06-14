import React from "react";
import { Search, Filter, X, Loader2, RotateCcw } from "lucide-react";
import { Input } from "../ui/input";
import { Button } from "../ui/button";
import { Checkbox } from "../ui/checkbox";
import { DIPLOMA_LEVELS } from "../../lib/diplomas";
import { SOURCES } from "../../lib/offerFilters";

/**
 * Sticky left-rail filter form for the Offers page.
 *
 * Props:
 * - draft, setDraft : controlled state owned by parent
 * - loading         : bool, disables the submit button while fetching
 * - active          : currently-applied filters (from URL) — used for the small
 *                     "selected region" chip below the form
 * - cityList        : array of FR cities for the radius selector
 * - onApply(e)      : called on form submit
 * - onReset()       : clears draft + URL params
 * - onClearRegion() : removes the region from active params
 */
export default function OffersFiltersSidebar({
  draft, setDraft, loading, active, cityList,
  onApply, onReset, onClearRegion,
}) {
  const setKey = (k, v) => setDraft(d => ({ ...d, [k]: v }));

  return (
    <aside className="card-soft p-6 h-fit lg:sticky lg:top-20" data-testid="filters-sidebar">
      <form onSubmit={onApply} className="space-y-5">
        <div className="flex items-center justify-between">
          <h2 className="font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <Filter className="w-4 h-4" />Filtres
          </h2>
          <button type="button" onClick={onReset} className="text-xs text-blue-600 font-semibold inline-flex items-center gap-1" data-testid="filters-reset">
            <RotateCcw className="w-3 h-3" />Réinitialiser
          </button>
        </div>

        <div>
          <label className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2 block">Recherche</label>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <Input data-testid="filter-query" value={draft.q} onChange={(e) => setKey("q", e.target.value)} placeholder="Métier, mot-clé..." className="rounded-xl pl-9" />
          </div>
        </div>

        <div>
          <label className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2 block">Ville</label>
          <Input data-testid="filter-city" value={draft.city} onChange={(e) => setKey("city", e.target.value)} placeholder="Paris, Lyon..." className="rounded-xl" />
        </div>

        <div>
          <label className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2 block">Entreprise précise</label>
          <Input data-testid="filter-company" value={draft.company} onChange={(e) => setKey("company", e.target.value)} placeholder="Ex: Sofratom, EDF, SNCF…" className="rounded-xl" />
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
                <input type="radio" name="contract_type" checked={draft.contract_type === o.val} onChange={() => setKey("contract_type", o.val)} className="accent-blue-600" />{o.label}
              </label>
            ))}
          </div>
        </div>

        <div>
          <label className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2 block">Niveau</label>
          <select data-testid="filter-level" value={draft.level} onChange={(e) => setKey("level", e.target.value)} className="w-full rounded-xl border border-slate-200 dark:border-slate-700 px-3 h-10 text-sm bg-white dark:bg-slate-800">
            <option value="">Tous niveaux</option>
            {DIPLOMA_LEVELS.map(d => <option key={d} value={d}>{d}</option>)}
          </select>
        </div>

        <div>
          <label className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2 block">Domaine / secteur</label>
          <Input data-testid="filter-domain" value={draft.domain} onChange={(e) => setKey("domain", e.target.value)} placeholder="Informatique..." className="rounded-xl" />
        </div>

        <div>
          <label className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2 block">Source</label>
          <select data-testid="filter-source" value={draft.source} onChange={(e) => setKey("source", e.target.value)} className="w-full rounded-xl border border-slate-200 dark:border-slate-700 px-3 h-10 text-sm bg-white dark:bg-slate-800">
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
              <select value={draft.country} onChange={(e) => setKey("country", e.target.value)}
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
          <select value={draft.near_city} onChange={(e) => setKey("near_city", e.target.value)} className="w-full rounded-xl border-0 bg-white dark:bg-slate-800 px-3 h-10 text-sm" data-testid="filter-near-city">
            <option value="">Aucun</option>
            {cityList.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
          {draft.near_city && (
            <div className="mt-2">
              <label className="text-[10px] font-semibold text-slate-500">Distance: {draft.distance_km} km</label>
              <input type="range" min="10" max="300" step="10" value={draft.distance_km} onChange={(e) => setKey("distance_km", e.target.value)} className="w-full accent-violet-600" data-testid="filter-distance" />
            </div>
          )}
        </div>

        <label className="flex items-center gap-2 cursor-pointer bg-amber-50 dark:bg-amber-950/30 -mx-2 px-3 py-2 rounded-xl" data-testid="filter-lba">
          <input type="checkbox" checked={draft.lba} onChange={(e) => setKey("lba", e.target.checked)} className="accent-amber-600" />
          <div>
            <div className="text-sm font-bold text-amber-900 dark:text-amber-200">Inclure La Bonne Alternance</div>
            <div className="text-[10px] text-amber-700 dark:text-amber-300">Offres officielles gouv (alternance)</div>
          </div>
        </label>
        <label className="flex items-center gap-2 cursor-pointer" data-testid="filter-remote">
          <Checkbox checked={draft.remote} onCheckedChange={(v) => setKey("remote", !!v)} />
          <span className="text-sm font-medium">Télétravail possible</span>
        </label>

        {/* Submit / Reset buttons */}
        <div className="sticky bottom-0 -mx-6 -mb-6 px-6 py-4 bg-white/95 dark:bg-slate-900/95 border-t border-slate-100 dark:border-slate-800 backdrop-blur rounded-b-2xl">
          <div className="flex gap-2">
            <Button type="submit" disabled={loading} className="rounded-full bg-blue-600 hover:bg-blue-700 text-white flex-1 h-11" data-testid="apply-filters-btn">
              {loading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Search className="w-4 h-4 mr-2" />}
              Rechercher
            </Button>
            <Button type="button" variant="outline" onClick={onReset} className="rounded-full h-11" data-testid="reset-filters-btn">
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
            <button type="button" onClick={onClearRegion} data-testid="clear-region"><X className="w-4 h-4 text-blue-700" /></button>
          </div>
        )}
      </form>
    </aside>
  );
}
