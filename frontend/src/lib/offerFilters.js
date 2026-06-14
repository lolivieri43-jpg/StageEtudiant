// Filter helpers shared between OffersPage and any place that reads/writes
// the offer-search URL params. Kept tiny on purpose.
export const FILTER_KEYS = [
  "q", "region", "city", "contract_type", "domain", "level",
  "remote", "source", "near_city", "distance_km", "lba",
  "company", "country", "european",
];

export function readFromParams(params) {
  return {
    q: params.get("q") || "",
    region: params.get("region") || "",
    city: params.get("city") || "",
    contract_type: params.get("contract_type") || "",
    domain: params.get("domain") || "",
    level: params.get("level") || "",
    remote: params.get("remote") === "true",
    source: params.get("source") || "",
    near_city: params.get("near_city") || "",
    distance_km: params.get("distance_km") || "50",
    lba: params.get("lba") !== "0", // default true
    company: params.get("company") || "",
    country: params.get("country") || "",
    european: params.get("european") === "1",
  };
}

export function writeToParams(draft) {
  const p = new URLSearchParams();
  if (draft.q) p.set("q", draft.q);
  if (draft.region) p.set("region", draft.region);
  if (draft.city) p.set("city", draft.city);
  if (draft.contract_type) p.set("contract_type", draft.contract_type);
  if (draft.domain) p.set("domain", draft.domain);
  if (draft.level) p.set("level", draft.level);
  if (draft.remote) p.set("remote", "true");
  if (draft.source) p.set("source", draft.source);
  if (draft.near_city) p.set("near_city", draft.near_city);
  if (draft.near_city && draft.distance_km) p.set("distance_km", draft.distance_km);
  if (draft.lba === false) p.set("lba", "0");
  if (draft.company) p.set("company", draft.company);
  if (draft.country) p.set("country", draft.country);
  if (draft.european) p.set("european", "1");
  return p;
}

export const REGIONS_LIST = [
  "Île-de-France", "Auvergne-Rhône-Alpes", "Nouvelle-Aquitaine", "Occitanie", "Hauts-de-France",
  "Provence-Alpes-Côte d'Azur", "Grand Est", "Pays de la Loire", "Bretagne", "Normandie",
  "Bourgogne-Franche-Comté", "Centre-Val de Loire", "Corse",
];

export const SOURCES = [
  { id: "StageConnect", label: "StageEtudiant" },
  { id: "La Bonne Alternance", label: "La Bonne Alternance ★" },
  { id: "FranceTravail", label: "France Travail ✓" },
  { id: "Adzuna", label: "Adzuna" },
  { id: "EURES", label: "EURES (UE)" },
  { id: "Ashby", label: "Ashby" },
  { id: "Arbeitnow", label: "Arbeitnow" },
  { id: "Remotive", label: "Remotive" },
  { id: "RemoteOK", label: "RemoteOK" },
  { id: "Jobicy", label: "Jobicy" },
  { id: "Greenhouse", label: "Greenhouse" },
];
