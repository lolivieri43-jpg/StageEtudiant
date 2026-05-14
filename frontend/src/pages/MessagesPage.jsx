import React, { useEffect, useState, useRef, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Send, Search } from "lucide-react";
import { Button } from "../components/ui/button";
import useChatSocket from "../hooks/useChatSocket";

export default function MessagesPage() {
  const { user } = useAuth();
  const [params] = useSearchParams();
  const [convs, setConvs] = useState([]);
  const [activeUser, setActiveUser] = useState(null);
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState("");
  const [onlineSet, setOnlineSet] = useState(new Set());
  const [typingFrom, setTypingFrom] = useState(null);
  const scrollRef = useRef();
  const typingTimer = useRef(null);
  const activeUserIdRef = useRef(null);

  const initId = params.get("user");

  const loadConvs = useCallback(async () => {
    const { data } = await api.get("/conversations");
    setConvs(data);
  }, []);

  const loadMessages = useCallback(async (otherId) => {
    const { data } = await api.get(`/messages/${otherId}`);
    setMessages(data);
    setTimeout(() => scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight), 50);
  }, []);

  // WebSocket connection
  const onWsMessage = useCallback((msg) => {
    const active = activeUserIdRef.current;
    if (active && (msg.from_id === active || msg.to_id === active)) {
      setMessages(prev => prev.some(m => m.message_id === msg.message_id) ? prev : [...prev, msg]);
      setTimeout(() => scrollRef.current?.scrollTo(0, scrollRef.current?.scrollHeight || 0), 50);
    }
    loadConvs();
  }, [loadConvs]);

  const onWsTyping = useCallback((data) => {
    if (data.is_typing) {
      setTypingFrom(data.from_id);
      clearTimeout(typingTimer.current);
      typingTimer.current = setTimeout(() => setTypingFrom(null), 3000);
    } else {
      setTypingFrom(null);
    }
  }, []);

  const onWsPresence = useCallback((data) => {
    setOnlineSet(prev => {
      const next = new Set(prev);
      if (data.online) next.add(data.user_id); else next.delete(data.user_id);
      return next;
    });
  }, []);

  const { connected, send } = useChatSocket({
    enabled: !!user,
    onMessage: onWsMessage,
    onTyping: onWsTyping,
    onPresence: onWsPresence,
  });

  useEffect(() => {
    activeUserIdRef.current = activeUser?.user_id || null;
  }, [activeUser]);

  useEffect(() => {
    if (!user) return;
    loadConvs();
    api.get("/presence").then((r) => setOnlineSet(new Set(r.data.online))).catch(() => {});
  }, [user, loadConvs]);

  useEffect(() => {
    if (initId && !activeUser) {
      api.get(`/users/${initId}`).then((r) => setActiveUser(r.data));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initId]);

  useEffect(() => {
    if (activeUser) loadMessages(activeUser.user_id);
  }, [activeUser, loadMessages]);

  const sendMessage = async () => {
    if (!text.trim() || !activeUser) return;
    const content = text;
    setText("");
    await api.post("/messages-rt", { to_user_id: activeUser.user_id, content });
    // WS will push the message back, but ensure UI updates immediately
    setTimeout(loadConvs, 200);
  };

  const handleTyping = (v) => {
    setText(v);
    if (activeUser && connected) {
      send({ type: "typing", to_user_id: activeUser.user_id, is_typing: !!v });
    }
  };

  if (!user) return null;
  const isActiveOnline = activeUser && onlineSet.has(activeUser.user_id);

  return (
    <div className="min-h-screen pt-16 bg-slate-50">
      <div className="max-w-6xl mx-auto h-[calc(100vh-4rem)] grid grid-cols-1 md:grid-cols-[320px_1fr]">
        <aside className="border-r border-slate-200 bg-white overflow-y-auto">
          <div className="p-4 border-b border-slate-100">
            <h2 className="font-bold text-slate-900 mb-3 flex items-center gap-2">
              Messages
              <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full ${connected ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-500"}`} data-testid="ws-status">
                {connected ? "Live" : "Offline"}
              </span>
            </h2>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input placeholder="Rechercher..." className="w-full bg-slate-100 rounded-full pl-9 pr-3 h-9 text-sm outline-none" />
            </div>
          </div>
          {convs.length === 0 && <div className="p-6 text-center text-sm text-slate-400">Aucune conversation</div>}
          {convs.map(c => {
            const isOnline = c.other && onlineSet.has(c.other.user_id);
            return (
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
                  <span className={`absolute bottom-0 right-0 w-3 h-3 rounded-full ${isOnline ? "bg-emerald-500" : "bg-slate-300"} border-2 border-white`}></span>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-semibold text-slate-900 truncate flex items-center justify-between">
                    {c.other?.name}
                    {c.unread > 0 && <span className="bg-blue-600 text-white text-[10px] font-bold rounded-full px-1.5">{c.unread}</span>}
                  </div>
                  <div className="text-xs text-slate-500 truncate">{c.last_message}</div>
                </div>
              </button>
            );
          })}
        </aside>

        <section className="flex flex-col bg-slate-50">
          {!activeUser ? (
            <div className="flex-1 grid place-items-center text-slate-400">Sélectionnez une conversation</div>
          ) : (
            <>
              <div className="bg-white border-b border-slate-200 p-4 flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-400 to-violet-400 grid place-items-center text-white font-bold relative">
                  {activeUser.profile?.avatar || activeUser.profile?.logo ? (
                    <img src={activeUser.profile.avatar || activeUser.profile.logo} className="w-full h-full rounded-full object-cover" alt="" />
                  ) : activeUser.name[0]}
                  <span className={`absolute bottom-0 right-0 w-3 h-3 rounded-full ${isActiveOnline ? "bg-emerald-500" : "bg-slate-300"} border-2 border-white`}></span>
                </div>
                <div>
                  <div className="font-bold text-slate-900">{activeUser.name}</div>
                  <div className="text-xs flex items-center gap-1" data-testid="presence-indicator">
                    <span className={`w-2 h-2 rounded-full ${isActiveOnline ? "bg-emerald-500" : "bg-slate-300"}`}></span>
                    {isActiveOnline ? "En ligne" : "Hors ligne"}
                  </div>
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
                {typingFrom === activeUser.user_id && (
                  <div className="flex justify-start" data-testid="typing-indicator">
                    <div className="bg-white border border-slate-200 rounded-2xl rounded-bl-sm px-4 py-2 text-sm text-slate-400 italic flex items-center gap-1">
                      <span className="inline-block w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }}></span>
                      <span className="inline-block w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }}></span>
                      <span className="inline-block w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }}></span>
                      <span className="ml-1">écrit...</span>
                    </div>
                  </div>
                )}
                {messages.length === 0 && <div className="text-center text-sm text-slate-400 mt-10">Commencez la conversation</div>}
              </div>
              <div className="bg-white border-t border-slate-200 p-3 flex items-center gap-2">
                <input
                  value={text}
                  onChange={(e) => handleTyping(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && sendMessage()}
                  placeholder="Écrire un message..."
                  className="flex-1 bg-slate-100 rounded-full px-4 h-10 text-sm outline-none"
                  data-testid="message-input"
                />
                <Button onClick={sendMessage} className="rounded-full bg-blue-600 hover:bg-blue-700 w-10 h-10 p-0" data-testid="message-send"><Send className="w-4 h-4" /></Button>
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
