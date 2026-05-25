import React, { useEffect, useState } from "react";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { CheckCircle2 } from "lucide-react";
import { toast } from "sonner";

export default function AdminPage() {
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);
  const [platform, setPlatform] = useState(null);
  const [apiStats, setApiStats] = useState(null);
  const [cache, setCache] = useState(null);

  useEffect(() => {
    if (user?.role !== "admin") return;
    api.get("/admin/stats").then((r) => setStats(r.data));
    api.get("/admin/users").then((r) => setUsers(r.data));
    api.get("/admin/platform-stats").then((r) => setPlatform(r.data));
    api.get("/admin/api-stats?days=30").then((r) => setApiStats(r.data));
    api.get("/admin/external-cache").then((r) => setCache(r.data));
  }, [user]);

  if (!user || user.role !== "admin") {
    return <div className="pt-24 text-center text-slate-500">Accès réservé aux administrateurs.</div>;
  }

  const verify = async (uid) => {
    await api.post(`/admin/verify/${uid}`);
    toast.success("Entreprise vérifiée");
    const r = await api.get("/admin/users"); setUsers(r.data);
  };

  const grantPremium = async (uid) => {
    await api.post(`/admin/grant-premium/${uid}?days=30`);
    toast.success("Premium accordé 30 jours");
    const r = await api.get("/admin/users"); setUsers(r.data);
  };

  const savePlatform = async () => {
    try {
      const { data } = await api.put("/admin/platform-stats", {
        displayed_obtained_count: parseInt(platform.displayed_obtained_count, 10) || 0,
        use_manual_count: !!platform.use_manual_count,
        public_message: platform.public_message,
        show_counter: !!platform.show_counter,
      });
      setPlatform({ ...platform, ...data });
      toast.success("Compteur public mis à jour");
    } catch {
      toast.error("Erreur");
    }
  };

  return (
    <div className="min-h-screen pt-20 pb-12 bg-slate-50">
      <div className="max-w-6xl mx-auto px-6">
        <h1 className="text-3xl font-black tracking-tight text-slate-900 mb-6">Administration</h1>
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-8">
            {Object.entries(stats).map(([k, v]) => (
              <div key={k} className="card-soft p-5">
                <div className="text-3xl font-black text-slate-900">{v}</div>
                <div className="text-xs text-slate-500 capitalize">{k}</div>
              </div>
            ))}
          </div>
        )}

        {platform && (
          <div className="card-soft p-6 mb-6" data-testid="admin-platform-stats">
            <h2 className="font-bold mb-1">Preuve sociale — Compteur "stages obtenus"</h2>
            <p className="text-sm text-slate-500 mb-4">
              Compteur réel (auto) : <strong>{platform.real_obtained_count}</strong>{" "}
              candidatures avec statut <code className="bg-slate-100 rounded px-1 text-[11px]">acceptee / internship_obtained / apprenticeship_obtained / contract_signed</code>.
            </p>
            <div className="grid sm:grid-cols-2 gap-3">
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="show_counter"
                  checked={!!platform.show_counter}
                  onChange={(e) => setPlatform({ ...platform, show_counter: e.target.checked })}
                  data-testid="show-counter"
                />
                <Label htmlFor="show_counter">Afficher le compteur publiquement</Label>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="use_manual"
                  checked={!!platform.use_manual_count}
                  onChange={(e) => setPlatform({ ...platform, use_manual_count: e.target.checked })}
                  data-testid="use-manual"
                />
                <Label htmlFor="use_manual">Surcharger avec une valeur marketing</Label>
              </div>
              <div>
                <Label>Valeur affichée (marketing)</Label>
                <Input
                  type="number"
                  value={platform.displayed_obtained_count || 0}
                  onChange={(e) => setPlatform({ ...platform, displayed_obtained_count: e.target.value })}
                  className="rounded-xl mt-1"
                  data-testid="displayed-count"
                  disabled={!platform.use_manual_count}
                />
              </div>
              <div className="sm:col-span-2">
                <Label>Message public</Label>
                <Input
                  value={platform.public_message || ""}
                  onChange={(e) => setPlatform({ ...platform, public_message: e.target.value })}
                  className="rounded-xl mt-1"
                  data-testid="public-message"
                />
              </div>
            </div>
            <Button onClick={savePlatform} className="rounded-full bg-blue-600 hover:bg-blue-700 mt-4" data-testid="save-platform-stats">Enregistrer</Button>
          </div>
        )}

        {apiStats && (
          <div className="card-soft p-6 mb-6" data-testid="admin-api-stats">
            <h2 className="font-bold mb-3">API & Statistiques ({apiStats.window_days} derniers jours)</h2>
            <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
              <Tile label="Appels API" value={apiStats.by_api[0]?.calls || 0} />
              <Tile label="Cache hits" value={apiStats.by_api[0]?.cache_hits || 0} />
              <Tile label="Recherches IA" value={apiStats.ai_searches} />
              <Tile label="Vues profils" value={apiStats.profile_views} />
            </div>
            <div className="grid sm:grid-cols-3 gap-4">
              <RankList title="Top recherches" rows={apiStats.top_queries.map(q => ({ label: q.q, n: q.count }))} testid="top-queries" />
              <RankList title="Top départements" rows={apiStats.top_departments.map(q => ({ label: q.department, n: q.count }))} testid="top-departments" />
              <RankList title="Top codes NAF" rows={apiStats.top_naf.map(q => ({ label: q.naf, n: q.count }))} testid="top-naf" />
            </div>
            {apiStats.recent_errors.length > 0 && (
              <div className="mt-4">
                <div className="text-xs font-semibold text-slate-500 mb-1">Erreurs récentes ({apiStats.recent_errors.length})</div>
                <div className="space-y-1 text-[11px] text-rose-700">
                  {apiStats.recent_errors.slice(0, 5).map((e, i) => (
                    <div key={i}>{e.created_at?.slice(0,16).replace('T',' ')} · {e.error?.slice(0, 100)}</div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {cache && (
          <div className="card-soft p-6 mb-6" data-testid="admin-cache">
            <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
              <h2 className="font-bold">Cache annuaire entreprises + La Bonne Alternance</h2>
              <div className="flex gap-2">
                <Button size="sm" variant="outline" className="rounded-full" onClick={async () => { await api.delete('/admin/external-cache?scope=search'); const r = await api.get('/admin/external-cache'); setCache(r.data); toast.success('Cache recherches vidé'); }} data-testid="purge-search">Purger recherches</Button>
                <Button size="sm" variant="outline" className="rounded-full" onClick={async () => { await api.delete('/admin/lba-cache'); toast.success('Cache LBA vidé'); }} data-testid="purge-lba">Purger LBA</Button>
                <Button size="sm" variant="outline" className="rounded-full text-rose-600 border-rose-200" onClick={async () => { await api.delete('/admin/external-cache?scope=all'); const r = await api.get('/admin/external-cache'); setCache(r.data); toast.success('Cache entier vidé'); }} data-testid="purge-all">Tout purger</Button>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3 mb-3">
              <Tile label="Recherches en cache" value={cache.search_cache_count} />
              <Tile label="Fiches détaillées en cache" value={cache.details_cache_count} />
            </div>
            {cache.search_cache_entries.slice(0, 6).map((e, i) => (
              <div key={i} className="text-xs text-slate-500 border-t border-slate-100 py-1.5 flex justify-between gap-3">
                <span className="truncate">q={e.query?.q || "—"} · cp={e.query?.code_postal || "—"} · dpt={e.query?.departement || "—"}</span>
                <span className="shrink-0">Exp: {e.expires_at?.slice(0, 10)} · {e.results_count} rés.</span>
              </div>
            ))}
          </div>
        )}

        <div className="card-soft p-6">
          <h2 className="font-bold mb-4">Utilisateurs ({users.length})</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="text-left text-slate-500 border-b border-slate-100"><th className="py-2">Nom</th><th>Email</th><th>Rôle</th><th>SIRET</th><th>Action</th></tr></thead>
              <tbody>
                {users.map(u => (
                  <tr key={u.user_id} className="border-b border-slate-50">
                    <td className="py-2 font-semibold">{u.name}</td>
                    <td className="text-slate-500">{u.email}</td>
                    <td><span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs">{u.role}</span></td>
                    <td className="text-slate-500">{u.profile?.siret || "—"}</td>
                    <td>
                      {u.role === "company" && !u.profile?.verified && (
                        <Button size="sm" onClick={() => verify(u.user_id)} className="rounded-full" data-testid={`verify-${u.user_id}`}>Vérifier</Button>
                      )}
                      {u.profile?.verified && <CheckCircle2 className="w-4 h-4 text-blue-500" />}
                      {u.role === "candidate" && !u.profile?.is_premium && (
                        <Button size="sm" variant="outline" onClick={() => grantPremium(u.user_id)} className="rounded-full ml-1 text-amber-700 border-amber-200" data-testid={`premium-${u.user_id}`}>Premium 30j</Button>
                      )}
                      {u.profile?.is_premium && <span className="text-[10px] font-bold uppercase bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full ml-1">Premium</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

const Tile = ({ label, value }) => (
  <div className="bg-slate-50 rounded-2xl p-3">
    <div className="text-2xl font-black text-slate-900">{value?.toLocaleString?.("fr-FR") ?? value}</div>
    <div className="text-xs text-slate-500">{label}</div>
  </div>
);

const RankList = ({ title, rows, testid }) => (
  <div data-testid={testid}>
    <div className="text-xs font-semibold text-slate-500 mb-1">{title}</div>
    {rows.length === 0 && <div className="text-xs text-slate-400 italic">Aucune donnée</div>}
    <ul className="space-y-1 text-sm">
      {rows.slice(0, 6).map((r, i) => (
        <li key={i} className="flex justify-between border-b border-slate-100 py-0.5">
          <span className="truncate max-w-[80%]">{r.label || "—"}</span>
          <span className="font-bold text-blue-600">{r.n}</span>
        </li>
      ))}
    </ul>
  </div>
);
