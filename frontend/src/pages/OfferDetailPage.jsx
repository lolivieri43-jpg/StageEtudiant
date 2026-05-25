import React, { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { MapPin, Clock, Briefcase, Wifi, CheckCircle2, Calendar, Award, Building2, Eye, Send, Bookmark, FileText, FileCheck2 } from "lucide-react";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Textarea } from "../components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { toast } from "sonner";

const TEMPLATES = [
  { id: "modern", label: "Moderne" },
  { id: "classique", label: "Classique" },
  { id: "etudiant", label: "Étudiant" },
  { id: "alternance", label: "Alternance" },
  { id: "professionnel", label: "Professionnel" },
];

export default function OfferDetailPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [offer, setOffer] = useState(null);
  const [applyOpen, setApplyOpen] = useState(false);
  const [letter, setLetter] = useState("");
  const [applying, setApplying] = useState(false);
  const [saved, setSaved] = useState(false);
  const [myCv, setMyCv] = useState(null);
  const [myDocs, setMyDocs] = useState([]);
  const [useOnlineCv, setUseOnlineCv] = useState(true);
  const [cvTemplate, setCvTemplate] = useState("modern");
  const [pickedDocs, setPickedDocs] = useState({});

  useEffect(() => {
    api.get(`/offers/${id}`).then((r) => setOffer(r.data)).catch(() => navigate("/offers"));
    if (user) api.get("/saved-offers").then((r) => setSaved(r.data.some(o => o.offer_id === id))).catch(() => {});
  }, [id, navigate, user]);

  // Prefetch CV + documents when the apply dialog opens
  useEffect(() => {
    if (!applyOpen || !user || user.role !== "candidate") return;
    (async () => {
      try {
        const cv = await api.get("/cv").then(r => r.data);
        setMyCv(cv);
        setCvTemplate(cv?.pdf_template || "modern");
        // CV is considered "ready" if title or summary is set
        const ready = !!(cv?.professional_title || cv?.summary || (cv?.experiences || []).length || (cv?.educations || []).length);
        setUseOnlineCv(ready);
      } catch { setMyCv(null); }
      try {
        const docs = await api.get(`/users/${user.user_id}/documents`).then(r => r.data);
        setMyDocs(docs || []);
      } catch { setMyDocs([]); }
    })();
  }, [applyOpen, user]);

  const toggleSave = async () => {
    if (!user) { navigate("/login"); return; }
    const { data } = await api.post(`/saved-offers/${id}`);
    setSaved(data.saved);
    toast.success(data.saved ? "Offre sauvegardée" : "Offre retirée");
  };

  const apply = async () => {
    if (!user) { navigate("/login"); return; }
    setApplying(true);
    try {
      const uploaded_doc_ids = Object.entries(pickedDocs).filter(([, v]) => v).map(([k]) => k);
      await api.post("/applications", {
        offer_id: id,
        cover_letter: letter,
        use_online_cv: useOnlineCv,
        online_cv_template: cvTemplate,
        uploaded_doc_ids,
      });
      toast.success("Candidature envoyée !");
      setApplyOpen(false);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erreur");
    } finally {
      setApplying(false);
    }
  };

  const cvReady = !!(myCv && (myCv.professional_title || myCv.summary || (myCv.experiences || []).length || (myCv.educations || []).length));
  const cvDocs = myDocs.filter(d => d.doc_type === "cv");
  const otherDocs = myDocs.filter(d => d.doc_type !== "cv");

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
            <Button variant={saved ? "default" : "outline"} onClick={toggleSave} className="rounded-full" data-testid="save-offer-btn"><Bookmark className={`w-4 h-4 mr-1 ${saved ? "fill-current" : ""}`} />{saved ? "Sauvegardée" : "Sauvegarder"}</Button>
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
        <DialogContent className="max-h-[85vh] overflow-y-auto">
          <DialogHeader><DialogTitle>Postuler à cette offre</DialogTitle></DialogHeader>

          {user?.role === "candidate" && (
            <div className="space-y-4">
              {/* CV en ligne */}
              <div className="border border-slate-200 rounded-2xl p-4" data-testid="apply-online-cv-block">
                <label className="flex items-start gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={useOnlineCv}
                    disabled={!cvReady}
                    onChange={(e) => setUseOnlineCv(e.target.checked)}
                    className="mt-1 accent-blue-600 w-4 h-4"
                    data-testid="apply-use-online-cv"
                  />
                  <div className="flex-1">
                    <div className="font-semibold text-slate-900 flex items-center gap-2"><FileCheck2 className="w-4 h-4 text-blue-500" />Joindre mon CV en ligne</div>
                    {cvReady ? (
                      <div className="text-xs text-slate-500 mt-0.5">
                        Une copie de votre CV en ligne sera figée et envoyée à l'entreprise.
                      </div>
                    ) : (
                      <div className="text-xs text-amber-600 mt-0.5">
                        Votre CV en ligne est vide. <Link to="/cv" className="underline">Remplissez-le</Link> pour pouvoir le joindre.
                      </div>
                    )}
                    {useOnlineCv && cvReady && (
                      <div className="mt-2 flex items-center gap-2">
                        <span className="text-xs text-slate-500">Modèle:</span>
                        <select
                          value={cvTemplate}
                          onChange={(e) => setCvTemplate(e.target.value)}
                          className="rounded-full border border-slate-200 h-8 px-3 text-xs bg-white"
                          data-testid="apply-cv-template"
                        >
                          {TEMPLATES.map(t => <option key={t.id} value={t.id}>{t.label}</option>)}
                        </select>
                      </div>
                    )}
                  </div>
                </label>
              </div>

              {/* PDF uploadé */}
              <div className="border border-slate-200 rounded-2xl p-4">
                <div className="font-semibold text-slate-900 flex items-center gap-2 mb-2"><FileText className="w-4 h-4 text-violet-500" />Joindre un PDF déjà uploadé</div>
                {cvDocs.length === 0 && otherDocs.length === 0 ? (
                  <p className="text-xs text-slate-400">Aucun document uploadé.{" "}
                    <Link to={`/profile/${user.user_id}`} className="underline text-blue-600">Ajouter un document</Link>
                  </p>
                ) : (
                  <div className="space-y-1.5">
                    {[...cvDocs, ...otherDocs].map(d => (
                      <label key={d.doc_id} className="flex items-center gap-2 cursor-pointer text-sm" data-testid={`apply-doc-${d.doc_id}`}>
                        <input
                          type="checkbox"
                          checked={!!pickedDocs[d.doc_id]}
                          onChange={(e) => setPickedDocs({ ...pickedDocs, [d.doc_id]: e.target.checked })}
                          className="accent-blue-600"
                        />
                        <FileText className="w-3.5 h-3.5 text-slate-400" />
                        <span className="truncate">{d.filename}</span>
                        <Badge className="rounded-full bg-slate-100 text-slate-600 border-0 text-[10px] ml-auto">{d.doc_type}</Badge>
                      </label>
                    ))}
                  </div>
                )}
              </div>

              {/* Cover letter */}
              <div>
                <label className="font-semibold text-slate-900 text-sm">Lettre de motivation (optionnel)</label>
                <Textarea data-testid="cover-letter" value={letter} onChange={(e) => setLetter(e.target.value)} rows={5} className="rounded-xl mt-1" placeholder="Bonjour, je suis intéressé(e) par cette offre car..." />
              </div>
            </div>
          )}

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
