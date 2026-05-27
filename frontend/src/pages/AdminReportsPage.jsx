import React, { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Flag, Check, Trash2, RefreshCw, AlertCircle, ExternalLink, MessageSquare, FileText } from "lucide-react";
import { toast } from "sonner";

const STATUSES = [
  { id: "pending", label: "À traiter", color: "bg-amber-100 text-amber-700" },
  { id: "kept", label: "Conservés", color: "bg-emerald-100 text-emerald-700" },
  { id: "removed", label: "Supprimés", color: "bg-rose-100 text-rose-700" },
  { id: "all", label: "Tous", color: "bg-slate-200 text-slate-800" },
];

const REASON_LABELS = {
  spam: "Spam",
  harassment: "Harcèlement",
  hate_speech: "Discours haineux",
  violence: "Violence",
  inappropriate: "Inapproprié",
  misinformation: "Désinformation",
  scam: "Arnaque",
  other: "Autre",
};

export default function AdminReportsPage() {
  const { user } = useAuth();
  const [data, setData] = useState({ reports: [], counts: {} });
  const [status, setStatus] = useState("pending");
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const p = new URLSearchParams();
      if (status) p.set("status", status);
      const { data } = await api.get(`/admin/reports?${p.toString()}`);
      setData(data);
    } finally { setLoading(false); }
  }, [status]);

  useEffect(() => { if (user?.role === "admin") load(); }, [user, load]);

  const dismiss = async (reportId) => {
    const note = window.prompt("Note de modération (facultatif) :", "") || "";
    try {
      await api.post(`/admin/reports/${reportId}/dismiss`, { note });
      toast.success("Signalement clos (contenu conservé)");
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Erreur");
    }
  };

  const removeContent = async (reportId, label) => {
    const reason = window.prompt(`Raison de la suppression du ${label} (visible par l'auteur) :`, "Contenu inapproprié");
    if (!reason) return;
    if (!window.confirm(`Confirmer la suppression de ce ${label} ?`)) return;
    try {
      await api.post(`/admin/reports/${reportId}/remove`, { reason });
      toast.success(`${label === "post" ? "Publication" : "Commentaire"} supprimé`);
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Erreur");
    }
  };

  const deleteReport = async (reportId) => {
    if (!window.confirm("Archiver définitivement ce signalement ?")) return;
    await api.delete(`/admin/reports/${reportId}`);
    toast.success("Signalement archivé");
    load();
  };

  if (user?.role !== "admin") {
    return <div className="pt-24 text-center text-slate-500">Accès admin uniquement.</div>;
  }

  return (
    <div className="min-h-screen pt-20 pb-12 bg-slate-50">
      <div className="max-w-6xl mx-auto px-6">
        <div className="flex items-end justify-between mb-6 flex-wrap gap-3">
          <div>
            <h1 className="text-3xl font-black tracking-tight text-slate-900 flex items-center gap-2">
              <Flag className="w-7 h-7 text-rose-600" />Signalements
            </h1>
            <p className="text-slate-500 mt-1">Modérez les publications et commentaires signalés par les utilisateurs</p>
          </div>
          <div className="flex gap-2">
            <Link to="/admin/deals"><Button variant="outline" className="rounded-full">Bons plans</Button></Link>
            <Link to="/admin/ads"><Button variant="outline" className="rounded-full">Publicités</Button></Link>
            <Button variant="outline" className="rounded-full" onClick={load} disabled={loading} data-testid="refresh-reports">
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            </Button>
          </div>
        </div>

        <div className="flex flex-wrap gap-2 mb-4" data-testid="reports-tabs">
          {STATUSES.map(s => (
            <button key={s.id} onClick={() => setStatus(s.id)} data-testid={`report-tab-${s.id}`}
                    className={`px-4 py-1.5 rounded-full text-xs font-bold transition-all flex items-center gap-2 ${
                      status === s.id ? "bg-slate-900 text-white" : "bg-white border border-slate-200 text-slate-600 hover:border-slate-300"
                    }`}>
              {s.label}
              <span className={`px-2 py-0.5 rounded-full text-[10px] ${status === s.id ? "bg-white/20" : s.color}`}>
                {data.counts[s.id] ?? 0}
              </span>
            </button>
          ))}
        </div>

        <div className="space-y-3">
          {data.reports.length === 0 && (
            <div className="card-soft p-12 text-center text-slate-500">
              <Flag className="w-10 h-10 mx-auto text-slate-300 mb-3" />
              Aucun signalement dans cet état
            </div>
          )}
          {data.reports.map(r => (
            <ReportRow key={r.report_id} report={r} onDismiss={() => dismiss(r.report_id)}
                       onRemove={() => removeContent(r.report_id, r.target_type)}
                       onDelete={() => deleteReport(r.report_id)} />
          ))}
        </div>
      </div>
    </div>
  );
}

