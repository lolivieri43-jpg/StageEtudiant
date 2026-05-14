import React from "react";
import { Link } from "react-router-dom";
import { XCircle } from "lucide-react";
import { Button } from "../components/ui/button";

export default function PaymentCancelPage() {
  return (
    <div className="min-h-screen pt-20 pb-12 bg-slate-50 grid place-items-center">
      <div className="card-soft p-10 max-w-md w-full mx-6 text-center" data-testid="payment-cancel-card">
        <XCircle className="w-16 h-16 text-slate-400 mx-auto mb-4" />
        <h1 className="text-2xl font-black mb-2">Paiement annulé</h1>
        <p className="text-slate-500 mb-6">Aucun montant n'a été débité. Vous pouvez réessayer à tout moment.</p>
        <Link to="/deals"><Button className="rounded-full bg-blue-600 hover:bg-blue-700">Retour aux bons plans</Button></Link>
      </div>
    </div>
  );
}
