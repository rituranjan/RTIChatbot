import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import AppNav from "../components/AppNav";
import ChatWindow from "../components/ChatWindow";
import { initialChatLanguage, writeStoredLanguage } from "../chatLanguage";
import EmbedShare from "../components/EmbedShare";
import IntakeForm from "../components/IntakeForm";
import Sidebar from "../components/Sidebar";
import Topbar from "../components/Topbar";
import DatabasesPage from "./DatabasesPage";
import FilesPage from "./FilesPage";
import InsightsPage from "./InsightsPage";
import QuestionsPage from "./QuestionsPage";
import SqlKeywordsPage from "./SqlKeywordsPage";
import AdminSettingsPage from "./AdminSettingsPage";
import ModelPage from "./ModelPage";
import WorkspaceBar from "../components/WorkspaceBar";
import WebsitesPage from "./WebsitesPage";

export default function ChatPage({ user, onLogout, theme, setTheme }) {
  const [conversations, setConversations] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [section, setSection] = useState("chat");
  const [questions, setQuestions] = useState([]);
  const [profile, setProfile] = useState(null);
  const [profileError, setProfileError] = useState("");
  const [acting, setActing] = useState(user?.acting_as || null);
  const [directoryVersion, setDirectoryVersion] = useState(0);
  const [languageConfig, setLanguageConfig] = useState(null);
  const [chatLanguage, setChatLanguage] = useState("");
  const admin = Boolean(user?.is_menu_admin);
  const workspaceKey = acting?.id || "self";

  useEffect(() => {
    if (!admin && ["files", "databases", "sql", "embed", "websites", "settings"].includes(section)) {
      setSection("chat");
    }
  }, [admin, section]);

  const refreshConversations = useCallback(async () => {
    const data = await api.listConversations();
    setConversations(data.results || data);
  }, []);

  useEffect(() => {
    setActiveId(null);
    setMessages([]);
    setProfile(null);
    refreshConversations().catch((err) => setError(err.message));
  }, [refreshConversations, workspaceKey]);

  useEffect(() => {
    let cancelled = false;
    api
      .myPlan()
      .then((data) => {
        if (cancelled) return;
        const lang = data.language;
        setLanguageConfig(lang || null);
        setChatLanguage(initialChatLanguage(lang));
      })
      .catch(() => {
        if (!cancelled) {
          setLanguageConfig(null);
          setChatLanguage("");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [workspaceKey]);

  useEffect(() => {
    if (section !== "chat") return;
    api
      .listIntake()
      .then((data) => setQuestions((data.results || data || []).filter((item) => item.enabled)))
      .catch(() => setQuestions([]));
  }, [section]);

  useEffect(() => {
    if (!activeId) {
      setMessages([]);
      setProfile(null);
      return;
    }
    api
      .getConversation(activeId)
      .then((data) => {
        setMessages(data.messages || []);
        setProfile(data.profile);
      })
      .catch((err) => setError(err.message));
  }, [activeId]);

  async function newConversation() {
    if (questions.length) {
      setActiveId(null);
      setMessages([]);
      setProfile(null);
      setSection("chat");
      return;
    }
    const conv = await api.createConversation("New conversation");
    await refreshConversations();
    setActiveId(conv.id);
  }

  async function saveIntake(answers) {
    setProfileError("");
    try {
      if (!activeId) {
        const title = answers.name || answers.email || "New conversation";
        const conv = await api.createConversation(title, answers);
        setProfile(conv.profile || answers);
        setActiveId(conv.id);
        await refreshConversations();
      } else {
        const saved = await api.saveProfile(activeId, answers);
        setProfile(saved.profile);
      }
    } catch (err) {
      setProfileError(err.message);
    }
  }

  async function deleteConversation(id) {
    if (!confirm("Delete this conversation?")) return;
    await api.deleteConversation(id);
    if (activeId === id) setActiveId(null);
    await refreshConversations();
  }

  async function renameConversation(id, title) {
    await api.renameConversation(id, title);
    await refreshConversations();
  }

  async function send(text, language) {
    if (!text.trim()) return;
    setError("");

    const lang = languageConfig?.enabled ? language || chatLanguage || "" : "";

    let convId = activeId;
    if (!convId) {
      const conv = await api.createConversation(text.slice(0, 60));
      convId = conv.id;
      setActiveId(convId);
      await refreshConversations();
    }

    setMessages((m) => [
      ...m,
      { id: "tmp-" + Date.now(), role: "user", content: text, sources: [] },
    ]);

    setBusy(true);
    try {
      const res = await api.sendMessage(convId, text, lang);
      setMessages((m) => [...m, res.message]);
      await refreshConversations();
    } catch (err) {
      setError(err.message || "Failed to get a response from Ollama.");
    } finally {
      setBusy(false);
    }
  }

  async function logout() {
    try {
      await api.logout();
    } catch {
      /* ignored */
    }
    onLogout();
  }

  function handleChatLanguage(code) {
    setChatLanguage(code);
    writeStoredLanguage(code);
  }

  const needsIntake = section === "chat" && questions.length > 0 && profile == null && messages.length === 0;

  return (
    <div className={section === "chat" ? "app-shell" : "app-shell studio-shell"}>
      {section === "chat" && (
        <Sidebar
          conversations={conversations}
          activeId={activeId}
          onSelect={setActiveId}
          onNew={newConversation}
          onDelete={deleteConversation}
          onRename={renameConversation}
          onLogout={logout}
        />
      )}

      <div className="main-area">
        <Topbar user={user} actingId={acting?.id || ""} theme={theme} setTheme={setTheme} onLogout={logout} />
        <AppNav section={section} onNavigate={setSection} admin={admin} />
        {admin && (
          <WorkspaceBar
            user={user}
            acting={acting}
            version={directoryVersion}
            onChange={setActing}
          />
        )}

        {error && section === "chat" && <div className="error-banner">{error}</div>}

        {section === "settings" && (
          <AdminSettingsPage
            actingId={acting?.id}
            onDirectoryChange={() => setDirectoryVersion((value) => value + 1)}
            onActingChange={setActing}
          />
        )}
        {section !== "settings" && <div className="workspace-stage" key={workspaceKey}>
          {needsIntake && (
            <IntakeForm questions={questions} onSubmit={saveIntake} error={profileError} />
          )}
          {section === "chat" && !needsIntake && (
            <ChatWindow
              messages={messages}
              busy={busy}
              onSend={send}
              languageConfig={languageConfig}
              chatLanguage={chatLanguage}
              onLanguageChange={handleChatLanguage}
            />
          )}
          {section === "websites" && <WebsitesPage />}
          {section === "files" && <FilesPage />}
          {section === "databases" && <DatabasesPage />}
          {section === "sql" && <SqlKeywordsPage />}
          {section === "questions" && <QuestionsPage />}
          {section === "embed" && (
            <section className="studio">
              <EmbedShare inline />
            </section>
          )}
          {section === "visitors" && <InsightsPage mode="visitors" />}
          {section === "chats" && <InsightsPage mode="chats" />}
          {section === "model" && <ModelPage />}
        </div>}
      </div>
    </div>
  );
}