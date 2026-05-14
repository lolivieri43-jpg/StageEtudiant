import React, { useEffect, useState } from "react";
import { useSearchParams, useNavigate, Link } from "react-router-dom";
import api from "../lib/api";
import { CheckCircle2, XCircle, Loader2 } from "lucide-react";
import { Button } from "../components/ui/button";

export default function PaymentSuccessPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const sessionId = params.get("session_id");
  const [status, setStatus] = useState("polling"); // polling, paid, failed, timeout
  const [tx, setTx] = useState(null);

  useEffect(() => {
    if (!sessionId) { setStatus("failed"); return; }
    let attempts = 0;
    const maxAttempts = 6;
    const poll = async () => {
      try {
        const { data } = await api.get(`/payments/status/${sessionId}`);
        setTx(data);
        if (data.payment_status === "paid") { setStatus("paid"); return; }
        if (data.status === "expired") { setStatus("failed"); return; }
        attempts++;
        if (attempts >= maxAttempts) { setStatus("timeout"); return; }
        setTimeout(poll, 2000);
      } catch {
        attempts++;
        if (attempts >= maxAttempts) setStatus("failed");
        else setTimeout(poll, 2000);
      }
    };
    poll();
  }, [sessionId]);

  return (
    <div className="min-h-screen pt-20 pb-12 bg-slate-50 grid place-items-center">
      <div className="card-soft p-10 max-w-md w-full mx-6 text-center" data-testid="payment-status-card">
        {status === "polling" && (
          <>
            <Loader2 className="w-12 h-12 text-blue-500 mx-auto animate-spin mb-4" />
            <h1 className="text-2xl font-black mb-2">Vérification du paiement...</h1>
            <p className="text-slate-500">Cela ne prend que quelques secondes.</p>
          </>
        )}
        {status === "paid" && (
          <>
            <CheckCircle2 className="w-16 h-16 text-emerald-500 mx-auto mb-4" />
            <h1 className="text-2xl font-black mb-2">Paiement confirmé !</h1>
            <p className="text-slate-500 mb-6">
              {tx?.kind === "subscription" ? "Votre abonnement Pro Bons Plans est actif." :
               tx?.kind === "boost" ? "Votre bon plan est mis en avant pendant 7 jours." :
               "Merci pour votre achat."}
            </p>
            <div className="flex flex-col gap-2">
              <Link to="/deals/mine"><Button className="rounded-full bg-blue-600 hover:bg-blue-700 w-full" data-testid="goto-mydeals">Voir mes bons plans</Button></Link>
              <Link to="/deals"><Button variant="outline" className="rounded-full w-full">Retour aux bons plans</Button></Link>
            </div>
          </>
        )}
        {(status === "failed" || status === "timeout") && (
          <>
            <XCircle className="w-16 h-16 text-rose-500 mx-auto mb-4" />
            <h1 className="text-2xl font-black mb-2">{status === "timeout" ? "Délai dépassé" : "Paiement échoué"}</h1>
            <p className="text-slate-500 mb-6">{status === "timeout" ? "Le paiement est toujours en cours de traitement." : "Le paiement n'a pas pu être finalisé."}</p>
            <Link to="/deals"><Button variant="outline" className="rounded-full">Retour</Button></Link>
          </>
        )}
      </div>
    </div>
  );
}
