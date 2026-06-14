import React from "react";
import {
  Briefcase, GraduationCap, Code, Languages as LanguagesIcon, FolderGit2, Award,
  FileCheck, Eye, Globe, Lock, Users as UsersIcon,
} from "lucide-react";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import { Textarea } from "../ui/textarea";
import { Badge } from "../ui/badge";
import { Section, Field, AIButton, SkillsEditor, Plus, Trash2 } from "./CVPrimitives";

const VISIBILITY = [
  { id: "public", label: "Public", icon: Globe },
  { id: "connected", label: "Contacts uniquement", icon: UsersIcon },
  { id: "after_application", label: "Après candidature", icon: FileCheck },
  { id: "private", label: "Privé", icon: Lock },
];

/**
 * One "editor" prop bag groups every shared callback so each section component
 * keeps its signature small. `ed` = { cv, isOwn, upd, updArr, addItem, removeItem, aiAssist, aiBusy, aiTarget }
 */

export function VisibilityCard({ ed }) {
  if (!ed.isOwn) return null;
  return (
    <div className="card-soft p-6 mb-6">
      <h2 className="font-bold mb-3 flex items-center gap-2"><Eye className="w-4 h-4" />Visibilité de mon CV</h2>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {VISIBILITY.map(v => {
          const Icon = v.icon;
          return (
            <button key={v.id} onClick={() => ed.upd("visibility", v.id)}
                    className={`p-3 rounded-xl border-2 text-sm font-semibold text-left transition ${ed.cv.visibility === v.id ? "border-blue-500 bg-blue-50" : "border-slate-200 hover:bg-slate-50"}`}
                    data-testid={`vis-${v.id}`}>
              <Icon className="w-4 h-4 mb-1" />{v.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function MainInfo({ ed }) {
  const { cv, isOwn, upd } = ed;
  return (
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
              <option value="a_l_ecoute">À l&apos;écoute</option>
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
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={cv.email_visible} onChange={(e) => upd("email_visible", e.target.checked)} className="accent-blue-600" />Afficher l&apos;email</label>
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
  );
}

export function SummaryBlock({ ed }) {
  const { cv, isOwn, upd, aiAssist, aiBusy, aiTarget } = ed;
  return (
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
  );
}

export function Experiences({ ed }) {
  const { cv, isOwn, updArr, addItem, removeItem, aiAssist, aiBusy } = ed;
  return (
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
  );
}

export function Educations({ ed }) {
  const { cv, isOwn, updArr, addItem, removeItem } = ed;
  return (
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
  );
}

export function Skills({ ed }) {
  const { cv, isOwn, upd, aiAssist, aiBusy } = ed;
  return (
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
  );
}

export function LanguagesBlock({ ed }) {
  const { cv, isOwn, updArr, addItem, removeItem } = ed;
  return (
    <Section title="Langues" icon={LanguagesIcon}>
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
  );
}

export function Projects({ ed }) {
  const { cv, isOwn, updArr, addItem, removeItem } = ed;
  return (
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
              {p.link && <a href={p.link} target="_blank" rel="noopener noreferrer" className="text-blue-600 text-xs">{p.link}</a>}
            </>
          )}
        </div>
      ))}
      {isOwn && <Button onClick={() => addItem("projects", { name: "", description: "", link: "" })} variant="outline" className="rounded-full"><Plus className="w-4 h-4 mr-1" />Ajouter un projet</Button>}
    </Section>
  );
}

export function Certifications({ ed }) {
  const { cv, isOwn, updArr, addItem, removeItem } = ed;
  return (
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
  );
}
