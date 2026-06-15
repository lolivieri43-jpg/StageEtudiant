import React, { useState } from "react";
import { Link } from "react-router-dom";
import { Mail, ArrowLeft, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";

import api from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.post("/auth/forgot-password", { email });
      setSent(true);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erreur");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen pt-16 bg-mesh flex items-center justify-center p-6">
      <div className="card-soft w-full max-w-md p-8" data-testid="forgot-password-card">
        {sent ? (
          <div className="text-center space-y-4">
            <CheckCircle2 className="w-12 h-12 text-emerald-500 mx-auto" />
            <h1 className="text-2xl font-black tracking-tight text-slate-900">Email envoyé</h1>
            <p className="text-slate-600">
              Si l&apos;adresse <b>{email}</b> correspond à un compte, vous recevrez un lien
              de réinitialisation dans quelques instants.
            </p>
            <p className="text-xs text-slate-400">Le lien expire dans 1 heure.</p>
            <Link to="/login" className="inline-flex items-center text-sm text-blue-600 font-semibold mt-4" data-testid="back-to-login">
              <ArrowLeft className="w-4 h-4 mr-1" />Retour à la connexion
            </Link>
          </div>
        ) : (
          <>
            <Link to="/login" className="inline-flex items-center text-xs text-slate-500 hover:text-slate-700 mb-4">
              <ArrowLeft className="w-3.5 h-3.5 mr-1" />Connexion
            </Link>
            <h1 className="text-3xl font-black tracking-tight text-slate-900 mb-2">Mot de passe oublié</h1>
            <p className="text-slate-500 mb-6">Indiquez votre email — nous vous enverrons un lien de réinitialisation.</p>
            <form onSubmit={submit} className="space-y-4">
              <div>
                <Label htmlFor="email">Email</Label>
                <div className="relative mt-1">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                  <Input id="email" type="email" required
                    data-testid="forgot-email"
                    value={email} onChange={(e) => setEmail(e.target.value)}
                    placeholder="vous@exemple.com" className="rounded-xl pl-9" />
                </div>
              </div>
              <Button type="submit" disabled={loading || !email}
                className="w-full rounded-xl bg-blue-600 hover:bg-blue-700 h-11"
                data-testid="forgot-submit">
                {loading ? "Envoi en cours…" : "Envoyer le lien"}
              </Button>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
