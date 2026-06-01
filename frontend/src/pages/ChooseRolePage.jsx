import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import api from "../lib/api";
import { Button } from "../components/ui/button";
import { GraduationCap, Briefcase, Loader2 } from "lucide-react";
import { toast } from "sonner";

export default function ChooseRolePage() {
  const { user, refreshUser } = useAuth();
  const [saving, setSaving] = useState(false);
  const [picked, setPicked] = useState(null);
  const navigate = useNavigate();

  // If the role is already set, send them where they belong (idempotent).
  if (user?.role === "candidate" || user?.role === "company") {
    navigate("/dashboard", { replace: true });
    return null;
  }
  if (user?.role === "admin") {
    navigate("/admin", { replace: true });
    return null;
  }
  if (!user) {
    return <div className="pt-24 text-center text-slate-400">Chargement…</div>;
  }

  const submit = async (role) => {
    setSaving(true);
    setPicked(role);
    try {
      await api.post("/auth/choose-role", { role });
      await refreshUser();
      toast.success("Compte finalisé !");
      navigate(role === "company" ? "/dashboard" : "/dashboard");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erreur");
    } finally {
      setSaving(false);
      setPicked(null);
    }
  };

  return (
    <div className="min-h-screen pt-20 pb-12 bg-slate-50 dark:bg-slate-900 flex items-center justify-center px-4">
      <div className="card-soft w-full max-w-2xl p-8 sm:p-10" data-testid="choose-role-card">
        <h1 className="text-3xl font-black tracking-tight text-slate-900 dark:text-slate-100 mb-2">
          Bienvenue, {user.name?.split(" ")[0] || "à toi"} !
        </h1>
        <p className="text-slate-500 mb-8">Pour finaliser ton inscription, choisis ton type de compte.</p>

        <div className="grid sm:grid-cols-2 gap-4">
          <button
            data-testid="choose-candidate"
            disabled={saving}
            onClick={() => submit("candidate")}
            className="group text-left p-6 rounded-2xl border-2 border-slate-200 dark:border-slate-700 hover:border-blue-500 hover:bg-blue-50/40 dark:hover:bg-blue-950/20 transition-all disabled:opacity-50"
          >
            <div className="w-12 h-12 rounded-xl bg-blue-100 text-blue-700 grid place-items-center mb-3">
              {picked === "candidate" ? <Loader2 className="w-5 h-5 animate-spin" /> : <GraduationCap className="w-6 h-6" />}
            </div>
            <h2 className="font-black text-lg text-slate-900 dark:text-slate-100 group-hover:text-blue-700">Étudiant / Alternant</h2>
            <p className="text-sm text-slate-500 mt-1">Rechercher des stages, l&apos;alternance, candidater, échanger avec des entreprises.</p>
          </button>

          <button
            data-testid="choose-company"
            disabled={saving}
            onClick={() => submit("company")}
            className="group text-left p-6 rounded-2xl border-2 border-slate-200 dark:border-slate-700 hover:border-violet-500 hover:bg-violet-50/40 dark:hover:bg-violet-950/20 transition-all disabled:opacity-50"
          >
            <div className="w-12 h-12 rounded-xl bg-violet-100 text-violet-700 grid place-items-center mb-3">
              {picked === "company" ? <Loader2 className="w-5 h-5 animate-spin" /> : <Briefcase className="w-6 h-6" />}
            </div>
            <h2 className="font-black text-lg text-slate-900 dark:text-slate-100 group-hover:text-violet-700">Entreprise / CFA</h2>
            <p className="text-sm text-slate-500 mt-1">Publier des offres, recevoir des candidatures, rechercher des étudiants.</p>
          </button>
        </div>

        <p className="text-xs text-slate-400 mt-6 text-center">
          Tu pourras compléter ton profil par la suite. Ce choix est définitif pour le rôle.
        </p>
      </div>
    </div>
  );
}
