import React, { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { Check, X, Pause, Play, Trash2, ExternalLink, Search, RefreshCw, AlertCircle } from "lucide-react";
import { toast } from "sonner";

const STATUSES = [
  { id: "pending", label: "En attente", color: "bg-amber-100 text-amber-700" },
  { id: "published", label: "Validés", color: "bg-emerald-100 text-emerald-700" },
  { id: "refused", label: "Refusés", color: "bg-rose-100 text-rose-700" },
  { id: "suspended", label: "Suspendus", color: "bg-orange-100 text-orange-700" },
  { id: "draft", label: "Brouillons", color: "bg-slate-100 text-slate-600" },
  { id: "expired", label: "Expirés", color: "bg-slate-100 text-slate-500" },
  { id: "all", label: "Tous", color: "bg-slate-200 text-slate-800" },
];

export default function AdminDealsPage() {
  const { user } = useAuth();
  const [data, setData] = useState({ deals: [], counts: {} });
  const [status, setStatus] = useState("pending");
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const p = new URLSearchParams();
      if (status) p.set("status", status);
      if (q) p.set("q", q);
      const { data } = await api.get(`/admin/deals?${p.toString()}`);
      setData(data);
    } finally {
      setLoading(false);
    }
  }, [status, q]);

  useEffect(() => {
    if (user?.role === "admin") load();
  }, [user, load]);

  const moderate = async (dealId, action, label) => {
    let reason = "";
    if (action === "refuse" || action === "suspend") {
      reason = window.prompt(`Raison du ${label} (optionnel) :`, "") || "";
    }
    try {
      await api.post(`/admin/deals/${dealId}/validate`, { action, reason });
      toast.success(`Bon plan ${label}`);
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Erreur");
    }
  };

  const remove = async (dealId) => {
    if (!window.confirm("Supprimer définitivement ce bon plan ?")) return;
    await api.delete(`/deals/${dealId}`);
    toast.success("Bon plan supprimé");
    load();
  };

  if (user?.role !== "admin") {
    return <div className="pt-24 text-center text-slate-500">Accès admin uniquement.</div>;
  }

  return (
    <div className="min-h-screen pt-20 pb-12 bg-slate-50">
      <div className="max-w-7xl mx-auto px-6">
        <div className="flex items-end justify-between mb-6 flex-wrap gap-3">
          <div>
            <h1 className="text-3xl font-black tracking-tight text-slate-900">Modération des bons plans</h1>
            <p className="text-slate-500 mt-1">Validez, refusez, suspendez ou supprimez les bons plans</p>
          </div>
          <div className="flex gap-2">
            <Link to="/admin/ads">
              <Button variant="outline" className="rounded-full" data-testid="goto-admin-ads">Publicités</Button>
            </Link>
            <Button variant="outline" className="rounded-full" onClick={load} disabled={loading} data-testid="refresh-deals">
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            </Button>
          </div>
        </div>

        {/* Status tabs */}
        <div className="flex flex-wrap gap-2 mb-4" data-testid="status-tabs">
          {STATUSES.map(s => (
            <button
              key={s.id}
              onClick={() => setStatus(s.id)}
              data-testid={`tab-${s.id}`}
              className={`px-4 py-1.5 rounded-full text-xs font-bold transition-all flex items-center gap-2 ${
                status === s.id ? "bg-slate-900 text-white" : "bg-white border border-slate-200 text-slate-600 hover:border-slate-300"
              }`}
            >
              {s.label}
              <span className={`px-2 py-0.5 rounded-full text-[10px] ${status === s.id ? "bg-white/20" : s.color}`}>
                {data.counts[s.id] ?? 0}
              </span>
            </button>
          ))}
        </div>

        <div className="card-soft p-3 mb-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <Input value={q} onChange={(e) => setQ(e.target.value)}
              placeholder="Rechercher par titre, description, auteur..."
              className="rounded-full pl-9 bg-slate-50 border-0"
              data-testid="search-deals" />
          </div>
        </div>

        <div className="space-y-3">
          {data.deals.length === 0 && (
            <div className="card-soft p-12 text-center text-slate-500">
              <AlertCircle className="w-10 h-10 mx-auto text-slate-300 mb-3" />
              Aucun bon plan dans cet état
            </div>
          )}
          {data.deals.map(d => (
            <DealRow key={d.deal_id} deal={d} onModerate={moderate} onDelete={remove} />
          ))}
        </div>
      </div>
    </div>
  );
}

