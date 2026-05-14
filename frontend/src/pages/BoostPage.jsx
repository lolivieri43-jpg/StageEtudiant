import React, { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Button } from "../components/ui/button";
import { Sparkles, Zap, Check } from "lucide-react";
import { toast } from "sonner";

export default function BoostPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [params] = useSearchParams();
  const dealId = params.get("deal_id");
  const [loading, setLoading] = useState(false);
  const [deal, setDeal] = useState(null);

  useEffect(() => {
    if (dealId) api.get(`/deals/${dealId}`).then((r) => setDeal(r.data));
  }, [dealId]);

  if (!user || !dealId) return <div className="pt-24 text-center text-slate-500">Paramètres manquants</div>;

  const pkg = user.role === "company" ? "boost_company" : "boost_student";
  const price = user.role === "company" ? "10€" : "1€";

  const buy = async () => {
    setLoading(true);
    try {
      const { data } = await api.post("/payments/checkout", {
        package_id: pkg,
        origin_url: window.location.origin,
        deal_id: dealId,
      });
      window.location.href = data.url;
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erreur");
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen pt-20 pb-12 bg-slate-50">
      <div className="max-w-2xl mx-auto px-6">
        <h1 className="text-3xl font-black tracking-tight text-slate-900 mb-2">Mettre en avant le bon plan</h1>
        <p className="text-slate-500 mb-6">{deal?.title}</p>

        <div className="card-soft p-8">
          <div className={`w-16 h-16 rounded-2xl grid place-items-center mb-5 ${user.role === "company" ? "bg-amber-100" : "bg-violet-100"}`}>
            {user.role === "company" ? <Sparkles className="w-7 h-7 text-amber-600" /> : <Zap className="w-7 h-7 text-violet-600" />}
          </div>
          <h2 className="text-2xl font-bold text-slate-900 mb-2">
            {user.role === "company" ? "Boost Sponsorisé" : "Boost étudiant"}
          </h2>
          <div className="flex items-baseline gap-2 mb-6">
            <span className="text-5xl font-black gradient-text">{price}</span>
            <span className="text-slate-500">pour 7 jours</span>
          </div>
          <ul className="space-y-2 mb-8">
            {user.role === "company" ? (
              <>
                <Li>Affichage prioritaire dans les résultats</Li>
                <Li>Section "Bons plans sponsorisés"</Li>
                <Li>Badge "Sponsorisé" clairement identifié</Li>
                <Li>Apparition possible sur la page d'accueil</Li>
              </>
            ) : (
              <>
                <Li>Apparaît plus haut dans les résultats</Li>
                <Li>Section "Bons plans mis en avant"</Li>
                <Li>Badge discret "Mis en avant"</Li>
              </>
            )}
          </ul>
          <Button onClick={buy} disabled={loading} className={`w-full rounded-xl h-12 ${user.role === "company" ? "bg-amber-600 hover:bg-amber-700" : "bg-violet-600 hover:bg-violet-700"}`} data-testid="buy-boost">
            {loading ? "Redirection vers Stripe..." : `Payer ${price}`}
          </Button>
          <p className="text-xs text-center text-slate-400 mt-4">Paiement sécurisé via Stripe</p>
        </div>
      </div>
    </div>
  );
}

const Li = ({ children }) => (
  <li className="flex items-start gap-2 text-sm text-slate-600"><Check className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />{children}</li>
);
