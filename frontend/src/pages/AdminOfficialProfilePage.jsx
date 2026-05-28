import React, { useEffect, useState } from "react";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { BadgeCheck, Save, Eye, EyeOff } from "lucide-react";
import { toast } from "sonner";
import PremiumBadge from "../components/PremiumBadge";

const FIELDS = [
  { key: "display_name", label: "Nom affiché", placeholder: "StageEtudiant.com" },
  { key: "slogan", label: "Slogan", placeholder: "Le site qui aide les étudiants à trouver leur stage" },
  { key: "website_url", label: "Lien du site", placeholder: "https://stageetudiant.com" },
  { key: "contact_email", label: "Email de contact", placeholder: "contact@stageetudiant.com" },
];

export default function AdminOfficialProfilePage() {
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (user?.role !== "admin") return;
    api.get("/official-profile").then((r) => setData(r.data)).catch(() => {});
  }, [user]);

  if (!user || user.role !== "admin") {
    return <div className="pt-24 text-center text-slate-500" data-testid="admin-only">Accès réservé à l&apos;administrateur.</div>;
  }
  if (!data) return <div className="pt-24 text-center text-slate-400">Chargement...</div>;

  const set = (k, v) => setData({ ...data, [k]: v });

  const save = async () => {
    setSaving(true);
    try {
      const payload = {
        display_name: data.display_name,
        slogan: data.slogan,
        description: data.description,
        website_url: data.website_url,
        contact_email: data.contact_email,
        profile_image_url: data.profile_image_url,
        banner_image_url: data.banner_image_url,
        primary_color: data.primary_color,
        is_visible: !!data.is_visible,
      };
      const { data: updated } = await api.patch("/admin/official-profile", payload);
      setData(updated);
      toast.success("Profil officiel mis à jour");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erreur");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-h-screen pt-20 pb-12 bg-slate-50 dark:bg-slate-900">
      <div className="max-w-4xl mx-auto px-4 sm:px-6">
        <div className="flex items-center gap-3 mb-2">
          <BadgeCheck className="w-7 h-7 text-blue-600" />
          <h1 className="text-2xl sm:text-3xl font-black tracking-tight text-slate-900 dark:text-slate-100">
            Profil officiel StageEtudiant.com
          </h1>
        </div>
        <p className="text-sm text-slate-500 mb-6">
          Ce profil représente la plateforme. Seul un administrateur peut le modifier.
          Le nom <code className="bg-slate-100 dark:bg-slate-800 rounded px-1">StageEtudiant.com</code> est réservé : aucun utilisateur ne peut le réutiliser à l&apos;inscription.
        </p>

        {/* Live preview */}
        <div className="card-soft p-0 mb-6 overflow-hidden" data-testid="official-preview">
          <div
            className="h-32 sm:h-40 bg-gradient-to-r"
            style={{
              backgroundImage: data.banner_image_url
                ? `url(${data.banner_image_url})`
                : `linear-gradient(135deg, ${data.primary_color || "#2563eb"}, #7c3aed)`,
              backgroundSize: "cover", backgroundPosition: "center",
            }}
          />
          <div className="p-5 -mt-10">
            <div className="flex items-end gap-4">
              <div className="w-20 h-20 rounded-2xl ring-4 ring-white dark:ring-slate-900 bg-white overflow-hidden shrink-0 grid place-items-center text-blue-600 font-black text-2xl">
                {data.profile_image_url
                  ? <img src={data.profile_image_url} className="w-full h-full object-cover" alt="" />
                  : (data.display_name?.[0] || "S")}
              </div>
              <div className="flex-1 min-w-0 pb-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <h2 className="font-black text-xl text-slate-900 dark:text-slate-100 truncate">{data.display_name || "StageEtudiant.com"}</h2>
                  <PremiumBadge role="official" size="sm" />
                </div>
                {data.slogan && <p className="text-sm text-slate-500 italic">« {data.slogan} »</p>}
              </div>
              <span className={`text-[10px] font-bold uppercase rounded-full px-2 py-1 ${data.is_visible ? "bg-emerald-100 text-emerald-700" : "bg-slate-200 text-slate-500"}`}>
                {data.is_visible ? <Eye className="w-3 h-3 inline mr-1" /> : <EyeOff className="w-3 h-3 inline mr-1" />}
                {data.is_visible ? "Visible" : "Masqué"}
              </span>
            </div>
            {data.description && <p className="text-sm text-slate-700 dark:text-slate-300 mt-3">{data.description}</p>}
          </div>
        </div>

        {/* Form */}
        <div className="card-soft p-6 space-y-4" data-testid="official-form">
          <div className="grid sm:grid-cols-2 gap-4">
            {FIELDS.map(f => (
              <div key={f.key}>
                <Label htmlFor={f.key}>{f.label}</Label>
                <Input
                  id={f.key}
                  data-testid={`field-${f.key}`}
                  value={data[f.key] || ""}
                  onChange={(e) => set(f.key, e.target.value)}
                  placeholder={f.placeholder}
                  className="rounded-xl mt-1"
                />
              </div>
            ))}
            <div>
              <Label htmlFor="profile_image_url">Photo de profil (URL)</Label>
              <Input id="profile_image_url" data-testid="field-profile-image" value={data.profile_image_url || ""} onChange={(e) => set("profile_image_url", e.target.value)} placeholder="https://..." className="rounded-xl mt-1" />
            </div>
            <div>
              <Label htmlFor="banner_image_url">Bannière (URL)</Label>
              <Input id="banner_image_url" data-testid="field-banner" value={data.banner_image_url || ""} onChange={(e) => set("banner_image_url", e.target.value)} placeholder="https://..." className="rounded-xl mt-1" />
            </div>
            <div>
              <Label htmlFor="primary_color">Couleur principale</Label>
              <div className="flex items-center gap-2 mt-1">
                <input
                  id="primary_color" data-testid="field-color" type="color"
                  value={data.primary_color || "#2563eb"}
                  onChange={(e) => set("primary_color", e.target.value)}
                  className="h-10 w-14 rounded-xl border border-slate-200 bg-white cursor-pointer"
                />
                <Input value={data.primary_color || ""} onChange={(e) => set("primary_color", e.target.value)} placeholder="#2563eb" className="rounded-xl flex-1" />
              </div>
            </div>
            <label className="flex items-center gap-2 cursor-pointer mt-6" data-testid="field-visible">
              <input
                type="checkbox"
                checked={!!data.is_visible}
                onChange={(e) => set("is_visible", e.target.checked)}
                className="accent-blue-600 w-4 h-4"
              />
              <span className="text-sm font-medium">Visible publiquement</span>
            </label>
          </div>
          <div>
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description" data-testid="field-description"
              value={data.description || ""}
              onChange={(e) => set("description", e.target.value)}
              placeholder="Présentez la plateforme officielle…"
              className="rounded-xl mt-1 min-h-[120px]"
            />
          </div>
          <div className="flex gap-2 pt-2">
            <Button onClick={save} disabled={saving} className="rounded-full bg-blue-600 hover:bg-blue-700" data-testid="save-official">
              <Save className="w-4 h-4 mr-1" /> {saving ? "Enregistrement…" : "Enregistrer"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
