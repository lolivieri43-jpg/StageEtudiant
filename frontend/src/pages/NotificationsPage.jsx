import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../lib/api";
import { Bell, Check } from "lucide-react";
import { Button } from "../components/ui/button";
import { formatDistanceToNow } from "date-fns";
import { fr } from "date-fns/locale";

export default function NotificationsPage() {
  const [notifs, setNotifs] = useState([]);

  const load = async () => {
    const { data } = await api.get("/notifications");
    setNotifs(data.notifications);
  };
  useEffect(() => {
    load();
    api.post("/notifications/read").catch(() => {});
  }, []);

  return (
    <div className="min-h-screen pt-20 pb-12 bg-slate-50">
      <div className="max-w-2xl mx-auto px-6">
        <h1 className="text-3xl font-black tracking-tight text-slate-900 mb-6">Notifications</h1>
        {notifs.length === 0 ? (
          <div className="card-soft p-12 text-center text-slate-400 text-sm">
            <Bell className="w-10 h-10 mx-auto mb-3 text-slate-300" />
            Aucune notification
          </div>
        ) : (
          <div className="space-y-2">
            {notifs.map(n => (
              <Link to={n.link || "#"} key={n.notif_id} className="card-soft p-4 flex items-start gap-3 hover-lift" data-testid={`notif-${n.notif_id}`}>
                <div className={`w-10 h-10 rounded-full grid place-items-center shrink-0 ${n.read ? "bg-slate-100" : "bg-blue-100"}`}>
                  <Bell className={`w-4 h-4 ${n.read ? "text-slate-400" : "text-blue-600"}`} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-slate-700">{n.message}</p>
                  <div className="text-xs text-slate-400 mt-1">{formatDistanceToNow(new Date(n.created_at), { addSuffix: true, locale: fr })}</div>
                </div>
                {!n.read && <span className="w-2 h-2 rounded-full bg-blue-500 mt-2"></span>}
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
