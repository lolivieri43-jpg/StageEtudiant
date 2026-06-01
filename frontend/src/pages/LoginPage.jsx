import React, { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { backendUrl } from "../lib/api";
import { toast } from "sonner";

export default function LoginPage() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const u = await login(email, password);
      toast.success("Connexion réussie");
      // Auto-redirect admins (and especially the owner) to the admin dashboard
      const isOwner = (u?.email || email).toLowerCase() === "bernardolivieri1326@gmail.com";
      if (u?.role === "admin" || isOwner) {
        navigate("/admin");
      } else {
        navigate("/dashboard");
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erreur de connexion");
    } finally {
      setLoading(false);
    }
  };

  // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
  const googleLogin = () => {
    // Hits our backend, which builds the Google authorize URL with the correct redirect_uri
    // based on the current host (preview or production), then redirects to Google.
    window.location.href = backendUrl("/api/auth/google");
  };

  return (
    <div className="min-h-screen pt-16 bg-mesh flex items-center justify-center p-6">
      <div className="card-soft w-full max-w-md p-8" data-testid="login-card">
        <h1 className="text-3xl font-black tracking-tight text-slate-900 mb-2">Connexion</h1>
        <p className="text-slate-500 mb-6">Bon retour parmi nous !</p>
        <form onSubmit={submit} className="space-y-4">
          <div>
            <Label htmlFor="email">Email</Label>
            <Input id="email" data-testid="login-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required className="rounded-xl mt-1" />
          </div>
          <div>
            <Label htmlFor="password">Mot de passe</Label>
            <Input id="password" data-testid="login-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required className="rounded-xl mt-1" />
          </div>
          <Button type="submit" disabled={loading} className="w-full rounded-xl bg-blue-600 hover:bg-blue-700 h-11" data-testid="login-submit">
            {loading ? "Connexion..." : "Se connecter"}
          </Button>
        </form>

        <div className="my-6 flex items-center gap-3 text-xs text-slate-400">
          <div className="flex-1 h-px bg-slate-200"></div>OU<div className="flex-1 h-px bg-slate-200"></div>
        </div>

        <Button onClick={googleLogin} variant="outline" className="w-full rounded-xl h-11" data-testid="login-google">
          <svg className="w-5 h-5 mr-2" viewBox="0 0 24 24">
            <path fill="#4285F4" d="M22.5 12.27c0-.79-.07-1.55-.2-2.27H12v4.3h5.9c-.26 1.37-1.04 2.53-2.21 3.31v2.75h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.75c-.99.66-2.25 1.06-3.71 1.06-2.85 0-5.27-1.92-6.13-4.51H2.18v2.84A11 11 0 0 0 12 23z"/>
            <path fill="#FBBC05" d="M5.87 14.14a6.6 6.6 0 0 1 0-4.28V7.02H2.18a11 11 0 0 0 0 9.96l3.69-2.84z"/>
            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.02l3.69 2.84C6.73 7.3 9.15 5.38 12 5.38z"/>
          </svg>
          Continuer avec Google
        </Button>

        <p className="text-center text-sm text-slate-500 mt-6">
          Pas encore de compte ? <Link to="/register" className="text-blue-600 font-semibold" data-testid="login-to-register">S'inscrire</Link>
        </p>
      </div>
    </div>
  );
}
