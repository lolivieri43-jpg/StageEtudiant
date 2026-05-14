import React, { useEffect, useState } from "react";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Button } from "../components/ui/button";
import { CheckCircle2 } from "lucide-react";
import { toast } from "sonner";

export default function AdminPage() {
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);

  useEffect(() => {
    if (user?.role !== "admin") return;
    api.get("/admin/stats").then((r) => setStats(r.data));
    api.get("/admin/users").then((r) => setUsers(r.data));
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
