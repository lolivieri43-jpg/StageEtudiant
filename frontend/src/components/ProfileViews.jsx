import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../lib/api";
import { Eye, Lock, Sparkles, UserCircle2 } from "lucide-react";
import { Button } from "./ui/button";
import { formatDistanceToNow } from "date-fns";
import { fr } from "date-fns/locale";

export default function ProfileViews() {
  const [stats, setStats] = useState(null);
  const [list, setList] = useState(null);
  const [premiumError, setPremiumError] = useState(false);

  useEffect(() => {
    api.get("/me/profile-views/stats").then(r => setStats(r.data)).catch(() => {});
  }, []);

  useEffect(() => {
    if (!stats || !stats.is_premium) return;
    api.get("/me/profile-views?limit=20")
      .then(r => setList(r.data))
      .catch((err) => {
        if (err?.response?.status === 402) setPremiumError(true);
      });
  }, [stats]);

  if (!stats) return null;

  return (
    <div className="card-soft p-6" data-testid="profile-views-block">
      <div className="flex items-center justify-between mb-4 gap-2">
        <h2 className="font-bold text-slate-900 flex items-center gap-2"><Eye className="w-4 h-4 text-blue-500" />Qui a consulté mon profil</h2>
        {!stats.is_premium && (
          <span className="text-xs font-semibold text-amber-600 bg-amber-50 rounded-full px-3 py-1">Premium</span>
        )}
      </div>

      <div className="grid grid-cols-3 gap-3 mb-4">
        <Stat label="Total" value={stats.total} />
        <Stat label="7 jours" value={stats.week} />
        <Stat label="30 jours" value={stats.month} />
      </div>

      {stats.is_premium ? (
        <div className="space-y-2">
          {list === null && <div className="text-sm text-slate-400">Chargement...</div>}
          {list && list.length === 0 && <div className="text-sm text-slate-400 italic">Aucune visite récente</div>}
          {list && list.map(v => (
            <Link
              to={`/profile/${v.viewer_user_id}`}
              key={v.view_id}
              className="flex items-center gap-3 p-3 rounded-xl hover:bg-slate-50 transition"
              data-testid={`viewer-row-${v.view_id}`}
            >
              <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-violet-500 text-white grid place-items-center font-bold text-sm overflow-hidden shrink-0">
                {v.viewer_avatar ? <img src={v.viewer_avatar} alt="" className="w-full h-full object-cover" /> : (v.viewer_name?.[0] || "?")}
              </div>
              <div className="flex-1 min-w-0">
                <div className="font-semibold text-slate-900 truncate text-sm">{v.viewer_name || "Anonyme"}</div>
                <div className="text-xs text-slate-500 truncate">{v.viewer_title || v.viewer_role}</div>
              </div>
              <div className="text-xs text-slate-400 shrink-0">
                {v.viewed_at ? formatDistanceToNow(new Date(v.viewed_at), { locale: fr, addSuffix: true }) : ""}
              </div>
            </Link>
          ))}
        </div>
      ) : (
        <div className="text-center py-6 px-4 bg-gradient-to-br from-blue-50 to-violet-50 rounded-2xl" data-testid="premium-cta">
          <Lock className="w-7 h-7 mx-auto mb-2 text-violet-500" />
          <div className="font-semibold text-slate-900 mb-1">Passez en Premium pour voir qui a consulté votre profil</div>
          <div className="text-xs text-slate-500 mb-3">Découvrez chaque recruteur ou étudiant qui s'intéresse à vous.</div>
          <Link to="/payments/subscribe">
            <Button className="rounded-full bg-violet-600 hover:bg-violet-700" data-testid="upgrade-premium">
              <Sparkles className="w-3.5 h-3.5 mr-1" />Découvrir Premium
            </Button>
          </Link>
        </div>
      )}

      {premiumError && <div className="text-xs text-amber-700 mt-2">Accès Premium requis.</div>}
    </div>
  );
}

const Stat = ({ label, value }) => (
  <div className="bg-slate-50 rounded-xl p-3 text-center">
    <div className="text-2xl font-black text-slate-900">{value}</div>
    <div className="text-xs text-slate-500 mt-0.5">{label}</div>
  </div>
);
