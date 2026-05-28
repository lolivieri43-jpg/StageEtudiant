import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Search, MapPin, GraduationCap, MessageSquare, UserPlus, Loader2, RotateCcw } from "lucide-react";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { toast } from "sonner";
import PremiumBadge, { isPremiumActive } from "../components/PremiumBadge";

const BLANK_FILTERS = { q: "", level: "", domain: "", city: "", contract_type: "", student_status: "", skill: "" };

export default function SearchStudentsPage() {
  const { user } = useAuth();
  // Draft (form values) vs applied (used for actual fetch)
  const [draft, setDraft] = useState(BLANK_FILTERS);
  const [applied, setApplied] = useState(BLANK_FILTERS);
  const [draftNearCity, setDraftNearCity] = useState("");
  const [draftDistanceKm, setDraftDistanceKm] = useState("50");
  const [appliedNear, setAppliedNear] = useState({ near_city: "", distance_km: "50" });

  const [cityList, setCityList] = useState([]);
  const [students, setStudents] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => { api.get("/cities").then((r) => setCityList(r.data.cities)); }, []);

  const load = async () => {
    setLoading(true);
    try {
      if (appliedNear.near_city) {
        const p = new URLSearchParams({ city: appliedNear.near_city, distance_km: appliedNear.distance_km });
        const { data } = await api.get(`/search/students-nearby?${p.toString()}`);
        setStudents(data);
      } else {
        const params = new URLSearchParams();
        Object.entries(applied).forEach(([k, v]) => v && params.set(k, v));
        const { data } = await api.get(`/search/students?${params.toString()}`);
        setStudents(data);
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erreur de recherche");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [applied, appliedNear]);

  const submit = (e) => {
    if (e?.preventDefault) e.preventDefault();
    setApplied(draft);
    setAppliedNear({ near_city: draftNearCity, distance_km: draftDistanceKm });
  };
  const resetAll = () => {
    setDraft(BLANK_FILTERS); setDraftNearCity(""); setDraftDistanceKm("50");
    setApplied(BLANK_FILTERS); setAppliedNear({ near_city: "", distance_km: "50" });
  };

  const sendContact = async (uid) => {
    try {
      await api.post("/contacts/request", { to_user_id: uid });
      toast.success("Invitation envoyée");
    } catch (err) { toast.error(err.response?.data?.detail || "Erreur"); }
  };

  if (user?.role !== "company") return <div className="pt-24 text-center text-slate-500">Réservé aux entreprises</div>;

  return (
    <div className="min-h-screen pt-20 pb-12 bg-slate-50 dark:bg-slate-900">
      <div className="max-w-6xl mx-auto px-6">
        <h1 className="text-3xl font-black tracking-tight text-slate-900 dark:text-slate-100 mb-2">Rechercher un étudiant</h1>
        <p className="text-slate-500 mb-6" data-testid="students-count">
          {loading ? "Chargement…" : <><b className="text-slate-700 dark:text-slate-300">{students.length}</b> profil{students.length > 1 ? "s" : ""} trouvé{students.length > 1 ? "s" : ""}</>}
        </p>

        <form onSubmit={submit} className="card-soft p-5 mb-6">
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <Input value={draft.q} onChange={(e) => setDraft({ ...draft, q: e.target.value })} placeholder="Nom" className="rounded-xl pl-9" data-testid="filter-q" />
            </div>
            <select value={draft.level} onChange={(e) => setDraft({ ...draft, level: e.target.value })} className="rounded-xl border border-slate-200 dark:border-slate-700 h-10 px-3 bg-white dark:bg-slate-800" data-testid="filter-level">
              <option value="">Tous niveaux</option><option>Bac+2</option><option>Bac+3</option><option>Bac+5</option>
            </select>
            <Input value={draft.domain} onChange={(e) => setDraft({ ...draft, domain: e.target.value })} placeholder="Domaine" className="rounded-xl" data-testid="filter-domain" />
            <Input value={draft.city} onChange={(e) => setDraft({ ...draft, city: e.target.value })} placeholder="Ville" className="rounded-xl" data-testid="filter-city" />
            <Input value={draft.skill} onChange={(e) => setDraft({ ...draft, skill: e.target.value })} placeholder="Compétence" className="rounded-xl" data-testid="filter-skill" />
            <select value={draft.contract_type} onChange={(e) => setDraft({ ...draft, contract_type: e.target.value })} className="rounded-xl border border-slate-200 dark:border-slate-700 h-10 px-3 bg-white dark:bg-slate-800" data-testid="filter-ct">
              <option value="">Stage ou alternance</option><option value="stage">Stage</option><option value="alternance">Alternance</option>
            </select>
            <select value={draft.student_status} onChange={(e) => setDraft({ ...draft, student_status: e.target.value })} className="rounded-xl border border-slate-200 dark:border-slate-700 h-10 px-3 bg-white dark:bg-slate-800" data-testid="filter-status">
              <option value="">Tous statuts</option>
              <option value="en_recherche">En recherche active</option>
              <option value="a_l_ecoute">À l&apos;écoute</option>
              <option value="deja_trouve">Déjà trouvé</option>
              <option value="non_disponible">Non disponible</option>
            </select>
          </div>
          <div className="mt-3 grid sm:grid-cols-2 gap-3 bg-gradient-to-r from-blue-50 to-violet-50 dark:from-blue-950/30 dark:to-violet-950/30 rounded-xl p-3">
            <select value={draftNearCity} onChange={(e) => setDraftNearCity(e.target.value)} className="rounded-xl border-0 bg-white dark:bg-slate-800 h-10 px-3" data-testid="filter-near-city">
              <option value="">Rayon autour d&apos;une ville (optionnel)</option>
              {cityList.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
            {draftNearCity && (
              <div className="flex items-center gap-2 bg-white dark:bg-slate-800 rounded-xl px-3 h-10">
                <span className="text-xs font-semibold text-slate-600 dark:text-slate-300 w-16">{draftDistanceKm} km</span>
                <input type="range" min="10" max="300" step="10" value={draftDistanceKm} onChange={(e) => setDraftDistanceKm(e.target.value)} className="flex-1 accent-violet-600" data-testid="filter-distance" />
              </div>
            )}
          </div>

          <div className="flex flex-wrap gap-2 mt-4">
            <Button type="submit" disabled={loading} className="rounded-full bg-blue-600 hover:bg-blue-700 h-11 px-5" data-testid="apply-students-btn">
              {loading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Search className="w-4 h-4 mr-2" />}
              Rechercher
            </Button>
            <Button type="button" variant="outline" onClick={resetAll} className="rounded-full h-11" data-testid="reset-students-btn">
              <RotateCcw className="w-4 h-4 mr-1" /> Réinitialiser
            </Button>
            <span className="text-xs text-slate-500 self-center">Sélectionnez vos critères puis cliquez sur <b>Rechercher</b></span>
          </div>
        </form>

        {loading ? <div className="text-center text-slate-400 py-12 flex flex-col items-center gap-2"><Loader2 className="w-6 h-6 animate-spin" />Recherche en cours…</div> : students.length === 0 ? (
          <div className="card-soft p-12 text-center text-slate-400" data-testid="students-empty">Aucun étudiant trouvé</div>
        ) : (
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
            {students.map(s => {
              const p = s.profile || {};
              const premium = isPremiumActive(s);
              return (
                <div key={s.user_id} className={`card-soft p-5 relative ${premium ? "ring-1 ring-amber-200" : ""}`} data-testid={`student-card-${s.user_id}`}>
                  {premium && <div className="absolute top-3 right-3"><PremiumBadge role="candidate" size="xs" /></div>}
                  <div className="flex items-start gap-3 mb-3">
                    <div className="w-14 h-14 rounded-full bg-gradient-to-br from-blue-400 to-violet-400 grid place-items-center text-white font-bold shrink-0">
                      {p.avatar ? <img src={p.avatar} className="w-full h-full rounded-full object-cover" alt="" /> : s.name[0]}
                    </div>
                    <div className="flex-1 min-w-0 pr-12">
                      <Link to={`/profile/${s.user_id}`} className="font-bold text-slate-900 dark:text-slate-100 hover:text-blue-600 truncate block">{s.name}</Link>
                      <div className="text-xs text-slate-500 truncate">{p.title || p.domain || "—"}</div>
                      <div className="flex items-center gap-1.5 mt-1 text-xs">
                        <span className={`w-2 h-2 rounded-full ${p.status === "en_recherche" ? "bg-emerald-500" : p.status === "a_l_ecoute" ? "bg-amber-400" : "bg-slate-400"}`} />
                        <span className="text-slate-600 dark:text-slate-300">{p.status === "en_recherche" ? "En recherche" : p.status === "a_l_ecoute" ? "À l'écoute" : p.status === "deja_trouve" ? "Déjà trouvé" : "Non disponible"}</span>
                      </div>
                    </div>
                  </div>
                  <div className="space-y-1 text-xs text-slate-500">
                    {p.school && <div className="flex items-center gap-1"><GraduationCap className="w-3 h-3" />{p.school} · {p.level}</div>}
                    {p.city && <div className="flex items-center gap-1"><MapPin className="w-3 h-3" />{p.city}</div>}
                    {p.contract_type && <Badge className="bg-blue-50 text-blue-700 border-0 rounded-full mt-1">{p.contract_type === "stage" ? "Stage" : "Alternance"}</Badge>}
                  </div>
                  {p.skills?.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-3">
                      {p.skills.slice(0, 4).map(sk => <Badge key={sk} className="bg-violet-50 text-violet-700 border-0 rounded-full text-[10px]">{sk}</Badge>)}
                    </div>
                  )}
                  <div className="flex gap-2 mt-4">
                    <Link to={`/profile/${s.user_id}`} className="flex-1"><Button variant="outline" size="sm" className="rounded-full w-full" data-testid={`view-${s.user_id}`}>Voir profil</Button></Link>
                    <Button size="sm" onClick={() => sendContact(s.user_id)} className="rounded-full bg-blue-600 hover:bg-blue-700" data-testid={`contact-${s.user_id}`}><UserPlus className="w-3.5 h-3.5" /></Button>
                    <Link to={`/messages?user=${s.user_id}`}><Button size="sm" variant="outline" className="rounded-full"><MessageSquare className="w-3.5 h-3.5" /></Button></Link>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
