import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Button } from "../components/ui/button";
import { Check, Sparkles } from "lucide-react";
import { toast } from "sonner";

export default function SubscribePage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [loading, setLoading] = useState(null);

  const buy = async (pkg) => {
    setLoading(pkg);
    try {
      const { data } = await api.post("/payments/checkout", {
        package_id: pkg,
        origin_url: window.location.origin,
      });
      window.location.href = data.url;
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erreur");
      setLoading(null);
    }
  };

  if (!user || user.role !== "company") {
    return <div className="pt-24 text-center text-slate-500">Réservé aux entreprises.</div>;
  }

  const FEATURES = [
    "Page bons plans personnalisée",
    "Publication illimitée de bons plans",
    "Codes promo, visuels, expiration",
    "Statistiques détaillées (vues, clics, saves, partages)",
    "Notifications quand un étudiant sauvegarde",
    "Modifier / désactiver à tout moment",
    "Accès au boost Sponsorisé (10€/semaine)",
  ];

  return (
    <div className="min-h-screen pt-20 pb-12 bg-slate-50">
      <div className="max-w-4xl mx-auto px-6 text-center">
        <span className="text-xs font-bold uppercase tracking-[0.15em] text-violet-600">Accès Pro Bons Plans</span>
        <h1 className="text-4xl font-black tracking-tight text-slate-900 mt-2 mb-3">Touchez des milliers d'étudiants</h1>
        <p className="text-slate-500 max-w-xl mx-auto mb-10">Activez votre mini-espace bons plans pour promouvoir vos offres étudiantes auprès de notre communauté.</p>

        <div className="grid md:grid-cols-2 gap-6 text-left">
          <Plan
            title="Mensuel"
            price="1€"
            period="par mois"
            features={FEATURES}
            onClick={() => buy("sub_monthly")}
            loading={loading === "sub_monthly"}
            testid="plan-monthly"
          />
          <Plan
            title="Annuel"
            price="10€"
            period="par an"
            badge="Économisez 17%"
            features={FEATURES}
            highlight
            onClick={() => buy("sub_yearly")}
            loading={loading === "sub_yearly"}
            testid="plan-yearly"
          />
        </div>

        <p className="text-xs text-slate-400 mt-8">Paiement sécurisé via Stripe · Annulation à tout moment · Conforme RGPD</p>
      </div>
    </div>
  );
}

const Plan = ({ title, price, period, features, badge, highlight, onClick, loading, testid }) => (
  <div className={`card-soft p-8 relative ${highlight ? "ring-4 ring-violet-200 border-violet-400" : ""}`}>
    {badge && (
      <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-violet-600 text-white text-xs font-bold px-3 py-1 rounded-full flex items-center gap-1">
        <Sparkles className="w-3 h-3" />{badge}
      </div>
    )}
    <h3 className="text-xl font-bold text-slate-900 mb-2">{title}</h3>
    <div className="flex items-baseline gap-2 mb-6">
      <span className="text-5xl font-black gradient-text">{price}</span>
      <span className="text-slate-500">{period}</span>
    </div>
    <ul className="space-y-2.5 mb-6">
      {features.map(f => (
        <li key={f} className="flex items-start gap-2 text-sm text-slate-600">
          <Check className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />{f}
        </li>
      ))}
    </ul>
    <Button onClick={onClick} disabled={loading} className={`w-full rounded-xl h-11 ${highlight ? "bg-violet-600 hover:bg-violet-700" : "bg-blue-600 hover:bg-blue-700"}`} data-testid={testid}>
      {loading ? "Redirection..." : "S'abonner"}
    </Button>
  </div>
);
