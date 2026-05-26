import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Search, ArrowRight, CheckCircle2, Sparkles, TrendingUp, Users, Briefcase } from "lucide-react";
import { Button } from "../components/ui/button";
import FranceMap from "../components/FranceMap";
import OfferCard from "../components/OfferCard";
import PlatformCounter from "../components/PlatformCounter";
import AISearchBar from "../components/AISearchBar";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";

export default function LandingPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [offers, setOffers] = useState([]);
  const [companies, setCompanies] = useState([]);
  const [candidates, setCandidates] = useState([]);
  const [stats, setStats] = useState({});
  const [q, setQ] = useState("");
  const [city, setCity] = useState("");
  const [ct, setCt] = useState("");

  useEffect(() => {
    api.post("/seed").catch(() => {});
    (async () => {
      try {
        const [o, c, ca, s] = await Promise.all([
          api.get("/offers?limit=6"),
          api.get("/users?role=company&limit=8"),
          api.get("/candidates/featured?limit=8"),
          api.get("/offers/regions"),
        ]);
        setOffers(o.data);
        setCompanies(c.data);
        setCandidates(ca.data);
        setStats(s.data);
      } catch {}
    })();
  }, []);

  const search = (e) => {
    e?.preventDefault();
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (city) params.set("city", city);
    if (ct) params.set("contract_type", ct);
    navigate(`/offers?${params.toString()}`);
  };

  return (
    <div className="min-h-screen pt-16">
      {/* Hero */}
      <section className="relative bg-mesh pt-16 pb-24 overflow-hidden">
        <div className="max-w-7xl mx-auto px-6 grid lg:grid-cols-2 gap-12 items-center">
          <div>
            <div className="inline-flex items-center gap-2 bg-violet-100 text-violet-700 px-3 py-1.5 rounded-full text-xs font-bold mb-6">
              <Sparkles className="w-3.5 h-3.5" />
              La plateforme N°1 du stage et de l'alternance
            </div>
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-black tracking-tight text-slate-900 leading-[1.05] mb-6" data-testid="hero-title">
              Trouve ton <span className="gradient-text">stage</span> ou ton <span className="gradient-text">alternance</span> près de chez toi
            </h1>
            <p className="text-lg text-slate-600 mb-8 leading-relaxed max-w-xl">
              Connecte-toi avec des entreprises françaises qui recrutent, postule en un clic, et développe ton réseau professionnel dès aujourd'hui.
            </p>

            <form onSubmit={search} className="bg-white rounded-2xl p-2 border border-slate-200 shadow-[0_12px_40px_rgba(15,23,42,0.06)] flex flex-col md:flex-row gap-2" data-testid="hero-search">
              <div className="flex items-center gap-2 flex-1 px-3">
                <Search className="w-4 h-4 text-slate-400" />
                <input
                  data-testid="hero-search-query"
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  placeholder="Métier, domaine..."
                  className="w-full h-11 outline-none text-sm bg-transparent"
                />
              </div>
              <div className="flex items-center gap-2 flex-1 px-3 md:border-l md:border-slate-200">
                <input
                  data-testid="hero-search-city"
                  value={city}
                  onChange={(e) => setCity(e.target.value)}
                  placeholder="Ville ou région"
                  className="w-full h-11 outline-none text-sm bg-transparent"
                />
              </div>
              <select
                data-testid="hero-search-contract"
                value={ct}
                onChange={(e) => setCt(e.target.value)}
                className="md:border-l md:border-slate-200 px-3 h-11 text-sm bg-transparent outline-none"
              >
                <option value="">Tout type</option>
                <option value="stage">Stage</option>
                <option value="alternance">Alternance</option>
              </select>
              <Button type="submit" className="rounded-xl bg-blue-600 hover:bg-blue-700 h-11 px-6" data-testid="hero-search-submit">
                Rechercher <ArrowRight className="w-4 h-4 ml-1" />
              </Button>
            </form>

            <div className="mt-6">
              <AISearchBar />
            </div>

            <div className="mt-8 flex flex-wrap items-center gap-6 text-sm text-slate-600">
              <div className="flex items-center gap-2"><CheckCircle2 className="w-4 h-4 text-emerald-500" />+1200 entreprises</div>
              <div className="flex items-center gap-2"><CheckCircle2 className="w-4 h-4 text-emerald-500" />Offres vérifiées</div>
              <div className="flex items-center gap-2"><CheckCircle2 className="w-4 h-4 text-emerald-500" />100% gratuit pour les candidats</div>
            </div>

            <div className="mt-4"><PlatformCounter variant="compact" /></div>

            {!user && (
              <div className="mt-8 flex flex-wrap gap-3">
                <Link to="/register?role=candidate"><Button className="rounded-full bg-blue-600 hover:bg-blue-700" data-testid="cta-candidate">Je suis étudiant·e</Button></Link>
                <Link to="/register?role=company"><Button variant="outline" className="rounded-full" data-testid="cta-company">Je suis une entreprise</Button></Link>
              </div>
            )}
          </div>

          <div className="relative">
            <div className="absolute -top-6 -left-6 w-32 h-32 bg-violet-200 rounded-full blur-3xl opacity-60"></div>
            <div className="absolute -bottom-6 -right-6 w-40 h-40 bg-blue-200 rounded-full blur-3xl opacity-60"></div>
            <div className="relative card-soft p-2 overflow-hidden">
              <img src="https://images.unsplash.com/photo-1758691736975-9f7f643d178e?w=900" alt="" className="rounded-xl w-full object-cover h-[420px]" />
            </div>
            <div className="absolute -bottom-8 -left-4 card-soft p-4 max-w-[200px]">
              <div className="flex items-center gap-2 mb-1"><TrendingUp className="w-4 h-4 text-emerald-500" /><span className="text-xs font-bold text-slate-700">Cette semaine</span></div>
              <div className="text-2xl font-black gradient-text">+247</div>
              <div className="text-xs text-slate-500">nouvelles offres</div>
            </div>
          </div>
        </div>
      </section>

      {/* Regions overview (no map) */}
      <section className="py-20 bg-white border-y border-slate-200">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center mb-10">
            <span className="text-xs font-bold uppercase tracking-[0.15em] text-violet-600">Explorer par région</span>
            <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-slate-900 mt-2 mb-3">Des opportunités partout en France</h2>
            <p className="text-slate-600 max-w-2xl mx-auto">Cliquez sur une région pour découvrir les entreprises qui recrutent et les offres disponibles.</p>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
            {(stats.by_region || []).slice(0, 12).map((r) => (
              <button key={r.region} onClick={() => navigate(`/offers?region=${encodeURIComponent(r.region)}`)} className="card-soft p-5 text-left hover-lift hover:border-blue-300" data-testid={`region-card-${r.region.replace(/\s/g, "_")}`}>
                <div className="text-xs text-slate-500 mb-1 truncate">{r.region}</div>
                <div className="text-3xl font-black gradient-text">{r.offers}</div>
                <div className="text-xs text-slate-500 mt-1">{r.companies} entreprises</div>
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* Latest offers */}
      <section className="py-20">
        <div className="max-w-7xl mx-auto px-6">
          <div className="flex items-end justify-between mb-8">
            <div>
              <span className="text-xs font-bold uppercase tracking-[0.15em] text-violet-600">Fraîchement publiées</span>
              <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-slate-900 mt-2">Dernières offres</h2>
            </div>
            <Link to="/offers" className="text-blue-600 font-semibold flex items-center gap-1 hover:gap-2 transition-all" data-testid="see-all-offers">
              Voir toutes les offres <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {offers.map((o) => <OfferCard key={o.offer_id} offer={o} />)}
          </div>
        </div>
      </section>

      {/* Companies */}
      <section className="py-20 bg-slate-50 border-y border-slate-200">
        <div className="max-w-7xl mx-auto px-6">
          <div className="flex items-end justify-between mb-8">
            <div>
              <span className="text-xs font-bold uppercase tracking-[0.15em] text-blue-600">Ils recrutent</span>
              <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-slate-900 mt-2">Entreprises actives</h2>
            </div>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-5">
            {companies.map((c) => (
              <Link key={c.user_id} to={`/profile/${c.user_id}`} className="card-soft p-5 hover-lift hover:border-blue-300" data-testid={`company-card-${c.user_id}`}>
                <div className="w-14 h-14 rounded-2xl bg-slate-100 overflow-hidden mb-3 grid place-items-center font-bold text-slate-400">
                  {c.profile?.logo ? <img src={c.profile.logo} className="w-full h-full object-cover" alt="" /> : c.name?.[0]}
                </div>
                <div className="flex items-center gap-1.5 mb-1">
                  <div className="font-bold text-slate-900 truncate">{c.profile?.company_name || c.name}</div>
                  {c.profile?.verified && <CheckCircle2 className="w-4 h-4 text-blue-500" />}
                </div>
                <div className="text-xs text-slate-500">{c.profile?.sector} · {c.profile?.city}</div>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* Featured candidates with premium priority */}
      <section className="py-20">
        <div className="max-w-7xl mx-auto px-6">
          <div className="flex items-end justify-between mb-8">
            <div>
              <span className="text-xs font-bold uppercase tracking-[0.15em] text-violet-600">Talents disponibles</span>
              <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-slate-900 mt-2">Stagiaires & alternants en vedette</h2>
            </div>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-5">
            {candidates.map((c) => (
              <Link key={c.user_id} to={`/profile/${c.user_id}`} className={`card-soft p-5 hover-lift relative ${c.is_premium ? "ring-2 ring-amber-300 border-amber-200" : "hover:border-violet-300"}`} data-testid={`candidate-card-${c.user_id}`}>
                {c.is_premium && (
                  <div className="absolute -top-2 -right-2 bg-gradient-to-r from-amber-500 to-orange-500 text-white text-[10px] font-black uppercase px-2 py-0.5 rounded-full shadow-md">Premium</div>
                )}
                <div className="flex items-center gap-3 mb-3">
                  <div className="w-12 h-12 rounded-full overflow-hidden bg-gradient-to-br from-blue-400 to-violet-400 grid place-items-center text-white font-bold shrink-0">
                    {c.profile?.avatar ? <img src={c.profile.avatar.startsWith("/api") ? `${process.env.REACT_APP_BACKEND_URL}${c.profile.avatar}` : c.profile.avatar} className="w-full h-full object-cover" alt="" /> : c.name?.[0]}
                  </div>
                  <div className="min-w-0">
                    <div className="font-bold text-slate-900 truncate">{c.name}</div>
                    <div className="text-xs text-slate-500 truncate">{c.profile?.title || c.profile?.domain}</div>
                  </div>
                </div>
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5">
                    <span className={`w-2 h-2 rounded-full ${c.profile?.status === "en_recherche" ? "bg-emerald-500" : "bg-amber-400"}`} />
                    <span className="text-xs text-slate-600">{c.profile?.status === "en_recherche" ? "En recherche" : "À l'écoute"}</span>
                  </div>
                  {c.profile?.contract_type && (
                    <span className="text-[10px] font-bold uppercase text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full">{c.profile.contract_type === "stage" ? "Stage" : "Alt."}</span>
                  )}
                </div>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* Bons plans teaser */}
      <section className="py-20 bg-gradient-to-br from-violet-50 to-blue-50">
        <div className="max-w-5xl mx-auto px-6 grid md:grid-cols-2 gap-10 items-center">
          <div>
            <span className="text-xs font-bold uppercase tracking-[0.15em] text-violet-600">Nouveau</span>
            <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-slate-900 mt-2 mb-4">Bons plans étudiants</h2>
            <p className="text-slate-600 mb-6 leading-relaxed">
              Réductions, codes promo et avantages partagés par la communauté et les entreprises partenaires. <strong>Gratuit pour les étudiants.</strong>
            </p>
            <div className="flex flex-wrap gap-3">
              <Link to="/deals"><Button className="rounded-full bg-violet-600 hover:bg-violet-700" data-testid="cta-deals">Découvrir les bons plans</Button></Link>
              <Link to="/payments/subscribe"><Button variant="outline" className="rounded-full" data-testid="cta-subscribe">Entreprise : 1€/mois</Button></Link>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            {["-30% Pizza", "Code -20%", "Cinéma 5€", "Sport offert"].map((tag, i) => (
              <div key={i} className="card-soft p-5 text-center hover-lift">
                <div className="text-2xl font-black gradient-text">{tag.split(" ")[0]}</div>
                <div className="text-xs text-slate-500 mt-1">{tag.split(" ").slice(1).join(" ")}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-24 bg-gradient-to-br from-blue-600 to-violet-700 text-white">
        <div className="max-w-4xl mx-auto px-6 text-center">
          <h2 className="text-4xl sm:text-5xl font-black mb-6">Prêt à lancer ta carrière ?</h2>
          <p className="text-blue-100 text-lg mb-8">Rejoins des milliers d'étudiants et d'entreprises qui font confiance à StageEtudiant.</p>
          <div className="flex flex-wrap justify-center gap-3">
            <Link to="/register?role=candidate"><Button className="rounded-full bg-white text-blue-700 hover:bg-blue-50 h-12 px-6" data-testid="cta-bottom-candidate">Créer un compte étudiant</Button></Link>
            <Link to="/register?role=company"><Button variant="outline" className="rounded-full border-white text-white hover:bg-white hover:text-blue-700 h-12 px-6 bg-transparent" data-testid="cta-bottom-company">Créer un compte entreprise</Button></Link>
          </div>
        </div>
      </section>

      <footer className="bg-slate-900 text-slate-400 py-12">
        <div className="max-w-7xl mx-auto px-6 text-center text-sm">
          <div className="font-black text-white text-lg mb-2">StageEtudiant</div>
          <p>© 2026 — La plateforme française du stage et de l'alternance</p>
        </div>
      </footer>
    </div>
  );
}
