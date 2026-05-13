import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import api from "../lib/api";
import { Briefcase, Users, Mail, Eye, FileText, TrendingUp, Plus, CheckCircle2 } from "lucide-react";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import OfferCard from "../components/OfferCard";

const StatusBadge = ({ status }) => {
  const map = {
    envoyee: { label: "Envoyée", color: "bg-blue-50 text-blue-700" },
    vue: { label: "Vue", color: "bg-violet-50 text-violet-700" },
    en_attente: { label: "En attente", color: "bg-amber-50 text-amber-700" },
    acceptee: { label: "Acceptée", color: "bg-emerald-50 text-emerald-700" },
    refusee: { label: "Refusée", color: "bg-rose-50 text-rose-700" },
  };
  const s = map[status] || map.envoyee;
  return <Badge className={`${s.color} border-0 rounded-full font-semibold`}>{s.label}</Badge>;
};

export default function DashboardPage() {
  const { user } = useAuth();
  const [data, setData] = useState(null);

  useEffect(() => {
    if (!user) return;
    (async () => {
      try {
        const { data } = await api.get("/dashboard");
        setData(data);
      } catch {}
    })();
  }, [user]);

  if (!user) return null;

  return (
    <div className="min-h-screen pt-20 pb-12 bg-slate-50">
      <div className="max-w-7xl mx-auto px-6">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-black tracking-tight text-slate-900">Bonjour, {user.name.split(" ")[0]} 👋</h1>
            <p className="text-slate-500 mt-1">Voici l'activité de votre compte</p>
          </div>
          {user.role === "company" && (
            <Link to="/offers/new"><Button className="rounded-full bg-blue-600 hover:bg-blue-700" data-testid="publish-offer-btn"><Plus className="w-4 h-4 mr-1" />Publier une offre</Button></Link>
          )}
        </div>

        {user.role === "company" ? (
          <>
            <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-5 mb-8">
              <StatCard icon={Briefcase} color="blue" label="Offres publiées" value={data?.offers_count ?? 0} />
              <StatCard icon={Users} color="violet" label="Candidatures reçues" value={data?.applications_count ?? 0} />
              <StatCard icon={FileText} color="amber" label="En attente" value={data?.pending_applications ?? 0} />
              <StatCard icon={Eye} color="emerald" label="Vues totales" value={data?.total_views ?? 0} />
            </div>
            <div className="grid lg:grid-cols-2 gap-6">
              <Section title="Mes offres" link="/offers" linkLabel="Toutes mes offres">
                <div className="space-y-3">
                  {(data?.offers || []).map(o => <OfferCard key={o.offer_id} offer={o} />)}
                  {(!data || data.offers.length === 0) && <Empty msg="Pas encore d'offres" />}
                </div>
              </Section>
              <Section title="Candidatures récentes">
                <div className="space-y-3">
                  {(data?.recent_applications || []).map(a => (
                    <div key={a.app_id} className="card-soft p-4 flex items-center gap-3" data-testid={`application-row-${a.app_id}`}>
                      <div className="w-10 h-10 rounded-full bg-slate-200 overflow-hidden grid place-items-center font-bold text-slate-500 shrink-0">
                        {a.candidate_avatar ? <img src={a.candidate_avatar} className="w-full h-full object-cover" alt="" /> : a.candidate_name[0]}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="font-semibold text-slate-900 truncate">{a.candidate_name}</div>
                        <div className="text-xs text-slate-500 truncate">{a.offer_title}</div>
                      </div>
                      <StatusBadge status={a.status} />
                    </div>
                  ))}
                  {(!data || data.recent_applications.length === 0) && <Empty msg="Aucune candidature" />}
                </div>
              </Section>
            </div>
          </>
        ) : (
          <>
            <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-5 mb-8">
              <StatCard icon={FileText} color="blue" label="Candidatures envoyées" value={data?.applications_count ?? 0} />
              <StatCard icon={TrendingUp} color="violet" label="En cours" value={data?.pending ?? 0} />
              <StatCard icon={CheckCircle2} color="emerald" label="Acceptées" value={data?.accepted ?? 0} />
              <StatCard icon={Mail} color="amber" label="Messages non lus" value={data?.unread_messages ?? 0} />
            </div>
            <div className="grid lg:grid-cols-2 gap-6">
              <Section title="Offres recommandées" link="/offers" linkLabel="Voir plus">
                <div className="space-y-3">
                  {(data?.recommended_offers || []).slice(0, 5).map(o => <OfferCard key={o.offer_id} offer={o} />)}
                </div>
              </Section>
              <Section title="Mes candidatures">
                <div className="space-y-3">
                  {(data?.applications || []).map(a => (
                    <Link to={`/offers/${a.offer_id}`} key={a.app_id} className="card-soft p-4 flex items-center gap-3 hover-lift" data-testid={`my-app-${a.app_id}`}>
                      <Briefcase className="w-5 h-5 text-slate-400" />
                      <div className="flex-1 min-w-0">
                        <div className="font-semibold text-slate-900 truncate">{a.offer_title}</div>
                        <div className="text-xs text-slate-500 truncate">{a.company_name}</div>
                      </div>
                      <StatusBadge status={a.status} />
                    </Link>
                  ))}
                  {(!data || data.applications.length === 0) && <Empty msg="Pas encore de candidature" />}
                </div>
              </Section>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

const StatCard = ({ icon: Icon, color, label, value }) => {
  const colors = {
    blue: "bg-blue-50 text-blue-600",
    violet: "bg-violet-50 text-violet-600",
    emerald: "bg-emerald-50 text-emerald-600",
    amber: "bg-amber-50 text-amber-600",
  };
  return (
    <div className="card-soft p-6" data-testid={`stat-${label.toLowerCase().replace(/\s/g, '-')}`}>
      <div className={`w-10 h-10 rounded-xl grid place-items-center ${colors[color]} mb-3`}><Icon className="w-5 h-5" /></div>
      <div className="text-3xl font-black text-slate-900">{value}</div>
      <div className="text-sm text-slate-500 mt-1">{label}</div>
    </div>
  );
};
const Section = ({ title, link, linkLabel, children }) => (
  <div>
    <div className="flex items-center justify-between mb-4">
      <h2 className="text-xl font-bold text-slate-900">{title}</h2>
      {link && <Link to={link} className="text-sm text-blue-600 font-semibold">{linkLabel}</Link>}
    </div>
    {children}
  </div>
);
const Empty = ({ msg }) => <div className="card-soft p-8 text-center text-slate-400 text-sm">{msg}</div>;
