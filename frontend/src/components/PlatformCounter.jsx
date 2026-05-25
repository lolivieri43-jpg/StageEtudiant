import React, { useEffect, useState } from "react";
import api from "../lib/api";
import { Sparkles } from "lucide-react";

export default function PlatformCounter({ variant = "default" }) {
  const [stats, setStats] = useState(null);
  useEffect(() => {
    api.get("/stats/platform").then(r => setStats(r.data)).catch(() => {});
  }, []);
  if (!stats || !stats.show_counter || !stats.displayed_obtained_count) return null;
  const compact = variant === "compact";
  return (
    <div className={compact ? "inline-flex items-center gap-2 text-sm" : "card-soft p-6 text-center"} data-testid="platform-counter">
      <Sparkles className={compact ? "w-4 h-4 text-violet-500" : "w-6 h-6 mx-auto mb-2 text-violet-500"} />
      <span className={compact ? "" : "block"}>
        <span className="font-black text-blue-600 text-lg">{stats.displayed_obtained_count.toLocaleString("fr-FR")}</span>{" "}
        <span className="text-slate-700">{stats.public_message}</span>
      </span>
    </div>
  );
}
