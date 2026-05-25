import React, { useState } from "react";
import api from "../lib/api";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Search, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";

/**
 * SIRET / SIREN / name lookup against the public Annuaire API.
 * Returns selected normalized company to the parent via `onSelect(company)`.
 */
export default function SiretLookup({ onSelect, defaultQuery = "" }) {
  const [q, setQ] = useState(defaultQuery);
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const search = async (e) => {
    if (e?.preventDefault) e.preventDefault();
    if (!q.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const { data } = await api.get(`/companies/search?q=${encodeURIComponent(q)}&per_page=8`);
      setResults(data.results || []);
      if (!data.results?.length) setError("Aucun résultat — vérifiez l'orthographe ou le SIRET.");
    } catch (err) {
      setError(err.response?.data?.detail || "Erreur de recherche");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-3" data-testid="siret-lookup">
      <form onSubmit={search} className="flex gap-2">
        <Input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Nom de l'entreprise ou SIRET (14 chiffres)"
          className="rounded-xl flex-1"
          data-testid="siret-lookup-input"
        />
        <Button type="submit" disabled={loading || !q.trim()} className="rounded-full bg-blue-600 hover:bg-blue-700" data-testid="siret-lookup-search">
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
        </Button>
      </form>

      {error && (
        <div className="flex items-center gap-2 text-xs text-amber-700 bg-amber-50 rounded-xl px-3 py-2">
          <AlertCircle className="w-3.5 h-3.5" />{error}
        </div>
      )}

      {results.length > 0 && (
        <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
          {results.map(c => (
            <button
              type="button"
              key={c.siret || c.siren}
              onClick={() => { onSelect && onSelect(c); setResults([]); setQ(c.name || ""); }}
              className="w-full text-left p-3 rounded-xl border border-slate-200 hover:border-blue-400 hover:bg-blue-50 transition"
              data-testid={`siret-pick-${c.siret || c.siren}`}
            >
              <div className="flex items-start gap-2">
                <CheckCircle2 className="w-4 h-4 text-blue-500 mt-0.5 shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="font-semibold text-slate-900 text-sm truncate">{c.name}</div>
                  <div className="text-xs text-slate-500 truncate">{[c.city, c.postal_code, c.naf_code].filter(Boolean).join(" · ")}</div>
                  {c.siret && <div className="text-[10px] text-slate-400 font-mono">SIRET {c.siret}</div>}
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
