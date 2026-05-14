import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Search, MapPin, GraduationCap, Filter, MessageSquare, UserPlus } from "lucide-react";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { toast } from "sonner";

export default function SearchStudentsPage() {
  const { user } = useAuth();
  const [filters, setFilters] = useState({
    q: "", level: "", domain: "", city: "", contract_type: "", student_status: "", skill: "",
  });
  const [nearCity, setNearCity] = useState("");
  const [distanceKm, setDistanceKm] = useState("50");
  const [cityList, setCityList] = useState([]);
  const [students, setStudents] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => { api.get("/cities").then((r) => setCityList(r.data.cities)); }, []);

  const load = async () => {
    setLoading(true);
    if (nearCity) {
      const p = new URLSearchParams({ city: nearCity, distance_km: distanceKm });
      const { data } = await api.get(`/search/students-nearby?${p.toString()}`);
      setStudents(data);
    } else {
      const params = new URLSearchParams();
      Object.entries(filters).forEach(([k, v]) => v && params.set(k, v));
      const { data } = await api.get(`/search/students?${params.toString()}`);
      setStudents(data);
    }
    setLoading(false);
  };
  useEffect(() => { load(); }, [filters, nearCity, distanceKm]);

  const sendContact = async (uid) => {
    try {
      await api.post("/contacts/request", { to_user_id: uid });
      toast.success("Invitation envoyée");
    } catch (err) { toast.error(err.response?.data?.detail || "Erreur"); }
  };

  if (user?.role !== "company") return <div className="pt-24 text-center text-slate-500">Réservé aux entreprises</div>;

  return (
    <div className="min-h-screen pt-20 pb-12 bg-slate-50">
      <div className="max-w-6xl mx-auto px-6">
        <h1 className="text-3xl font-black tracking-tight text-slate-900 mb-2">Rechercher un étudiant</h1>
        <p className="text-slate-500 mb-6">{students.length} profils correspondant à votre recherche</p>

        <div className="card-soft p-5 mb-6">
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <Input value={filters.q} onChange={(e) => setFilters({ ...filters, q: e.target.value })} placeholder="Nom" className="rounded-xl pl-9" data-testid="filter-q" />
            </div>
            <select value={filters.level} onChange={(e) => setFilters({ ...filters, level: e.target.value })} className="rounded-xl border border-slate-200 h-10 px-3" data-testid="filter-level">
              <option value="">Tous niveaux</option><option>Bac+2</option><option>Bac+3</option><option>Bac+5</option>
            </select>
            <Input value={filters.domain} onChange={(e) => setFilters({ ...filters, domain: e.target.value })} placeholder="Domaine" className="rounded-xl" data-testid="filter-domain" />
            <Input value={filters.city} onChange={(e) => setFilters({ ...filters, city: e.target.value })} placeholder="Ville" className="rounded-xl" data-testid="filter-city" />
            <Input value={filters.skill} onChange={(e) => setFilters({ ...filters, skill: e.target.value })} placeholder="Compétence" className="rounded-xl" data-testid="filter-skill" />
            <select value={filters.contract_type} onChange={(e) => setFilters({ ...filters, contract_type: e.target.value })} className="rounded-xl border border-slate-200 h-10 px-3" data-testid="filter-ct">
              <option value="">Stage ou alternance</option><option value="stage">Stage</option><option value="alternance">Alternance</option>
            </select>
            <select value={filters.student_status} onChange={(e) => setFilters({ ...filters, student_status: e.target.value })} className="rounded-xl border border-slate-200 h-10 px-3" data-testid="filter-status">
              <option value="">Tous statuts</option>
              <option value="en_recherche">En recherche active</option>
              <option value="a_l_ecoute">À l'écoute</option>
              <option value="deja_trouve">Déjà trouvé</option>
              <option value="non_disponible">Non disponible</option>
            </select>
          </div>
          <div className="mt-3 grid sm:grid-cols-2 gap-3 bg-gradient-to-r from-blue-50 to-violet-50 rounded-xl p-3">
            <select value={nearCity} onChange={(e) => setNearCity(e.target.value)} className="rounded-xl border-0 bg-white h-10 px-3" data-testid="filter-near-city">
              <option value="">Rayon autour d'une ville (optionnel)</option>
              {cityList.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
            {nearCity && (
              <div className="flex items-center gap-2 bg-white rounded-xl px-3 h-10">
                <span className="text-xs font-semibold text-slate-600 w-16">{distanceKm} km</span>
                <input type="range" min="10" max="300" step="10" value={distanceKm} onChange={(e) => setDistanceKm(e.target.value)} className="flex-1 accent-violet-600" data-testid="filter-distance" />
              </div>
            )}
          </div>
        </div>

        {loading ? <div className="text-center text-slate-400 py-12">Chargement...</div> : students.length === 0 ? (
          <div className="card-soft p-12 text-center text-slate-400">Aucun étudiant trouvé</div>
        ) : (
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
            {students.map(s => {
              const p = s.profile || {};
              return (
                <div key={s.user_id} className="card-soft p-5" data-testid={`student-card-${s.user_id}`}>
                  <div className="flex items-start gap-3 mb-3">
                    <div className="w-14 h-14 rounded-full bg-gradient-to-br from-blue-400 to-violet-400 grid place-items-center text-white font-bold shrink-0">
                      {p.avatar ? <img src={p.avatar} className="w-full h-full rounded-full object-cover" alt="" /> : s.name[0]}
                    </div>
                    <div className="flex-1 min-w-0">
                      <Link to={`/profile/${s.user_id}`} className="font-bold text-slate-900 hover:text-blue-600 truncate block">{s.name}</Link>
                      <div className="text-xs text-slate-500 truncate">{p.title || p.domain || "—"}</div>
                      <div className="flex items-center gap-1.5 mt-1 text-xs">
                        <span className={`w-2 h-2 rounded-full ${p.status === "en_recherche" ? "bg-emerald-500" : p.status === "a_l_ecoute" ? "bg-amber-400" : "bg-slate-400"}`} />
                        <span className="text-slate-600">{p.status === "en_recherche" ? "En recherche" : p.status === "a_l_ecoute" ? "À l'écoute" : p.status === "deja_trouve" ? "Déjà trouvé" : "Non disponible"}</span>
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
