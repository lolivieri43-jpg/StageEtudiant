import React, { useEffect, useState } from "react";
import api from "../lib/api";
import OfferCard from "../components/OfferCard";
import { Bookmark } from "lucide-react";

export default function SavedOffersPage() {
  const [offers, setOffers] = useState([]);
  useEffect(() => {
    api.get("/saved-offers").then((r) => setOffers(r.data));
  }, []);
  return (
    <div className="min-h-screen pt-20 pb-12 bg-slate-50">
      <div className="max-w-6xl mx-auto px-6">
        <h1 className="text-3xl font-black tracking-tight text-slate-900 mb-2 flex items-center gap-2"><Bookmark className="w-7 h-7 text-blue-500" />Offres sauvegardées</h1>
        <p className="text-slate-500 mb-6">{offers.length} offres mises de côté</p>
        {offers.length === 0 ? (
          <div className="card-soft p-12 text-center text-slate-400">Aucune offre sauvegardée pour le moment</div>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {offers.map(o => <OfferCard key={o.offer_id} offer={o} />)}
          </div>
        )}
      </div>
    </div>
  );
}
