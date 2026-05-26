import React, { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { Check, X, Pause, Play, Trash2, ExternalLink, Search, RefreshCw, AlertCircle, Eye, MousePointerClick, TrendingUp, Megaphone } from "lucide-react";
import { toast } from "sonner";

const STATUSES = [
  { id: "pending", label: "En attente", color: "bg-amber-100 text-amber-700" },
  { id: "published", label: "Diffusées", color: "bg-emerald-100 text-emerald-700" },
  { id: "refused", label: "Refusées", color: "bg-rose-100 text-rose-700" },
  { id: "suspended", label: "Suspendues", color: "bg-orange-100 text-orange-700" },
  { id: "draft", label: "Brouillons", color: "bg-slate-100 text-slate-600" },
  { id: "expired", label: "Expirées", color: "bg-slate-100 text-slate-500" },
  { id: "all", label: "Toutes", color: "bg-slate-200 text-slate-800" },
];

const STATUS_BADGE = {
  draft: "bg-slate-100 text-slate-600",
  pending: "bg-amber-100 text-amber-700",
  published: "bg-emerald-100 text-emerald-700",
  refused: "bg-rose-100 text-rose-700",
  suspended: "bg-orange-100 text-orange-700",
  expired: "bg-slate-100 text-slate-500",
};

export default function AdminAdsPage() {
  const { user } = useAuth();
  const [data, setData] = useState({ ads: [], counts: {}, stats: {} });
  const [status, setStatus] = useState("pending");
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const p = new URLSearchParams();
      if (status) p.set("status", status);
      if (q) p.set("q", q);
      const { data } = await api.get(`/admin/ads?${p.toString()}`);
      setData(data);
    } finally {
      setLoading(false);
    }
  }, [status, q]);

  useEffect(() => { if (user?.role === "admin") load(); }, [user, load]);

  const moderate = async (adId, action, label) => {
    let reason = "";
    if (action === "refuse" || action === "suspend") {
      reason = window.prompt(`Raison du ${label} (optionnel) :`, "") || "";
    }
    try {
      await api.post(`/admin/ads/${adId}/validate`, { action, reason });
      toast.success(`Publicité ${label}`);
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Erreur");
    }
  };

  const remove = async (adId) => {
    if (!window.confirm("Supprimer définitivement cette publicité ?")) return;
    await api.delete(`/ads/${adId}`);
    toast.success("Publicité supprimée");
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
            <h1 className="text-3xl font-black tracking-tight text-slate-900 flex items-center gap-2">
              <Megaphone className="w-7 h-7 text-violet-600" />Modération des publicités
            </h1>
            <p className="text-slate-500 mt-1">Validez les publicités sponsorisées avant diffusion dans l'espace Bons Plans</p>
          </div>
          <div className="flex gap-2">
            <Link to="/admin/deals"><Button variant="outline" className="rounded-full" data-testid="goto-admin-deals">Bons plans</Button></Link>
            <Button variant="outline" className="rounded-full" onClick={load} disabled={loading} data-testid="refresh-ads">
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            </Button>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
          <StatTile icon={Megaphone} label="Publicités totales" value={data.stats.ads || 0} color="bg-violet-50 text-violet-600" />
          <StatTile icon={Eye} label="Vues cumulées" value={(data.stats.total_views || 0).toLocaleString("fr-FR")} color="bg-blue-50 text-blue-600" />
          <StatTile icon={MousePointerClick} label="Clics cumulés" value={(data.stats.total_clicks || 0).toLocaleString("fr-FR")} color="bg-emerald-50 text-emerald-600" />
          <StatTile icon={TrendingUp} label="Taux de clic (CTR)" value={`${data.stats.ctr || 0}%`} color="bg-amber-50 text-amber-600" />
        </div>

        {/* Status tabs */}
        <div className="flex flex-wrap gap-2 mb-4" data-testid="ads-status-tabs">
          {STATUSES.map(s => (
            <button
              key={s.id}
              onClick={() => setStatus(s.id)}
              data-testid={`ads-tab-${s.id}`}
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
              placeholder="Rechercher par titre, texte, entreprise..."
              className="rounded-full pl-9 bg-slate-50 border-0"
              data-testid="search-ads" />
          </div>
        </div>

        <div className="space-y-3">
          {data.ads.length === 0 && (
            <div className="card-soft p-12 text-center text-slate-500">
              <AlertCircle className="w-10 h-10 mx-auto text-slate-300 mb-3" />
              Aucune publicité dans cet état
            </div>
          )}
          {data.ads.map(a => <AdRow key={a.ad_id} ad={a} onModerate={moderate} onDelete={remove} />)}
        </div>
      </div>
    </div>
  );
}

function AdRow({ ad: a, onModerate, onDelete }) {
  const ctr = (a.views || 0) > 0 ? Math.min((a.clicks || 0) / a.views * 100, 100).toFixed(1) : "0.0";
  return (
    <div className="card-soft p-4 flex items-start gap-3" data-testid={`ad-row-${a.ad_id}`}>
      <div className="w-16 h-16 rounded-xl overflow-hidden bg-gradient-to-br from-violet-100 to-blue-100 grid place-items-center font-bold text-violet-600 shrink-0">
        {a.image ? <img src={a.image} alt="" className="w-full h-full object-cover" /> : (a.company_name?.[0] || "?")}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-bold">{a.title}</span>
          <Badge className={`border-0 rounded-full text-[10px] ${STATUS_BADGE[a.status] || "bg-slate-100"}`}>{a.status}</Badge>
          {a.promo_code && <Badge className="border-0 rounded-full text-[10px] bg-violet-100 text-violet-700">Code: {a.promo_code}</Badge>}
        </div>
        <div className="text-xs text-slate-500 line-clamp-2 mt-1">{a.short_text}</div>
        <div className="text-[11px] text-slate-400 mt-1 flex flex-wrap gap-2">
          <span>par {a.company_name}</span>
          {a.category && <span>· {a.category}</span>}
          {(a.city || a.region || a.geo_zone) && <span>· {a.city || a.region || a.geo_zone}</span>}
          {a.start_date && <span>· du {a.start_date.slice(0, 10)}</span>}
          {a.end_date && <span>au {a.end_date.slice(0, 10)}</span>}
        </div>
        <div className="text-[11px] text-slate-500 mt-1 flex flex-wrap gap-3">
          <span><Eye className="w-3 h-3 inline mr-1" />{a.views || 0} vues</span>
          <span><MousePointerClick className="w-3 h-3 inline mr-1" />{a.clicks || 0} clics</span>
          <span><TrendingUp className="w-3 h-3 inline mr-1" />CTR {ctr}%</span>
        </div>
        {a.moderation_reason && (
          <div className="text-[11px] text-rose-600 mt-1">Modération : {a.moderation_reason}</div>
        )}
      </div>
      <div className="flex items-center gap-1 shrink-0">
        {a.cta_url && (
          <a href={a.cta_url} target="_blank" rel="noreferrer">
            <Button size="sm" variant="outline" className="rounded-full" data-testid={`ad-view-${a.ad_id}`} title="Tester le lien">
              <ExternalLink className="w-4 h-4" />
            </Button>
          </a>
        )}
        {a.status !== "published" && (
          <Button size="sm" className="rounded-full bg-emerald-600 hover:bg-emerald-700" onClick={() => onModerate(a.ad_id, "approve", "validée")} data-testid={`ad-approve-${a.ad_id}`} title="Valider">
            <Check className="w-4 h-4" />
          </Button>
        )}
        {a.status !== "refused" && (
          <Button size="sm" variant="outline" className="rounded-full" onClick={() => onModerate(a.ad_id, "refuse", "refusée")} data-testid={`ad-refuse-${a.ad_id}`} title="Refuser">
            <X className="w-4 h-4" />
          </Button>
        )}
        {a.status === "published" && (
          <Button size="sm" variant="outline" className="rounded-full text-orange-600 border-orange-200" onClick={() => onModerate(a.ad_id, "suspend", "suspendue")} data-testid={`ad-suspend-${a.ad_id}`} title="Suspendre">
            <Pause className="w-4 h-4" />
          </Button>
        )}
        {a.status === "suspended" && (
          <Button size="sm" variant="outline" className="rounded-full text-emerald-600 border-emerald-200" onClick={() => onModerate(a.ad_id, "reactivate", "réactivée")} data-testid={`ad-reactivate-${a.ad_id}`} title="Réactiver">
            <Play className="w-4 h-4" />
          </Button>
        )}
        <Button size="sm" variant="outline" className="rounded-full text-rose-600 border-rose-200" onClick={() => onDelete(a.ad_id)} data-testid={`ad-delete-${a.ad_id}`} title="Supprimer">
          <Trash2 className="w-4 h-4" />
        </Button>
      </div>
    </div>
  );
}

function StatTile({ icon: Icon, label, value, color }) {
  return (
    <div className="card-soft p-4">
      <div className={`w-10 h-10 rounded-xl grid place-items-center ${color} mb-2`}><Icon className="w-5 h-5" /></div>
      <div className="text-2xl font-black text-slate-900">{value}</div>
      <div className="text-xs text-slate-500 mt-0.5">{label}</div>
    </div>
  );
}
