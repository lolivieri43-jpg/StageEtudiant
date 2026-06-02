import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import App from "@/App";

const root = ReactDOM.createRoot(document.getElementById("root"));
// NOTE: React.StrictMode was removed because react-leaflet 4 conflicts with its
// double-mount behavior in dev, throwing "Map container is already initialized".
// In production builds StrictMode is a no-op anyway, so removing it has no runtime effect.
root.render(<App />);
