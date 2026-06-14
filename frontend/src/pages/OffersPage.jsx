import React, { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Filter, Map as MapIcon, List } from "lucide-react";
import { Button } from "../components/ui/button";

import api from "../lib/api";
import { readFromParams, writeToParams } from "../lib/offerFilters";
import AISearchBar from "../components/AISearchBar";
import OffersFiltersSidebar from "../components/offers/OffersFiltersSidebar";
import OffersRegionChips from "../components/offers/OffersRegionChips";
import OffersResults from "../components/offers/OffersResults";
import useOfferSearch from "../hooks/useOfferSearch";

/**
 * Top-level offers search page. Owns the URL <-> draft sync and delegates
 * UI to dedicated sub-components in `components/offers/` and the data
 * fetching to `useOfferSearch`.
 */
export default function OffersPage() {
  const [params, setParams] = useSearchParams();
  const [stats, setStats] = useState({});
  const [cityList, setCityList] = useState([]);
  const [mobileView, setMobileView] = useState("list");
  const [showFilters, setShowFilters] = useState(true);

  // Draft state — only applied on explicit submit.
  const [draft, setDraft] = useState(() => readFromParams(params));
  // Active filters reflect what's currently in the URL (drives data fetching).
  const active = readFromParams(params);

  // Stats + city list — one-shot.
  useEffect(() => {
    api.get("/offers/regions").then((r) => setStats(r.data)).catch(() => {});
    api.get("/cities").then((r) => setCityList(r.data.cities)).catch(() => {});
  }, []);

  // Re-sync draft whenever the URL changes externally (AI bar, browser back…).
  useEffect(() => {
    setDraft(readFromParams(params));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.toString()]);

  const { offers, loading } = useOfferSearch(active, params.toString());

  const applyFilters = (e) => {
    if (e?.preventDefault) e.preventDefault();
    setParams(writeToParams(draft));
  };
  const resetFilters = () => {
    const blank = readFromParams(new URLSearchParams());
    setDraft(blank);
    setParams(new URLSearchParams());
  };
  const clearRegion = () => {
    const p = new URLSearchParams(params);
    p.delete("region");
    setParams(p);
  };
  const toggleRegion = (r) => {
    const p = new URLSearchParams(params);
    if (active.region === r) p.delete("region"); else p.set("region", r);
    setParams(p);
  };

  const sidebar = (
    <OffersFiltersSidebar
      draft={draft}
      setDraft={setDraft}
      loading={loading}
      active={active}
      cityList={cityList}
      onApply={applyFilters}
      onReset={resetFilters}
      onClearRegion={clearRegion}
    />
  );

  return (
    <div className="min-h-screen pt-20 pb-12 bg-slate-50 dark:bg-slate-900">
      <div className="max-w-7xl mx-auto px-4 sm:px-6">
        <h1 className="text-3xl font-black tracking-tight text-slate-900 dark:text-slate-100 mb-2">Offres de stage & alternance</h1>
        <p className="text-slate-500 mb-4" data-testid="results-count">
          {loading ? "Chargement…" : (
            <><b className="text-slate-700 dark:text-slate-300">{offers.length}</b> offre{offers.length > 1 ? "s" : ""} trouvée{offers.length > 1 ? "s" : ""} · Sources multiples agrégées</>
          )}
        </p>

        <AISearchBar onCriteria={(c) => {
          const p = new URLSearchParams(params);
          if (c?.city) p.set("city", c.city);
          if (c?.contract_type) p.set("contract_type", c.contract_type);
          if (c?.keywords) p.set("q", c.keywords);
          if (c?.domain) p.set("domain", c.domain);
          setParams(p);
        }} />

        {/* Mobile toggle */}
        <div className="lg:hidden flex gap-2 mb-4">
          <Button onClick={() => setMobileView("list")} variant={mobileView === "list" ? "default" : "outline"} className="rounded-full flex-1" data-testid="mobile-list-btn"><List className="w-4 h-4 mr-1" />Liste</Button>
          <Button onClick={() => setMobileView("map")} variant={mobileView === "map" ? "default" : "outline"} className="rounded-full flex-1" data-testid="mobile-map-btn"><MapIcon className="w-4 h-4 mr-1" />Carte</Button>
          <Button onClick={() => setShowFilters(!showFilters)} variant="outline" className="rounded-full" data-testid="mobile-filters-btn">
            <Filter className="w-4 h-4 mr-1" />Filtres
          </Button>
        </div>

        {showFilters && <div className="lg:hidden mb-4">{sidebar}</div>}

        <div className="grid lg:grid-cols-[280px_1fr] gap-6">
          <div className="hidden lg:block">{sidebar}</div>
          <div>
            <div className={`${mobileView === "map" ? "block" : "hidden"} lg:block`}>
              <OffersRegionChips activeRegion={active.region} stats={stats} onToggleRegion={toggleRegion} />
            </div>
            <div className={`${mobileView === "list" ? "block" : "hidden"} lg:block`}>
              <OffersResults loading={loading} offers={offers} onReset={resetFilters} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
