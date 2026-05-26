import React, { useEffect, useState, useRef, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Send, Search, Paperclip, FileText, Image as ImageIcon, X, Loader2 } from "lucide-react";
import { Button } from "../components/ui/button";
import useChatSocket from "../hooks/useChatSocket";
import { toast } from "sonner";

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
  const fileInputRef = useRef(null);
  const [pendingAttachments, setPendingAttachments] = useState([]);
  const [uploading, setUploading] = useState(false);

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
    if ((!text.trim() && pendingAttachments.length === 0) || !activeUser) return;
    const content = text;
    const atts = [...pendingAttachments];
    setText("");
    setPendingAttachments([]);
    await api.post("/messages-rt", { to_user_id: activeUser.user_id, content, attachments: atts });
    // WS will push the message back, but ensure UI updates immediately
    setTimeout(loadConvs, 200);
  };

  const detectType = (mime, filename) => {
    if (!mime) {
      const ext = (filename || "").split(".").pop()?.toLowerCase();
      if (["jpg","jpeg","png","gif","webp"].includes(ext)) return "image";
      if (["mp4","webm","mov"].includes(ext)) return "video";
      if (ext === "pdf") return "pdf";
      return "file";
    }
    if (mime.startsWith("image/")) return "image";
    if (mime.startsWith("video/")) return "video";
    if (mime === "application/pdf") return "pdf";
    return "file";
  };

  const onAttachFile = async (e) => {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (!f) return;
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", f);
      const { data } = await api.post("/upload?kind=message", form, { headers: { "Content-Type": "multipart/form-data" } });
      const API = process.env.REACT_APP_BACKEND_URL || "";
      const fullUrl = data.url.startsWith("http") ? data.url : `${API}${data.url}`;
      setPendingAttachments(a => [...a, {
        type: detectType(data.content_type, data.filename),
        url: fullUrl, file_id: data.file_id, filename: data.filename,
        mime: data.content_type, size: data.size,
      }]);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Échec de l'envoi du fichier");
    } finally {
      setUploading(false);
    }
  };

  const removePending = (i) => setPendingAttachments(a => a.filter((_, idx) => idx !== i));

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
                  const atts = m.attachments && m.attachments.length ? m.attachments :
                               (m.attachment ? [{ type: "file", url: m.attachment, filename: "Pièce jointe" }] : []);
                  return (
                    <div key={m.message_id} className={`flex ${mine ? "justify-end" : "justify-start"}`} data-testid={`msg-${m.message_id}`}>
                      <div className={`max-w-[75%] space-y-2`}>
                        {m.content && (
                          <div className={`px-4 py-2 rounded-2xl text-sm ${mine ? "bg-blue-600 text-white rounded-br-sm" : "bg-white text-slate-900 rounded-bl-sm border border-slate-200"}`}>
                            {m.content}
                          </div>
                        )}
                        {atts.map((a, i) => <MessageAttachmentView key={i} a={a} mine={mine} />)}
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
              <div className="bg-white border-t border-slate-200 p-3">
                {pendingAttachments.length > 0 && (
                  <div className="flex flex-wrap gap-2 mb-2" data-testid="pending-attachments">
                    {pendingAttachments.map((a, i) => (
                      <div key={i} className="relative rounded-xl border border-slate-200 p-2 pr-7 flex items-center gap-2 bg-slate-50 max-w-[200px]">
                        {a.type === "image" && <img src={a.url} alt="" className="w-8 h-8 rounded-lg object-cover" />}
                        {a.type === "video" && <div className="w-8 h-8 rounded-lg bg-slate-900 text-white grid place-items-center"><Paperclip className="w-3 h-3" /></div>}
                        {(a.type === "pdf" || a.type === "file") && <div className="w-8 h-8 rounded-lg bg-rose-100 text-rose-600 grid place-items-center"><FileText className="w-4 h-4" /></div>}
                        <div className="flex-1 min-w-0">
                          <div className="text-xs font-semibold truncate">{a.filename}</div>
                          <div className="text-[10px] text-slate-500">{a.size ? `${Math.round(a.size/1024)} ko` : a.type}</div>
                        </div>
                        <button onClick={() => removePending(i)} className="absolute top-1 right-1 text-slate-400 hover:text-slate-700" data-testid={`remove-attachment-${i}`}>
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
                <div className="flex items-center gap-2">
                  <input ref={fileInputRef} type="file"
                         accept=".pdf,.docx,.xlsx,.pptx,image/*,video/*"
                         className="hidden" onChange={onAttachFile} data-testid="msg-file-input" />
                  <button onClick={() => fileInputRef.current?.click()} disabled={uploading}
                          className="p-2 rounded-full hover:bg-slate-100 text-slate-600 disabled:opacity-50"
                          data-testid="msg-attach-btn" title="Joindre un fichier">
                    {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Paperclip className="w-4 h-4" />}
                  </button>
                  <input
                    value={text}
                    onChange={(e) => handleTyping(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && sendMessage()}
                    placeholder="Écrire un message..."
                    className="flex-1 bg-slate-100 rounded-full px-4 h-10 text-sm outline-none"
                    data-testid="message-input"
                  />
                  <Button onClick={sendMessage} disabled={uploading || (!text.trim() && pendingAttachments.length === 0)} className="rounded-full bg-blue-600 hover:bg-blue-700 w-10 h-10 p-0" data-testid="message-send"><Send className="w-4 h-4" /></Button>
                </div>
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}


function MessageAttachmentView({ a, mine }) {
  if (a.type === "image") {
    return (
      <a href={a.url} target="_blank" rel="noopener noreferrer" className="block max-w-[280px]">
        <img src={a.url} alt={a.filename || ""} className="rounded-2xl max-h-72 object-cover w-full border border-slate-200" />
      </a>
    );
  }
  if (a.type === "video") {
    return (
      <video controls preload="metadata" className="rounded-2xl max-h-72 bg-slate-900 max-w-[320px]">
        <source src={a.url} type={a.mime || "video/mp4"} />
      </video>
    );
  }
  // pdf / doc / file
  const bg = mine ? "bg-blue-700/90 text-white border-blue-500" : "bg-white border-slate-200 text-slate-900";
  return (
    <a href={a.url} target="_blank" rel="noopener noreferrer"
       className={`flex items-center gap-2 px-3 py-2 rounded-2xl border ${bg} text-sm max-w-[280px]`}>
      <FileText className="w-4 h-4 shrink-0" />
      <div className="flex-1 min-w-0">
        <div className="font-semibold truncate">{a.filename || "Pièce jointe"}</div>
        <div className={`text-[10px] ${mine ? "text-blue-100" : "text-slate-500"}`}>
          {a.size ? `${Math.round(a.size/1024)} ko` : (a.mime || a.type)}
        </div>
      </div>
    </a>
  );
}
