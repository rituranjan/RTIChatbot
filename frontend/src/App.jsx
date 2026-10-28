import { useEffect, useState } from "react";
import { api } from "./api/client";
import EmbedWidget from "./pages/EmbedWidget";
import AuthPage from "./pages/AuthPage";
import ChatPage from "./pages/ChatPage";

function embedRoute() {
  const path = window.location.pathname.replace(/\/+$/, "") || "/";
  if (path !== "/embed") return null;
  const params = new URLSearchParams(window.location.search);
  return {
    botId: params.get("bot") || "",
    mode: params.get("mode") || "launcher",
  };
}

export default function App() {
  const [embed] = useState(embedRoute);
  const [user, setUser] = useState(undefined);
  const [theme, setTheme] = useState(
    () => localStorage.getItem("theme") || "dark"
  );

  useEffect(() => {
    if (embed) return;
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("theme", theme);
  }, [theme, embed]);

  useEffect(() => {
    if (embed) return;
    api
      .me()
      .then((u) => setUser(u))
      .catch(() => setUser(null));
  }, [embed]);

  if (embed) {
    return <EmbedWidget botId={embed.botId} mode={embed.mode} />;
  }

  if (user === undefined) {
    return <div className="app-loading">Loading…</div>;
  }

  if (!user) {
    return <AuthPage onLogin={(u) => setUser(u)} />;
  }

  return (
    <ChatPage
      user={user}
      onLogout={() => setUser(null)}
      theme={theme}
      setTheme={setTheme}
    />
  );
}