import React, { useState } from "react";

// Approximate stylized regions of metropolitan France as polygons (no external library).
const REGIONS = [
  { name: "Hauts-de-France", d: "M260,55 L355,55 L370,110 L290,125 L260,100 Z" },
  { name: "Normandie", d: "M170,90 L260,100 L290,125 L260,165 L180,150 Z" },
  { name: "Île-de-France", d: "M275,135 L320,130 L325,165 L285,170 Z" },
  { name: "Grand Est", d: "M320,90 L420,80 L440,160 L380,180 L325,165 L320,130 Z" },
  { name: "Bretagne", d: "M55,170 L170,150 L180,200 L75,220 Z" },
  { name: "Pays de la Loire", d: "M170,170 L255,170 L260,230 L180,235 L160,200 Z" },
  { name: "Centre-Val de Loire", d: "M255,170 L320,170 L325,235 L260,240 Z" },
  { name: "Bourgogne-Franche-Comté", d: "M320,170 L420,180 L425,260 L325,255 Z" },
  { name: "Nouvelle-Aquitaine", d: "M115,235 L260,235 L270,355 L150,365 L100,310 Z" },
  { name: "Auvergne-Rhône-Alpes", d: "M260,240 L420,260 L430,360 L300,365 L270,310 Z" },
  { name: "Occitanie", d: "M150,365 L320,360 L335,440 L195,440 Z" },
  { name: "Provence-Alpes-Côte d'Azur", d: "M320,360 L430,360 L445,430 L335,440 Z" },
  { name: "Corse", d: "M470,400 L490,395 L498,430 L478,450 Z" },
];

export default function FranceMap({ stats = {}, onSelect, selected }) {
  const [hover, setHover] = useState(null);

  const counts = Object.fromEntries(
    (stats.by_region || []).map((s) => [s.region, s])
  );

  const colorFor = (name) => {
    if (selected === name) return "#2563EB";
    if (hover === name) return "#8B5CF6";
    const c = counts[name]?.offers || 0;
    if (c > 5) return "#A78BFA";
    if (c > 2) return "#C4B5FD";
    if (c > 0) return "#DDD6FE";
    return "#E0E7FF";
  };

  return (
    <div className="relative w-full" data-testid="france-map">
      <svg viewBox="0 30 520 480" className="w-full h-auto">
        <defs>
          <filter id="soft" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="2" stdDeviation="3" floodColor="#1e293b" floodOpacity="0.08" />
          </filter>
        </defs>
        {REGIONS.map((r) => (
          <g key={r.name} filter="url(#soft)">
            <path
              d={r.d}
              fill={colorFor(r.name)}
              stroke="white"
              strokeWidth="2"
              onMouseEnter={() => setHover(r.name)}
              onMouseLeave={() => setHover(null)}
              onClick={() => onSelect && onSelect(r.name === selected ? null : r.name)}
              style={{ cursor: "pointer", transition: "fill 200ms" }}
              data-testid={`region-${r.name.replace(/\s|'|-/g, "_")}`}
            />
          </g>
        ))}
      </svg>
      {hover && (
        <div className="absolute top-3 right-3 bg-white border border-slate-200 shadow-lg rounded-xl px-4 py-3 text-sm" data-testid="region-tooltip">
          <div className="font-bold text-slate-900">{hover}</div>
          <div className="text-slate-500">
            {(counts[hover]?.offers || 0)} offres · {(counts[hover]?.companies || 0)} entreprises
          </div>
        </div>
      )}
      <div className="absolute bottom-3 left-3 flex items-center gap-2 text-xs text-slate-500 bg-white/80 backdrop-blur rounded-full px-3 py-1.5">
        <span className="w-3 h-3 rounded bg-violet-200"></span>Moins
        <span className="w-3 h-3 rounded bg-violet-400"></span>Plus
        <span className="font-medium">d'offres</span>
      </div>
    </div>
  );
}
