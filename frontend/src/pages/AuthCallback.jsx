import React, { useEffect } from "react";
import api from "../lib/api";

/**
 * Handles Emergent Google Auth callback.
 * Flow: Emergent redirects back with #session_id=xxx in the URL hash.
 * We exchange it for our app session, then do a HARD reload to /dashboard
 * so AuthProvider re-mounts with the token in localStorage and fetches /me cleanly.
 * This avoids the React state race that caused the loop with <Protected> redirecting
 * to /login before setUser() was committed.
 */
export default function AuthCallback() {
  const hasProcessed = React.useRef(false);
  const [error, setError] = React.useState(null);

  useEffect(() => {
    if (hasProcessed.current) return;
    hasProcessed.current = true;
    const hash = window.location.hash;
    const m = hash.match(/session_id=([^&]+)/);
    if (!m) {
      window.location.replace("/login");
      return;
    }
    const sessionId = m[1];
    (async () => {
      try {
        const { data } = await api.post("/auth/session", { session_id: sessionId });
        if (data?.token) {
          localStorage.setItem("token", data.token);
        }
        // Hard reload so AuthProvider re-initializes with the new token.
        // Clears the URL hash and avoids the race with <Protected>.
        window.location.replace("/dashboard");
      } catch (err) {
        const detail = err?.response?.data?.detail || "Authentification Google échouée";
        setError(detail);
        // Stay on this page a moment so user can read the error, then redirect.
        setTimeout(() => window.location.replace("/login"), 3000);
      }
    })();
  }, []);

  return (
    <div className="min-h-screen pt-16 grid place-items-center bg-mesh">
      <div className="card-soft p-8 max-w-md text-center" data-testid="auth-callback-card">
        {error ? (
          <>
            <div className="text-rose-600 font-bold mb-2">{error}</div>
            <div className="text-slate-500 text-sm">Redirection vers la connexion...</div>
          </>
        ) : (
          <>
            <div className="w-10 h-10 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin mx-auto mb-4"></div>
            <div className="text-slate-700 font-semibold">Connexion en cours...</div>
            <div className="text-slate-500 text-sm mt-1">Vous allez être redirigé(e) vers votre tableau de bord</div>
          </>
        )}
      </div>
    </div>
  );
}
