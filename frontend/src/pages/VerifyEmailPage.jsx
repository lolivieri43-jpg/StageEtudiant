import React, { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { CheckCircle2, XCircle, Loader2 } from "lucide-react";

import api from "../lib/api";

/**
 * Lands the user after they click the verification link in their email.
 * Reads `?token=...` from the URL, calls /auth/verify-email, displays
 * success or failure.
 */
export default function VerifyEmailPage() {
  const [params] = useSearchParams();
  const token = params.get("token");
  const [state, setState] = useState("loading"); // loading | ok | error
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!token) {
      setState("error");
      setError("Lien invalide (token manquant)");
      return;
    }
    api.get(`/auth/verify-email?token=${encodeURIComponent(token)}`)
      .then(() => setState("ok"))
      .catch((err) => {
        setState("error");
        setError(err.response?.data?.detail || "Lien invalide ou expiré");
      });
  }, [token]);

  return (
    <div className="min-h-screen pt-16 bg-mesh flex items-center justify-center p-6">
      <div className="card-soft w-full max-w-md p-8 text-center" data-testid="verify-email-card">
        {state === "loading" && (
          <>
            <Loader2 className="w-12 h-12 text-blue-500 mx-auto animate-spin" />
            <p className="mt-4 text-slate-500">Vérification en cours…</p>
          </>
        )}
        {state === "ok" && (
          <>
            <CheckCircle2 className="w-12 h-12 text-emerald-500 mx-auto" />
            <h1 className="text-2xl font-black tracking-tight text-slate-900 mt-3 mb-2">Email vérifié</h1>
            <p className="text-slate-600">Votre adresse email est maintenant confirmée.</p>
            <Link to="/dashboard" className="inline-block mt-4 text-sm text-blue-600 font-semibold" data-testid="verify-goto-dashboard">
              Aller à mon tableau de bord
            </Link>
          </>
        )}
        {state === "error" && (
          <>
            <XCircle className="w-12 h-12 text-rose-500 mx-auto" />
            <h1 className="text-2xl font-black tracking-tight text-slate-900 mt-3 mb-2">Échec de vérification</h1>
            <p className="text-slate-600">{error}</p>
            <Link to="/login" className="inline-block mt-4 text-sm text-blue-600 font-semibold">
              Retour à la connexion
            </Link>
          </>
        )}
      </div>
    </div>
  );
}