const STATUS_BADGE = {
  pending: "bg-amber-100 text-amber-700",
  kept: "bg-emerald-100 text-emerald-700",
  removed: "bg-rose-100 text-rose-700",
};

function ReportRow({ report, onDismiss, onRemove, onDelete }) {
  const r = report;
  const TargetIcon = r.target_type === "post" ? FileText : MessageSquare;
  const snapshot = r.target_snapshot;
  return (
    <div className="card-soft p-4" data-testid={`report-row-${r.report_id}`}>
      <div className="flex items-start gap-3">
        <div className="w-12 h-12 rounded-xl bg-rose-50 grid place-items-center text-rose-600 shrink-0">
          <TargetIcon className="w-5 h-5" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <Badge className={`border-0 rounded-full text-[10px] ${STATUS_BADGE[r.status] || "bg-slate-100"}`}>{r.status}</Badge>
            <Badge className="border-0 rounded-full text-[10px] bg-slate-100">{r.target_type === "post" ? "Publication" : "Commentaire"}</Badge>
            <Badge className="border-0 rounded-full text-[10px] bg-rose-100 text-rose-700">{REASON_LABELS[r.reason] || r.reason}</Badge>
            {!r.target_exists && (
              <Badge className="border-0 rounded-full text-[10px] bg-slate-100 text-slate-500">Cible supprimée</Badge>
            )}
          </div>
          {snapshot ? (
            <div className="bg-slate-50 border border-slate-100 rounded-xl p-3 text-sm">
              <div className="text-xs text-slate-500 mb-1">
                par {snapshot.author_name} · {(snapshot.created_at || "").slice(0, 10)}
              </div>
              <div className="text-slate-800 whitespace-pre-wrap line-clamp-3">{snapshot.content || <em>(contenu vide)</em>}</div>
              {snapshot.media && snapshot.media.length > 0 && (
                <div className="text-[11px] text-slate-500 mt-1">
                  {snapshot.media.length} média{snapshot.media.length > 1 ? "s" : ""} joint{snapshot.media.length > 1 ? "s" : ""}
                </div>
              )}
            </div>
          ) : (
            <div className="text-xs text-slate-400 italic">Contenu supprimé · extrait au moment du signalement : "{r.target_excerpt || "—"}"</div>
          )}
          {r.details && (
            <div className="text-[11px] text-slate-500 mt-2">Détails reporter : "{r.details}"</div>
          )}
          <div className="text-[11px] text-slate-400 mt-2 flex flex-wrap gap-2">
            <span>Signalé par {r.reporter_name}</span>
            <span>·</span>
            <span>{(r.created_at || "").slice(0, 16).replace("T", " ")}</span>
            {r.moderated_at && (
              <>
                <span>·</span>
                <span>Modéré : {(r.moderated_at || "").slice(0, 16).replace("T", " ")}</span>
              </>
            )}
          </div>
          {r.moderation_reason && (
            <div className="text-[11px] text-rose-600 mt-1">Motif suppression : {r.moderation_reason}</div>
          )}
          {r.moderation_note && (
            <div className="text-[11px] text-emerald-700 mt-1">Note : {r.moderation_note}</div>
          )}
        </div>
        <div className="flex flex-col gap-1 shrink-0">
          {r.target_exists && r.target_type === "post" && (
            <Link to={`/feed`} target="_blank" rel="noreferrer">
              <Button size="sm" variant="outline" className="rounded-full w-full" title="Voir le post">
                <ExternalLink className="w-4 h-4" />
              </Button>
            </Link>
          )}
          {r.status === "pending" && (
            <>
              <Button size="sm" className="rounded-full bg-emerald-600 hover:bg-emerald-700" onClick={onDismiss}
                      data-testid={`dismiss-${r.report_id}`} title="Conserver (faux signalement)">
                <Check className="w-4 h-4" />
              </Button>
              <Button size="sm" variant="outline" className="rounded-full text-rose-600 border-rose-200" onClick={onRemove}
                      data-testid={`remove-${r.report_id}`} title="Supprimer le contenu">
                <Trash2 className="w-4 h-4" />
              </Button>
            </>
          )}
          {r.status !== "pending" && (
            <Button size="sm" variant="outline" className="rounded-full text-slate-500" onClick={onDelete} title="Archiver le signalement">
              <AlertCircle className="w-4 h-4" />
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
