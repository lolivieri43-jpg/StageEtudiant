import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { toast } from "sonner";
import { AlertCircle, Megaphone, Smartphone, Monitor, Save, Send, Image as ImageIcon, Tag, Calendar, MapPin, Link as LinkIcon } from "lucide-react";

const CATS = [
  { id: "general", label: "Général" },
  { id: "food", label: "Restauration" },
  { id: "sport", label: "Sport" },
  { id: "culture", label: "Culture" },
  { id: "transport", label: "Transport" },
  { id: "study", label: "Études" },
  { id: "fashion", label: "Mode" },
  { id: "tech", label: "Tech" },
];

const REGIONS = [
  "", "Île-de-France", "Auvergne-Rhône-Alpes", "Nouvelle-Aquitaine", "Occitanie", "Hauts-de-France",
  "Provence-Alpes-Côte d'Azur", "Grand Est", "Pays de la Loire", "Bretagne", "Normandie",
  "Bourgogne-Franche-Comté", "Centre-Val de Loire", "Corse",
];

// 4 modèles prédéfinis
const TEMPLATES = [
  { id: "minimal",  label: "Minimal", bg: "#ffffff", text: "#0f172a", accent: "#2563eb" },
  { id: "promo",    label: "Code promo XXL", bg: "#fef3c7", text: "#78350f", accent: "#d97706" },
  { id: "event",    label: "Événement", bg: "#ecfeff", text: "#164e63", accent: "#0891b2" },
  { id: "career",   label: "Recrutement", bg: "#f5f3ff", text: "#4c1d95", accent: "#7c3aed" },
];

