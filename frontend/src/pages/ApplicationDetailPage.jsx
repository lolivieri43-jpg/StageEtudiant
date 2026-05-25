import React, { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Textarea } from "../components/ui/textarea";
import { Download, MessageSquare, User, CheckCircle2, XCircle, Calendar, Archive, FileText, FileCheck2, Eye } from "lucide-react";
import { toast } from "sonner";
import { triggerBlobDownload } from "../lib/download";

const STATUS_LABELS = {
  envoyee: "Envoyée",
  retiree: "Retirée",
  vue: "Vue",
  en_analyse: "En analyse",
  entretien_propose: "Entretien proposé",
  acceptee: "Acceptée",
  refusee: "Refusée",
  archivee: "Archivée",
};

export default function ApplicationDetailPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [note, setNote] = useState("");

  const load = async () => {
    try {
      const { data } = await api.get(`/applications/${id}`);
      setData(data);
      setNote(data.application.company_note || "");
    } catch {
      navigate("/dashboard");
    }
  };
  useEffect(() => { load(); }, [id]);

  if (!data) return <div className="pt-24 text-center text-slate-400">Chargement...</div>;
  const { application: a, candidate, offer, documents } = data;
  const isCompany = user?.user_id === a.company_id;
  const isCandidate = user?.user_id === a.candidate_id;

  const downloadOnlineCvPdf = async () => {
    try {
      const tpl = a.online_cv_template || "modern";
      const resp = await api.get(`/applications/${id}/cv/export?template=${tpl}`, { responseType: "blob" });
      const blob = new Blob([resp.data], { type: "application/pdf" });
      triggerBlobDownload(blob, `CV-${candidate?.name?.replace(/\s/g, "_") || "candidat"}.pdf`);
      toast.success("Téléchargement lancé");
    } catch (err) {
      console.error("App CV download error", err);
      toast.error("Export PDF impossible");
    }
  };

  const setStatus = async (status) => {
    await api.patch(`/applications/${id}/status`, { status });
    toast.success(`Statut: ${STATUS_LABELS[status]}`);
    load();
  };
  const saveNote = async () => {
    await api.post(`/applications/${id}/note`, { note });
    toast.success("Note enregistrée");
  };
  const withdraw = async () => {
    if (!window.confirm("Retirer cette candidature ?")) return;
    await api.delete(`/applications/${id}`);
    toast.success("Candidature retirée");
    navigate("/dashboard");
  };

  return (
    <div className="min-h-screen pt-20 pb-12 bg-slate-50">
      <div className="max-w-5xl mx-auto px-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-3xl font-black tracking-tight text-slate-900">Candidature</h1>
            <p className="text-slate-500">{offer?.title}</p>
          </div>
          <Badge className="bg-blue-50 text-blue-700 border-0 rounded-full text-sm" data-testid="app-status-badge">{STATUS_LABELS[a.status] || a.status}</Badge>
        </div>

        <div className="grid lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            <div className="card-soft p-6">
              <h2 className="font-bold text-slate-900 mb-3">Message du candidat</h2>
              <p className="text-slate-700 whitespace-pre-wrap">{a.cover_letter || <em className="text-slate-400">Aucun message</em>}</p>
            </div>

            {isCompany && a.use_online_cv && a.online_cv_snapshot && (
              <div className="card-soft p-6" data-testid="online-cv-block">
                <div className="flex items-center justify-between mb-3 gap-2">
                  <h2 className="font-bold text-slate-900 flex items-center gap-2"><FileCheck2 className="w-4 h-4 text-blue-500" />CV en ligne du candidat</h2>
                  <div className="flex gap-2">
                    <Button onClick={downloadOnlineCvPdf} variant="outline" size="sm" className="rounded-full" data-testid="download-online-cv">
                      <Download className="w-3.5 h-3.5 mr-1" />Télécharger PDF
                    </Button>
                    <Link to={`/cv/${a.candidate_id}`}>
                      <Button variant="outline" size="sm" className="rounded-full" data-testid="view-cv-fullpage"><Eye className="w-3.5 h-3.5 mr-1" />Plein écran</Button>
                    </Link>
                  </div>
                </div>
                <OnlineCvPreview cv={a.online_cv_snapshot} />
              </div>
            )}

            {isCompany && (a.selected_documents?.length > 0) && (
              <div className="card-soft p-6">
                <h2 className="font-bold text-slate-900 mb-4">Documents joints à la candidature</h2>
                <div className="space-y-2">
                  {a.selected_documents.map(d => (
                    <a key={d.doc_id} href={`/api/files/${d.file_id}`} target="_blank" rel="noopener" className="flex items-center justify-between bg-slate-50 hover:bg-slate-100 rounded-xl p-3 transition" data-testid={`sel-doc-${d.doc_id}`}>
                      <div className="flex items-center gap-3">
                        <FileText className="w-5 h-5 text-blue-500" />
                        <div>
                          <div className="font-semibold text-slate-900 text-sm">{d.filename}</div>
                          <div className="text-xs text-slate-400">{d.doc_type}</div>
                        </div>
                      </div>
                      <Download className="w-4 h-4 text-slate-400" />
                    </a>
                  ))}
                </div>
              </div>
            )}

            {isCompany && documents && documents.length > 0 && (
              <div className="card-soft p-6">
                <h2 className="font-bold text-slate-900 mb-4">Autres documents publics du candidat</h2>
                <div className="space-y-2">
                  {documents.map(d => (
                    <a key={d.doc_id} href={`/api/files/${d.file_id}`} target="_blank" rel="noopener" className="flex items-center justify-between bg-slate-50 hover:bg-slate-100 rounded-xl p-3 transition" data-testid={`doc-${d.doc_id}`}>
                      <div className="flex items-center gap-3">
                        <FileText className="w-5 h-5 text-blue-500" />
                        <div>
                          <div className="font-semibold text-slate-900 text-sm">{d.filename}</div>
                          <div className="text-xs text-slate-400">{d.doc_type}</div>
                        </div>
                      </div>
                      <Download className="w-4 h-4 text-slate-400" />
                    </a>
                  ))}
                </div>
              </div>
            )}

            {isCompany && (
              <div className="card-soft p-6">
                <h2 className="font-bold text-slate-900 mb-3">Note interne</h2>
                <Textarea value={note} onChange={(e) => setNote(e.target.value)} rows={4} className="rounded-xl" placeholder="Vos notes privées sur ce candidat..." data-testid="company-note" />
                <Button onClick={saveNote} className="mt-3 rounded-full bg-blue-600 hover:bg-blue-700" data-testid="save-note">Enregistrer la note</Button>
              </div>
            )}

            {isCompany && (
              <div className="card-soft p-6">
                <h2 className="font-bold text-slate-900 mb-3">Actions</h2>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                  <Button onClick={() => setStatus("en_analyse")} variant="outline" className="rounded-full" data-testid="status-analyse">En analyse</Button>
                  <Button onClick={() => setStatus("entretien_propose")} variant="outline" className="rounded-full text-violet-600 border-violet-200" data-testid="status-interview"><Calendar className="w-3.5 h-3.5 mr-1" />Entretien</Button>
                  <Button onClick={() => setStatus("acceptee")} className="rounded-full bg-emerald-600 hover:bg-emerald-700" data-testid="status-accept"><CheckCircle2 className="w-3.5 h-3.5 mr-1" />Accepter</Button>
                  <Button onClick={() => setStatus("refusee")} variant="outline" className="rounded-full text-rose-600 border-rose-200" data-testid="status-refuse"><XCircle className="w-3.5 h-3.5 mr-1" />Refuser</Button>
                  <Button onClick={() => setStatus("archivee")} variant="outline" className="rounded-full" data-testid="status-archive"><Archive className="w-3.5 h-3.5 mr-1" />Archiver</Button>
                  <Link to={`/messages?user=${a.candidate_id}`}><Button variant="outline" className="rounded-full w-full" data-testid="msg-candidate"><MessageSquare className="w-3.5 h-3.5 mr-1" />Message</Button></Link>
                </div>
              </div>
            )}

            {isCandidate && a.status !== "retiree" && (
              <div className="card-soft p-6">
                <Button onClick={withdraw} variant="outline" className="rounded-full text-rose-600 border-rose-200" data-testid="withdraw-btn">Retirer ma candidature</Button>
              </div>
            )}
          </div>

          <aside className="card-soft p-6 h-fit space-y-4">
            {candidate && (
              <div>
                <div className="flex items-center gap-3 mb-3">
                  <div className="w-12 h-12 rounded-full bg-gradient-to-br from-blue-400 to-violet-400 grid place-items-center text-white font-bold">
                    {candidate.profile?.avatar ? <img src={candidate.profile.avatar} className="w-full h-full rounded-full object-cover" alt="" /> : candidate.name[0]}
                  </div>
                  <div>
                    <Link to={`/profile/${candidate.user_id}`} className="font-bold hover:text-blue-600">{candidate.name}</Link>
                    <div className="text-xs text-slate-500">{candidate.profile?.title}</div>
                  </div>
                </div>
                <Link to={`/profile/${candidate.user_id}`}><Button variant="outline" size="sm" className="rounded-full w-full" data-testid="view-profile"><User className="w-3.5 h-3.5 mr-1" />Voir le profil</Button></Link>
              </div>
            )}
            <div className="border-t border-slate-100 pt-4 text-xs space-y-2">
              <Row label="Envoyée le" value={new Date(a.created_at).toLocaleDateString("fr-FR")} />
              {a.viewed_at && <Row label="Vue le" value={new Date(a.viewed_at).toLocaleDateString("fr-FR")} />}
              <Row label="Statut" value={STATUS_LABELS[a.status] || a.status} />
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}
const Row = ({ label, value }) => (
  <div className="flex justify-between gap-2"><span className="text-slate-400">{label}</span><span className="font-semibold text-slate-700 text-right">{value}</span></div>
);

