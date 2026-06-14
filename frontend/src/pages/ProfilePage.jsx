import React, { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import {
  CheckCircle2, MapPin, Briefcase, GraduationCap, MessageSquare, UserPlus, Edit2,
  X, UserCheck, UserMinus, FileCheck2,
} from "lucide-react";
import { toast } from "sonner";

import api, { backendUrl } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import OfferCard from "../components/OfferCard";
import PremiumBadge, { isPremiumActive } from "../components/PremiumBadge";
import ProfileEditDialog from "../components/profile/ProfileEditDialog";
import {
  ProfileGallery, ProfileDocuments, HiddenFileButton,
} from "../components/profile/ProfileMediaBlocks";

const STUDENT_STATUS = {
  en_recherche: { label: "En recherche active", color: "bg-emerald-500" },
  a_l_ecoute: { label: "À l'écoute", color: "bg-amber-400" },
  deja_trouve: { label: "Déjà trouvé", color: "bg-blue-400" },
  non_disponible: { label: "Non disponible", color: "bg-slate-400" },
};
const COMPANY_STATUS = {
  recrute_stagiaire: { label: "Recherche stagiaire", color: "bg-emerald-500" },
  recrute_alternant: { label: "Recherche alternant", color: "bg-violet-500" },
  recrute_les_deux: { label: "Recrute activement", color: "bg-emerald-500" },
  pas_de_recrutement: { label: "Pas de recrutement", color: "bg-slate-400" },
};

const Row = ({ label, value }) => (
  <div className="flex justify-between gap-3">
    <span className="text-slate-400">{label}</span>
    <span className="font-semibold text-slate-700 text-right">{value}</span>
  </div>
);

function resolveUrl(u) {
  if (!u) return u;
  if (u.startsWith("/api/")) return backendUrl(u);
  return u;
}

export default function ProfilePage() {
  const { id } = useParams();
  const { user, refreshUser } = useAuth();
  const navigate = useNavigate();
  const [profile, setProfile] = useState(null);
  const [offers, setOffers] = useState([]);
  const [docs, setDocs] = useState([]);
  const [gallery, setGallery] = useState([]);
  const [contactStatus, setContactStatus] = useState(null);
  const [editOpen, setEditOpen] = useState(false);
  const [form, setForm] = useState({});
  const [hasOnlineCv, setHasOnlineCv] = useState(false);

  const isOwn = user && user.user_id === id;

  const reload = async () => {
    const { data } = await api.get(`/users/${id}`);
    setProfile(data);
    setForm(data.profile || {});
    if (data.role === "company") {
      api.get(`/offers?company_id=${id}`).then((o) => setOffers(o.data));
      api.get(`/users/${id}/gallery`).then((g) => setGallery(g.data));
    }
    if (data.role === "candidate") {
      api.get(`/users/${id}/documents`).then((d) => setDocs(d.data)).catch(() => setDocs([]));
      api.get(`/users/${id}/cv`)
        .then(() => setHasOnlineCv(true))
        .catch((err) => setHasOnlineCv(err?.response?.status === 403));
    }
    if (user && !isOwn) {
      api.get(`/contacts/status/${id}`).then((c) => setContactStatus(c.data));
    }
  };

  useEffect(() => {
    reload().catch(() => navigate("/"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, navigate, user]);

  const saveProfile = async () => {
    try {
      await api.put("/profile-v2", form);
      await refreshUser();
      const { data } = await api.get(`/users/${id}`);
      setProfile(data);
      setEditOpen(false);
      toast.success("Profil mis à jour");
    } catch {
      toast.error("Erreur");
    }
  };

  const uploadMedia = async (kind, file) => {
    const fd = new FormData();
    fd.append("file", file);
    try {
      await api.post(`/me/${kind}`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success(kind === "avatar" ? "Photo de profil mise à jour" : "Bannière mise à jour");
      await refreshUser();
      reload();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erreur upload");
    }
  };
  const removeMedia = async (kind) => {
    if (!window.confirm(kind === "avatar" ? "Supprimer la photo ?" : "Supprimer la bannière ?")) return;
    await api.delete(`/me/${kind}`);
    await refreshUser();
    reload();
  };

  const requestContact = async () => {
    try {
      await api.post("/contacts/request", { to_user_id: id });
      toast.success("Invitation envoyée");
      reload();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erreur");
    }
  };
  const cancelInvite = async () => {
    if (!contactStatus?.request_id) return;
    await api.delete(`/contacts/request/${contactStatus.request_id}`);
    toast.success("Invitation annulée");
    reload();
  };
  const acceptInvite = async () => {
    if (!contactStatus?.request_id) return;
    await api.post(`/contacts/${contactStatus.request_id}/accept`);
    toast.success("Contact ajouté");
    reload();
  };
  const removeContact = async () => {
    if (!window.confirm("Retirer ce contact ?")) return;
    await api.delete(`/contacts/${id}`);
    toast.success("Contact retiré");
    reload();
  };
  const addDocument = async (file, doc_type = "cv", visibility = "after_application") => {
    await api.post("/me/documents", { file_id: file.file_id, filename: file.filename, doc_type, visibility });
    reload();
  };
  const deleteDocument = async (doc_id) => {
    await api.delete(`/me/documents/${doc_id}`);
    reload();
  };
  const addPhoto = async (file) => {
    await api.post("/me/gallery", { file_id: file.file_id, url: `/api/files/${file.file_id}`, title: file.filename });
    reload();
  };
  const removePhoto = async (photo_id) => {
    await api.delete(`/me/gallery/${photo_id}`);
    reload();
  };

  if (!profile) return <div className="pt-24 text-center text-slate-400">Chargement...</div>;

  const p = profile.profile || {};
  const isCompany = profile.role === "company";
  const statusInfo = isCompany ? COMPANY_STATUS[p.company_status] : STUDENT_STATUS[p.status];

  return (
    <div className="min-h-screen pt-16 pb-12 bg-slate-50">
      {/* Banner */}
      <div className="h-48 sm:h-64 bg-gradient-to-br from-blue-500 to-violet-600 relative overflow-hidden group">
        {p.banner && <img src={resolveUrl(p.banner)} alt="" className="w-full h-full object-cover" />}
        {isOwn && (
          <div className="absolute top-4 right-4 flex gap-2 opacity-0 group-hover:opacity-100 transition">
            <HiddenFileButton onUpload={(f) => uploadMedia("banner", f)} testid="banner-upload"
              className="rounded-full bg-white/90 px-3 py-1.5 text-xs font-semibold hover:bg-white">
              Modifier la bannière
            </HiddenFileButton>
            {p.banner && <Button onClick={() => removeMedia("banner")} size="sm" variant="outline" className="rounded-full bg-white/90" data-testid="remove-banner-btn"><X className="w-3.5 h-3.5" /></Button>}
          </div>
        )}
      </div>

      <div className="max-w-5xl mx-auto px-6">
        <div className="card-soft -mt-20 relative p-6 sm:p-8">
          <div className="flex flex-col sm:flex-row gap-5">
            <div className="w-28 h-28 rounded-2xl bg-white p-1 -mt-16 shrink-0 relative group">
              <div className="w-full h-full rounded-xl bg-slate-100 overflow-hidden grid place-items-center font-black text-2xl text-slate-400">
                {(p.avatar || p.logo) ? <img src={resolveUrl(p.avatar || p.logo)} alt="" className="w-full h-full object-cover" /> : profile.name[0]}
              </div>
              {isOwn && (
                <div className="absolute bottom-1 right-1 flex gap-1">
                  <HiddenFileButton onUpload={(f) => uploadMedia("avatar", f)} testid="avatar-upload"
                    className="bg-white rounded-full p-1.5 shadow-md hover:bg-blue-50">
                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="text-blue-600"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>
                  </HiddenFileButton>
                  {(p.avatar || p.logo) && <button onClick={() => removeMedia("avatar")} className="bg-white rounded-full p-1.5 shadow-md hover:bg-rose-50" data-testid="remove-avatar-btn"><X className="w-3.5 h-3.5 text-rose-600" /></button>}
                </div>
              )}
            </div>
            <div className="flex-1">
              <div className="flex flex-wrap items-center gap-2 mb-1">
                <h1 className="text-2xl sm:text-3xl font-black tracking-tight text-slate-900" data-testid="profile-name">{profile.name}</h1>
                {p.verified && <CheckCircle2 className="w-5 h-5 text-blue-500" />}
                {isPremiumActive(profile) && (
                  <PremiumBadge role={isCompany ? "company" : "candidate"} size="sm" />
                )}
              </div>
              <p className="text-slate-600 mb-3">{p.title || p.sector || (isCompany ? "Entreprise" : "Étudiant·e")}</p>
              {statusInfo && (
                <div className="flex items-center gap-1.5 mb-2" data-testid="profile-status">
                  <span className={`w-2.5 h-2.5 rounded-full ${statusInfo.color}`} />
                  <span className="text-sm font-semibold text-slate-700">{statusInfo.label}</span>
                </div>
              )}
              <div className="flex flex-wrap items-center gap-3 text-sm text-slate-500">
                {p.city && <span className="flex items-center gap-1"><MapPin className="w-3.5 h-3.5" />{p.city}</span>}
                {p.level && <span className="flex items-center gap-1"><GraduationCap className="w-3.5 h-3.5" />{p.level}</span>}
                {p.size && <span className="flex items-center gap-1"><Briefcase className="w-3.5 h-3.5" />{p.size} salariés</span>}
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              {isOwn ? (
                <>
                  <Button onClick={() => setEditOpen(true)} variant="outline" className="rounded-full" data-testid="edit-profile-btn"><Edit2 className="w-4 h-4 mr-1" />Modifier</Button>
                  {profile.role === "candidate" && (
                    <Link to="/cv"><Button variant="outline" className="rounded-full" data-testid="my-cv-btn"><FileCheck2 className="w-4 h-4 mr-1" />Mon CV en ligne</Button></Link>
                  )}
                </>
              ) : user ? (
                <>
                  {profile.role === "candidate" && hasOnlineCv && (
                    <Link to={`/cv/${id}`}><Button variant="outline" className="rounded-full" data-testid="view-cv-btn"><FileCheck2 className="w-4 h-4 mr-1" />Voir le CV en ligne</Button></Link>
                  )}
                  {contactStatus?.status === "connected" && <Button onClick={() => navigate(`/messages?user=${id}`)} className="rounded-full bg-blue-600 hover:bg-blue-700" data-testid="message-btn"><MessageSquare className="w-4 h-4 mr-1" />Message</Button>}
                  {contactStatus?.status === "none" && <Button onClick={requestContact} className="rounded-full bg-blue-600 hover:bg-blue-700" data-testid="contact-btn"><UserPlus className="w-4 h-4 mr-1" />Ajouter en contact</Button>}
                  {contactStatus?.status === "sent" && <Button onClick={cancelInvite} variant="outline" className="rounded-full" data-testid="cancel-invite-btn">Invitation envoyée</Button>}
                  {contactStatus?.status === "received" && <Button onClick={acceptInvite} className="rounded-full bg-emerald-600 hover:bg-emerald-700" data-testid="accept-invite-btn"><UserCheck className="w-4 h-4 mr-1" />Accepter l&apos;invitation</Button>}
                  {contactStatus?.status === "connected" && <Button onClick={removeContact} variant="outline" size="icon" className="rounded-full" data-testid="remove-contact-btn"><UserMinus className="w-4 h-4" /></Button>}
                  {contactStatus?.status !== "connected" && <Button onClick={() => navigate(`/messages?user=${id}`)} variant="outline" className="rounded-full" data-testid="message-btn-fallback"><MessageSquare className="w-4 h-4 mr-1" />Message</Button>}
                </>
              ) : null}
            </div>
          </div>
        </div>

        <div className="grid lg:grid-cols-3 gap-6 mt-6">
          <div className="lg:col-span-2 space-y-6">
            {p.description && (
              <div className="card-soft p-6">
                <h2 className="font-bold mb-3">À propos</h2>
                <p className="text-slate-600 leading-relaxed whitespace-pre-wrap">{p.description}</p>
              </div>
            )}
            {p.skills && p.skills.length > 0 && (
              <div className="card-soft p-6">
                <h2 className="font-bold mb-3">Compétences</h2>
                <div className="flex flex-wrap gap-2">
                  {p.skills.map(s => <Badge key={s} className="rounded-full bg-violet-50 text-violet-700 border-0">{s}</Badge>)}
                </div>
              </div>
            )}
            {isCompany && offers.length > 0 && (
              <div>
                <h2 className="font-bold mb-3 text-slate-900">Offres en cours ({offers.length})</h2>
                <div className="space-y-3">
                  {offers.map(o => <OfferCard key={o.offer_id} offer={o} />)}
                </div>
              </div>
            )}

            {isCompany && (gallery.length > 0 || isOwn) && (
              <ProfileGallery photos={gallery} isOwn={isOwn} onAdd={addPhoto} onRemove={removePhoto} />
            )}

            {!isCompany && (docs.length > 0 || isOwn) && (
              <ProfileDocuments docs={docs} isOwn={isOwn} onAdd={(f) => addDocument(f)} onDelete={deleteDocument} />
            )}
          </div>
          <aside className="space-y-4">
            <div className="card-soft p-6 text-sm space-y-3">
              {p.school && <Row label="École" value={p.school} />}
              {p.sector && <Row label="Secteur" value={p.sector} />}
              {p.domain && <Row label="Domaine" value={p.domain} />}
              {p.contract_type && <Row label="Recherche" value={p.contract_type === "stage" ? "Stage" : "Alternance"} />}
              {p.duration && <Row label="Durée" value={p.duration} />}
              {p.website && <Row label="Site web" value={<a href={p.website} target="_blank" rel="noopener noreferrer" className="text-blue-600">{p.website}</a>} />}
              {p.linkedin_url && <Row label="LinkedIn" value={<a href={p.linkedin_url} target="_blank" rel="noopener noreferrer" className="text-blue-600">Voir</a>} />}
            </div>
          </aside>
        </div>
      </div>

      <ProfileEditDialog
        open={editOpen}
        onOpenChange={setEditOpen}
        isCompany={isCompany}
        form={form}
        setForm={setForm}
        onSave={saveProfile}
      />
    </div>
  );
}
