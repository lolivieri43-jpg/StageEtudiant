import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Heart, MessageCircle, Share2, Send, Image as ImageIcon } from "lucide-react";
import { Button } from "../components/ui/button";
import { Textarea } from "../components/ui/textarea";
import { Badge } from "../components/ui/badge";
import { formatDistanceToNow } from "date-fns";
import { fr } from "date-fns/locale";

export default function FeedPage() {
  const { user } = useAuth();
  const [posts, setPosts] = useState([]);
  const [content, setContent] = useState("");
  const [category, setCategory] = useState("general");
  const [posting, setPosting] = useState(false);

  const load = async () => {
    const { data } = await api.get("/posts");
    setPosts(data);
  };

  useEffect(() => { load(); }, []);

  const publish = async () => {
    if (!content.trim()) return;
    setPosting(true);
    try {
      await api.post("/posts", { content, category });
      setContent("");
      load();
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
                <div className="flex items-center justify-between mt-3">
                  <select value={category} onChange={(e) => setCategory(e.target.value)} className="text-xs rounded-full bg-slate-100 px-3 py-1.5 outline-none" data-testid="post-category">
                    <option value="general">Publication générale</option>
                    <option value="annonce">Annonce</option>
                    <option value="recherche">Recherche urgente</option>
                    <option value="conseil">Conseil</option>
                  </select>
                  <Button onClick={publish} disabled={posting || !content.trim()} className="rounded-full bg-blue-600 hover:bg-blue-700" data-testid="publish-post">
                    <Send className="w-4 h-4 mr-1" />Publier
                  </Button>
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

  const cats = {
    annonce: { label: "Annonce", color: "bg-blue-50 text-blue-700" },
    recherche: { label: "Recherche", color: "bg-amber-50 text-amber-700" },
    conseil: { label: "Conseil", color: "bg-emerald-50 text-emerald-700" },
    general: null,
  };
  const cat = cats[post.category];

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
      </div>
      <p className="text-slate-700 leading-relaxed mb-4 whitespace-pre-wrap">{post.content}</p>
      {post.image && <img src={post.image} alt="" className="rounded-xl mb-4 w-full object-cover max-h-96" />}
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
            <div key={c.comment_id} className="flex gap-2 text-sm">
              <div className="w-8 h-8 rounded-full bg-slate-200 grid place-items-center text-xs font-bold shrink-0">{c.author_name[0]}</div>
              <div className="flex-1 bg-slate-50 rounded-2xl px-3 py-2">
                <div className="font-semibold">{c.author_name}</div>
                <div className="text-slate-600">{c.content}</div>
              </div>
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
