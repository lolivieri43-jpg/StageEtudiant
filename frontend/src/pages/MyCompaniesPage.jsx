import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { Badge } from "../components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { Download, Trash2, Sparkles, Building2, MapPin, FileSpreadsheet, FileText, FileType2 } from "lucide-react";
import { toast } from "sonner";

const STATUSES = [
  { id: "a_contacter", label: "À contacter", color: "bg-slate-100 text-slate-700" },
  { id: "cv_envoye", label: "CV envoyé", color: "bg-blue-50 text-blue-700" },
  { id: "relance_a_faire", label: "Relance à faire", color: "bg-amber-50 text-amber-700" },
  { id: "relance", label: "Relancé", color: "bg-amber-50 text-amber-700" },
  { id: "reponse_recue", label: "Réponse reçue", color: "bg-violet-50 text-violet-700" },
  { id: "entretien_obtenu", label: "Entretien obtenu", color: "bg-violet-50 text-violet-700" },
  { id: "refus", label: "Refus", color: "bg-rose-50 text-rose-700" },
  { id: "stage_obtenu", label: "Stage obtenu", color: "bg-emerald-50 text-emerald-700" },
  { id: "alternance_obtenue", label: "Alternance obtenue", color: "bg-emerald-50 text-emerald-700" },
];

export default function MyCompaniesPage() {
  const [items, setItems] = useState([]);
  const [filter, setFilter] = useState("");
  const [aiOpen, setAiOpen] = useState(null);

  const load = async () => {
    const { data } = await api.get(`/me/companies${filter ? `?status=${filter}` : ""}`);
    setItems(data);
  };
  useEffect(() => { load(); }, [filter]);

  const update = async (id, body) => {
    await api.patch(`/me/companies/${id}`, body);
    load();
  };
  const remove = async (id) => {
    if (!window.confirm("Retirer cette entreprise de votre liste ?")) return;
    await api.delete(`/me/companies/${id}`);
    load();
  };
  const exportAs = async (fmt) => {
    try {
      const resp = await api.get(`/me/companies/export?fmt=${fmt}`, { responseType: "blob" });
      const blob = new Blob([resp.data]);
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `entreprises.${fmt}`;
      a.click();
      toast.success(`Export ${fmt.toUpperCase()} prêt`);
    } catch {
      toast.error("Export impossible");
    }
  };

  return (
    <div className="min-h-screen pt-20 pb-12 bg-slate-50">
      <div className="max-w-6xl mx-auto px-6">
        <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
          <div>
            <h1 className="text-3xl font-black tracking-tight text-slate-900">Mes entreprises</h1>
            <p className="text-slate-500">Suivi de mes candidatures spontanées</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => exportAs("csv")} variant="outline" className="rounded-full" data-testid="export-csv"><FileText className="w-4 h-4 mr-1" />CSV</Button>
            <Button onClick={() => exportAs("xlsx")} variant="outline" className="rounded-full" data-testid="export-xlsx"><FileSpreadsheet className="w-4 h-4 mr-1" />Excel</Button>
            <Button onClick={() => exportAs("pdf")} variant="outline" className="rounded-full" data-testid="export-pdf"><FileType2 className="w-4 h-4 mr-1" />PDF</Button>
            <Link to="/companies"><Button className="rounded-full bg-blue-600 hover:bg-blue-700">Trouver des entreprises</Button></Link>
          </div>
        </div>

        <div className="card-soft p-4 mb-4 flex flex-wrap gap-2" data-testid="status-filters">
          <button onClick={() => setFilter("")} className={`text-xs font-semibold px-3 py-1.5 rounded-full ${!filter ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-600"}`}>Tous ({items.length})</button>
          {STATUSES.map(s => (
            <button key={s.id} onClick={() => setFilter(s.id)} className={`text-xs font-semibold px-3 py-1.5 rounded-full ${filter === s.id ? "bg-blue-600 text-white" : s.color}`} data-testid={`filter-${s.id}`}>{s.label}</button>
          ))}
        </div>

        {items.length === 0 && (
          <div className="card-soft p-12 text-center text-slate-400" data-testid="mc-empty">
            <Building2 className="w-10 h-10 mx-auto mb-3 text-slate-300" />
            <div className="font-semibold">Aucune entreprise dans cette catégorie</div>
            <div className="text-sm mt-1">Allez sur <Link to="/companies" className="underline text-blue-600">/companies</Link> et ajoutez-en à votre liste.</div>
          </div>
        )}

        <div className="space-y-3">
          {items.map(it => (
            <div key={it.id} className="card-soft p-5" data-testid={`mc-row-${it.id}`}>
              <div className="flex items-start gap-3 flex-wrap">
                <div className="w-10 h-10 rounded-xl bg-blue-50 grid place-items-center shrink-0">
                  <Building2 className="w-5 h-5 text-blue-600" />
                </div>
                <div className="flex-1 min-w-[200px]">
                  <div className="font-bold text-slate-900">{it.name}</div>
                  <div className="text-xs text-slate-500 flex items-center gap-1"><MapPin className="w-3 h-3" />{[it.city, it.naf_code].filter(Boolean).join(" · ") || "—"}</div>
                  {it.siret && <div className="text-[10px] text-slate-400 font-mono mt-0.5">SIRET {it.siret}</div>}
                </div>
                <select
                  value={it.status}
                  onChange={(e) => update(it.id, { status: e.target.value })}
                  className="rounded-full border border-slate-200 px-3 h-8 text-xs bg-white"
                  data-testid={`mc-status-${it.id}`}
                >
                  {STATUSES.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
                </select>
                <Button onClick={() => setAiOpen(it)} variant="outline" size="sm" className="rounded-full text-violet-700 border-violet-200" data-testid={`mc-ai-${it.id}`}>
                  <Sparkles className="w-3.5 h-3.5 mr-1" />Message IA
                </Button>
                <Button onClick={() => remove(it.id)} variant="outline" size="icon" className="rounded-full text-rose-600 border-rose-200" data-testid={`mc-del-${it.id}`}>
                  <Trash2 className="w-4 h-4" />
                </Button>
              </div>
              <div className="mt-3 grid sm:grid-cols-3 gap-2">
                <Input type="date" value={it.relance_date || ""} onChange={(e) => update(it.id, { relance_date: e.target.value })} className="rounded-xl text-sm" placeholder="Relance" data-testid={`mc-date-${it.id}`} />
                <Input value={it.email || ""} onChange={(e) => update(it.id, { email: e.target.value })} className="rounded-xl text-sm" placeholder="Email contact" />
                <Input value={it.note || ""} onChange={(e) => update(it.id, { note: e.target.value })} className="rounded-xl text-sm sm:col-span-1" placeholder="Note" data-testid={`mc-note-${it.id}`} />
              </div>
            </div>
          ))}
        </div>
      </div>

      {aiOpen && <SpontaneousMessageDialog company={aiOpen} onClose={() => setAiOpen(null)} />}
    </div>
  );
}

