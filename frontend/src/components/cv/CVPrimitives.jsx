import React, { useState } from "react";
import { Plus, Trash2, Sparkles } from "lucide-react";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import { Textarea } from "../ui/textarea";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { toast } from "sonner";
import api from "../../lib/api";

/** Card-style section wrapper used by every CV block. */
export const Section = ({ title, icon: Icon, children }) => (
  <div className="card-soft p-6 mb-6">
    <h2 className="font-bold text-slate-900 mb-4 flex items-center gap-2"><Icon className="w-4 h-4 text-blue-500" />{title}</h2>
    {children}
  </div>
);

/** Labelled text input — keeps the same data-testid contract as the legacy page. */
export const Field = ({ label, value, onChange, testid, type = "text" }) => (
  <div>
    <Label>{label}</Label>
    <Input type={type} value={value || ""} onChange={(e) => onChange(e.target.value)} className="rounded-xl mt-1" data-testid={testid} />
  </div>
);

/** Small violet "AI" button used for inline LLM helpers. */
export const AIButton = ({ children, onClick, busy, className = "" }) => (
  <Button type="button" size="sm" variant="outline" onClick={onClick} disabled={busy} className={`rounded-full text-violet-700 border-violet-200 ${className}`}>
    <Sparkles className="w-3.5 h-3.5 mr-1" />{busy ? "..." : children}
  </Button>
);

/** Tag-style skills editor with Enter to add and × to remove. */
export const SkillsEditor = ({ skills, onChange }) => {
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
          <Badge key={s} className="rounded-full bg-violet-50 text-violet-700 border-0 pr-1.5">
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

/** AI cover-letter generator, scoped to the current CV. */
export const CoverLetterAI = ({ cv }) => {
  const [context, setContext] = useState("");
  const [result, setResult] = useState("");
  const [busy, setBusy] = useState(false);
  const generate = async () => {
    setBusy(true);
    try {
      const profileSummary = `${cv.professional_title}. ${cv.summary}. Compétences: ${(cv.skills || []).join(", ")}`;
      const { data } = await api.post("/cv/ai/cover_letter", { text: profileSummary, context });
      setResult(data.suggestion);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erreur IA");
    } finally { setBusy(false); }
  };
  return (
    <div>
      <Label>Décrivez l&apos;offre ou l&apos;entreprise visée</Label>
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

/** Re-export shared icons for convenience so CVSections.jsx doesn't pull from lucide directly. */
export { Plus, Trash2 };
