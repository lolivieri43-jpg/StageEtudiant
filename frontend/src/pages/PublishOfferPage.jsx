import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Button } from "../components/ui/button";
import { Checkbox } from "../components/ui/checkbox";
import { toast } from "sonner";

const REGIONS = ["Île-de-France", "Auvergne-Rhône-Alpes", "Nouvelle-Aquitaine", "Occitanie", "Hauts-de-France", "Provence-Alpes-Côte d'Azur", "Grand Est", "Pays de la Loire", "Bretagne", "Normandie", "Bourgogne-Franche-Comté", "Centre-Val de Loire", "Corse"];

export default function PublishOfferPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [form, setForm] = useState({
    title: "", contract_type: "stage", domain: "", city: "", region: REGIONS[0],
    remote: false, duration: "6 mois", rhythm: "", start_date: "Septembre 2026",
    level: "Bac+3", skills: "", description: "", profile: "", benefits: "", salary: "",
  });
  const [loading, setLoading] = useState(false);

  if (user && user.role !== "company") {
    return <div className="pt-24 text-center text-slate-500">Réservé aux comptes entreprise.</div>;
  }

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const payload = { ...form, skills: form.skills.split(",").map(s => s.trim()).filter(Boolean) };
      const { data } = await api.post("/offers", payload);
      toast.success("Offre publiée !");
      navigate(`/offers/${data.offer_id}`);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erreur");
    } finally {
      setLoading(false);
    }
  };

  const set = (k) => (e) => setForm({ ...form, [k]: e?.target ? e.target.value : e });

  return (
    <div className="min-h-screen pt-20 pb-12 bg-slate-50">
      <div className="max-w-3xl mx-auto px-6">
        <h1 className="text-3xl font-black tracking-tight text-slate-900 mb-6">Publier une offre</h1>
        <form onSubmit={submit} className="card-soft p-8 space-y-5">
          <div>
            <Label>Titre du poste</Label>
            <Input data-testid="offer-title-input" required value={form.title} onChange={set("title")} className="rounded-xl mt-1" />
          </div>
          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <Label>Type de contrat</Label>
              <select data-testid="offer-ct" value={form.contract_type} onChange={set("contract_type")} className="w-full rounded-xl border border-slate-200 h-10 px-3 mt-1">
                <option value="stage">Stage</option>
                <option value="alternance">Alternance</option>
              </select>
            </div>
            <div>
              <Label>Domaine</Label>
              <Input data-testid="offer-domain" required value={form.domain} onChange={set("domain")} className="rounded-xl mt-1" placeholder="Informatique, Marketing..." />
            </div>
            <div>
              <Label>Ville</Label>
              <Input data-testid="offer-city" required value={form.city} onChange={set("city")} className="rounded-xl mt-1" />
            </div>
            <div>
              <Label>Région</Label>
              <select data-testid="offer-region" value={form.region} onChange={set("region")} className="w-full rounded-xl border border-slate-200 h-10 px-3 mt-1">
                {REGIONS.map(r => <option key={r}>{r}</option>)}
              </select>
            </div>
            <div>
              <Label>Niveau</Label>
              <select data-testid="offer-level" value={form.level} onChange={set("level")} className="w-full rounded-xl border border-slate-200 h-10 px-3 mt-1">
                <option>Bac+2</option><option>Bac+3</option><option>Bac+5</option>
              </select>
            </div>
            <div>
              <Label>Durée</Label>
              <Input data-testid="offer-duration" value={form.duration} onChange={set("duration")} className="rounded-xl mt-1" />
            </div>
            <div>
              <Label>Rythme (alternance)</Label>
              <Input data-testid="offer-rhythm" value={form.rhythm} onChange={set("rhythm")} className="rounded-xl mt-1" placeholder="3j entreprise / 2j école" />
            </div>
            <div>
              <Label>Date de début</Label>
              <Input data-testid="offer-start" value={form.start_date} onChange={set("start_date")} className="rounded-xl mt-1" />
            </div>
          </div>
          <label className="flex items-center gap-2" data-testid="offer-remote">
            <Checkbox checked={form.remote} onCheckedChange={(v) => setForm({ ...form, remote: v })} />
            <span className="text-sm">Télétravail possible</span>
          </label>
          <div>
            <Label>Compétences (séparées par virgule)</Label>
            <Input data-testid="offer-skills" value={form.skills} onChange={set("skills")} className="rounded-xl mt-1" placeholder="React, Python, Communication" />
          </div>
          <div>
            <Label>Description</Label>
            <Textarea data-testid="offer-description" required value={form.description} onChange={set("description")} rows={5} className="rounded-xl mt-1" />
          </div>
          <div>
            <Label>Profil recherché</Label>
            <Textarea data-testid="offer-profile" value={form.profile} onChange={set("profile")} rows={3} className="rounded-xl mt-1" />
          </div>
          <div>
            <Label>Avantages</Label>
            <Textarea data-testid="offer-benefits" value={form.benefits} onChange={set("benefits")} rows={2} className="rounded-xl mt-1" />
          </div>
          <div>
            <Label>Rémunération</Label>
            <Input data-testid="offer-salary" value={form.salary} onChange={set("salary")} className="rounded-xl mt-1" placeholder="1200€ / mois" />
          </div>
          <Button type="submit" disabled={loading} className="rounded-xl bg-blue-600 hover:bg-blue-700 h-11 w-full" data-testid="publish-submit">
            {loading ? "Publication..." : "Publier l'offre"}
          </Button>
        </form>
      </div>
    </div>
  );
}