function SpontaneousMessageDialog({ company, onClose }) {
  const [brief, setBrief] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState("");
  const gen = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/ai/spontaneous-message", { company, brief });
      setResult(data.message || "");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erreur IA");
    } finally { setBusy(false); }
  };
  return (
    <Dialog open={true} onOpenChange={onClose}>
      <DialogContent className="max-h-[85vh] overflow-y-auto">
        <DialogHeader><DialogTitle>Message de candidature spontanée — {company.name}</DialogTitle></DialogHeader>
        <p className="text-xs text-slate-500">L'IA génère un message court basé sur votre CV en ligne et cette entreprise.</p>
        <Textarea value={brief} onChange={(e) => setBrief(e.target.value)} rows={2} className="rounded-xl" placeholder="Précisions (poste visé, dates, motivation...)" data-testid="ai-brief" />
        <Button onClick={gen} disabled={busy} className="rounded-full bg-violet-600 hover:bg-violet-700" data-testid="ai-generate">
          <Sparkles className="w-4 h-4 mr-1" />{busy ? "Génération..." : "Générer le message"}
        </Button>
        {result && (
          <div className="mt-3 bg-violet-50 rounded-xl p-4 text-sm whitespace-pre-wrap" data-testid="ai-result">
            {result}
            <Button onClick={() => { navigator.clipboard.writeText(result); toast.success("Copié"); }} variant="outline" size="sm" className="mt-3 rounded-full">Copier</Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
