import React from "react";
import { Loader2 } from "lucide-react";
import { Button } from "../ui/button";
import OfferCard from "../OfferCard";

/**
 * Loading / empty / grid state for the offers list.
 *
 * Props:
 * - loading  : bool
 * - offers   : array
 * - onReset  : called when the user clicks "Réinitialiser les filtres" in the empty state
 */
export default function OffersResults({ loading, offers, onReset }) {
  if (loading) {
    return (
      <div className="text-center py-12 text-slate-400 flex flex-col items-center gap-2" data-testid="results-loading">
        <Loader2 className="w-6 h-6 animate-spin" />
        Recherche en cours…
      </div>
    );
  }
  if (offers.length === 0) {
    return (
      <div className="card-soft p-12 text-center" data-testid="results-empty">
        <div className="text-slate-400 mb-2">Aucune offre trouvée</div>
        <p className="text-xs text-slate-500 mb-3">Essayez d&apos;élargir le rayon ou de retirer un filtre.</p>
        <Button variant="outline" onClick={onReset} className="rounded-full mt-2">Réinitialiser les filtres</Button>
      </div>
    );
  }
  return (
    <div className="grid sm:grid-cols-2 gap-4">
      {offers.map(o => <OfferCard key={o.offer_id} offer={o} />)}
    </div>
  );
}
