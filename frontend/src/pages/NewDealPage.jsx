import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Button } from "../components/ui/button";
import { toast } from "sonner";
import { AlertCircle, CheckCircle2 } from "lucide-react";

const CATS = [
  { id: "food", label: "Restauration" },
  { id: "sport", label: "Sport" },
  { id: "culture", label: "Culture" },
  { id: "transport", label: "Transport" },
  { id: "study", label: "Études" },
  { id: "fashion", label: "Mode" },
  { id: "tech", label: "Tech" },
  { id: "general", label: "Autre" },
];

export default function NewDealPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [subActive, setSubActive] = useState(null);
  const [form, setForm] = useState({
    title: "", description: "", category: "food", city: "",
    image: "", promo_code: "", discount: "", url: "", expires_at: "",
  });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (user?.role === "company") {
      api.get("/subscriptions/me").then((r) => setSubActive(r.data.subscription?.status === "active"));
    }
  }, [user]);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const { data } = await api.post("/deals", form);
      toast.success(user.role === "candidate" ? "Bon plan envoyé en validation !" : "Bon plan publié !");
      navigate(`/deals/${data.deal_id}`);
    } catch (err) {
      if (err.response?.status === 402) {
        toast.error("Abonnement Pro Bons Plans requis");
        navigate("/payments/subscribe");
      } else {
        toast.error(err.response?.data?.detail || "Erreur");
      }
    } finally {
      setLoading(false);
    }
  };

  if (!user) return null;

  return (
    <div className="min-h-screen pt-20 pb-12 bg-slate-50">
      <div className="max-w-2xl mx-auto px-6">
        <h1 className="text-3xl font-black tracking-tight text-slate-900 mb-2">Proposer un bon plan</h1>
        {user.role === "candidate" && (
          <div className="card-soft p-4 mb-6 bg-amber-50 border-amber-200 flex gap-3">
            <AlertCircle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
            <div className="text-sm">
              <div className="font-bold text-amber-900">Validation administrateur</div>
              <div className="text-amber-800">Votre bon plan sera vérifié avant publication. Cela prend généralement moins de 24h.</div>
            </div>
          </div>
        )}
        {user.role === "company" && subActive === false && (
          <div className="card-soft p-4 mb-6 bg-rose-50 border-rose-200 flex gap-3">
            <AlertCircle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
            <div className="text-sm flex-1">
              <div className="font-bold text-rose-900">Abonnement requis</div>
              <div className="text-rose-800">Vous devez activer l'abonnement Pro Bons Plans (1€/mois ou 10€/an) pour publier.</div>
              <Button onClick={() => navigate("/payments/subscribe")} className="mt-2 rounded-full bg-rose-600 hover:bg-rose-700" size="sm" data-testid="goto-subscribe">Voir les offres</Button>
            </div>
          </div>
        )}
        {user.role === "company" && subActive && (
          <div className="card-soft p-4 mb-6 bg-emerald-50 border-emerald-200 flex gap-3">
            <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
            <div className="text-sm text-emerald-800"><b>Abonnement actif</b> — votre bon plan sera publié immédiatement.</div>
          </div>
        )}

        <form onSubmit={submit} className="card-soft p-8 space-y-4">
          <div>
            <Label>Titre</Label>
            <Input required value={form.title} onChange={set("title")} className="rounded-xl mt-1" data-testid="deal-title-input" />
          </div>
          <div>
            <Label>Description</Label>
            <Textarea required value={form.description} onChange={set("description")} rows={4} className="rounded-xl mt-1" data-testid="deal-description" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>Catégorie</Label>
              <select value={form.category} onChange={set("category")} className="w-full rounded-xl border border-slate-200 h-10 px-3 mt-1" data-testid="deal-category">
                {CATS.map(c => <option key={c.id} value={c.id}>{c.label}</option>)}
              </select>
            </div>
            <div>
              <Label>Ville</Label>
              <Input value={form.city} onChange={set("city")} className="rounded-xl mt-1" data-testid="deal-city" />
            </div>
            <div>
              <Label>Réduction (ex: -20%)</Label>
              <Input value={form.discount} onChange={set("discount")} className="rounded-xl mt-1" data-testid="deal-discount" />
            </div>
            <div>
              <Label>Code promo</Label>
              <Input value={form.promo_code} onChange={set("promo_code")} className="rounded-xl mt-1" data-testid="deal-promo" />
            </div>
            <div className="col-span-2">
              <Label>Lien externe</Label>
              <Input type="url" value={form.url} onChange={set("url")} placeholder="https://..." className="rounded-xl mt-1" data-testid="deal-url" />
            </div>
            <div className="col-span-2">
              <Label>Image (URL)</Label>
              <Input value={form.image} onChange={set("image")} placeholder="https://..." className="rounded-xl mt-1" data-testid="deal-image" />
            </div>
            <div className="col-span-2">
              <Label>Date d'expiration</Label>
              <Input type="date" value={form.expires_at} onChange={set("expires_at")} className="rounded-xl mt-1" data-testid="deal-expires" />
            </div>
          </div>
          <Button type="submit" disabled={loading} className="w-full rounded-xl bg-blue-600 hover:bg-blue-700 h-11" data-testid="submit-deal">
            {loading ? "Envoi..." : "Publier le bon plan"}
          </Button>
        </form>
      </div>
    </div>
  );
}
