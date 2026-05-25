import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../lib/api";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Sparkles, Loader2 } from "lucide-react";
import { toast } from "sonner";

const EXAMPLES = [
  "Stage en informatique autour de Lyon pour juin",
  "Alternance BTS SIO proche de Valence",
  "Stage en communication à Bordeaux",
];

export default function AISearchBar({ onCriteria }) {
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [criteria, setCriteria] = useState(null);
  const navigate = useNavigate();

  const submit = async () => {
    if (!query.trim()) return;
    setBusy(true);
    try {
      const { data } = await api.post("/ai/search", { query });
      const c = data.criteria || {};
      setCriteria(c);
      if (onCriteria) onCriteria(c, query);
      // Log to search history
      try {
        await api.post("/me/search-history", {
          search_type: c.intent === "companies" ? "companies" : c.intent === "students" ? "students" : "offers",
          query_text: query,
          filters: c,
          ai_generated: true,
        });
      } catch { /* ignore */ }
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erreur IA");
    } finally { setBusy(false); }
  };

  const applyToOffers = () => {
    const p = new URLSearchParams();
    if (criteria?.city) p.set("city", criteria.city);
    if (criteria?.contract_type) p.set("type", criteria.contract_type);
    if (criteria?.keywords) p.set("q", criteria.keywords);
    navigate(`/offers?${p.toString()}`);
  };
  const applyToCompanies = () => {
    const p = new URLSearchParams();
    if (criteria?.city) p.set("q", criteria.city);
    else if (criteria?.keywords) p.set("q", criteria.keywords);
    if (criteria?.naf_code) p.set("activite_principale", criteria.naf_code);
    navigate(`/companies?${p.toString()}`);
  };

  return (
    <div className="card-soft p-5 mb-6" data-testid="ai-search-bar">
      <div className="flex items-center gap-2 mb-2">
        <Sparkles className="w-4 h-4 text-violet-500" />
        <span className="font-bold text-slate-900">Recherche intelligente</span>
        <span className="text-xs text-slate-400">— décrivez ce que vous cherchez en français</span>
      </div>
      <div className="flex gap-2">
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") submit(); }}
          placeholder="Ex: stage en informatique autour de Lyon pour juin"
          className="rounded-xl flex-1"
          data-testid="ai-search-input"
        />
        <Button onClick={submit} disabled={busy || !query.trim()} className="rounded-full bg-violet-600 hover:bg-violet-700" data-testid="ai-search-submit">
          {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4 mr-1" />}
          {busy ? "Analyse..." : "Rechercher"}
        </Button>
      </div>
      <div className="flex flex-wrap gap-1.5 mt-2">
        {EXAMPLES.map(ex => (
          <button key={ex} onClick={() => { setQuery(ex); }} className="text-[11px] bg-violet-50 text-violet-700 rounded-full px-2.5 py-1 hover:bg-violet-100">
            « {ex} »
          </button>
        ))}
      </div>

      {criteria && (
        <div className="mt-3 bg-violet-50 rounded-2xl p-4" data-testid="ai-search-criteria">
          <div className="text-xs font-semibold text-violet-900 mb-2">Critères compris :</div>
          <div className="flex flex-wrap gap-1.5 mb-3 text-xs">
            {criteria.intent && <Chip>Type: {criteria.intent}</Chip>}
            {criteria.contract_type && <Chip>{criteria.contract_type}</Chip>}
            {criteria.domain && <Chip>{criteria.domain}</Chip>}
            {criteria.city && <Chip>📍 {criteria.city}</Chip>}
            {criteria.region && <Chip>{criteria.region}</Chip>}
            {criteria.department && <Chip>Dpt {criteria.department}</Chip>}
            {criteria.naf_code && <Chip>NAF {criteria.naf_code}</Chip>}
            {(criteria.skills || []).map(s => <Chip key={s}>{s}</Chip>)}
          </div>
          <div className="flex gap-2 flex-wrap">
            <Button size="sm" onClick={applyToOffers} className="rounded-full bg-blue-600 hover:bg-blue-700" data-testid="ai-apply-offers">Voir les offres</Button>
            <Button size="sm" variant="outline" onClick={applyToCompanies} className="rounded-full" data-testid="ai-apply-companies">Voir les entreprises</Button>
          </div>
        </div>
      )}
    </div>
  );
}

const Chip = ({ children }) => <span className="bg-white text-violet-700 rounded-full px-2 py-0.5 text-[11px] font-semibold border border-violet-200">{children}</span>;
