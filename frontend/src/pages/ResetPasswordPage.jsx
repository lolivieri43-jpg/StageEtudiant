import React, { useState } from "react";
import { Link, useParams, useNavigate } from "react-router-dom";
import { Lock, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";

import api from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";

export default function ResetPasswordPage() {
  const { token } = useParams();
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (password.length < 8) {
      toast.error("Mot de passe trop court (8 caractères minimum)");
      return;
    }
    if (password !== confirm) {
      toast.error("Les deux mots de passe ne correspondent pas");
      return;
    }
    setLoading(true);
    try {
      await api.post("/auth/reset-password", { token, password });
      setDone(true);
      setTimeout(() => navigate("/login"), 2500);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Lien invalide ou expiré");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen pt-16 bg-mesh flex items-center justify-center p-6">
      <div className="card-soft w-full max-w-md p-8" data-testid="reset-password-card">
        {done ? (
          <div className="text-center space-y-4">
            <CheckCircle2 className="w-12 h-12 text-emerald-500 mx-auto" />
            <h1 className="text-2xl font-black tracking-tight text-slate-900">Mot de passe mis à jour</h1>
            <p className="text-slate-600">Vous allez être redirigé vers la connexion…</p>
            <Link to="/login" className="text-sm text-blue-600 font-semibold" data-testid="goto-login">
              Aller à la connexion
            </Link>
          </div>
        ) : (
          <>
            <h1 className="text-3xl font-black tracking-tight text-slate-900 mb-2">Nouveau mot de passe</h1>
            <p className="text-slate-500 mb-6">Choisissez un mot de passe d&apos;au moins 8 caractères.</p>
            <form onSubmit={submit} className="space-y-4">
              <div>
                <Label htmlFor="pw">Nouveau mot de passe</Label>
                <div className="relative mt-1">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                  <Input id="pw" type="password" required
                    data-testid="new-password"
                    value={password} onChange={(e) => setPassword(e.target.value)}
                    className="rounded-xl pl-9" />
                </div>
              </div>
              <div>
                <Label htmlFor="pw2">Confirmation</Label>
                <Input id="pw2" type="password" required
                  data-testid="confirm-password"
                  value={confirm} onChange={(e) => setConfirm(e.target.value)}
                  className="rounded-xl mt-1" />
              </div>
              <Button type="submit" disabled={loading || !password || !confirm}
                className="w-full rounded-xl bg-blue-600 hover:bg-blue-700 h-11"
                data-testid="reset-submit">
                {loading ? "Enregistrement…" : "Réinitialiser"}
              </Button>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
