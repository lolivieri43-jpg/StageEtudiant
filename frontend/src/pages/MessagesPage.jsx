import React, { useEffect, useState, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Send, Search } from "lucide-react";
import { Button } from "../components/ui/button";

export default function MessagesPage() {
  const { user } = useAuth();
  const [params] = useSearchParams();
  const [convs, setConvs] = useState([]);
  const [activeUser, setActiveUser] = useState(null);
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState("");
  const scrollRef = useRef();

  const initId = params.get("user");

  const loadConvs = async () => {
    const { data } = await api.get("/conversations");
    setConvs(data);
  };

  useEffect(() => { if (user) loadConvs(); }, [user]);
  useEffect(() => {
    if (!user) return;
    const t = setInterval(() => { loadConvs(); if (activeUser) loadMessages(activeUser.user_id); }, 5000);
    return () => clearInterval(t);
  }, [user, activeUser]);

  useEffect(() => {
    if (initId && !activeUser) {
      api.get(`/users/${initId}`).then((r) => setActiveUser(r.data));
    }
  }, [initId]);

  const loadMessages = async (otherId) => {
    const { data } = await api.get(`/messages/${otherId}`);
    setMessages(data);
    setTimeout(() => scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight), 50);
  };

  useEffect(() => {
    if (activeUser) loadMessages(activeUser.user_id);
  }, [activeUser]);

  const send = async () => {
    if (!text.trim() || !activeUser) return;
    await api.post("/messages", { to_user_id: activeUser.user_id, content: text });
    setText("");
    loadMessages(activeUser.user_id);
    loadConvs();
  };

  if (!user) return null;

  return (
    <div className="min-h-screen pt-16 bg-slate-50">
      <div className="max-w-6xl mx-auto h-[calc(100vh-4rem)] grid grid-cols-1 md:grid-cols-[320px_1fr]">
        {/* Conversation list */}
        <aside className="border-r border-slate-200 bg-white overflow-y-auto">
          <div className="p-4 border-b border-slate-100">
            <h2 className="font-bold text-slate-900 mb-3">Messages</h2>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input placeholder="Rechercher..." className="w-full bg-slate-100 rounded-full pl-9 pr-3 h-9 text-sm outline-none" />
            </div>
          </div>
          {convs.length === 0 && <div className="p-6 text-center text-sm text-slate-400">Aucune conversation</div>}
          {convs.map(c => (
            <button
              key={c.conv_id}
              onClick={() => setActiveUser(c.other)}
              className={`w-full flex items-center gap-3 p-3 hover:bg-slate-50 border-b border-slate-100 text-left ${activeUser?.user_id === c.other?.user_id ? "bg-blue-50" : ""}`}
              data-testid={`conv-${c.conv_id}`}
            >
              <div className="w-11 h-11 rounded-full bg-gradient-to-br from-blue-400 to-violet-400 grid place-items-center text-white font-bold shrink-0 relative">
                {c.other?.profile?.avatar || c.other?.profile?.logo ? (
                  <img src={c.other.profile.avatar || c.other.profile.logo} alt="" className="w-full h-full rounded-full object-cover" />
                ) : c.other?.name?.[0]}
                <span className="absolute bottom-0 right-0 w-3 h-3 rounded-full bg-emerald-500 border-2 border-white"></span>
              </div>
              <div className="flex-1 min-w-0">
                <div className="font-semibold text-slate-900 truncate flex items-center justify-between">
                  {c.other?.name}
                  {c.unread > 0 && <span className="bg-blue-600 text-white text-[10px] font-bold rounded-full px-1.5">{c.unread}</span>}
                </div>
                <div className="text-xs text-slate-500 truncate">{c.last_message}</div>
              </div>
            </button>
          ))}
        </aside>

        {/* Chat panel */}
        <section className="flex flex-col bg-slate-50">
          {!activeUser ? (
            <div className="flex-1 grid place-items-center text-slate-400">Sélectionnez une conversation</div>
          ) : (
            <>
              <div className="bg-white border-b border-slate-200 p-4 flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-400 to-violet-400 grid place-items-center text-white font-bold">
                  {activeUser.profile?.avatar || activeUser.profile?.logo ? (
                    <img src={activeUser.profile.avatar || activeUser.profile.logo} className="w-full h-full rounded-full object-cover" alt="" />
                  ) : activeUser.name[0]}
                </div>
                <div>
                  <div className="font-bold text-slate-900">{activeUser.name}</div>
                  <div className="text-xs flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-500"></span>En ligne</div>
                </div>
              </div>
              <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-2">
                {messages.map(m => {
                  const mine = m.from_id === user.user_id;
                  return (
                    <div key={m.message_id} className={`flex ${mine ? "justify-end" : "justify-start"}`} data-testid={`msg-${m.message_id}`}>
                      <div className={`max-w-[75%] px-4 py-2 rounded-2xl text-sm ${mine ? "bg-blue-600 text-white rounded-br-sm" : "bg-white text-slate-900 rounded-bl-sm border border-slate-200"}`}>
                        {m.content}
                      </div>
                    </div>
                  );
                })}
                {messages.length === 0 && <div className="text-center text-sm text-slate-400 mt-10">Commencez la conversation</div>}
              </div>
              <div className="bg-white border-t border-slate-200 p-3 flex items-center gap-2">
                <input
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && send()}
                  placeholder="Écrire un message..."
                  className="flex-1 bg-slate-100 rounded-full px-4 h-10 text-sm outline-none"
                  data-testid="message-input"
                />
                <Button onClick={send} className="rounded-full bg-blue-600 hover:bg-blue-700 w-10 h-10 p-0" data-testid="message-send"><Send className="w-4 h-4" /></Button>
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
