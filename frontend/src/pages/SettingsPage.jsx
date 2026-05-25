import React from "react";
import { useAuth } from "../context/AuthContext";
import { useTheme } from "../context/ThemeContext";
import { Button } from "../components/ui/button";
import { Sun, Moon, Monitor } from "lucide-react";

const APPEARANCE = [
  { id: "light", label: "Clair", icon: Sun },
  { id: "dark", label: "Sombre", icon: Moon },
  { id: "system", label: "Automatique", icon: Monitor },
];

export default function SettingsPage() {
  const { user, logout } = useAuth();
  const { preference, setTheme } = useTheme() || {};
  if (!user) return null;
  return (
    <div className="min-h-screen pt-20 pb-12 bg-slate-50">
      <div className="max-w-2xl mx-auto px-6">
        <h1 className="text-3xl font-black tracking-tight text-slate-900 mb-6">Paramètres</h1>

        <div className="card-soft p-6 space-y-4">
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div className="text-slate-500">Email</div><div className="font-semibold">{user.email}</div>
            <div className="text-slate-500">Type de compte</div><div className="font-semibold capitalize">{user.role}</div>
            <div className="text-slate-500">Membre depuis</div><div className="font-semibold">{new Date(user.created_at).toLocaleDateString("fr-FR")}</div>
          </div>
        </div>

        <div className="card-soft p-6 mt-4" data-testid="appearance-section">
          <h2 className="font-bold mb-1">Apparence</h2>
          <p className="text-sm text-slate-500 mb-4">Choisissez le thème du site. Le réglage est sauvegardé sur votre compte.</p>
          <div className="grid grid-cols-3 gap-2">
            {APPEARANCE.map(a => {
              const Icon = a.icon;
              const active = preference === a.id;
              return (
                <button
                  key={a.id}
                  onClick={() => setTheme(a.id)}
                  className={`p-4 rounded-2xl border-2 text-sm font-semibold flex flex-col items-center gap-2 transition ${active ? "border-blue-500 bg-blue-50" : "border-slate-200 hover:bg-slate-50"}`}
                  data-testid={`theme-${a.id}`}
                >
                  <Icon className="w-5 h-5" />
                  {a.label}
                </button>
              );
            })}
          </div>
        </div>

        <div className="card-soft p-6 mt-4">
          <h2 className="font-bold mb-3">Confidentialité (RGPD)</h2>
          <p className="text-sm text-slate-500 mb-4">Conformément au RGPD, vous pouvez demander la suppression de votre compte et de toutes vos données personnelles.</p>
          <Button variant="outline" className="rounded-full text-red-600 border-red-200" data-testid="delete-account">Supprimer mon compte</Button>
        </div>
        <Button onClick={logout} className="mt-6 rounded-full" data-testid="settings-logout">Se déconnecter</Button>
      </div>
    </div>
  );
}
