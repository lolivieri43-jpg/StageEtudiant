import React, { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { toast } from "sonner";
import { Building2, GraduationCap } from "lucide-react";

export default function RegisterPage() {
  const navigate = useNavigate();
  const { register } = useAuth();
  const [params] = useSearchParams();
  const [role, setRole] = useState(params.get("role") || "candidate");
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await register({ ...form, role });
      toast.success("Compte créé !");
      navigate("/dashboard");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erreur");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen pt-16 bg-mesh py-12 px-6">
      <div className="max-w-2xl mx-auto">
        <div className="text-center mb-8">
          <h1 className="text-3xl sm:text-4xl font-black tracking-tight text-slate-900 mb-2">Créer un compte</h1>
          <p className="text-slate-500">Choisis le type de compte qui te correspond</p>
        </div>

        <div className="grid grid-cols-2 gap-4 mb-6">
          <button onClick={() => setRole("candidate")} className={`card-soft p-5 text-left border-2 ${role === "candidate" ? "border-blue-500 ring-4 ring-blue-100" : "border-transparent"}`} data-testid="role-candidate">
            <GraduationCap className="w-7 h-7 text-blue-600 mb-2" />
            <div className="font-bold text-slate-900">Stagiaire / Alternant</div>
            <div className="text-xs text-slate-500 mt-1">Je cherche un stage ou une alternance</div>
          </button>
          <button onClick={() => setRole("company")} className={`card-soft p-5 text-left border-2 ${role === "company" ? "border-violet-500 ring-4 ring-violet-100" : "border-transparent"}`} data-testid="role-company">
            <Building2 className="w-7 h-7 text-violet-600 mb-2" />
            <div className="font-bold text-slate-900">Entreprise</div>
            <div className="text-xs text-slate-500 mt-1">Je recrute des stagiaires/alternants</div>
          </button>
        </div>

        <form onSubmit={submit} className="card-soft p-8 space-y-4">
          <div>
            <Label>{role === "company" ? "Nom de l'entreprise" : "Nom et prénom"}</Label>
            <Input data-testid="register-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required className="rounded-xl mt-1" />
          </div>
          <div>
            <Label>Email {role === "company" && "professionnel"}</Label>
            <Input data-testid="register-email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required className="rounded-xl mt-1" />
          </div>
          <div>
            <Label>Mot de passe</Label>
            <Input data-testid="register-password" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required minLength={6} className="rounded-xl mt-1" />
          </div>
          <Button type="submit" disabled={loading} className="w-full rounded-xl bg-blue-600 hover:bg-blue-700 h-11" data-testid="register-submit">
            {loading ? "Création..." : "Créer mon compte"}
          </Button>
          <p className="text-center text-sm text-slate-500">
            Déjà un compte ? <Link to="/login" className="text-blue-600 font-semibold" data-testid="register-to-login">Se connecter</Link>
          </p>
        </form>
      </div>
    </div>
  );
}
