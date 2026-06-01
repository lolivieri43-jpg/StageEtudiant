import { useEffect, useRef, useState, useCallback } from "react";

import { BACKEND_ORIGIN } from "../lib/api";
const WS_URL = BACKEND_ORIGIN.replace(/^http/, "ws") + "/api/ws";

export default function useChatSocket({ enabled, onMessage, onTyping, onPresence }) {
  const wsRef = useRef(null);
  const [connected, setConnected] = useState(false);
  const reconnectTimer = useRef(null);

  const connect = useCallback(() => {
    const token = localStorage.getItem("token");
    if (!token || !enabled) return;
    const ws = new WebSocket(`${WS_URL}?token=${encodeURIComponent(token)}`);
    wsRef.current = ws;
    ws.onopen = () => setConnected(true);
    ws.onclose = () => {
      setConnected(false);
      if (enabled) {
        reconnectTimer.current = setTimeout(connect, 3000);
      }
    };
    ws.onerror = () => { try { ws.close(); } catch {} };
    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.type === "message" && onMessage) onMessage(data.message);
        else if (data.type === "typing" && onTyping) onTyping(data);
        else if (data.type === "presence" && onPresence) onPresence(data);
      } catch {}
    };
  }, [enabled, onMessage, onTyping, onPresence]);

  useEffect(() => {
    if (enabled) connect();
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (wsRef.current) {
        try { wsRef.current.close(); } catch {}
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled]);

  const send = useCallback((payload) => {
    if (wsRef.current?.readyState === 1) {
      wsRef.current.send(JSON.stringify(payload));
    }
  }, []);

  return { connected, send };
}
