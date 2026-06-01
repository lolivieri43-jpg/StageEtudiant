import React, { useEffect, useState, useRef } from "react";
import { Link } from "react-router-dom";
import api, { backendUrl } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Heart, MessageCircle, Share2, Send, Image as ImageIcon, Video, FileText, Link as LinkIcon, X, Loader2, Paperclip, Flag, MoreHorizontal } from "lucide-react";
import { Button } from "../components/ui/button";
import { Textarea } from "../components/ui/textarea";
import { Badge } from "../components/ui/badge";
import { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem } from "../components/ui/dropdown-menu";
import { formatDistanceToNow } from "date-fns";
import { fr } from "date-fns/locale";
import { toast } from "sonner";

export default function FeedPage() {
  const { user } = useAuth();
  const [posts, setPosts] = useState([]);
  const [content, setContent] = useState("");
  const [category, setCategory] = useState("general");
  const [posting, setPosting] = useState(false);
  const [media, setMedia] = useState([]); // [{type, url, file_id, filename, mime, size}]
  const [linkPreview, setLinkPreview] = useState(null);
  const [linkLoading, setLinkLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef(null);
  const linkUrlSeen = useRef("");

  const load = async () => {
    const { data } = await api.get("/posts");
    setPosts(data);
  };
  useEffect(() => { load(); }, []);

  // Detect URLs in content for link preview (debounced)
  useEffect(() => {
    if (!content || media.length || linkPreview) return;
    const urlMatch = content.match(/https?:\/\/[^\s]+/i);
    if (!urlMatch) return;
    const url = urlMatch[0].replace(/[.,;!?]+$/, "");
    if (url === linkUrlSeen.current) return;
    linkUrlSeen.current = url;
    setLinkLoading(true);
    const t = setTimeout(async () => {
      try {
        const { data } = await api.post("/posts/link-preview", { url });
        if (data?.url) setLinkPreview(data);
      } catch { /* silent */ }
      finally { setLinkLoading(false); }
    }, 800);
    return () => clearTimeout(t);
  }, [content, media.length, linkPreview]);

  const upload = async (file, type) => {
    if (!file) return;
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const { data } = await api.post(`/upload?kind=post`, form, { headers: { "Content-Type": "multipart/form-data" } });
      const fullUrl = data.url.startsWith("http") ? data.url : backendUrl(data.url);
      setMedia(m => [...m, {
        type, url: fullUrl, file_id: data.file_id, filename: data.filename,
        mime: data.content_type, size: data.size,
      }]);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Échec de l'upload");
    } finally {
      setUploading(false);
    }
  };

  const onPick = (accept, type) => () => {
    if (!fileInputRef.current) return;
    fileInputRef.current.accept = accept;
    fileInputRef.current.dataset.type = type;
    fileInputRef.current.click();
  };

  const handleFile = (e) => {
    const f = e.target.files?.[0];
    if (f) upload(f, e.target.dataset.type || "image");
    e.target.value = "";
  };

  const removeMedia = (i) => setMedia(m => m.filter((_, idx) => idx !== i));

  const publish = async () => {
    if (!content.trim() && media.length === 0) return;
    setPosting(true);
    try {
      await api.post("/posts", { content, category, media, link_preview: linkPreview });
      setContent("");
      setMedia([]);
      setLinkPreview(null);
      linkUrlSeen.current = "";
      load();
      toast.success("Publication envoyée");
    } finally {
      setPosting(false);
    }
  };

  const toggleLike = async (postId) => {
    const { data } = await api.post(`/posts/${postId}/like`);
    setPosts(posts.map(p => p.post_id === postId ? { ...p, likes: data.likes } : p));
  };

  return (
    <div className="min-h-screen pt-20 pb-12 bg-slate-50">
      <div className="max-w-2xl mx-auto px-4 sm:px-6">
        {user && (
          <div className="card-soft p-5 mb-6">
            <div className="flex gap-3">
              <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-violet-500 grid place-items-center text-white font-bold shrink-0">
                {user.name[0]}
              </div>
              <div className="flex-1">
                <Textarea
                  data-testid="post-composer"
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  placeholder="Partagez une publication, une recherche, une réussite..."
                  rows={3}
                  className="rounded-xl resize-none"
                />

                {/* Media previews */}
                {media.length > 0 && (
                  <div className="grid grid-cols-2 gap-2 mt-3" data-testid="media-previews">
                    {media.map((m, i) => (
                      <div key={i} className="relative rounded-xl overflow-hidden bg-slate-100 group">
                        {m.type === "image" && <img src={m.url} alt="" className="w-full h-32 object-cover" />}
                        {m.type === "video" && (
                          <div className="w-full h-32 grid place-items-center bg-slate-900 text-white">
                            <Video className="w-6 h-6" />
                            <div className="text-[10px] truncate max-w-full px-2">{m.filename}</div>
                          </div>
                        )}
                        {m.type === "pdf" && (
                          <div className="w-full h-32 grid place-items-center bg-rose-50 text-rose-700">
                            <FileText className="w-6 h-6" />
                            <div className="text-[10px] truncate max-w-full px-2">{m.filename}</div>
                          </div>
                        )}
                        <button
                          onClick={() => removeMedia(i)}
                          className="absolute top-1 right-1 w-6 h-6 rounded-full bg-slate-900/70 text-white grid place-items-center hover:bg-slate-900"
                          data-testid={`remove-media-${i}`}>
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                {/* Link preview */}
                {linkLoading && (
                  <div className="mt-3 flex items-center gap-2 text-xs text-slate-500">
                    <Loader2 className="w-3 h-3 animate-spin" />Chargement de l'aperçu du lien…
                  </div>
                )}
                {linkPreview && (
                  <div className="mt-3 border border-slate-200 rounded-xl p-3 flex gap-3 relative" data-testid="link-preview">
                    {linkPreview.image && <img src={linkPreview.image} alt="" className="w-20 h-20 rounded-lg object-cover shrink-0" onError={(e) => { e.currentTarget.style.display = "none"; }} />}
                    <div className="flex-1 min-w-0">
                      <div className="text-[10px] uppercase tracking-wide text-slate-400">{linkPreview.domain}</div>
                      <div className="font-bold text-sm text-slate-900 truncate">{linkPreview.title}</div>
                      <div className="text-xs text-slate-500 line-clamp-2">{linkPreview.description}</div>
                    </div>
                    <button onClick={() => setLinkPreview(null)} className="absolute top-2 right-2 w-6 h-6 rounded-full bg-slate-100 grid place-items-center hover:bg-slate-200">
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                )}

                <div className="flex items-center justify-between mt-3 flex-wrap gap-2">
                  <div className="flex items-center gap-1">
                    <button onClick={onPick("image/*", "image")} disabled={uploading} className="p-2 rounded-full hover:bg-slate-100 text-slate-600 disabled:opacity-50" data-testid="upload-image" title="Ajouter une image">
                      <ImageIcon className="w-4 h-4" />
                    </button>
                    <button onClick={onPick("video/*", "video")} disabled={uploading} className="p-2 rounded-full hover:bg-slate-100 text-slate-600 disabled:opacity-50" data-testid="upload-video" title="Ajouter une vidéo">
                      <Video className="w-4 h-4" />
                    </button>
                    <button onClick={onPick(".pdf,application/pdf", "pdf")} disabled={uploading} className="p-2 rounded-full hover:bg-slate-100 text-slate-600 disabled:opacity-50" data-testid="upload-pdf" title="Ajouter un PDF">
                      <FileText className="w-4 h-4" />
                    </button>
                    <span className="w-px h-5 bg-slate-200 mx-1" />
                    <span className="text-[10px] text-slate-400 hidden sm:inline">
                      <LinkIcon className="w-3 h-3 inline mr-0.5" />Collez un lien dans le texte pour l'aperçu
                    </span>
                    {uploading && <Loader2 className="w-4 h-4 animate-spin text-blue-500" />}
                    <input ref={fileInputRef} type="file" className="hidden" onChange={handleFile} data-testid="post-file-input" />
                  </div>
                  <div className="flex items-center gap-2">
                    <select value={category} onChange={(e) => setCategory(e.target.value)} className="text-xs rounded-full bg-slate-100 px-3 py-1.5 outline-none" data-testid="post-category">
                      <option value="general">Général</option>
                      <option value="annonce">Annonce</option>
                      <option value="recherche">Recherche</option>
                      <option value="conseil">Conseil</option>
                    </select>
                    <Button onClick={publish} disabled={posting || uploading || (!content.trim() && media.length === 0)} className="rounded-full bg-blue-600 hover:bg-blue-700" data-testid="publish-post">
                      <Send className="w-4 h-4 mr-1" />Publier
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        <div className="space-y-4">
          {posts.map(p => <PostCard key={p.post_id} post={p} user={user} onLike={() => toggleLike(p.post_id)} />)}
        </div>
      </div>
    </div>
  );
}

const PostCard = ({ post, user, onLike }) => {
  const [showComments, setShowComments] = useState(false);
  const [comments, setComments] = useState([]);
  const [comment, setComment] = useState("");
  const liked = user && post.likes?.includes(user.user_id);
  const isMine = user && post.author_id === user.user_id;

  const loadComments = async () => {
    const { data } = await api.get(`/posts/${post.post_id}/comments`);
    setComments(data);
    setShowComments(true);
  };
  const addComment = async () => {
    if (!comment.trim()) return;
    await api.post("/posts/comment", { post_id: post.post_id, content: comment });
    setComment("");
    loadComments();
  };

  const reportPost = async () => {
    const reasons = [
      ["spam", "Spam / publicité"],
      ["harassment", "Harcèlement"],
      ["hate_speech", "Discours haineux"],
      ["violence", "Violence"],
      ["inappropriate", "Contenu inapproprié"],
      ["misinformation", "Désinformation"],
      ["scam", "Arnaque"],
      ["other", "Autre"],
    ];
    const msg = "Pourquoi signalez-vous cette publication ?\n" +
      reasons.map((r, i) => `${i + 1}. ${r[1]}`).join("\n") +
      "\n\nEntrez le numéro (1-8) :";
    const choice = window.prompt(msg, "1");
    if (!choice) return;
    const idx = parseInt(choice, 10) - 1;
    if (idx < 0 || idx >= reasons.length) {
      toast.error("Choix invalide");
      return;
    }
    const details = window.prompt("Précisions (facultatif) :", "") || "";
    try {
      await api.post("/reports", {
        target_type: "post",
        target_id: post.post_id,
        reason: reasons[idx][0],
        details,
      });
      toast.success("Signalement transmis à la modération");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Erreur");
    }
  };

  const reportComment = async (commentId) => {
    const reason = window.prompt("Raison (spam, harassment, hate_speech, violence, inappropriate, misinformation, scam, other) :", "spam");
    if (!reason) return;
    try {
      await api.post("/reports", {
        target_type: "comment", target_id: commentId, reason,
      });
      toast.success("Commentaire signalé");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Erreur");
    }
  };

  const cats = {
    annonce: { label: "Annonce", color: "bg-blue-50 text-blue-700" },
    recherche: { label: "Recherche", color: "bg-amber-50 text-amber-700" },
    conseil: { label: "Conseil", color: "bg-emerald-50 text-emerald-700" },
    general: null,
  };
  const cat = cats[post.category];
  const mediaList = post.media && post.media.length ? post.media : (post.image ? [{ type: "image", url: post.image }] : []);

  return (
    <div className="card-soft p-5" data-testid={`post-${post.post_id}`}>
      <div className="flex items-start gap-3 mb-3">
        <Link to={`/profile/${post.author_id}`} className="w-11 h-11 rounded-full overflow-hidden bg-gradient-to-br from-blue-500 to-violet-500 grid place-items-center text-white font-bold shrink-0">
          {post.author_avatar ? <img src={post.author_avatar} className="w-full h-full object-cover" alt="" /> : post.author_name[0]}
        </Link>
        <div className="flex-1">
          <Link to={`/profile/${post.author_id}`} className="font-bold text-slate-900 hover:text-blue-600">{post.author_name}</Link>
          <div className="text-xs text-slate-400 flex items-center gap-2">
            <span>{post.author_role === "company" ? "Entreprise" : "Étudiant"}</span>
            <span>·</span>
            <span>{formatDistanceToNow(new Date(post.created_at), { addSuffix: true, locale: fr })}</span>
            {cat && <Badge className={`${cat.color} border-0 rounded-full text-[10px]`}>{cat.label}</Badge>}
          </div>
        </div>
        {user && !isMine && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="p-1.5 rounded-full hover:bg-slate-100 text-slate-400" data-testid={`post-menu-${post.post_id}`}>
                <MoreHorizontal className="w-4 h-4" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={reportPost} className="text-rose-600" data-testid={`report-post-${post.post_id}`}>
                <Flag className="w-4 h-4 mr-2" />Signaler
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>
      <p className="text-slate-700 leading-relaxed mb-4 whitespace-pre-wrap">{post.content}</p>

      {mediaList.length > 0 && (
        <div className={`grid gap-2 mb-4 ${mediaList.length > 1 ? "grid-cols-2" : "grid-cols-1"}`} data-testid={`media-${post.post_id}`}>
          {mediaList.map((m, i) => (
            <PostMedia key={i} m={m} />
          ))}
        </div>
      )}

        {post.link_preview && (
          <a href={post.link_preview.url} target="_blank" rel="noopener noreferrer"
             className="block border border-slate-200 rounded-xl p-3 mb-4 flex gap-3 hover:bg-slate-50" data-testid={`linkpreview-${post.post_id}`}>
            {post.link_preview.image && <img src={post.link_preview.image} alt="" className="w-20 h-20 rounded-lg object-cover shrink-0" onError={(e) => { e.currentTarget.style.display = "none"; }} />}
            <div className="flex-1 min-w-0">
              <div className="text-[10px] uppercase tracking-wide text-slate-400">{post.link_preview.domain}</div>
              <div className="font-bold text-sm text-slate-900 truncate">{post.link_preview.title || post.link_preview.url}</div>
              {post.link_preview.description && <div className="text-xs text-slate-500 line-clamp-2">{post.link_preview.description}</div>}
            </div>
          </a>
        )}

      <div className="flex items-center gap-1 pt-3 border-t border-slate-100">
        <button onClick={onLike} className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full hover:bg-slate-50 text-sm ${liked ? "text-rose-500" : "text-slate-500"}`} data-testid={`like-${post.post_id}`}>
          <Heart className={`w-4 h-4 ${liked ? "fill-current" : ""}`} />{post.likes?.length || 0}
        </button>
        <button onClick={loadComments} className="flex items-center gap-1.5 px-3 py-1.5 rounded-full hover:bg-slate-50 text-sm text-slate-500" data-testid={`comment-toggle-${post.post_id}`}>
          <MessageCircle className="w-4 h-4" />{post.comments_count || comments.length}
        </button>
        <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-full hover:bg-slate-50 text-sm text-slate-500">
          <Share2 className="w-4 h-4" />Partager
        </button>
      </div>
      {showComments && (
        <div className="mt-4 space-y-3 border-t border-slate-100 pt-4">
          {comments.map(c => (
            <div key={c.comment_id} className="flex gap-2 text-sm group">
              <div className="w-8 h-8 rounded-full bg-slate-200 grid place-items-center text-xs font-bold shrink-0">{c.author_name[0]}</div>
              <div className="flex-1 bg-slate-50 rounded-2xl px-3 py-2">
                <div className="font-semibold">{c.author_name}</div>
                <div className="text-slate-600">{c.content}</div>
              </div>
              {user && c.author_id !== user.user_id && (
                <button onClick={() => reportComment(c.comment_id)} className="opacity-0 group-hover:opacity-100 text-slate-400 hover:text-rose-600 p-1" data-testid={`report-comment-${c.comment_id}`} title="Signaler ce commentaire">
                  <Flag className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          ))}
          {user && (
            <div className="flex gap-2">
              <input value={comment} onChange={(e) => setComment(e.target.value)} onKeyDown={(e) => e.key === "Enter" && addComment()} placeholder="Commenter..." className="flex-1 bg-slate-50 rounded-full px-4 py-2 text-sm outline-none" data-testid={`comment-input-${post.post_id}`} />
              <Button size="sm" onClick={addComment} className="rounded-full" data-testid={`comment-submit-${post.post_id}`}>Envoyer</Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

function PostMedia({ m }) {
  if (m.type === "image") {
    return <img src={m.url} alt="" className="rounded-xl w-full object-cover max-h-96" />;
  }
  if (m.type === "video") {
    return (
      <video controls preload="metadata" className="rounded-xl w-full max-h-96 bg-slate-900">
        <source src={m.url} type={m.mime || "video/mp4"} />
        Votre navigateur ne supporte pas la lecture vidéo.
      </video>
    );
  }
  if (m.type === "pdf") {
    return (
      <a href={m.url} target="_blank" rel="noopener noreferrer"
         className="flex items-center gap-3 p-4 rounded-xl bg-rose-50 hover:bg-rose-100 border border-rose-100">
        <div className="w-12 h-12 rounded-xl bg-rose-100 grid place-items-center text-rose-600 shrink-0">
          <FileText className="w-6 h-6" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="font-bold text-rose-900 truncate">{m.filename || "Document PDF"}</div>
          <div className="text-xs text-rose-700">{m.size ? `${Math.round(m.size/1024)} ko` : "PDF"} · Cliquez pour ouvrir</div>
        </div>
      </a>
    );
  }
  return null;
}
