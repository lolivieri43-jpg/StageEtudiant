import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Download, Save, Sparkles, Lock } from "lucide-react";
import { toast } from "sonner";

import api from "../lib/api";
import { triggerBlobDownload } from "../lib/download";
import { useAuth } from "../context/AuthContext";
import { Button } from "../components/ui/button";
import { Section, CoverLetterAI } from "../components/cv/CVPrimitives";
import {
  VisibilityCard, MainInfo, SummaryBlock, Experiences, Educations,
  Skills, LanguagesBlock, Projects, Certifications,
} from "../components/cv/CVSections";

const TEMPLATES = [
  { id: "modern", label: "Moderne" },
  { id: "classique", label: "Classique" },
  { id: "etudiant", label: "Étudiant" },
  { id: "alternance", label: "Alternance" },
  { id: "professionnel", label: "Professionnel" },
];

export default function CVPage() {
  const { id: paramId } = useParams();
  const { user } = useAuth();
  // eslint-disable-next-line no-unused-vars
  const navigate = useNavigate();
  const targetId = paramId || user?.user_id;
  const isOwn = !!user && targetId === user.user_id;

  const [cv, setCv] = useState(null);
  const [owner, setOwner] = useState(null);
  const [template, setTemplate] = useState("modern");
  const [saving, setSaving] = useState(false);
  const [aiTarget, setAiTarget] = useState(null);
  const [aiBusy, setAiBusy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!targetId) return;
    (async () => {
      try {
        const [ownerData, cvData] = await Promise.all([
          api.get(`/users/${targetId}`).then(r => r.data),
          (isOwn ? api.get("/cv") : api.get(`/users/${targetId}/cv`)).then(r => r.data),
        ]);
        setOwner(ownerData);
        setCv(cvData);
        if (cvData?.pdf_template) setTemplate(cvData.pdf_template);
      } catch (err) {
        setError(err.response?.data?.detail || "CV non disponible");
      }
    })();
  }, [targetId, isOwn]);

  const save = async () => {
    if (!isOwn) return;
    setSaving(true);
    try {
      await api.put("/cv", { ...cv, pdf_template: template });
      toast.success("CV enregistré");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erreur");
    } finally {
      setSaving(false);
    }
  };

  const downloadPdf = async () => {
    const url = isOwn ? `/cv/export?template=${template}` : `/users/${targetId}/cv/export?template=${template}`;
    try {
      const resp = await api.get(url, { responseType: "blob" });
      const blob = new Blob([resp.data], { type: "application/pdf" });
      triggerBlobDownload(blob, `CV-${owner?.name?.replace(/\s/g, "_") || "candidat"}.pdf`);
      toast.success("Téléchargement lancé");
    } catch (err) {
      console.error("CV PDF download error", err);
      toast.error(err?.response?.data?.detail || "Export PDF impossible");
    }
  };

  const aiAssist = async (target, action, context = "") => {
    setAiBusy(true);
    setAiTarget(target);
    try {
      const { data } = await api.post(`/cv/ai/${action}`, { text: target.text || "", context });
      target.apply(data.suggestion.trim());
      toast.success("Suggestion IA appliquée");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erreur IA");
    } finally {
      setAiBusy(false);
      setAiTarget(null);
    }
  };

  if (error) return (
    <div className="min-h-screen pt-24 px-6 text-center">
      <div className="card-soft p-12 max-w-md mx-auto">
        <Lock className="w-12 h-12 mx-auto text-slate-300 mb-3" />
        <div className="font-bold text-slate-900 mb-2">{error}</div>
      </div>
    </div>
  );
  if (!cv || !owner) return <div className="pt-24 text-center text-slate-400">Chargement...</div>;

  // The "editor" prop bag shared by every section (helpers + state).
  const ed = {
    cv,
    isOwn,
    aiBusy,
    aiTarget,
    upd: (k, v) => setCv({ ...cv, [k]: v }),
    updArr: (k, idx, field, val) => {
      const list = [...(cv[k] || [])];
      list[idx] = { ...list[idx], [field]: val };
      setCv({ ...cv, [k]: list });
    },
    addItem: (k, item) => setCv({ ...cv, [k]: [...(cv[k] || []), item] }),
    removeItem: (k, idx) => setCv({ ...cv, [k]: cv[k].filter((_, i) => i !== idx) }),
    aiAssist,
  };

  return (
    <div className="min-h-screen pt-20 pb-12 bg-slate-50">
      <div className="max-w-4xl mx-auto px-6">
        {/* Header */}
        <div className="card-soft p-6 mb-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-black tracking-tight text-slate-900">{isOwn ? "Mon CV en ligne" : `CV de ${owner.name}`}</h1>
            <p className="text-slate-500 text-sm">Modifiable et exportable en PDF</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <select value={template} onChange={(e) => setTemplate(e.target.value)} className="rounded-full border border-slate-200 h-10 px-4 text-sm bg-white" data-testid="pdf-template">
              {TEMPLATES.map(t => <option key={t.id} value={t.id}>Modèle {t.label}</option>)}
            </select>
            <Button onClick={downloadPdf} variant="outline" className="rounded-full" data-testid="download-cv-pdf"><Download className="w-4 h-4 mr-1" />Télécharger PDF</Button>
            {isOwn && <Button onClick={save} disabled={saving} className="rounded-full bg-blue-600 hover:bg-blue-700" data-testid="save-cv"><Save className="w-4 h-4 mr-1" />{saving ? "..." : "Enregistrer"}</Button>}
          </div>
        </div>

        <VisibilityCard ed={ed} />
        <MainInfo ed={ed} />
        <SummaryBlock ed={ed} />
        <Experiences ed={ed} />
        <Educations ed={ed} />
        <Skills ed={ed} />
        <LanguagesBlock ed={ed} />
        <Projects ed={ed} />
        <Certifications ed={ed} />

        {/* AI cover letter helper */}
        {isOwn && (
          <Section title="Aide IA — Lettre de motivation" icon={Sparkles}>
            <CoverLetterAI cv={cv} />
          </Section>
        )}
      </div>
    </div>
  );
}
