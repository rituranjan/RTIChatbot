import { useEffect, useState } from "react";
import { api } from "../api/client";

export default function Topbar({ user, theme, setTheme, onLogout }) {
  const [status, setStatus] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const s = await api.ollamaStatus();
        if (!cancelled) setStatus(s);
      } catch {
        if (!cancelled) setStatus({ available: false });
      }
    }

    load();
    const t = setInterval(load, 15000);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, []);

  const provider =
    status?.provider === "openai" || status?.provider === "chatgpt"
      ? "ChatGPT"
      : status?.provider === "azure"
      ? "Azure"
      : status?.provider === "ollama"
      ? "Ollama"
      : status?.provider || "model";
  const label = !status
    ? "Checking model…"
    : status.available
    ? `${provider} · ${status.chat_model}`
    : `${provider} offline`;

  return (
    <header className="topbar">
      <div className="brand">
        <strong>Local AI Chatbot</strong>
        <span className={`dot ${status?.available ? "ok" : "bad"}`} />
        <span className="muted">{label}</span>
      </div>

      <div className="topbar-actions">
        <button
          className="link"
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
        >
          {theme === "dark" ? "Light" : "Dark"} theme
        </button>
        <span className="muted">{user.username}</span>
        <button className="link" onClick={onLogout}>
          Log out
        </button>
      </div>
    </header>
  );
}