function OnlineCvPreview({ cv }) {
  if (!cv) return null;
  return (
    <div className="space-y-4 text-sm" data-testid="online-cv-preview">
      {cv.professional_title && (
        <div>
          <div className="text-xs uppercase tracking-wide text-slate-400 font-semibold">Titre</div>
          <div className="font-bold text-slate-900">{cv.professional_title}</div>
        </div>
      )}
      {cv.summary && (
        <div>
          <div className="text-xs uppercase tracking-wide text-slate-400 font-semibold mb-1">Profil</div>
          <p className="text-slate-700 whitespace-pre-wrap">{cv.summary}</p>
        </div>
      )}
      {(cv.experiences || []).length > 0 && (
        <div>
          <div className="text-xs uppercase tracking-wide text-slate-400 font-semibold mb-1">Expériences</div>
          <ul className="space-y-2">
            {cv.experiences.map((e, i) => (
              <li key={i} className="border-l-2 border-blue-200 pl-3">
                <div className="font-semibold text-slate-900">{e.job_title} — {e.company_name}</div>
                <div className="text-xs text-slate-500">{e.city} · {e.start_date} → {e.end_date || "En cours"} · {e.experience_type}</div>
                {e.description && <div className="text-slate-700 mt-0.5 whitespace-pre-wrap">{e.description}</div>}
              </li>
            ))}
          </ul>
        </div>
      )}
      {(cv.educations || []).length > 0 && (
        <div>
          <div className="text-xs uppercase tracking-wide text-slate-400 font-semibold mb-1">Formation</div>
          <ul className="space-y-2">
            {cv.educations.map((e, i) => (
              <li key={i} className="border-l-2 border-violet-200 pl-3">
                <div className="font-semibold text-slate-900">{e.degree} — {e.school}</div>
                <div className="text-xs text-slate-500">{e.city} · {e.start_date} → {e.end_date}</div>
                {e.description && <div className="text-slate-700">{e.description}</div>}
              </li>
            ))}
          </ul>
        </div>
      )}
      {(cv.skills || []).length > 0 && (
        <div>
          <div className="text-xs uppercase tracking-wide text-slate-400 font-semibold mb-1">Compétences</div>
          <div className="flex flex-wrap gap-1.5">
            {cv.skills.map((s, i) => <span key={i} className="rounded-full bg-violet-50 text-violet-700 text-xs px-2.5 py-0.5">{s}</span>)}
          </div>
        </div>
      )}
      {(cv.languages || []).length > 0 && (
        <div>
          <div className="text-xs uppercase tracking-wide text-slate-400 font-semibold mb-1">Langues</div>
          <div className="text-slate-700">{cv.languages.map(l => `${l.language} (${l.level})`).join(" · ")}</div>
        </div>
      )}
    </div>
  );
}
