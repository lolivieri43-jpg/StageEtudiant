import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../lib/api";
import { Button } from "../components/ui/button";
import { Check, X, MessageSquare } from "lucide-react";
import { toast } from "sonner";
import PremiumBadge, { isPremiumActive } from "../components/PremiumBadge";

export default function ContactsPage() {
  const [data, setData] = useState({ contacts: [], pending: [], sent: [] });

  const load = async () => {
    const { data } = await api.get("/contacts");
    setData(data);
  };
  useEffect(() => { load(); }, []);

  const accept = async (id) => { await api.post(`/contacts/${id}/accept`); toast.success("Contact ajouté"); load(); };
  const refuse = async (id) => { await api.post(`/contacts/${id}/refuse`); load(); };

  return (
    <div className="min-h-screen pt-20 pb-12 bg-slate-50">
      <div className="max-w-4xl mx-auto px-6">
        <h1 className="text-3xl font-black tracking-tight text-slate-900 mb-6">Mon réseau</h1>

        {data.pending.length > 0 && (
          <section className="mb-8">
            <h2 className="font-bold text-slate-900 mb-3">Demandes reçues ({data.pending.length})</h2>
            <div className="space-y-3">
              {data.pending.map(r => (
                <div key={r.request_id} className="card-soft p-4 flex items-center gap-3" data-testid={`pending-${r.request_id}`}>
                  <div className="w-12 h-12 rounded-full bg-slate-200 overflow-hidden grid place-items-center font-bold text-slate-500">
                    {r.from_avatar ? <img src={r.from_avatar} alt="" className="w-full h-full object-cover" /> : r.from_name[0]}
                  </div>
                  <div className="flex-1">
                    <div className="font-semibold">{r.from_name}</div>
                    <div className="text-xs text-slate-500">souhaite vous ajouter en contact</div>
                  </div>
                  <Button onClick={() => accept(r.request_id)} className="rounded-full bg-blue-600 hover:bg-blue-700" data-testid={`accept-${r.request_id}`}><Check className="w-4 h-4 mr-1" />Accepter</Button>
                  <Button onClick={() => refuse(r.request_id)} variant="outline" className="rounded-full" data-testid={`refuse-${r.request_id}`}><X className="w-4 h-4" /></Button>
                </div>
              ))}
            </div>
          </section>
        )}

        <section>
          <h2 className="font-bold text-slate-900 mb-3">Mes contacts ({data.contacts.length})</h2>
          {data.contacts.length === 0 ? (
            <div className="card-soft p-12 text-center text-slate-400 text-sm">Aucun contact pour le moment</div>
          ) : (
            <div className="grid sm:grid-cols-2 gap-3">
              {data.contacts.map(c => (
                <div key={c.user_id} className="card-soft p-4 flex items-center gap-3" data-testid={`contact-${c.user_id}`}>
                  <Link to={`/profile/${c.user_id}`} className="w-12 h-12 rounded-full bg-gradient-to-br from-blue-400 to-violet-400 grid place-items-center text-white font-bold shrink-0">
                    {c.profile?.avatar || c.profile?.logo ? <img src={c.profile.avatar || c.profile.logo} className="w-full h-full rounded-full object-cover" alt="" /> : c.name[0]}
                  </Link>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <Link to={`/profile/${c.user_id}`} className="font-semibold truncate hover:text-blue-600 block">{c.name}</Link>
                      {isPremiumActive(c) && <PremiumBadge role={c.role === "company" ? "company" : "candidate"} size="xs" />}
                    </div>
                    <div className="text-xs text-slate-500 truncate">{c.profile?.title || c.profile?.sector}</div>
                  </div>
                  <Link to={`/messages?user=${c.user_id}`}><Button variant="outline" size="icon" className="rounded-full"><MessageSquare className="w-4 h-4" /></Button></Link>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
