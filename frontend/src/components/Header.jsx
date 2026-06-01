import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Search, Bell, MessageSquare, Home, Users, Briefcase, LogOut, User, LayoutDashboard, Newspaper, Tag, Sun, Moon, Building2, Shield } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useTheme } from "../context/ThemeContext";
import api from "../lib/api";
import { Button } from "./ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "./ui/dropdown-menu";

export default function Header() {
  const { user, logout } = useAuth();
  const { effective, toggle } = useTheme() || {};
  const navigate = useNavigate();
  const [unread, setUnread] = useState(0);
  const [q, setQ] = useState("");

  useEffect(() => {
    if (!user) return;
    const fetchUnread = async () => {
      try {
        const { data } = await api.get("/notifications");
        setUnread(data.unread);
      } catch (err) { console.warn("notifications fetch failed:", err?.message || err); }
    };
    fetchUnread();
    const t = setInterval(fetchUnread, 30000);
    return () => clearInterval(t);
  }, [user]);

  const submit = (e) => {
    e.preventDefault();
    navigate(`/offers?q=${encodeURIComponent(q)}`);
  };

  const avatar = user?.profile?.avatar || user?.profile?.logo;
  const initials = user?.name?.split(" ").map(s => s[0]).slice(0, 2).join("").toUpperCase();

  return (
    <header className="fixed top-0 left-0 right-0 z-40 glass border-b border-slate-200/70" data-testid="main-header">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center gap-4">
        <Link to="/" className="flex items-center gap-2 shrink-0" data-testid="logo-link">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-blue-600 to-violet-600 grid place-items-center text-white font-black">S</div>
          <span className="font-black text-lg tracking-tight hidden sm:inline">StageEtudiant</span>
        </Link>

        <form onSubmit={submit} className="flex-1 max-w-xl" data-testid="header-search-form">
          <div className="relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              data-testid="header-search-input"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Rechercher un poste, une entreprise, une ville..."
              className="w-full bg-slate-100 hover:bg-slate-200/70 focus:bg-white focus:ring-2 focus:ring-blue-200 border-0 rounded-full pl-11 pr-4 h-10 text-sm outline-none"
            />
          </div>
        </form>

        {user ? (
          <nav className="flex items-center gap-1">
            <button
              onClick={toggle}
              className="hidden sm:flex flex-col items-center px-2.5 py-1 text-slate-600 hover:text-blue-600"
              title={effective === "dark" ? "Mode clair" : "Mode sombre"}
              data-testid="theme-toggle"
            >
              {effective === "dark" ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
              <span className="text-[10px] font-medium">Thème</span>
            </button>
            <Link to="/feed" className="hidden md:flex flex-col items-center px-3 py-1 text-slate-600 hover:text-blue-600" data-testid="nav-feed">
              <Newspaper className="w-5 h-5" />
              <span className="text-[10px] font-medium">Actualités</span>
            </Link>
            <Link to="/offers" className="hidden md:flex flex-col items-center px-3 py-1 text-slate-600 hover:text-blue-600" data-testid="nav-offers">
              <Briefcase className="w-5 h-5" />
              <span className="text-[10px] font-medium">Offres</span>
            </Link>
            <Link to="/companies" className="hidden md:flex flex-col items-center px-3 py-1 text-slate-600 hover:text-blue-600" data-testid="nav-companies">
              <Building2 className="w-5 h-5" />
              <span className="text-[10px] font-medium">Entreprises</span>
            </Link>
            <Link to="/deals" className="hidden md:flex flex-col items-center px-3 py-1 text-slate-600 hover:text-violet-600" data-testid="nav-deals">
              <Tag className="w-5 h-5" />
              <span className="text-[10px] font-medium">Bons plans</span>
            </Link>
            <Link to="/contacts" className="hidden md:flex flex-col items-center px-3 py-1 text-slate-600 hover:text-blue-600" data-testid="nav-contacts">
              <Users className="w-5 h-5" />
              <span className="text-[10px] font-medium">Réseau</span>
            </Link>
            <Link to="/messages" className="flex flex-col items-center px-3 py-1 text-slate-600 hover:text-blue-600" data-testid="nav-messages">
              <MessageSquare className="w-5 h-5" />
              <span className="text-[10px] font-medium hidden md:inline">Messages</span>
            </Link>
            <Link to="/notifications" className="relative flex flex-col items-center px-3 py-1 text-slate-600 hover:text-blue-600" data-testid="nav-notifications">
              <Bell className="w-5 h-5" />
              {unread > 0 && <span className="absolute top-0 right-2 bg-red-500 text-white text-[10px] font-bold rounded-full w-4 h-4 grid place-items-center" data-testid="notif-badge">{unread}</span>}
              <span className="text-[10px] font-medium hidden md:inline">Alertes</span>
            </Link>

            {user.role === "admin" && (
              <Link to="/admin" className="hidden md:flex flex-col items-center px-3 py-1 text-rose-600 hover:text-rose-700 font-bold" data-testid="nav-admin">
                <Shield className="w-5 h-5" />
                <span className="text-[10px] font-medium">Admin</span>
              </Link>
            )}

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className="ml-2 w-9 h-9 rounded-full overflow-hidden bg-gradient-to-br from-blue-500 to-violet-500 text-white font-bold text-sm grid place-items-center" data-testid="profile-menu-trigger">
                  {avatar ? <img src={avatar} className="w-full h-full object-cover" alt="" /> : initials}
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                <DropdownMenuLabel>{user.name}</DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={() => navigate("/dashboard")} data-testid="menu-dashboard"><LayoutDashboard className="w-4 h-4 mr-2" />Tableau de bord</DropdownMenuItem>
                <DropdownMenuItem onClick={() => navigate(`/profile/${user.user_id}`)} data-testid="menu-profile"><User className="w-4 h-4 mr-2" />Mon profil</DropdownMenuItem>
                <DropdownMenuItem onClick={() => navigate("/deals/mine")} data-testid="menu-mydeals"><Tag className="w-4 h-4 mr-2" />Mes bons plans</DropdownMenuItem>
                {user.role === "candidate" && <DropdownMenuItem onClick={() => navigate("/saved-offers")} data-testid="menu-saved">Offres sauvegardées</DropdownMenuItem>}
                {user.role === "candidate" && <DropdownMenuItem onClick={() => navigate("/my-companies")} data-testid="menu-my-companies">Mes entreprises</DropdownMenuItem>}
                {user.role === "candidate" && <DropdownMenuItem onClick={() => navigate("/cv")} data-testid="menu-my-cv">Mon CV en ligne</DropdownMenuItem>}
                <DropdownMenuItem onClick={() => navigate("/history")} data-testid="menu-history">Mon historique</DropdownMenuItem>
                {user.role === "company" && <DropdownMenuItem onClick={() => navigate("/search/students")} data-testid="menu-search-students">Rechercher des étudiants</DropdownMenuItem>}
                {user.role === "admin" && <DropdownMenuItem onClick={() => navigate("/search/students")} data-testid="menu-search-students-admin">Rechercher des étudiants</DropdownMenuItem>}
                <DropdownMenuItem onClick={() => navigate("/settings")} data-testid="menu-settings">Paramètres</DropdownMenuItem>
                {user.role === "admin" && <DropdownMenuItem onClick={() => navigate("/admin")} data-testid="menu-admin">Administration</DropdownMenuItem>}
                {user.role === "admin" && <DropdownMenuItem onClick={() => navigate("/admin/monetization")} data-testid="menu-monetization">Monétisation</DropdownMenuItem>}
                {user.role === "admin" && <DropdownMenuItem onClick={() => navigate("/admin/deals")} data-testid="menu-admin-deals">Modération bons plans</DropdownMenuItem>}
                {user.role === "admin" && <DropdownMenuItem onClick={() => navigate("/admin/ads")} data-testid="menu-admin-ads">Modération publicités</DropdownMenuItem>}
                {user.role === "admin" && <DropdownMenuItem onClick={() => navigate("/admin/reports")} data-testid="menu-admin-reports">Signalements</DropdownMenuItem>}
                {user.role === "admin" && <DropdownMenuItem onClick={() => navigate("/admin/official-profile")} data-testid="menu-admin-official">Profil officiel StageEtudiant.com</DropdownMenuItem>}
                <DropdownMenuItem onClick={() => navigate("/a-propos")} data-testid="menu-about">À propos</DropdownMenuItem>
                {user.role === "company" && <DropdownMenuItem onClick={() => navigate("/ads/mine")} data-testid="menu-my-ads">Mes publicités</DropdownMenuItem>}
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={logout} data-testid="menu-logout" className="text-red-600"><LogOut className="w-4 h-4 mr-2" />Déconnexion</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </nav>
        ) : (
          <div className="flex items-center gap-2">
            <button onClick={toggle} className="p-2 text-slate-600 hover:text-blue-600" title={effective === "dark" ? "Mode clair" : "Mode sombre"} data-testid="theme-toggle-anon">
              {effective === "dark" ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
            </button>
            <Link to="/login" data-testid="header-login-link"><Button variant="ghost" className="rounded-full">Se connecter</Button></Link>
            <Link to="/a-propos" data-testid="header-about-link" className="hidden sm:inline"><Button variant="ghost" className="rounded-full">À propos</Button></Link>
            <Link to="/register" data-testid="header-register-link">
              <Button className="rounded-full bg-blue-600 hover:bg-blue-700">S'inscrire</Button>
            </Link>
          </div>
        )}
      </div>
    </header>
  );
}
