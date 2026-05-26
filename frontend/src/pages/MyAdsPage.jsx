import React, { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Plus, Edit, Trash2, Eye, MousePointerClick, TrendingUp, Megaphone, AlertCircle, Sparkles } from "lucide-react";
import { toast } from "sonner";

const STATUS_BADGE = {
  draft: "bg-slate-100 text-slate-600",
  pending: "bg-amber-100 text-amber-700",
  published: "bg-emerald-100 text-emerald-700",
  refused: "bg-rose-100 text-rose-700",
  suspended: "bg-orange-100 text-orange-700",
  expired: "bg-slate-100 text-slate-500",
};
const STATUS_LABEL = {
  draft: "Brouillon", pending: "En attente",
  published: "Diffusée", refused: "Refusée", suspended: "Suspendue", expired: "Expirée",
};

export default function MyAdsPage() {
  const { user } = useAuth();
  const [data, setData] = useState({ ads: [], quota: { used: 0, max: 1 }, pro: false });

  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/ads/mine");
      setData(data);
    } catch {
      // silent
    }
  }, []);
  useEffect(() => { if (user?.role === "company") load(); }, [user, load]);

  const remove = async (adId) => {
    if (!window.confirm("Supprimer cette publicité ?")) return;
    await api.delete(`/ads/${adId}`);
    toast.success("Publicité supprimée");
    load();
  };

  if (!user || user.role !== "company") {
    return <div className="pt-24 text-center text-slate-500">Réservé aux entreprises.</div>;
  }

  return (
    <div className="min-h-screen pt-20 pb-12 bg-slate-50">
      <div className="max-w-5xl mx-auto px-6">
        <div className="flex items-end justify-between mb-6 flex-wrap gap-3">
          <div>
            <h1 className="text-3xl font-black tracking-tight text-slate-900 flex items-center gap-2">
              <Megaphone className="w-7 h-7 text-violet-600" />Mes publicités
            </h1>
            <p className="text-slate-500 mt-1">
              {data.pro ? (
                <span className="flex items-center gap-1"><Sparkles className="w-4 h-4 text-amber-500" />Compte Pro · publications illimitées</span>
              ) : (
                <>Compte gratuit · <b>{data.quota.used}/{data.quota.max}</b> publicité active</>
              )}
            </p>
          </div>
          <Link to="/ads/new">
            <Button className="rounded-full bg-violet-600 hover:bg-violet-700" data-testid="new-ad-btn"><Plus className="w-4 h-4 mr-1" />Nouvelle publicité</Button>
          </Link>
        </div>

        {!data.pro && data.quota.used >= data.quota.max && (
          <div className="card-soft p-4 mb-4 bg-amber-50 border-amber-200 flex gap-3" data-testid="quota-banner">
            <AlertCircle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
            <div className="text-sm flex-1">
              <div className="font-bold text-amber-900">Quota atteint</div>
              <div className="text-amber-800">Vous avez déjà <b>1 publicité active</b>. Passez à l'offre Pro pour en diffuser plusieurs simultanément.</div>
            </div>
            <Link to="/payments/subscribe"><Button size="sm" className="rounded-full bg-amber-600 hover:bg-amber-700">Passer Pro</Button></Link>
          </div>
        )}

        {data.ads.length === 0 && (
          <div className="card-soft p-12 text-center">
            <Megaphone className="w-10 h-10 mx-auto text-slate-300 mb-3" />
            <div className="text-slate-500 mb-2">Vous n'avez pas encore créé de publicité</div>
            <Link to="/ads/new" className="text-violet-600 font-semibold">Créer ma première publicité →</Link>
          </div>
        )}

        <div className="space-y-3">
          {data.ads.map(a => {
            const ctr = (a.views || 0) > 0 ? Math.min((a.clicks || 0) / a.views * 100, 100).toFixed(1) : "0.0";
            return (
              <div key={a.ad_id} className="card-soft p-4 flex items-start gap-3" data-testid={`my-ad-${a.ad_id}`}>
                <div className="w-16 h-16 rounded-xl bg-gradient-to-br from-violet-100 to-blue-100 overflow-hidden grid place-items-center font-bold text-violet-600 shrink-0">
                  {a.image ? <img src={a.image} alt="" className="w-full h-full object-cover" /> : "AD"}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-bold">{a.title}</span>
                    <Badge className={`border-0 rounded-full text-[10px] ${STATUS_BADGE[a.status]}`}>{STATUS_LABEL[a.status] || a.status}</Badge>
                    {a.promo_code && <Badge className="border-0 rounded-full text-[10px] bg-violet-100 text-violet-700">Code: {a.promo_code}</Badge>}
                  </div>
                  <div className="text-xs text-slate-500 line-clamp-2 mt-1">{a.short_text}</div>
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
                  <Link to={`/ads/${a.ad_id}/edit`}>
                    <Button size="sm" variant="outline" className="rounded-full" data-testid={`edit-ad-${a.ad_id}`} title="Modifier">
                      <Edit className="w-4 h-4" />
                    </Button>
                  </Link>
                  <Button size="sm" variant="outline" className="rounded-full text-rose-600 border-rose-200" onClick={() => remove(a.ad_id)} data-testid={`del-ad-${a.ad_id}`} title="Supprimer">
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
