import React from "react";
import { useAuth } from "../context/AuthContext";
import { Button } from "../components/ui/button";

export default function SettingsPage() {
  const { user, logout } = useAuth();
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
