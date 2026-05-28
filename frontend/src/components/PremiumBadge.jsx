import React from "react";
import { Crown, Star, BadgeCheck } from "lucide-react";

/**
 * Detects whether a user/profile is currently premium (active + not expired).
 * Accepts either a `user` object (with .profile.*) or a flat `profile` object.
 */
export function isPremiumActive(input) {
  if (!input) return false;
  const root = input.profile ? input.profile : input;
  const flag = root.is_premium || input.is_premium;
  if (!flag) return false;
  const status = root.premium_status || input.premium_status;
  if (status && status !== "active") return false;
  const end = root.premium_end_date || input.premium_end_date;
  if (end) {
    try {
      const d = new Date(end);
      if (!isNaN(d.getTime()) && d.getTime() < Date.now()) return false;
    } catch {
      /* ignore */
    }
  }
  return true;
}

const SIZE_MAP = {
  xs: "text-[9px] px-1.5 py-0.5",
  sm: "text-[10px] px-2 py-0.5",
  md: "text-xs px-2.5 py-1",
  lg: "text-sm px-3 py-1.5",
};

const ROLE_PRESETS = {
  candidate: { label: "Profil Premium", Icon: Star },
  student:   { label: "Profil Premium", Icon: Star },
  company:   { label: "Entreprise Premium", Icon: Crown },
  official:  { label: "Compte officiel", Icon: BadgeCheck, isOfficial: true },
};

/**
 * Modern, gold-accented premium badge.
 * Props:
 *  - role: "candidate" | "company" | "official"
 *  - size: "xs" | "sm" | "md" | "lg"
 *  - label (optional override)
 *  - solid: render as solid pill instead of soft (default soft)
 */
export default function PremiumBadge({
  role = "candidate",
  size = "sm",
  label,
  solid = false,
  className = "",
  ...rest
}) {
  const preset = ROLE_PRESETS[role] || ROLE_PRESETS.candidate;
  const text = label || preset.label;
  const Icon = preset.Icon;
  const sizeCls = SIZE_MAP[size] || SIZE_MAP.sm;
  if (preset.isOfficial) {
    return (
      <span
        data-testid={`badge-${role}`}
        className={`inline-flex items-center gap-1 rounded-full font-bold uppercase tracking-wide bg-blue-600 text-white ${sizeCls} ${className}`}
        title="Compte officiel StageEtudiant.com"
        {...rest}
      >
        <Icon className="w-3 h-3" />
        {text}
      </span>
    );
  }
  if (solid) {
    return (
      <span
        data-testid={`badge-${role}`}
        className={`inline-flex items-center gap-1 rounded-full font-bold uppercase tracking-wide bg-gradient-to-r from-amber-400 to-amber-600 text-white shadow-sm ${sizeCls} ${className}`}
        title={text}
        {...rest}
      >
        <Icon className="w-3 h-3" />
        {text}
      </span>
    );
  }
  return (
    <span
      data-testid={`badge-${role}`}
      className={`inline-flex items-center gap-1 rounded-full font-bold uppercase tracking-wide bg-amber-50 text-amber-700 border border-amber-200 ${sizeCls} ${className}`}
      title={text}
      {...rest}
    >
      <Icon className="w-3 h-3" />
      {text}
    </span>
  );
}
