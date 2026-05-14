import React, { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Bookmark, Share2, ExternalLink, Tag, MapPin, Calendar, Sparkles, Zap, Copy, Eye, MousePointer, Heart } from "lucide-react";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { toast } from "sonner";

export default function DealDetailPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [deal, setDeal] = useState(null);
  const [copied, setCopied] = useState(false);

  const load = async () => {
    try {
      const { data } = await api.get(`/deals/${id}`);
      setDeal(data);
    } catch {
      navigate("/deals");
    }
  };
  useEffect(() => { load(); }, [id]);

  const save = async () => {
    if (!user) { navigate("/login"); return; }
    await api.post(`/deals/${id}/save`);
    load();
  };
  const share = async () => {
    await api.post(`/deals/${id}/share`);
    if (navigator.share) {
      navigator.share({ title: deal.title, url: window.location.href }).catch(() => {});
    } else {
      navigator.clipboard.writeText(window.location.href);
      toast.success("Lien copié");
    }
  };
  const trackClick = () => {
    api.post(`/deals/${id}/click`).catch(() => {});
  };
  const copyCode = () => {
    navigator.clipboard.writeText(deal.promo_code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!deal) return <div className="pt-24 text-center text-slate-400">Chargement...</div>;

  const saved = user && deal.saves?.includes(user.user_id);
  const now = new Date();
  const isSponsored = deal.sponsored_until && new Date(deal.sponsored_until) > now;
  const isBoosted = deal.boosted_until && new Date(deal.boosted_until) > now;

  return (
    <div className="min-h-screen pt-20 pb-12 bg-slate-50">
      <div className="max-w-4xl mx-auto px-6">
        <div className="card-soft overflow-hidden">
          <div className="aspect-[21/9] bg-gradient-to-br from-violet-200 to-blue-200 relative">
            {deal.image && <img src={deal.image} alt="" className="w-full h-full object-cover" />}
            {deal.discount && (
              <div className="absolute top-5 left-5 bg-violet-600 text-white font-black text-2xl px-5 py-2 rounded-full shadow-lg">{deal.discount}</div>
            )}
            <div className="absolute top-5 right-5 flex gap-2">
              {isSponsored && <Badge className="bg-amber-100 text-amber-700 border-0 rounded-full"><Sparkles className="w-3 h-3 mr-1" />Sponsorisé</Badge>}
              {isBoosted && !isSponsored && <Badge className="bg-violet-100 text-violet-700 border-0 rounded-full"><Zap className="w-3 h-3 mr-1" />Mis en avant</Badge>}
            </div>
          </div>

          <div className="p-8">
            <div className="flex items-center gap-2 text-xs text-slate-500 mb-2">
              <Tag className="w-3.5 h-3.5" />{deal.category}
              {deal.city && <><span>·</span><MapPin className="w-3.5 h-3.5" />{deal.city}</>}
              {deal.expires_at && <><span>·</span><Calendar className="w-3.5 h-3.5" />Jusqu'au {new Date(deal.expires_at).toLocaleDateString("fr-FR")}</>}
            </div>
            <h1 className="text-3xl font-black tracking-tight text-slate-900 mb-3" data-testid="deal-title">{deal.title}</h1>
            <Link to={`/profile/${deal.author_id}`} className="text-sm text-slate-500 hover:text-blue-600">par {deal.author_name}</Link>
            <p className="text-slate-700 leading-relaxed mt-5 whitespace-pre-wrap">{deal.description}</p>

            {deal.promo_code && (
              <div className="mt-6 bg-gradient-to-r from-violet-50 to-blue-50 border-2 border-dashed border-violet-300 rounded-2xl p-5 flex items-center justify-between gap-4">
                <div>
                  <div className="text-xs font-bold uppercase tracking-wider text-violet-700 mb-1">Code promo</div>
                  <div className="text-2xl font-black tracking-wider text-slate-900" data-testid="deal-promo-code">{deal.promo_code}</div>
                </div>
                <Button onClick={copyCode} className="rounded-full bg-violet-600 hover:bg-violet-700" data-testid="copy-promo-code"><Copy className="w-4 h-4 mr-1" />{copied ? "Copié !" : "Copier"}</Button>
              </div>
            )}

            <div className="mt-6 flex flex-wrap gap-3">
              {deal.url && (
                <a href={deal.url} target="_blank" rel="noopener noreferrer" onClick={trackClick}>
                  <Button className="rounded-full bg-blue-600 hover:bg-blue-700" data-testid="deal-cta-link"><ExternalLink className="w-4 h-4 mr-1" />Profiter du bon plan</Button>
                </a>
              )}
              <Button onClick={save} variant={saved ? "default" : "outline"} className="rounded-full" data-testid="save-deal-btn"><Bookmark className={`w-4 h-4 mr-1 ${saved ? "fill-current" : ""}`} />{saved ? "Sauvegardé" : "Sauvegarder"}</Button>
              <Button onClick={share} variant="outline" className="rounded-full" data-testid="share-deal-btn"><Share2 className="w-4 h-4 mr-1" />Partager</Button>
              {user && user.user_id === deal.author_id && (
                <Link to={`/payments/boost?deal_id=${deal.deal_id}`}>
                  <Button variant="outline" className="rounded-full border-amber-300 text-amber-700"><Sparkles className="w-4 h-4 mr-1" />Mettre en avant</Button>
                </Link>
              )}
            </div>

            <div className="mt-6 grid grid-cols-3 gap-4 text-center pt-6 border-t border-slate-100">
              <Stat icon={Eye} label="vues" value={deal.views} />
              <Stat icon={MousePointer} label="clics" value={deal.clicks} />
              <Stat icon={Heart} label="sauvegardes" value={deal.saves?.length || 0} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

const Stat = ({ icon: Icon, label, value }) => (
  <div>
    <Icon className="w-4 h-4 text-slate-400 mx-auto mb-1" />
    <div className="font-bold text-slate-900">{value}</div>
    <div className="text-xs text-slate-500">{label}</div>
  </div>
);
