import React, { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { CheckCircle2, MapPin, Briefcase, GraduationCap, MessageSquare, UserPlus, Edit2, FileText, Trash2, Image as ImageIcon, X, UserCheck, UserMinus, ShieldOff, FileCheck2 } from "lucide-react";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import OfferCard from "../components/OfferCard";
import FileUploader from "../components/FileUploader";
import { toast } from "sonner";

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
      // Probe CV visibility (404 = no CV, 403 = exists but restricted, 200 = visible)
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

  const uploadAvatar = async (file) => {
    const fd = new FormData();
    fd.append("file", file);
    try {
      await api.post("/me/avatar", fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success("Photo de profil mise à jour");
      await refreshUser();
      reload();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erreur upload");
    }
  };
  const uploadBanner = async (file) => {
    const fd = new FormData();
    fd.append("file", file);
    try {
      await api.post("/me/banner", fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success("Bannière mise à jour");
      await refreshUser();
      reload();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erreur upload");
    }
  };
  const removeAvatar = async () => {
    if (!window.confirm("Supprimer la photo ?")) return;
    await api.delete("/me/avatar");
    await refreshUser();
    reload();
  };
  const removeBanner = async () => {
    if (!window.confirm("Supprimer la bannière ?")) return;
    await api.delete("/me/banner");
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
  const blockUser = async () => {
    if (!window.confirm("Bloquer cet utilisateur ?")) return;
    await api.post(`/contacts/block/${id}`);
    toast.success("Utilisateur bloqué");
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
            <BannerUpload onUpload={uploadBanner} />
            {p.banner && <Button onClick={removeBanner} size="sm" variant="outline" className="rounded-full bg-white/90" data-testid="remove-banner-btn"><X className="w-3.5 h-3.5" /></Button>}
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
                  <AvatarUpload onUpload={uploadAvatar} />
                  {(p.avatar || p.logo) && <button onClick={removeAvatar} className="bg-white rounded-full p-1.5 shadow-md hover:bg-rose-50" data-testid="remove-avatar-btn"><X className="w-3.5 h-3.5 text-rose-600" /></button>}
                </div>
              )}
            </div>
            <div className="flex-1">
              <div className="flex flex-wrap items-center gap-2 mb-1">
                <h1 className="text-2xl sm:text-3xl font-black tracking-tight text-slate-900" data-testid="profile-name">{profile.name}</h1>
                {p.verified && <CheckCircle2 className="w-5 h-5 text-blue-500" />}
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
                  {contactStatus?.status === "received" && <Button onClick={acceptInvite} className="rounded-full bg-emerald-600 hover:bg-emerald-700" data-testid="accept-invite-btn"><UserCheck className="w-4 h-4 mr-1" />Accepter l'invitation</Button>}
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

            {/* Company photo gallery */}
            {isCompany && (gallery.length > 0 || isOwn) && (
              <div className="card-soft p-6" data-testid="gallery-section">
                <div className="flex items-center justify-between mb-3">
                  <h2 className="font-bold flex items-center gap-2"><ImageIcon className="w-4 h-4" />Galerie photos</h2>
                  {isOwn && <FileUploader kind="photo" accept="image/*" onUploaded={addPhoto} label="Ajouter une photo" testid="upload-photo" />}
                </div>
                {gallery.length === 0 ? (
                  <p className="text-sm text-slate-400">Aucune photo dans la galerie</p>
                ) : (
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                    {gallery.map(ph => (
                      <div key={ph.photo_id} className="relative aspect-square rounded-xl overflow-hidden bg-slate-100 group" data-testid={`photo-${ph.photo_id}`}>
                        <img src={ph.url} alt={ph.title} className="w-full h-full object-cover" />
                        {isOwn && (
                          <button onClick={() => removePhoto(ph.photo_id)} className="absolute top-2 right-2 bg-white/90 rounded-full p-1.5 opacity-0 group-hover:opacity-100 transition" data-testid={`remove-photo-${ph.photo_id}`}>
                            <X className="w-3.5 h-3.5 text-rose-600" />
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Student documents */}
            {!isCompany && (docs.length > 0 || isOwn) && (
              <div className="card-soft p-6" data-testid="documents-section">
                <div className="flex items-center justify-between mb-3">
                  <h2 className="font-bold flex items-center gap-2"><FileText className="w-4 h-4" />Documents</h2>
                  {isOwn && <FileUploader kind="doc" accept=".pdf,.png,.jpg,.jpeg" onUploaded={(f) => addDocument(f)} label="Ajouter un document" testid="upload-doc" />}
                </div>
                {docs.length === 0 ? (
                  <p className="text-sm text-slate-400">Aucun document partagé</p>
                ) : (
                  <div className="space-y-2">
                    {docs.map(d => (
                      <div key={d.doc_id} className="flex items-center justify-between bg-slate-50 rounded-xl p-3" data-testid={`doc-${d.doc_id}`}>
                        <a href={`/api/files/${d.file_id}`} target="_blank" rel="noopener" className="flex items-center gap-3 flex-1 min-w-0 hover:text-blue-600">
                          <FileText className="w-5 h-5 text-blue-500 shrink-0" />
                          <div className="min-w-0">
                            <div className="font-semibold text-slate-900 text-sm truncate">{d.filename}</div>
                            <div className="text-xs text-slate-400">{d.doc_type} · {d.visibility}</div>
                          </div>
                        </a>
                        {isOwn && <button onClick={() => deleteDocument(d.doc_id)} className="p-1.5 hover:bg-rose-50 rounded-full" data-testid={`del-doc-${d.doc_id}`}><Trash2 className="w-4 h-4 text-rose-500" /></button>}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
          <aside className="space-y-4">
            <div className="card-soft p-6 text-sm space-y-3">
              {p.school && <Row label="École" value={p.school} />}
              {p.sector && <Row label="Secteur" value={p.sector} />}
              {p.domain && <Row label="Domaine" value={p.domain} />}
              {p.contract_type && <Row label="Recherche" value={p.contract_type === "stage" ? "Stage" : "Alternance"} />}
              {p.duration && <Row label="Durée" value={p.duration} />}
              {p.website && <Row label="Site web" value={<a href={p.website} target="_blank" rel="noopener" className="text-blue-600">{p.website}</a>} />}
              {p.linkedin_url && <Row label="LinkedIn" value={<a href={p.linkedin_url} target="_blank" rel="noopener" className="text-blue-600">Voir</a>} />}
            </div>
          </aside>
        </div>
      </div>

      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="max-h-[80vh] overflow-y-auto">
          <DialogHeader><DialogTitle>Modifier mon profil</DialogTitle></DialogHeader>
          <div className="space-y-3">
            {isCompany ? (
              <>
                <Field label="Nom de l'entreprise" value={form.company_name} onChange={(v) => setForm({ ...form, company_name: v })} testid="edit-company-name" />
                <Field label="Secteur" value={form.sector} onChange={(v) => setForm({ ...form, sector: v })} testid="edit-sector" />
                <Field label="Taille" value={form.size} onChange={(v) => setForm({ ...form, size: v })} />
                <Field label="Ville" value={form.city} onChange={(v) => setForm({ ...form, city: v })} />
                <Field label="Site web" value={form.website} onChange={(v) => setForm({ ...form, website: v })} />
                <Field label="Logo URL" value={form.logo} onChange={(v) => setForm({ ...form, logo: v })} />
              </>
            ) : (
              <>
                <Field label="Titre professionnel" value={form.title} onChange={(v) => setForm({ ...form, title: v })} testid="edit-title" />
                <Field label="École" value={form.school} onChange={(v) => setForm({ ...form, school: v })} />
                <Field label="Niveau" value={form.level} onChange={(v) => setForm({ ...form, level: v })} />
                <Field label="Domaine" value={form.domain} onChange={(v) => setForm({ ...form, domain: v })} />
                <Field label="Ville" value={form.city} onChange={(v) => setForm({ ...form, city: v })} />
                <Field label="LinkedIn URL" value={form.linkedin_url} onChange={(v) => setForm({ ...form, linkedin_url: v })} />
                <Field label="Photo URL" value={form.avatar} onChange={(v) => setForm({ ...form, avatar: v })} />
                <div>
                  <Label>Statut de recherche</Label>
                  <select value={form.status || "en_recherche"} onChange={(e) => setForm({ ...form, status: e.target.value })} className="w-full rounded-xl border border-slate-200 h-10 px-3 mt-1" data-testid="edit-status">
                    <option value="en_recherche">En recherche active</option>
                    <option value="a_l_ecoute">À l'écoute</option>
                    <option value="deja_trouve">Déjà trouvé</option>
                    <option value="non_disponible">Non disponible</option>
                  </select>
                </div>
              </>
            )}
            {isCompany && (
              <div>
                <Label>Statut de recrutement</Label>
                <select value={form.company_status || "recrute_les_deux"} onChange={(e) => setForm({ ...form, company_status: e.target.value })} className="w-full rounded-xl border border-slate-200 h-10 px-3 mt-1" data-testid="edit-company-status">
                  <option value="recrute_stagiaire">Recherche stagiaire</option>
                  <option value="recrute_alternant">Recherche alternant</option>
                  <option value="recrute_les_deux">Recrute activement</option>
                  <option value="pas_de_recrutement">Pas de recrutement</option>
                </select>
              </div>
            )}
            <div>
              <Label>Description</Label>
              <Textarea value={form.description || ""} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={4} className="rounded-xl mt-1" data-testid="edit-description" />
            </div>
            <Button onClick={saveProfile} className="rounded-xl bg-blue-600 hover:bg-blue-700 w-full" data-testid="save-profile">Enregistrer</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

const Row = ({ label, value }) => (
  <div className="flex justify-between gap-3">
    <span className="text-slate-400">{label}</span>
    <span className="font-semibold text-slate-700 text-right">{value}</span>
  </div>
);
const Field = ({ label, value, onChange, testid }) => (
  <div>
    <Label>{label}</Label>
    <Input value={value || ""} onChange={(e) => onChange(e.target.value)} className="rounded-xl mt-1" data-testid={testid} />
  </div>
);

function resolveUrl(u) {
  if (!u) return u;
  if (u.startsWith("/api/")) return process.env.REACT_APP_BACKEND_URL + u;
  return u;
}

function AvatarUpload({ onUpload }) {
  const ref = React.useRef();
  return (
    <>
      <input ref={ref} type="file" accept="image/jpeg,image/png,image/webp" className="hidden" data-testid="avatar-upload-input"
        onChange={(e) => { const f = e.target.files?.[0]; if (f) onUpload(f); e.target.value = ""; }} />
      <button onClick={() => ref.current?.click()} className="bg-white rounded-full p-1.5 shadow-md hover:bg-blue-50" data-testid="avatar-upload-btn"
        title="Modifier la photo">
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="text-blue-600"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>
      </button>
    </>
  );
}

function BannerUpload({ onUpload }) {
  const ref = React.useRef();
  return (
    <>
      <input ref={ref} type="file" accept="image/jpeg,image/png,image/webp" className="hidden" data-testid="banner-upload-input"
        onChange={(e) => { const f = e.target.files?.[0]; if (f) onUpload(f); e.target.value = ""; }} />
      <Button onClick={() => ref.current?.click()} size="sm" variant="outline" className="rounded-full bg-white/90" data-testid="banner-upload-btn">
        Modifier la bannière
      </Button>
    </>
  );
}
