import React, { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { CheckCircle2, MapPin, Briefcase, GraduationCap, MessageSquare, UserPlus, Edit2 } from "lucide-react";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import OfferCard from "../components/OfferCard";
import { toast } from "sonner";

export default function ProfilePage() {
  const { id } = useParams();
  const { user, refreshUser } = useAuth();
  const navigate = useNavigate();
  const [profile, setProfile] = useState(null);
  const [offers, setOffers] = useState([]);
  const [editOpen, setEditOpen] = useState(false);
  const [form, setForm] = useState({});

  const isOwn = user && user.user_id === id;

  useEffect(() => {
    api.get(`/users/${id}`).then((r) => {
      setProfile(r.data);
      setForm(r.data.profile || {});
      if (r.data.role === "company") {
        api.get(`/offers?company_id=${id}`).then((o) => setOffers(o.data));
      }
    }).catch(() => navigate("/"));
  }, [id, navigate]);

  const saveProfile = async () => {
    try {
      await api.put("/profile", form);
      await refreshUser();
      const { data } = await api.get(`/users/${id}`);
      setProfile(data);
      setEditOpen(false);
      toast.success("Profil mis à jour");
    } catch {
      toast.error("Erreur");
    }
  };

  const requestContact = async () => {
    try {
      await api.post("/contacts/request", { to_user_id: id });
      toast.success("Demande envoyée");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erreur");
    }
  };

  if (!profile) return <div className="pt-24 text-center text-slate-400">Chargement...</div>;

  const p = profile.profile || {};
  const isCompany = profile.role === "company";

  return (
    <div className="min-h-screen pt-16 pb-12 bg-slate-50">
      {/* Banner */}
      <div className="h-48 sm:h-64 bg-gradient-to-br from-blue-500 to-violet-600 relative overflow-hidden">
        {p.banner && <img src={p.banner} alt="" className="w-full h-full object-cover" />}
      </div>

      <div className="max-w-5xl mx-auto px-6">
        <div className="card-soft -mt-20 relative p-6 sm:p-8">
          <div className="flex flex-col sm:flex-row gap-5">
            <div className="w-28 h-28 rounded-2xl bg-white p-1 -mt-16 shrink-0">
              <div className="w-full h-full rounded-xl bg-slate-100 overflow-hidden grid place-items-center font-black text-2xl text-slate-400">
                {(p.avatar || p.logo) ? <img src={p.avatar || p.logo} alt="" className="w-full h-full object-cover" /> : profile.name[0]}
              </div>
            </div>
            <div className="flex-1">
              <div className="flex flex-wrap items-center gap-2 mb-1">
                <h1 className="text-2xl sm:text-3xl font-black tracking-tight text-slate-900" data-testid="profile-name">{profile.name}</h1>
                {p.verified && <CheckCircle2 className="w-5 h-5 text-blue-500" />}
              </div>
              <p className="text-slate-600 mb-3">{p.title || p.sector || (isCompany ? "Entreprise" : "Étudiant·e")}</p>
              <div className="flex flex-wrap items-center gap-3 text-sm text-slate-500">
                {p.city && <span className="flex items-center gap-1"><MapPin className="w-3.5 h-3.5" />{p.city}</span>}
                {p.level && <span className="flex items-center gap-1"><GraduationCap className="w-3.5 h-3.5" />{p.level}</span>}
                {p.size && <span className="flex items-center gap-1"><Briefcase className="w-3.5 h-3.5" />{p.size} salariés</span>}
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              {isOwn ? (
                <Button onClick={() => setEditOpen(true)} variant="outline" className="rounded-full" data-testid="edit-profile-btn"><Edit2 className="w-4 h-4 mr-1" />Modifier</Button>
              ) : user ? (
                <>
                  <Button onClick={() => navigate(`/messages?user=${id}`)} className="rounded-full bg-blue-600 hover:bg-blue-700" data-testid="message-btn"><MessageSquare className="w-4 h-4 mr-1" />Message</Button>
                  <Button onClick={requestContact} variant="outline" className="rounded-full" data-testid="contact-btn"><UserPlus className="w-4 h-4 mr-1" />Contact</Button>
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
              </>
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
