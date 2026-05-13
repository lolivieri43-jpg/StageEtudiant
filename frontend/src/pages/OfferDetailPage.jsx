import React, { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { MapPin, Clock, Briefcase, Wifi, CheckCircle2, Calendar, Award, Building2, Eye, Send, Bookmark } from "lucide-react";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Textarea } from "../components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { toast } from "sonner";

export default function OfferDetailPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [offer, setOffer] = useState(null);
  const [applyOpen, setApplyOpen] = useState(false);
  const [letter, setLetter] = useState("");
  const [applying, setApplying] = useState(false);

  useEffect(() => {
    api.get(`/offers/${id}`).then((r) => setOffer(r.data)).catch(() => navigate("/offers"));
  }, [id, navigate]);

  const apply = async () => {
    if (!user) { navigate("/login"); return; }
    setApplying(true);
    try {
      await api.post("/applications", { offer_id: id, cover_letter: letter });
      toast.success("Candidature envoyée !");
      setApplyOpen(false);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erreur");
    } finally {
      setApplying(false);
    }
  };

  if (!offer) return <div className="pt-24 text-center text-slate-400">Chargement...</div>;

  return (
    <div className="min-h-screen pt-20 pb-12 bg-slate-50">
      <div className="max-w-5xl mx-auto px-6">
        <div className="card-soft p-8 mb-6">
          <div className="flex items-start gap-5 mb-6">
            <div className="w-20 h-20 rounded-2xl bg-slate-100 overflow-hidden grid place-items-center font-bold text-slate-400 shrink-0">
              {offer.company_logo ? <img src={offer.company_logo} alt="" className="w-full h-full object-cover" /> : offer.company_name?.[0]}
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <Link to={`/profile/${offer.company_id}`} className="font-semibold text-slate-700 hover:text-blue-600" data-testid="offer-company-link">{offer.company_name}</Link>
                {offer.verified && <CheckCircle2 className="w-4 h-4 text-blue-500" />}
              </div>
              <h1 className="text-3xl font-black tracking-tight text-slate-900 mb-3" data-testid="offer-title">{offer.title}</h1>
              <div className="flex flex-wrap gap-2">
                <Badge className="rounded-full bg-blue-50 text-blue-700 border-0"><Briefcase className="w-3 h-3 mr-1" />{offer.contract_type === "stage" ? "Stage" : "Alternance"}</Badge>
                <Badge className="rounded-full bg-violet-50 text-violet-700 border-0"><MapPin className="w-3 h-3 mr-1" />{offer.city}, {offer.region}</Badge>
                <Badge className="rounded-full bg-slate-100 text-slate-700 border-0"><Clock className="w-3 h-3 mr-1" />{offer.duration}</Badge>
                {offer.remote && <Badge className="rounded-full bg-emerald-50 text-emerald-700 border-0"><Wifi className="w-3 h-3 mr-1" />Télétravail</Badge>}
                <Badge className="rounded-full bg-amber-50 text-amber-700 border-0"><Award className="w-3 h-3 mr-1" />{offer.level}</Badge>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap gap-3 mb-2">
            {(!user || user.role !== "company") && (
              <Button onClick={() => setApplyOpen(true)} className="rounded-full bg-blue-600 hover:bg-blue-700" data-testid="apply-btn">
                <Send className="w-4 h-4 mr-1" />Postuler
              </Button>
            )}
            <Button variant="outline" className="rounded-full" data-testid="save-offer-btn"><Bookmark className="w-4 h-4 mr-1" />Sauvegarder</Button>
            <Link to={`/profile/${offer.company_id}`}><Button variant="outline" className="rounded-full"><Building2 className="w-4 h-4 mr-1" />Voir l'entreprise</Button></Link>
            <span className="ml-auto text-sm text-slate-400 flex items-center gap-1"><Eye className="w-3.5 h-3.5" />{offer.views} vues</span>
          </div>
        </div>

        <div className="grid lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            <Card title="Description du poste">{offer.description}</Card>
            {offer.profile && <Card title="Profil recherché">{offer.profile}</Card>}
            {offer.skills?.length > 0 && (
              <div className="card-soft p-6">
                <h3 className="font-bold mb-3">Compétences</h3>
                <div className="flex flex-wrap gap-2">
                  {offer.skills.map(s => <Badge key={s} className="rounded-full bg-violet-50 text-violet-700 border-0">{s}</Badge>)}
                </div>
              </div>
            )}
            {offer.benefits && <Card title="Avantages">{offer.benefits}</Card>}
          </div>

          <aside className="card-soft p-6 h-fit space-y-4 text-sm">
            <Info icon={Calendar} label="Date de début" value={offer.start_date} />
            <Info icon={Clock} label="Durée" value={offer.duration} />
            <Info icon={Briefcase} label="Rythme" value={offer.rhythm || "—"} />
            <Info icon={Award} label="Rémunération" value={offer.salary || "—"} />
          </aside>
        </div>
      </div>

      <Dialog open={applyOpen} onOpenChange={setApplyOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Postuler à cette offre</DialogTitle></DialogHeader>
          <p className="text-sm text-slate-500">Ajoutez une lettre de motivation (optionnel) pour vous démarquer.</p>
          <Textarea data-testid="cover-letter" value={letter} onChange={(e) => setLetter(e.target.value)} rows={6} className="rounded-xl" placeholder="Bonjour, je suis intéressé(e) par cette offre car..." />
          <Button onClick={apply} disabled={applying} className="rounded-xl bg-blue-600 hover:bg-blue-700" data-testid="submit-application">
            {applying ? "Envoi..." : "Envoyer ma candidature"}
          </Button>
        </DialogContent>
      </Dialog>
    </div>
  );
}

const Card = ({ title, children }) => (
  <div className="card-soft p-6">
    <h3 className="font-bold mb-3 text-slate-900">{title}</h3>
    <p className="text-slate-600 leading-relaxed whitespace-pre-wrap">{children}</p>
  </div>
);
const Info = ({ icon: Icon, label, value }) => (
  <div className="flex items-start gap-2">
    <Icon className="w-4 h-4 text-slate-400 mt-0.5" />
    <div><div className="text-xs text-slate-400">{label}</div><div className="font-semibold text-slate-700">{value}</div></div>
  </div>
);
