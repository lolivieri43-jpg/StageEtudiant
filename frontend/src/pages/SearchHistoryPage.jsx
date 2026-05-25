import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Button } from "../components/ui/button";
import { Trash2, History, Sparkles, Search } from "lucide-react";
import { toast } from "sonner";
import { formatDistanceToNow } from "date-fns";
import { fr } from "date-fns/locale";

export default function SearchHistoryPage() {
  const { user, refresh } = useAuth();
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const disabled = !!user?.history_disabled;

  const load = async () => {
    const { data } = await api.get("/me/search-history");
    setItems(data);
  };
  useEffect(() => { load(); }, []);

  const del = async (id) => {
    await api.delete(`/me/search-history/${id}`);
    load();
  };
  const clearAll = async () => {
    if (!window.confirm("Effacer tout l'historique ?")) return;
    await api.delete("/me/search-history");
    load();
    toast.success("Historique vidé");
  };
  const setDisabled = async (val) => {
    await api.patch("/me/history-settings", { history_disabled: val });
    refresh && refresh();
    toast.success(val ? "Historique désactivé" : "Historique activé");
  };
  const relaunch = (it) => {
    if (it.search_type === "offers") navigate(`/offers?q=${encodeURIComponent(it.query_text || "")}`);
    else if (it.search_type === "companies") navigate(`/companies`);
    else navigate(`/offers?q=${encodeURIComponent(it.query_text || "")}`);
  };

  return (
    <div className="min-h-screen pt-20 pb-12 bg-slate-50">
      <div className="max-w-3xl mx-auto px-6">
        <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
          <div>
            <h1 className="text-3xl font-black tracking-tight text-slate-900 flex items-center gap-2"><History className="w-7 h-7 text-blue-500" />Mon historique de recherche</h1>
            <p className="text-slate-500">Retrouvez et relancez vos recherches passées</p>
          </div>
          <div className="flex gap-2">
            <Button onClick={() => setDisabled(!disabled)} variant="outline" className="rounded-full" data-testid="toggle-history">
              {disabled ? "Réactiver" : "Désactiver"}
            </Button>
            <Button onClick={clearAll} variant="outline" className="rounded-full text-rose-600 border-rose-200" data-testid="clear-history"><Trash2 className="w-4 h-4 mr-1" />Tout effacer</Button>
          </div>
        </div>

        {disabled && (
          <div className="card-soft p-4 bg-amber-50 text-sm text-amber-800 mb-4">
            L'enregistrement de l'historique est désactivé. Les nouvelles recherches ne seront pas sauvegardées.
          </div>
        )}

        {items.length === 0 && (
          <div className="card-soft p-12 text-center text-slate-400">
            <History className="w-10 h-10 mx-auto mb-3 text-slate-300" />
            Aucune recherche enregistrée
          </div>
        )}

        <div className="space-y-2">
          {items.map(it => (
            <div key={it.id} className="card-soft p-4 flex items-center gap-3 flex-wrap" data-testid={`sh-row-${it.id}`}>
              <div className="w-9 h-9 rounded-xl bg-blue-50 grid place-items-center shrink-0">
                {it.ai_generated ? <Sparkles className="w-4 h-4 text-violet-500" /> : <Search className="w-4 h-4 text-blue-500" />}
              </div>
              <div className="flex-1 min-w-0">
                <div className="font-semibold text-slate-900 truncate">{it.query_text || "(sans texte)"}</div>
                <div className="text-xs text-slate-500">{it.search_type} · {it.results_count} résultats · {formatDistanceToNow(new Date(it.created_at), { locale: fr, addSuffix: true })}</div>
              </div>
              <Button onClick={() => relaunch(it)} variant="outline" size="sm" className="rounded-full" data-testid={`sh-rerun-${it.id}`}>Relancer</Button>
              <Button onClick={() => del(it.id)} variant="outline" size="icon" className="rounded-full text-rose-600 border-rose-200" data-testid={`sh-del-${it.id}`}><Trash2 className="w-4 h-4" /></Button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
