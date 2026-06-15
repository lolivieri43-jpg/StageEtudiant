import React, { useState } from "react";
import { Mail, CheckCircle2, Loader2 } from "lucide-react";
import { toast } from "sonner";
import api from "../lib/api";

/**
 * Soft amber banner shown on the dashboard when the current user has not yet
 * confirmed their email. Lets the user request a fresh verification link
 * via /api/auth/send-verification.
 *
 * Returns null for users whose `email_verified === true` so the parent
 * doesn't need any conditional.
 */
export default function EmailVerificationBanner({ user }) {
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);

  if (!user || user.email_verified) return null;
  // Google-OAuth users land already verified; this is for the email/password flow.
  if (user.provider === "google") return null;

  const send = async () => {
    setSending(true);
    try {
      await api.post("/auth/send-verification");
      setSent(true);
      toast.success("Email de vérification envoyé");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Envoi impossible");
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900 rounded-2xl p-4 mb-5 flex items-center gap-3" data-testid="email-verification-banner">
      <Mail className="w-5 h-5 text-amber-700 shrink-0" />
      <div className="flex-1 min-w-0">
        <div className="font-bold text-amber-900 dark:text-amber-200 text-sm">Vérifiez votre adresse email</div>
        <div className="text-xs text-amber-800 dark:text-amber-300">
          Confirmez <b className="break-all">{user.email}</b> pour débloquer toutes les fonctionnalités.
        </div>
      </div>
      {sent ? (
        <div className="text-xs font-semibold text-emerald-700 inline-flex items-center gap-1">
          <CheckCircle2 className="w-4 h-4" />Envoyé
        </div>
      ) : (
        <button onClick={send} disabled={sending}
          className="text-xs font-bold text-amber-900 hover:text-amber-950 underline disabled:opacity-50 inline-flex items-center gap-1"
          data-testid="send-verification-btn">
          {sending && <Loader2 className="w-3 h-3 animate-spin" />}
          {sending ? "Envoi…" : "Renvoyer le lien"}
        </button>
      )}
    </div>
  );
}
