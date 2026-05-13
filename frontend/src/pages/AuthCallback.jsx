import React, { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";

export default function AuthCallback() {
  const navigate = useNavigate();
  const { setUser } = useAuth();
  const hasProcessed = React.useRef(false);

  useEffect(() => {
    if (hasProcessed.current) return;
    hasProcessed.current = true;
    const hash = window.location.hash;
    const m = hash.match(/session_id=([^&]+)/);
    if (!m) {
      navigate("/login");
      return;
    }
    const sessionId = m[1];
    (async () => {
      try {
        const { data } = await api.post("/auth/session", { session_id: sessionId });
        localStorage.setItem("token", data.token);
        setUser(data.user);
        window.history.replaceState({}, "", "/dashboard");
        navigate("/dashboard", { state: { user: data.user } });
      } catch {
        navigate("/login");
      }
    })();
  }, [navigate, setUser]);

  return (
    <div className="min-h-screen pt-16 grid place-items-center">
      <div className="text-slate-500">Connexion en cours...</div>
    </div>
  );
}
