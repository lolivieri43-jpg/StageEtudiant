import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Sparkles, Plus, Eye, MousePointer, Heart, Zap, Calendar, CreditCard } from "lucide-react";
import { DealCard } from "./DealsPage";
import { toast } from "sonner";

const STATUS_MAP = {
  draft: { label: "Brouillon", color: "bg-slate-100 text-slate-600" },
  pending: { label: "En validation", color: "bg-amber-100 text-amber-700" },
  published: { label: "Publié", color: "bg-emerald-100 text-emerald-700" },
  refused: { label: "Refusé", color: "bg-rose-100 text-rose-700" },
  expired: { label: "Expiré", color: "bg-slate-200 text-slate-500" },
};

export default function MyDealsPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState({ deals: [], saved: [], boosts: [] });
  const [sub, setSub] = useState(null);
  const [history, setHistory] = useState([]);

  const load = async () => {
    const { data } = await api.get("/deals/mine");
    setData(data);
    if (user?.role === "company") {
      const { data: subData } = await api.get("/subscriptions/me");
      setSub(subData.subscription);
      setHistory(subData.history);
    }
  };
  useEffect(() => { if (user) load(); }, [user]);

  const cancelSub = async () => {
    if (!window.confirm("Annuler l'abonnement ? L'accès restera actif jusqu'à la date de fin.")) return;
    await api.post("/subscriptions/cancel");
    toast.success("Abonnement annulé");
    load();
  };

  if (!user) return null;
  const isCompany = user.role === "company";
  const subActive = sub?.status === "active";

  return (
    <div className="min-h-screen pt-20 pb-12 bg-slate-50">
      <div className="max-w-6xl mx-auto px-6">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-3xl font-black tracking-tight text-slate-900">Mes bons plans</h1>
          <Link to="/deals/new"><Button className="rounded-full bg-blue-600 hover:bg-blue-700"><Plus className="w-4 h-4 mr-1" />Nouveau</Button></Link>
        </div>

        {/* Subscription card for companies */}
        {isCompany && (
          <div className="card-soft p-6 mb-8" data-testid="sub-status">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
              <div>
                <h2 className="font-bold text-slate-900 mb-1">Accès Pro Bons Plans</h2>
                {subActive ? (
                  <div className="flex flex-wrap items-center gap-3">
                    <Badge className="bg-emerald-100 text-emerald-700 border-0 rounded-full">Actif</Badge>
                    <span className="text-sm text-slate-500">
                      <Calendar className="w-3.5 h-3.5 inline mr-1" />
                      Renouvelle le {new Date(sub.renewal_date).toLocaleDateString("fr-FR")}
                    </span>
                    <span className="text-sm text-slate-500">Plan: {sub.period === "yearly" ? "Annuel (10€/an)" : "Mensuel (1€/mois)"}</span>
                  </div>
                ) : (
                  <div className="text-sm text-slate-500">Aucun abonnement actif</div>
                )}
              </div>
              <div className="flex gap-2">
                {subActive ? (
                  <Button onClick={cancelSub} variant="outline" className="rounded-full" data-testid="cancel-sub">Annuler</Button>
                ) : (
                  <Button onClick={() => navigate("/payments/subscribe")} className="rounded-full bg-violet-600 hover:bg-violet-700" data-testid="subscribe-btn"><CreditCard className="w-4 h-4 mr-1" />S'abonner</Button>
                )}
              </div>
            </div>
          </div>
        )}

        {/* My deals */}
        <section className="mb-10">
          <h2 className="font-bold text-slate-900 mb-4">Mes publications ({data.deals.length})</h2>
          {data.deals.length === 0 ? (
            <div className="card-soft p-8 text-center text-slate-400 text-sm">Aucun bon plan publié</div>
          ) : (
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
              {data.deals.map(d => {
                const st = STATUS_MAP[d.status] || STATUS_MAP.published;
                const now = new Date();
                const boosted = (d.boosted_until && new Date(d.boosted_until) > now) || (d.sponsored_until && new Date(d.sponsored_until) > now);
                return (
                  <div key={d.deal_id} className="card-soft p-5" data-testid={`my-deal-${d.deal_id}`}>
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <Link to={`/deals/${d.deal_id}`} className="font-bold text-slate-900 hover:text-blue-600">{d.title}</Link>
                      <Badge className={`${st.color} border-0 rounded-full text-[10px] shrink-0`}>{st.label}</Badge>
                    </div>
                    <p className="text-xs text-slate-500 line-clamp-2 mb-3">{d.description}</p>
                    <div className="flex items-center gap-4 text-xs text-slate-500 mb-3">
                      <span className="flex items-center gap-1"><Eye className="w-3 h-3" />{d.views}</span>
                      <span className="flex items-center gap-1"><MousePointer className="w-3 h-3" />{d.clicks}</span>
                      <span className="flex items-center gap-1"><Heart className="w-3 h-3" />{d.saves?.length || 0}</span>
                    </div>
                    {d.status === "published" && !boosted && (
                      <Link to={`/payments/boost?deal_id=${d.deal_id}`}>
                        <Button size="sm" variant="outline" className="rounded-full w-full text-amber-700 border-amber-200" data-testid={`boost-${d.deal_id}`}>
                          <Sparkles className="w-3 h-3 mr-1" />{isCompany ? "Sponsoriser 10€" : "Mettre en avant 1€"}
                        </Button>
                      </Link>
                    )}
                    {boosted && <Badge className="bg-violet-100 text-violet-700 border-0 rounded-full w-full justify-center"><Zap className="w-3 h-3 mr-1" />Boost actif</Badge>}
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {data.saved.length > 0 && (
          <section className="mb-10">
            <h2 className="font-bold text-slate-900 mb-4">Sauvegardés ({data.saved.length})</h2>
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
              {data.saved.map(d => <DealCard key={d.deal_id} deal={d} />)}
            </div>
          </section>
        )}

        {/* Payment history */}
        {isCompany && history.length > 0 && (
          <section>
            <h2 className="font-bold text-slate-900 mb-4">Historique des paiements</h2>
            <div className="card-soft overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="text-left text-slate-500 border-b border-slate-100"><th className="p-3">Date</th><th>Montant</th><th>Type</th><th>Statut</th></tr></thead>
                <tbody>
                  {history.map(t => (
                    <tr key={t.tx_id} className="border-b border-slate-50">
                      <td className="p-3">{new Date(t.created_at).toLocaleDateString("fr-FR")}</td>
                      <td className="font-bold">{t.amount} {t.currency.toUpperCase()}</td>
                      <td className="text-slate-500">{t.kind}</td>
                      <td>
                        <Badge className={`border-0 rounded-full text-xs ${t.payment_status === "paid" ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>
                          {t.payment_status}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {data.boosts.length > 0 && (
          <section className="mt-10">
            <h2 className="font-bold text-slate-900 mb-4">Mes boosts</h2>
            <div className="card-soft p-5 space-y-2 text-sm">
              {data.boosts.map(b => (
                <div key={b.boost_id} className="flex items-center justify-between border-b border-slate-100 last:border-0 pb-2 last:pb-0">
                  <div>
                    <div className="font-semibold">{b.boost_type === "sponsored" ? "Sponsorisé" : "Mis en avant"}</div>
                    <div className="text-xs text-slate-500">{new Date(b.start_date).toLocaleDateString("fr-FR")} → {new Date(b.end_date).toLocaleDateString("fr-FR")}</div>
                  </div>
                  <div className="font-bold">{b.price}€</div>
                </div>
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
