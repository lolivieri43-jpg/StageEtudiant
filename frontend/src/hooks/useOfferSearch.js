import { useEffect, useState } from "react";
import api from "../lib/api";

/**
 * Fetch offers from all sources (internal db, LBA, France Travail, keyless
 * aggregator) based on the currently-active URL filters. Returns
 * `{ offers, loading }`.
 *
 * `active` is the filter object produced by `readFromParams` and `paramsKey`
 * is `params.toString()` — passed as a dep so this re-runs only when the
 * URL search changes, not on every render.
 */
export default function useOfferSearch(active, paramsKey) {
  const [offers, setOffers] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const a = active;
    const lbaOnly = a.source === "La Bonne Alternance";
    const ftOnly  = a.source === "FranceTravail";

    const fetchLba = async () => {
      if (ftOnly) return [];
      if (!a.lba && !lbaOnly) return [];
      if (!lbaOnly && a.contract_type && a.contract_type !== "alternance") return [];
      try {
        const lbaCity = a.near_city || a.city;
        if (!lbaOnly && !a.company && !lbaCity && !a.region) return [];
        const lp = new URLSearchParams();
        if (lbaCity) lp.set("city", lbaCity);
        if (a.company) lp.set("romes", a.company);
        lp.set("radius", a.near_city ? a.distance_km : "30");
        lp.set("per_page", lbaOnly ? "60" : "30");
        const { data } = await api.get(`/lba/search?${lp.toString()}`);
        return data.results || [];
      } catch { return []; }
    };

    const fetchFt = async () => {
      const shouldFetchFt = ftOnly || (a.company && !lbaOnly);
      if (!shouldFetchFt) return [];
      try {
        const fp = new URLSearchParams();
        if (a.city) fp.set("city", a.city);
        if (a.region) fp.set("region", a.region);
        if (a.q) fp.set("q", a.q);
        if (a.company) fp.set("q", a.company);
        if (a.domain) fp.set("domain", a.domain);
        fp.set("per_page", "50");
        const { data } = await api.get(`/francetravail/search?${fp.toString()}`);
        return data.results || [];
      } catch { return []; }
    };

    const fetchInternal = async () => {
      if (lbaOnly || ftOnly) return [];
      if (a.near_city) {
        const p = new URLSearchParams();
        p.set("city", a.near_city);
        p.set("distance_km", a.distance_km);
        if (a.contract_type) p.set("contract_type", a.contract_type);
        if (a.source) p.set("source", a.source);
        p.set("limit", "200");
        const r = await api.get(`/offers-nearby?${p.toString()}`);
        return r.data;
      }
      const p = new URLSearchParams();
      if (a.q) p.set("q", a.q);
      if (a.region) p.set("region", a.region);
      if (a.city) p.set("city", a.city);
      if (a.contract_type) p.set("contract_type", a.contract_type);
      if (a.domain) p.set("domain", a.domain);
      if (a.level) p.set("level", a.level);
      if (a.remote) p.set("remote", "true");
      if (a.source) p.set("source", a.source);
      if (a.company) p.set("company", a.company);
      if (a.country) p.set("country", a.country);
      if (a.european) p.set("european_only", "true");
      p.set("limit", "300");
      const r = await api.get(`/offers?${p.toString()}`);
      return r.data;
    };

    const fetchKeyless = async () => {
      const EXT = new Set(["Adzuna","Jooble","EURES","Ashby","Arbeitnow","Remotive","RemoteOK","Jobicy","Greenhouse"]);
      if (lbaOnly || ftOnly) return [];
      if (a.source && !EXT.has(a.source)) return [];
      try {
        const ep = new URLSearchParams();
        if (a.company) ep.set("company", a.company);
        if (a.near_city) { ep.set("city", a.near_city); ep.set("radius_km", a.distance_km); }
        else if (a.city) ep.set("city", a.city);
        if (a.country) ep.set("country", a.country);
        if (a.european) ep.set("european_only", "true");
        const { data } = await api.get(`/external-offers/all?${ep.toString()}`);
        const all = data.results || [];
        return a.source ? all.filter(o => o.source === a.source) : all;
      } catch { return []; }
    };

    Promise.all([fetchInternal(), fetchLba(), fetchFt(), fetchKeyless()])
      .then(([internal, lba, ft, keyless]) => {
        const seen = new Set();
        const merged = [];
        for (const o of [...internal, ...lba, ...ft, ...keyless]) {
          const k = o.external_url || o.offer_id || o.siret;
          if (k && seen.has(k)) continue;
          seen.add(k);
          merged.push(o);
        }
        let final = merged;
        if (a.company) {
          const term = a.company.toLowerCase().normalize("NFD").replace(/\p{Diacritic}/gu, "").trim();
          final = merged.filter(o => {
            const name = (o.company_name || "").toLowerCase().normalize("NFD").replace(/\p{Diacritic}/gu, "");
            return name.includes(term);
          });
        }
        setOffers(final);
      })
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paramsKey]);

  return { offers, loading };
}