const STATUS_BADGE = {
  draft: "bg-slate-100 text-slate-600",
  pending: "bg-amber-100 text-amber-700",
  published: "bg-emerald-100 text-emerald-700",
  refused: "bg-rose-100 text-rose-700",
  suspended: "bg-orange-100 text-orange-700",
  expired: "bg-slate-100 text-slate-500",
};

function DealRow({ deal: d, onModerate, onDelete }) {
  return (
    <div className="card-soft p-4 flex items-start gap-3" data-testid={`deal-row-${d.deal_id}`}>
      <div className="w-14 h-14 rounded-xl overflow-hidden bg-gradient-to-br from-violet-100 to-blue-100 grid place-items-center font-bold text-violet-600 shrink-0">
        {d.image ? <img src={d.image} alt="" className="w-full h-full object-cover" /> : (d.author_name?.[0] || "?")}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-bold">{d.title}</span>
          <Badge className={`border-0 rounded-full text-[10px] ${STATUS_BADGE[d.status] || "bg-slate-100"}`}>
            {d.status}
          </Badge>
          {d.discount && <Badge className="border-0 rounded-full text-[10px] bg-violet-100 text-violet-700">{d.discount}</Badge>}
        </div>
        <div className="text-xs text-slate-500 line-clamp-2 mt-1">{d.description}</div>
        <div className="text-[11px] text-slate-400 mt-1 flex flex-wrap gap-2">
          <span>par {d.author_name}</span>
          {d.author_type && <span>· {d.author_type === "company" ? "entreprise" : "étudiant"}</span>}
          {d.city && <span>· {d.city}</span>}
          {d.category && <span>· {d.category}</span>}
          <span>· {(d.created_at || "").slice(0, 10)}</span>
        </div>
        {d.moderation_reason && (
          <div className="text-[11px] text-rose-600 mt-1">Modération : {d.moderation_reason}</div>
        )}
      </div>
      <div className="flex items-center gap-1 shrink-0">
        <Link to={`/deals/${d.deal_id}`} target="_blank" rel="noreferrer">
          <Button size="sm" variant="outline" className="rounded-full" data-testid={`view-${d.deal_id}`} title="Voir">
            <ExternalLink className="w-4 h-4" />
          </Button>
        </Link>
        {d.status !== "published" && (
          <Button size="sm" className="rounded-full bg-emerald-600 hover:bg-emerald-700" onClick={() => onModerate(d.deal_id, "approve", "validé")} data-testid={`approve-${d.deal_id}`} title="Valider">
            <Check className="w-4 h-4" />
          </Button>
        )}
        {d.status !== "refused" && (
          <Button size="sm" variant="outline" className="rounded-full" onClick={() => onModerate(d.deal_id, "refuse", "refusé")} data-testid={`refuse-${d.deal_id}`} title="Refuser">
            <X className="w-4 h-4" />
          </Button>
        )}
        {d.status === "published" && (
          <Button size="sm" variant="outline" className="rounded-full text-orange-600 border-orange-200" onClick={() => onModerate(d.deal_id, "suspend", "suspendu")} data-testid={`suspend-${d.deal_id}`} title="Suspendre">
            <Pause className="w-4 h-4" />
          </Button>
        )}
        {d.status === "suspended" && (
          <Button size="sm" variant="outline" className="rounded-full text-emerald-600 border-emerald-200" onClick={() => onModerate(d.deal_id, "reactivate", "réactivé")} data-testid={`reactivate-${d.deal_id}`} title="Réactiver">
            <Play className="w-4 h-4" />
          </Button>
        )}
        <Button size="sm" variant="outline" className="rounded-full text-rose-600 border-rose-200" onClick={() => onDelete(d.deal_id)} data-testid={`delete-${d.deal_id}`} title="Supprimer">
          <Trash2 className="w-4 h-4" />
        </Button>
      </div>
    </div>
  );
}
