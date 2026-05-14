import React, { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Tag, MapPin, Sparkles, Zap, Search, Plus, Bookmark, Share2 } from "lucide-react";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Input } from "../components/ui/input";

const CATEGORIES = [
  { id: "", label: "Tous" },
  { id: "food", label: "Restauration" },
  { id: "sport", label: "Sport" },
  { id: "culture", label: "Culture" },
  { id: "transport", label: "Transport" },
  { id: "study", label: "Études" },
  { id: "fashion", label: "Mode" },
  { id: "tech", label: "Tech" },
];

export default function DealsPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [deals, setDeals] = useState([]);
  const cat = params.get("category") || "";
  const city = params.get("city") || "";
  const q = params.get("q") || "";

  useEffect(() => {
    const p = new URLSearchParams();
    if (cat) p.set("category", cat);
    if (city) p.set("city", city);
    if (q) p.set("q", q);
    api.get(`/deals?${p.toString()}`).then((r) => setDeals(r.data));
  }, [cat, city, q]);

  const update = (k, v) => {
    const p = new URLSearchParams(params);
    if (v) p.set(k, v); else p.delete(k);
    setParams(p);
  };

  const now = new Date();
  const sponsored = deals.filter(d => d.sponsored_until && new Date(d.sponsored_until) > now);
  const boosted = deals.filter(d => d.boosted_until && new Date(d.boosted_until) > now && !sponsored.includes(d));
  const regular = deals.filter(d => !sponsored.includes(d) && !boosted.includes(d));

  return (
    <div className="min-h-screen pt-20 pb-12 bg-slate-50">
      <div className="max-w-7xl mx-auto px-6">
        <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4 mb-8">
          <div>
            <span className="text-xs font-bold uppercase tracking-[0.15em] text-violet-600">Étudiants & Entreprises</span>
            <h1 className="text-3xl sm:text-4xl font-black tracking-tight text-slate-900 mt-1">Bons plans étudiants</h1>
            <p className="text-slate-500 mt-1">Réductions, codes promo et avantages près de chez toi</p>
          </div>
          {user && (
            <Link to="/deals/new"><Button className="rounded-full bg-blue-600 hover:bg-blue-700" data-testid="new-deal-btn"><Plus className="w-4 h-4 mr-1" />Proposer un bon plan</Button></Link>
          )}
        </div>

        {/* Filters */}
        <div className="card-soft p-4 mb-6">
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <Input value={q} onChange={(e) => update("q", e.target.value)} placeholder="Rechercher..." className="rounded-full pl-9 bg-slate-50 border-0" data-testid="deals-search" />
            </div>
            <Input value={city} onChange={(e) => update("city", e.target.value)} placeholder="Ville" className="rounded-full bg-slate-50 border-0 max-w-[200px]" data-testid="deals-city" />
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {CATEGORIES.map(c => (
              <button
                key={c.id || "all"}
                onClick={() => update("category", c.id)}
                className={`px-4 py-1.5 rounded-full text-xs font-bold transition-all ${cat === c.id ? "bg-violet-600 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}
                data-testid={`cat-${c.id || "all"}`}
              >
                {c.label}
              </button>
            ))}
          </div>
        </div>

        {sponsored.length > 0 && (
          <Section title="Bons plans sponsorisés" icon={Sparkles} color="amber" deals={sponsored} badge="Sponsorisé" badgeColor="bg-amber-100 text-amber-700" />
        )}
        {boosted.length > 0 && (
          <Section title="Mis en avant" icon={Zap} color="violet" deals={boosted} badge="Mis en avant" badgeColor="bg-violet-100 text-violet-700" />
        )}
        <Section title="Tous les bons plans" icon={Tag} color="blue" deals={regular} />

        {deals.length === 0 && (
          <div className="card-soft p-12 text-center">
            <Tag className="w-10 h-10 mx-auto text-slate-300 mb-3" />
            <div className="text-slate-500">Aucun bon plan pour le moment</div>
            {user && <Link to="/deals/new" className="text-blue-600 font-semibold mt-2 inline-block">Proposez le premier !</Link>}
          </div>
        )}
      </div>
    </div>
  );
}

const Section = ({ title, icon: Icon, color, deals, badge, badgeColor }) => {
  if (deals.length === 0) return null;
  return (
    <div className="mb-8">
      <h2 className={`flex items-center gap-2 text-lg font-bold mb-4 text-slate-900`}>
        <Icon className={`w-5 h-5 text-${color}-500`} />
        {title} <span className="text-slate-400 text-sm font-normal">({deals.length})</span>
      </h2>
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
        {deals.map(d => <DealCard key={d.deal_id} deal={d} badge={badge} badgeColor={badgeColor} />)}
      </div>
    </div>
  );
};

export const DealCard = ({ deal, badge, badgeColor }) => (
  <Link to={`/deals/${deal.deal_id}`} className="card-soft overflow-hidden hover-lift hover:border-violet-300 block" data-testid={`deal-card-${deal.deal_id}`}>
    <div className="aspect-[16/9] bg-gradient-to-br from-violet-100 to-blue-100 relative overflow-hidden">
      {deal.image && <img src={deal.image} alt="" className="w-full h-full object-cover" />}
      {deal.discount && (
        <div className="absolute top-3 left-3 bg-violet-600 text-white text-xs font-black px-3 py-1.5 rounded-full">{deal.discount}</div>
      )}
      {badge && (
        <div className={`absolute top-3 right-3 ${badgeColor} text-[10px] font-bold px-2 py-1 rounded-full flex items-center gap-1`}>
          <Sparkles className="w-3 h-3" />{badge}
        </div>
      )}
    </div>
    <div className="p-5">
      <div className="text-xs text-slate-500 mb-1 flex items-center gap-1">
        <Tag className="w-3 h-3" /> {deal.category || "general"}
        {deal.city && <><span>·</span><MapPin className="w-3 h-3" />{deal.city}</>}
      </div>
      <h3 className="font-bold text-slate-900 leading-snug truncate">{deal.title}</h3>
      <p className="text-sm text-slate-500 mt-1 line-clamp-2">{deal.description}</p>
      <div className="text-xs text-slate-400 mt-3">par {deal.author_name}</div>
    </div>
  </Link>
);
