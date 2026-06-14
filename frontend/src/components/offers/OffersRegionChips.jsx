import React from "react";
import { REGIONS_LIST } from "../../lib/offerFilters";

/**
 * Horizontal chip list of French regions used as a quick filter on top of the
 * results pane. Highlights the currently-active region from the URL.
 */
export default function OffersRegionChips({ activeRegion, stats, onToggleRegion }) {
  return (
    <div className="card-soft p-5 mb-6">
      <h3 className="font-bold text-slate-900 dark:text-slate-100 mb-3">Filtrer par région</h3>
      <div className="flex flex-wrap gap-2">
        {REGIONS_LIST.map(r => {
          const found = stats?.by_region?.find(s => s.region === r);
          return (
            <button
              key={r}
              onClick={() => onToggleRegion(r)}
              className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-all ${activeRegion === r ? "bg-blue-600 text-white" : "bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700"}`}
              data-testid={`region-chip-${r.replace(/\s|'|-/g, "_")}`}
            >
              {r}
              {found && <span className="ml-1.5 text-[10px] opacity-70">({found.offers})</span>}
            </button>
          );
        })}
      </div>
    </div>
  );
}