export default function NewAdPage() {
  const navigate = useNavigate();
  const { id } = useParams();
  const editMode = Boolean(id);
  const { user } = useAuth();
  const [quota, setQuota] = useState({ pro: false, used: 0, max: 1 });
  const [preview, setPreview] = useState("desktop"); // desktop|mobile
  const [form, setForm] = useState({
    title: "", short_text: "", image: "", logo: "",
    cta_label: "Découvrir", cta_url: "",
    promo_code: "", category: "general",
    region: "", city: "", geo_zone: "",
    start_date: "", end_date: "",
    template_id: "minimal",
    style: { bg_color: "#ffffff", text_color: "#0f172a", accent_color: "#2563eb",
             text_align: "left", border_radius: 16 },
  });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (user?.role !== "company") return;
    api.get("/ads/mine").then(r => setQuota({ pro: r.data.pro, used: r.data.quota.used, max: r.data.quota.max })).catch(() => {});
    if (editMode) {
      api.get(`/ads/${id}`).then(r => {
        setForm(f => ({ ...f, ...r.data, style: { ...f.style, ...(r.data.style || {}) } }));
      }).catch(() => toast.error("Publicité introuvable"));
    }
  }, [user, editMode, id]);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const setStyle = (k, v) => setForm(f => ({ ...f, style: { ...f.style, [k]: v } }));

  const applyTemplate = (tpl) => {
    setForm(f => ({
      ...f,
      template_id: tpl.id,
      style: { ...f.style, bg_color: tpl.bg, text_color: tpl.text, accent_color: tpl.accent },
    }));
  };

  const submit = async (asDraft) => {
    if (!form.title || !form.short_text) {
      toast.error("Titre et texte court requis"); return;
    }
    setLoading(true);
    try {
      const payload = { ...form, save_as_draft: asDraft };
      if (editMode) {
        await api.patch(`/ads/${id}`, { ...payload, submit: !asDraft });
        toast.success(asDraft ? "Brouillon enregistré" : "Publicité renvoyée en validation");
      } else {
        await api.post("/ads", payload);
        toast.success(asDraft ? "Brouillon enregistré" : "Publicité envoyée en validation");
      }
      navigate("/ads/mine");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Erreur");
    } finally {
      setLoading(false);
    }
  };

  if (!user || user.role !== "company") {
    return <div className="pt-24 text-center text-slate-500">Réservé aux entreprises.</div>;
  }
  const quotaFull = !quota.pro && quota.used >= quota.max && !editMode;

  return (
    <div className="min-h-screen pt-20 pb-12 bg-slate-50">
      <div className="max-w-7xl mx-auto px-6">
        <div className="mb-6">
          <h1 className="text-3xl font-black tracking-tight text-slate-900 flex items-center gap-2">
            <Megaphone className="w-7 h-7 text-violet-600" />
            {editMode ? "Modifier la publicité" : "Créer une publicité"}
          </h1>
          <p className="text-slate-500 mt-1">
            Visible dans l'espace <b>Bons Plans</b> après validation administrateur.
            {!quota.pro && <> · Quota gratuit : <b>{quota.used}/{quota.max}</b></>}
            {quota.pro && <> · Compte Pro <b>(illimité)</b></>}
          </p>
        </div>

        {quotaFull && (
          <div className="card-soft p-4 mb-6 bg-amber-50 border-amber-200 flex gap-3" data-testid="quota-warning">
            <AlertCircle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
            <div className="text-sm flex-1">
              <div className="font-bold text-amber-900">Quota atteint</div>
              <div className="text-amber-800">Votre compte gratuit ne permet qu'<b>1 publicité active</b>. Activez l'abonnement Pro pour publier sans limite.</div>
              <Button onClick={() => navigate("/payments/subscribe")} className="mt-2 rounded-full bg-amber-600 hover:bg-amber-700" size="sm">Passer Pro</Button>
            </div>
          </div>
        )}

        <div className="grid lg:grid-cols-2 gap-6">
          {/* Form */}
          <div className="card-soft p-6 space-y-4">
            <h2 className="font-bold text-slate-900 mb-2 flex items-center gap-2"><Tag className="w-4 h-4" />Contenu</h2>
            <div>
              <Label>Titre *</Label>
              <Input required value={form.title} onChange={set("title")} className="rounded-xl mt-1" data-testid="ad-title" maxLength={80} />
            </div>
            <div>
              <Label>Texte court * <span className="text-xs text-slate-400 font-normal">(max 220 caractères)</span></Label>
              <Textarea required value={form.short_text} onChange={set("short_text")} rows={3} maxLength={220} className="rounded-xl mt-1" data-testid="ad-short-text" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Image (URL)</Label>
                <Input value={form.image} onChange={set("image")} placeholder="https://..." className="rounded-xl mt-1" data-testid="ad-image" />
              </div>
              <div>
                <Label>Logo entreprise (URL)</Label>
                <Input value={form.logo} onChange={set("logo")} placeholder="https://..." className="rounded-xl mt-1" data-testid="ad-logo" />
              </div>
              <div>
                <Label>Texte du bouton</Label>
                <Input value={form.cta_label} onChange={set("cta_label")} className="rounded-xl mt-1" data-testid="ad-cta-label" maxLength={30} />
              </div>
              <div>
                <Label>Lien externe (CTA)</Label>
                <Input type="url" value={form.cta_url} onChange={set("cta_url")} placeholder="https://..." className="rounded-xl mt-1" data-testid="ad-cta-url" />
              </div>
              <div>
                <Label>Code promo</Label>
                <Input value={form.promo_code} onChange={set("promo_code")} className="rounded-xl mt-1" data-testid="ad-promo" />
              </div>
              <div>
                <Label>Catégorie</Label>
                <select value={form.category} onChange={set("category")} className="w-full rounded-xl border border-slate-200 h-10 px-3 mt-1" data-testid="ad-category">
                  {CATS.map(c => <option key={c.id} value={c.id}>{c.label}</option>)}
                </select>
              </div>
            </div>

            <h2 className="font-bold text-slate-900 mt-6 mb-2 flex items-center gap-2"><MapPin className="w-4 h-4" />Ciblage géographique</h2>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Région</Label>
                <select value={form.region} onChange={set("region")} className="w-full rounded-xl border border-slate-200 h-10 px-3 mt-1" data-testid="ad-region">
                  {REGIONS.map(r => <option key={r} value={r}>{r || "Toutes"}</option>)}
                </select>
              </div>
              <div>
                <Label>Ville</Label>
                <Input value={form.city} onChange={set("city")} className="rounded-xl mt-1" data-testid="ad-city" />
              </div>
              <div className="col-span-2">
                <Label>Zone ciblée (texte libre)</Label>
                <Input value={form.geo_zone} onChange={set("geo_zone")} placeholder="ex: étudiants Paris 10°, Sud-Est, etc." className="rounded-xl mt-1" data-testid="ad-geo-zone" />
              </div>
            </div>

            <h2 className="font-bold text-slate-900 mt-6 mb-2 flex items-center gap-2"><Calendar className="w-4 h-4" />Période de diffusion</h2>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Début</Label>
                <Input type="date" value={form.start_date?.slice(0,10) || ""} onChange={set("start_date")} className="rounded-xl mt-1" data-testid="ad-start" />
              </div>
              <div>
                <Label>Fin</Label>
                <Input type="date" value={form.end_date?.slice(0,10) || ""} onChange={set("end_date")} className="rounded-xl mt-1" data-testid="ad-end" />
              </div>
            </div>

            <h2 className="font-bold text-slate-900 mt-6 mb-2">Modèle</h2>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {TEMPLATES.map(t => (
                <button key={t.id} type="button" onClick={() => applyTemplate(t)}
                  className={`p-3 rounded-xl border text-left transition-all ${form.template_id === t.id ? "border-violet-500 ring-2 ring-violet-200" : "border-slate-200"}`}
                  data-testid={`template-${t.id}`}
                  style={{ background: t.bg, color: t.text }}>
                  <div className="text-[10px] font-bold uppercase opacity-60">{t.label}</div>
                  <div className="text-sm font-bold mt-1">Aperçu</div>
                  <div className="inline-block mt-2 text-[10px] font-bold px-2 py-0.5 rounded-full" style={{ background: t.accent, color: "#fff" }}>CTA</div>
                </button>
              ))}
            </div>

            <h2 className="font-bold text-slate-900 mt-6 mb-2">Style</h2>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <Label>Fond</Label>
                <input type="color" value={form.style.bg_color} onChange={(e) => setStyle("bg_color", e.target.value)} className="w-full h-10 rounded-xl mt-1" data-testid="style-bg" />
              </div>
              <div>
                <Label>Texte</Label>
                <input type="color" value={form.style.text_color} onChange={(e) => setStyle("text_color", e.target.value)} className="w-full h-10 rounded-xl mt-1" data-testid="style-text" />
              </div>
              <div>
                <Label>Accent</Label>
                <input type="color" value={form.style.accent_color} onChange={(e) => setStyle("accent_color", e.target.value)} className="w-full h-10 rounded-xl mt-1" data-testid="style-accent" />
              </div>
              <div className="col-span-3">
                <Label>Alignement</Label>
                <div className="flex gap-2 mt-1">
                  {["left", "center", "right"].map(a => (
                    <button key={a} type="button" onClick={() => setStyle("text_align", a)}
                      className={`flex-1 h-10 rounded-xl text-xs font-bold capitalize ${form.style.text_align === a ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-600"}`}
                      data-testid={`align-${a}`}>
                      {a === "left" ? "Gauche" : a === "center" ? "Centré" : "Droite"}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="flex gap-2 pt-4 border-t border-slate-100 mt-4">
              <Button type="button" variant="outline" onClick={() => submit(true)} disabled={loading} className="rounded-full" data-testid="save-draft">
                <Save className="w-4 h-4 mr-1" />Brouillon
              </Button>
              <Button type="button" onClick={() => submit(false)} disabled={loading || (quotaFull && !editMode)} className="flex-1 rounded-full bg-violet-600 hover:bg-violet-700" data-testid="submit-ad">
                <Send className="w-4 h-4 mr-1" />
                {loading ? "Envoi..." : editMode ? "Renvoyer en validation" : "Soumettre à validation"}
              </Button>
            </div>
          </div>

          {/* Preview */}
          <div className="lg:sticky lg:top-20 self-start">
            <div className="card-soft p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="font-bold text-slate-900">Aperçu</h2>
                <div className="flex gap-1">
                  <button onClick={() => setPreview("desktop")} className={`p-2 rounded-lg ${preview === "desktop" ? "bg-slate-900 text-white" : "bg-slate-100"}`} data-testid="preview-desktop"><Monitor className="w-4 h-4" /></button>
                  <button onClick={() => setPreview("mobile")} className={`p-2 rounded-lg ${preview === "mobile" ? "bg-slate-900 text-white" : "bg-slate-100"}`} data-testid="preview-mobile"><Smartphone className="w-4 h-4" /></button>
                </div>
              </div>
              <div className={preview === "mobile" ? "max-w-[360px] mx-auto" : ""} data-testid="ad-preview-frame">
                <SponsoredAdPreview ad={form} mode={preview} />
              </div>
              <div className="mt-3 text-[11px] text-slate-500 text-center">Aperçu — {preview === "mobile" ? "mobile (360px)" : "desktop"}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// Reusable preview/render component
export function SponsoredAdPreview({ ad, mode = "desktop", onClick }) {
  const st = ad.style || {};
  return (
    <div
      className="overflow-hidden border border-slate-100 shadow-sm cursor-pointer hover:shadow-md transition-shadow"
      style={{
        background: st.bg_color || "#fff",
        color: st.text_color || "#0f172a",
        textAlign: st.text_align || "left",
        borderRadius: `${st.border_radius ?? 16}px`,
      }}
      onClick={onClick}
      data-testid="ad-preview"
    >
      <div className="px-3 pt-3 flex items-center justify-between">
        <Badge className="border-0 rounded-full text-[9px] uppercase tracking-wider" style={{ background: st.accent_color, color: "#fff" }}>
          Sponsorisé
        </Badge>
        {ad.logo && <img src={ad.logo} alt="logo" className="w-7 h-7 rounded-full object-cover" />}
      </div>
      {ad.image && (
        <div className={`mt-3 ${mode === "mobile" ? "aspect-[16/10]" : "aspect-[16/9]"} bg-slate-100 overflow-hidden`}>
          <img src={ad.image} alt="" className="w-full h-full object-cover" />
        </div>
      )}
      <div className="px-4 py-3">
        <div className="font-bold text-base leading-snug">{ad.title || "Titre de votre publicité"}</div>
        <div className="text-sm mt-1 opacity-80 line-clamp-3">{ad.short_text || "Texte court qui présente votre offre."}</div>
        <div className="text-[11px] mt-2 opacity-60">
          {ad.company_name || "Votre entreprise"}
          {ad.city && ` · ${ad.city}`}
          {ad.region && ` · ${ad.region}`}
        </div>
        {ad.promo_code && (
          <div className="mt-3 inline-block text-[11px] font-bold border border-dashed px-3 py-1.5 rounded-lg" style={{ borderColor: st.accent_color, color: st.accent_color }}>
            Code : <span className="font-mono">{ad.promo_code}</span>
          </div>
        )}
        {(ad.cta_url || ad.cta_label) && (
          <button
            type="button"
            className="mt-3 w-full text-sm font-bold py-2.5 rounded-xl"
            style={{ background: st.accent_color || "#2563eb", color: "#fff" }}
          >
            {ad.cta_label || "Découvrir"}
          </button>
        )}
      </div>
    </div>
  );
}
