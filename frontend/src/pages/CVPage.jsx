import React, { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import api from "../lib/api";
import { triggerBlobDownload } from "../lib/download";
import { useAuth } from "../context/AuthContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Badge } from "../components/ui/badge";
import {
  Briefcase, GraduationCap, Code, Languages, FolderGit2, Award, Plus, Trash2,
  Download, Save, Sparkles, Eye, Lock, Users as UsersIcon, FileCheck, Globe,
} from "lucide-react";
import { toast } from "sonner";

const TEMPLATES = [
  { id: "modern", label: "Moderne" },
  { id: "classique", label: "Classique" },
  { id: "etudiant", label: "Étudiant" },
  { id: "alternance", label: "Alternance" },
  { id: "professionnel", label: "Professionnel" },
];
const VISIBILITY = [
  { id: "public", label: "Public", icon: Globe },
  { id: "connected", label: "Contacts uniquement", icon: UsersIcon },
  { id: "after_application", label: "Après candidature", icon: FileCheck },
  { id: "private", label: "Privé", icon: Lock },
];

export default function CVPage() {
  const { id: paramId } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const targetId = paramId || user?.user_id;
  const isOwn = user && targetId === user.user_id;
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
      // Save preferred template alongside other CV data
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
      const { data } = await api.post(`/cv/ai/${action}`, {
        text: target.text || "",
        context,
      });
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

  const upd = (k, v) => setCv({ ...cv, [k]: v });
  const updArr = (k, idx, field, val) => {
    const list = [...(cv[k] || [])];
    list[idx] = { ...list[idx], [field]: val };
    setCv({ ...cv, [k]: list });
  };
  const addItem = (k, item) => setCv({ ...cv, [k]: [...(cv[k] || []), item] });
  const removeItem = (k, idx) => setCv({ ...cv, [k]: cv[k].filter((_, i) => i !== idx) });

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

        {/* Visibility + Header info */}
        {isOwn && (
          <div className="card-soft p-6 mb-6">
            <h2 className="font-bold mb-3 flex items-center gap-2"><Eye className="w-4 h-4" />Visibilité de mon CV</h2>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {VISIBILITY.map(v => {
                const Icon = v.icon;
                return (
                  <button key={v.id} onClick={() => upd("visibility", v.id)} className={`p-3 rounded-xl border-2 text-sm font-semibold text-left transition ${cv.visibility === v.id ? "border-blue-500 bg-blue-50" : "border-slate-200 hover:bg-slate-50"}`} data-testid={`vis-${v.id}`}>
                    <Icon className="w-4 h-4 mb-1" />{v.label}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Main info */}
        <Section title="Informations principales" icon={Briefcase}>
          {isOwn ? (
            <div className="grid sm:grid-cols-2 gap-3">
              <Field label="Titre professionnel" value={cv.professional_title} onChange={(v) => upd("professional_title", v)} testid="cv-title" />
              <Field label="Mobilité géographique" value={cv.mobility} onChange={(v) => upd("mobility", v)} testid="cv-mobility" />
              <Field label="Date de disponibilité" value={cv.availability_date} onChange={(v) => upd("availability_date", v)} type="date" testid="cv-availability" />
              <div>
                <Label>Statut</Label>
                <select value={cv.search_status} onChange={(e) => upd("search_status", e.target.value)} className="w-full rounded-xl border border-slate-200 h-10 px-3 mt-1" data-testid="cv-status">
                  <option value="en_recherche">En recherche active</option>
                  <option value="a_l_ecoute">À l'écoute</option>
                  <option value="non_disponible">Non disponible</option>
                </select>
              </div>
              <div>
                <Label>Type recherché</Label>
                <select value={cv.contract_type_searched} onChange={(e) => upd("contract_type_searched", e.target.value)} className="w-full rounded-xl border border-slate-200 h-10 px-3 mt-1" data-testid="cv-ct">
                  <option value="stage">Stage</option>
                  <option value="alternance">Alternance</option>
                  <option value="les_deux">Les deux</option>
                </select>
              </div>
              <div className="flex items-center gap-4 mt-2 col-span-2">
                <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={cv.email_visible} onChange={(e) => upd("email_visible", e.target.checked)} className="accent-blue-600" />Afficher l'email</label>
                <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={cv.phone_visible} onChange={(e) => upd("phone_visible", e.target.checked)} className="accent-blue-600" />Afficher le téléphone</label>
              </div>
            </div>
          ) : (
            <div className="space-y-1 text-sm">
              <div className="font-bold text-lg">{cv.professional_title || "—"}</div>
              {cv.mobility && <div className="text-slate-600">Mobilité: {cv.mobility}</div>}
              {cv.availability_date && <div className="text-slate-600">Disponible: {cv.availability_date}</div>}
              <div><Badge className="bg-emerald-50 text-emerald-700 border-0 rounded-full">{cv.search_status}</Badge> <Badge className="bg-blue-50 text-blue-700 border-0 rounded-full ml-1">{cv.contract_type_searched}</Badge></div>
            </div>
          )}
        </Section>

        {/* Summary */}
        <Section title="Résumé professionnel" icon={FileCheck}>
          {isOwn ? (
            <div>
              <Textarea value={cv.summary} onChange={(e) => upd("summary", e.target.value)} rows={4} className="rounded-xl" placeholder="Présentez-vous en quelques lignes : projet, objectif, type d'entreprise souhaitée..." data-testid="cv-summary" />
              <div className="flex flex-wrap gap-2 mt-2">
                <AIButton onClick={() => aiAssist({ text: cv.summary, apply: (s) => upd("summary", s) }, "improve")} busy={aiBusy && aiTarget?.text === cv.summary}>Améliorer</AIButton>
                <AIButton onClick={() => aiAssist({ text: cv.summary, apply: (s) => upd("summary", s) }, "correct")} busy={aiBusy}>Corriger fautes</AIButton>
                <AIButton onClick={() => aiAssist({ text: cv.professional_title + " " + cv.summary, apply: (s) => upd("summary", s) }, "summary", cv.professional_title)} busy={aiBusy}>Générer un résumé</AIButton>
              </div>
            </div>
          ) : <p className="text-slate-700 whitespace-pre-wrap">{cv.summary || <em className="text-slate-400">Pas de résumé</em>}</p>}
        </Section>

        {/* Experiences */}
        <Section title="Expériences" icon={Briefcase}>
          {(cv.experiences || []).map((e, i) => (
            <div key={i} className="border-l-2 border-blue-200 pl-4 mb-4" data-testid={`exp-${i}`}>
              {isOwn ? (
                <div className="grid sm:grid-cols-2 gap-2">
                  <Field label="Poste" value={e.job_title} onChange={(v) => updArr("experiences", i, "job_title", v)} testid={`exp-job-${i}`} />
                  <Field label="Entreprise" value={e.company_name} onChange={(v) => updArr("experiences", i, "company_name", v)} testid={`exp-company-${i}`} />
                  <Field label="Ville" value={e.city} onChange={(v) => updArr("experiences", i, "city", v)} />
                  <div>
                    <Label>Type</Label>
                    <select value={e.experience_type || "stage"} onChange={(ev) => updArr("experiences", i, "experience_type", ev.target.value)} className="w-full rounded-xl border border-slate-200 h-10 px-3 mt-1">
                      <option value="stage">Stage</option><option value="alternance">Alternance</option>
                      <option value="job_etudiant">Job étudiant</option><option value="benevolat">Bénévolat</option><option value="autre">Autre</option>
                    </select>
                  </div>
                  <Field label="Début" value={e.start_date} onChange={(v) => updArr("experiences", i, "start_date", v)} />
                  <Field label="Fin (vide si en cours)" value={e.end_date} onChange={(v) => updArr("experiences", i, "end_date", v)} />
                  <div className="sm:col-span-2">
                    <Label>Missions & description</Label>
                    <Textarea value={e.description} onChange={(ev) => updArr("experiences", i, "description", ev.target.value)} rows={3} className="rounded-xl mt-1" />
                    <div className="flex flex-wrap gap-2 mt-2">
                      <AIButton onClick={() => aiAssist({ text: e.description, apply: (s) => updArr("experiences", i, "description", s) }, "improve")} busy={aiBusy}>Améliorer</AIButton>
                      <AIButton onClick={() => aiAssist({ text: e.description, apply: (s) => updArr("experiences", i, "description", s) }, "rephrase")} busy={aiBusy}>Reformuler</AIButton>
                    </div>
                  </div>
                  <Button onClick={() => removeItem("experiences", i)} variant="outline" className="rounded-full text-rose-600 border-rose-200 sm:col-span-2 mt-2" data-testid={`del-exp-${i}`}><Trash2 className="w-3.5 h-3.5 mr-1" />Supprimer</Button>
                </div>
              ) : (
                <>
                  <div className="font-bold">{e.job_title} — {e.company_name}</div>
                  <div className="text-xs text-slate-500">{e.city} · {e.start_date} → {e.end_date || "En cours"} · {e.experience_type}</div>
                  {e.description && <div className="text-sm mt-1 whitespace-pre-wrap">{e.description}</div>}
                </>
              )}
            </div>
          ))}
          {isOwn && <Button onClick={() => addItem("experiences", { job_title: "", company_name: "", city: "", experience_type: "stage", start_date: "", end_date: "", description: "" })} variant="outline" className="rounded-full" data-testid="add-exp"><Plus className="w-4 h-4 mr-1" />Ajouter une expérience</Button>}
        </Section>

        {/* Educations */}
        <Section title="Formation" icon={GraduationCap}>
          {(cv.educations || []).map((e, i) => (
            <div key={i} className="border-l-2 border-violet-200 pl-4 mb-4" data-testid={`edu-${i}`}>
              {isOwn ? (
                <div className="grid sm:grid-cols-2 gap-2">
                  <Field label="Diplôme" value={e.degree} onChange={(v) => updArr("educations", i, "degree", v)} testid={`edu-degree-${i}`} />
                  <Field label="Établissement" value={e.school} onChange={(v) => updArr("educations", i, "school", v)} testid={`edu-school-${i}`} />
                  <Field label="Ville" value={e.city} onChange={(v) => updArr("educations", i, "city", v)} />
                  <Field label="Niveau" value={e.level} onChange={(v) => updArr("educations", i, "level", v)} />
                  <Field label="Début" value={e.start_date} onChange={(v) => updArr("educations", i, "start_date", v)} />
                  <Field label="Fin" value={e.end_date} onChange={(v) => updArr("educations", i, "end_date", v)} />
                  <div className="sm:col-span-2">
                    <Label>Spécialité / description</Label>
                    <Textarea value={e.description} onChange={(ev) => updArr("educations", i, "description", ev.target.value)} rows={2} className="rounded-xl mt-1" />
                  </div>
                  <Button onClick={() => removeItem("educations", i)} variant="outline" className="rounded-full text-rose-600 border-rose-200 sm:col-span-2"><Trash2 className="w-3.5 h-3.5 mr-1" />Supprimer</Button>
                </div>
              ) : (
                <>
                  <div className="font-bold">{e.degree} — {e.school}</div>
                  <div className="text-xs text-slate-500">{e.city} · {e.start_date} → {e.end_date}</div>
                  {e.description && <div className="text-sm mt-1">{e.description}</div>}
                </>
              )}
            </div>
          ))}
          {isOwn && <Button onClick={() => addItem("educations", { degree: "", school: "", city: "", start_date: "", end_date: "", description: "" })} variant="outline" className="rounded-full"><Plus className="w-4 h-4 mr-1" />Ajouter une formation</Button>}
        </Section>

        {/* Skills */}
        <Section title="Compétences" icon={Code}>
          {isOwn ? (
            <div>
              <SkillsEditor skills={cv.skills || []} onChange={(s) => upd("skills", s)} />
              <AIButton className="mt-3" onClick={() => aiAssist({ text: cv.professional_title + " " + cv.summary, apply: (s) => upd("skills", s.split(",").map(x => x.trim()).filter(Boolean)) }, "skills", cv.professional_title)} busy={aiBusy}>Suggérer des compétences</AIButton>
            </div>
          ) : (
            <div className="flex flex-wrap gap-2">
              {(cv.skills || []).map(s => <Badge key={s} className="rounded-full bg-violet-50 text-violet-700 border-0">{s}</Badge>)}
            </div>
          )}
        </Section>

        {/* Languages */}
        <Section title="Langues" icon={Languages}>
          {(cv.languages || []).map((l, i) => (
            <div key={i} className="flex gap-2 items-end mb-2" data-testid={`lang-${i}`}>
              {isOwn ? (
                <>
                  <Field label="Langue" value={l.language} onChange={(v) => updArr("languages", i, "language", v)} />
                  <div>
                    <Label>Niveau</Label>
                    <select value={l.level || "intermediaire"} onChange={(e) => updArr("languages", i, "level", e.target.value)} className="rounded-xl border border-slate-200 h-10 px-3 mt-1">
                      <option value="debutant">Débutant</option><option value="intermediaire">Intermédiaire</option>
                      <option value="avance">Avancé</option><option value="courant">Courant</option><option value="bilingue">Bilingue</option>
                    </select>
                  </div>
                  <Button onClick={() => removeItem("languages", i)} variant="outline" size="icon" className="rounded-full text-rose-600"><Trash2 className="w-4 h-4" /></Button>
                </>
              ) : (
                <div><span className="font-semibold">{l.language}</span> <span className="text-slate-500 text-sm">— {l.level}</span></div>
              )}
            </div>
          ))}
          {isOwn && <Button onClick={() => addItem("languages", { language: "", level: "intermediaire" })} variant="outline" className="rounded-full"><Plus className="w-4 h-4 mr-1" />Ajouter une langue</Button>}
        </Section>

        {/* Projects */}
        <Section title="Projets" icon={FolderGit2}>
          {(cv.projects || []).map((p, i) => (
            <div key={i} className="border-l-2 border-emerald-200 pl-4 mb-4" data-testid={`proj-${i}`}>
              {isOwn ? (
                <div className="grid sm:grid-cols-2 gap-2">
                  <Field label="Nom" value={p.name} onChange={(v) => updArr("projects", i, "name", v)} />
                  <Field label="Lien" value={p.link} onChange={(v) => updArr("projects", i, "link", v)} />
                  <div className="sm:col-span-2"><Label>Description</Label><Textarea value={p.description} onChange={(e) => updArr("projects", i, "description", e.target.value)} rows={2} className="rounded-xl mt-1" /></div>
                  <Button onClick={() => removeItem("projects", i)} variant="outline" className="rounded-full text-rose-600 border-rose-200 sm:col-span-2"><Trash2 className="w-3.5 h-3.5 mr-1" />Supprimer</Button>
                </div>
              ) : (
                <>
                  <div className="font-bold">{p.name}</div>
                  {p.description && <div className="text-sm mt-1">{p.description}</div>}
                  {p.link && <a href={p.link} target="_blank" rel="noopener" className="text-blue-600 text-xs">{p.link}</a>}
                </>
              )}
            </div>
          ))}
          {isOwn && <Button onClick={() => addItem("projects", { name: "", description: "", link: "" })} variant="outline" className="rounded-full"><Plus className="w-4 h-4 mr-1" />Ajouter un projet</Button>}
        </Section>

        {/* Certifications */}
        <Section title="Certifications" icon={Award}>
          {(cv.certifications || []).map((c, i) => (
            <div key={i} className="border-l-2 border-amber-200 pl-4 mb-3" data-testid={`cert-${i}`}>
              {isOwn ? (
                <div className="grid sm:grid-cols-3 gap-2">
                  <Field label="Nom" value={c.name} onChange={(v) => updArr("certifications", i, "name", v)} />
                  <Field label="Organisme" value={c.issuer} onChange={(v) => updArr("certifications", i, "issuer", v)} />
                  <Field label="Date" value={c.date} onChange={(v) => updArr("certifications", i, "date", v)} />
                  <Button onClick={() => removeItem("certifications", i)} variant="outline" className="rounded-full text-rose-600 border-rose-200 sm:col-span-3"><Trash2 className="w-3.5 h-3.5 mr-1" />Supprimer</Button>
                </div>
              ) : (
                <>
                  <div className="font-bold">{c.name}</div>
                  <div className="text-xs text-slate-500">{c.issuer} · {c.date}</div>
                </>
              )}
            </div>
          ))}
          {isOwn && <Button onClick={() => addItem("certifications", { name: "", issuer: "", date: "" })} variant="outline" className="rounded-full"><Plus className="w-4 h-4 mr-1" />Ajouter</Button>}
        </Section>

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

const Section = ({ title, icon: Icon, children }) => (
  <div className="card-soft p-6 mb-6">
    <h2 className="font-bold text-slate-900 mb-4 flex items-center gap-2"><Icon className="w-4 h-4 text-blue-500" />{title}</h2>
    {children}
  </div>
);
const Field = ({ label, value, onChange, testid, type = "text" }) => (
  <div>
    <Label>{label}</Label>
    <Input type={type} value={value || ""} onChange={(e) => onChange(e.target.value)} className="rounded-xl mt-1" data-testid={testid} />
  </div>
);
const AIButton = ({ children, onClick, busy, className = "" }) => (
  <Button type="button" size="sm" variant="outline" onClick={onClick} disabled={busy} className={`rounded-full text-violet-700 border-violet-200 ${className}`}>
    <Sparkles className="w-3.5 h-3.5 mr-1" />{busy ? "..." : children}
  </Button>
);

const SkillsEditor = ({ skills, onChange }) => {
  const [input, setInput] = useState("");
  const add = () => {
    const v = input.trim();
    if (v && !skills.includes(v)) onChange([...skills, v]);
    setInput("");
  };
  return (
    <div>
      <div className="flex flex-wrap gap-2 mb-3">
        {skills.map((s, i) => (
          <Badge key={i} className="rounded-full bg-violet-50 text-violet-700 border-0 pr-1.5">
            {s}
            <button onClick={() => onChange(skills.filter((_, j) => j !== i))} className="ml-1.5 hover:text-rose-600">×</button>
          </Badge>
        ))}
      </div>
      <div className="flex gap-2">
        <Input value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), add())} placeholder="Tapez une compétence et Entrée" className="rounded-xl flex-1" data-testid="skill-input" />
        <Button onClick={add} className="rounded-full" data-testid="add-skill"><Plus className="w-4 h-4" /></Button>
      </div>
    </div>
  );
};

const CoverLetterAI = ({ cv }) => {
  const [context, setContext] = useState("");
  const [result, setResult] = useState("");
  const [busy, setBusy] = useState(false);
  const generate = async () => {
    setBusy(true);
    try {
      const profileSummary = `${cv.professional_title}. ${cv.summary}. Compétences: ${(cv.skills||[]).join(", ")}`;
      const { data } = await api.post("/cv/ai/cover_letter", { text: profileSummary, context });
      setResult(data.suggestion);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erreur IA");
    } finally { setBusy(false); }
  };
  return (
    <div>
      <Label>Décrivez l'offre ou l'entreprise visée</Label>
      <Textarea value={context} onChange={(e) => setContext(e.target.value)} rows={2} className="rounded-xl mt-1 mb-3" placeholder="Ex: Stage développeur web chez TechNova à Lyon..." data-testid="ai-cover-context" />
      <Button onClick={generate} disabled={busy} className="rounded-full bg-violet-600 hover:bg-violet-700" data-testid="generate-cover"><Sparkles className="w-4 h-4 mr-1" />{busy ? "Génération..." : "Générer la lettre"}</Button>
      {result && (
        <div className="mt-4 bg-violet-50 rounded-xl p-4 text-sm whitespace-pre-wrap" data-testid="ai-cover-result">
          {result}
          <Button onClick={() => navigator.clipboard.writeText(result)} variant="outline" size="sm" className="mt-3 rounded-full">Copier</Button>
        </div>
      )}
    </div>
  );
};
