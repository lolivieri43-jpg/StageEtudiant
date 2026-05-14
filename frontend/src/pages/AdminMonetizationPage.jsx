import React, { useEffect, useState } from "react";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Check, X, EyeOff, Euro, TrendingUp, CreditCard, AlertCircle } from "lucide-react";
import { toast } from "sonner";

export default function AdminMonetizationPage() {
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [pending, setPending] = useState([]);

  const load = async () => {
    const [m, p] = await Promise.all([
      api.get("/admin/monetization"),
      api.get("/admin/deals/pending"),
    ]);
    setData(m.data);
    setPending(p.data);
  };
  useEffect(() => { if (user?.role === "admin") load(); }, [user]);

  const moderate = async (dealId, action) => {
    await api.post(`/admin/deals/${dealId}/validate`, { action });
    toast.success(action === "approve" ? "Bon plan approuvé" : "Bon plan refusé");
    load();
  };

  if (user?.role !== "admin") return <div className="pt-24 text-center text-slate-500">Accès admin uniquement</div>;
  if (!data) return <div className="pt-24 text-center text-slate-400">Chargement...</div>;

  return (
    <div className="min-h-screen pt-20 pb-12 bg-slate-50">
      <div className="max-w-6xl mx-auto px-6">
        <h1 className="text-3xl font-black tracking-tight text-slate-900 mb-6">Monétisation</h1>

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <Stat icon={Euro} color="emerald" label="Revenus totaux" value={`${data.total_revenue.toFixed(2)}€`} />
          <Stat icon={CreditCard} color="blue" label="Abonnements actifs" value={data.active_subs} sub={`${data.monthly_subs} mensuels · ${data.yearly_subs} annuels`} />
          <Stat icon={TrendingUp} color="violet" label="Boosts entreprises" value={`${data.boost_company_revenue.toFixed(2)}€`} />
          <Stat icon={TrendingUp} color="amber" label="Boosts étudiants" value={`${data.boost_student_revenue.toFixed(2)}€`} />
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
          <Stat icon={Euro} color="emerald" label="Revenus abonnements" value={`${data.subscription_revenue.toFixed(2)}€`} />
          <Stat icon={X} color="rose" label="Paiements échoués" value={data.failed_payments} />
          <Stat icon={EyeOff} color="slate" label="Abonnements annulés" value={data.canceled_subs} />
        </div>

        {pending.length > 0 && (
          <section className="mb-8">
            <h2 className="font-bold text-slate-900 mb-4 flex items-center gap-2"><AlertCircle className="w-4 h-4 text-amber-500" />Bons plans en attente ({pending.length})</h2>
            <div className="space-y-3">
              {pending.map(d => (
                <div key={d.deal_id} className="card-soft p-4 flex items-start gap-3" data-testid={`pending-deal-${d.deal_id}`}>
                  <div className="w-12 h-12 rounded-xl bg-violet-100 grid place-items-center font-bold text-violet-600 shrink-0">{d.author_name[0]}</div>
                  <div className="flex-1 min-w-0">
                    <div className="font-bold">{d.title}</div>
                    <div className="text-xs text-slate-500 line-clamp-2">{d.description}</div>
                    <div className="text-xs text-slate-400 mt-1">par {d.author_name} · {d.city || "—"}</div>
                  </div>
                  <Button size="sm" onClick={() => moderate(d.deal_id, "approve")} className="rounded-full bg-emerald-600 hover:bg-emerald-700" data-testid={`approve-${d.deal_id}`}><Check className="w-4 h-4" /></Button>
                  <Button size="sm" variant="outline" onClick={() => moderate(d.deal_id, "refuse")} className="rounded-full" data-testid={`refuse-${d.deal_id}`}><X className="w-4 h-4" /></Button>
                </div>
              ))}
            </div>
          </section>
        )}

        <section>
          <h2 className="font-bold text-slate-900 mb-4">Transactions récentes</h2>
          <div className="card-soft overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="text-left text-slate-500 border-b border-slate-100"><th className="p-3">Date</th><th>Utilisateur</th><th>Type</th><th>Montant</th><th>Statut</th></tr></thead>
              <tbody>
                {data.transactions.map(t => (
                  <tr key={t.tx_id} className="border-b border-slate-50">
                    <td className="p-3 text-slate-500">{new Date(t.created_at).toLocaleString("fr-FR")}</td>
                    <td className="font-mono text-xs">{t.user_id.slice(-8)}</td>
                    <td>{t.package_id}</td>
                    <td className="font-bold">{t.amount.toFixed(2)} {t.currency.toUpperCase()}</td>
                    <td>
                      <Badge className={`border-0 rounded-full text-xs ${t.payment_status === "paid" ? "bg-emerald-100 text-emerald-700" : t.payment_status === "failed" ? "bg-rose-100 text-rose-700" : "bg-amber-100 text-amber-700"}`}>
                        {t.payment_status}
                      </Badge>
                    </td>
                  </tr>
                ))}
                {data.transactions.length === 0 && <tr><td colSpan={5} className="p-8 text-center text-slate-400">Aucune transaction</td></tr>}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  );
}

const Stat = ({ icon: Icon, color, label, value, sub }) => {
  const colors = {
    emerald: "bg-emerald-50 text-emerald-600",
    blue: "bg-blue-50 text-blue-600",
    violet: "bg-violet-50 text-violet-600",
    amber: "bg-amber-50 text-amber-600",
    rose: "bg-rose-50 text-rose-600",
    slate: "bg-slate-100 text-slate-600",
  };
  return (
    <div className="card-soft p-5">
      <div className={`w-10 h-10 rounded-xl grid place-items-center ${colors[color]} mb-3`}><Icon className="w-5 h-5" /></div>
      <div className="text-2xl font-black text-slate-900">{value}</div>
      <div className="text-xs text-slate-500 mt-1">{label}</div>
      {sub && <div className="text-[10px] text-slate-400 mt-0.5">{sub}</div>}
    </div>
  );
};
