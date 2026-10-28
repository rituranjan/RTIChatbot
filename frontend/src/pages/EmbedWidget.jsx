import { useEffect, useRef, useState } from "react";
import IntakeForm from "../components/IntakeForm";

let memoryVisitor = "";

function visitorId() {
  const key = "chatbot-visitor";
  try {
    let id = localStorage.getItem(key);
    if (!id) {
      id = newId();
      localStorage.setItem(key, id);
    }
    return id;
  } catch (err) {
    if (!memoryVisitor) memoryVisitor = newId();
    return memoryVisitor;
  }
}

function newId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID().replace(/-/g, "");
  }
  const bytes = new Uint8Array(16);
  if (typeof crypto !== "undefined" && typeof crypto.getRandomValues === "function") {
    crypto.getRandomValues(bytes);
  } else {
    for (let index = 0; index < bytes.length; index += 1) {
      bytes[index] = Math.floor(Math.random() * 256);
    }
  }
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  return Array.from(bytes, (value) => value.toString(16).padStart(2, "0")).join("");
}

function notifyParent(open) {
  if (window.parent === window) return;
  window.parent.postMessage({ source: "chatbot-widget", open }, "*");
}

export default function EmbedWidget({ botId, mode }) {
  const panelMode = mode === "panel";
  const inFrame = window.self !== window.top;
  const [open, setOpen] = useState(panelMode);
  const [bot, setBot] = useState(null);
  const [error, setError] = useState("");
  const [messages, setMessages] = useState([]);
  const [questions, setQuestions] = useState([]);
  const [profile, setProfile] = useState(null);
  const [profileError, setProfileError] = useState("");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    document.documentElement.classList.add("embed-root");
    if (!inFrame || panelMode) document.documentElement.classList.add("embed-page");
    return () => {
      document.documentElement.classList.remove("embed-root", "embed-page");
    };
  }, [inFrame, panelMode]);

  useEffect(() => {
    notifyParent(open);
  }, [open]);

  useEffect(() => {
    if (!botId) {
      setError("Missing chatbot id. Use /embed?bot=YOUR_ID");
      return;
    }
    const visitor = visitorId();
    fetch(`/api/embed/${botId}/?visitor_id=${encodeURIComponent(visitor)}`)
      .then(async (res) => {
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || "Chatbot not found.");
        setBot(data);
        setMessages(data.messages || []);
        setQuestions(data.questions || []);
        setProfile(data.profile);
      })
      .catch((err) => setError(err.message));
  }, [botId]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy, open]);

  async function send(value) {
    const message = (value ?? text).trim();
    if (!message || busy || !bot) return;
    setText("");
    setMessages((current) => [
      ...current,
      { id: "tmp-" + Date.now(), role: "user", content: message },
    ]);
    setBusy(true);
    setError("");
    try {
      const res = await fetch(`/api/embed/${botId}/chat/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ visitor_id: visitorId(), message }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "The assistant could not reply.");
      setMessages((current) => [...current, data.message]);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
      inputRef.current?.focus();
    }
  }

  async function saveIntake(answers) {
    setProfileError("");
    try {
      const res = await fetch(`/api/embed/${botId}/profile/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ visitor_id: visitorId(), answers }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "Could not save your details.");
      setProfile(data.profile || answers);
    } catch (err) {
      setProfileError(err.message);
    }
  }

  function toggle(next) {
    setOpen(next);
    if (next) setTimeout(() => inputRef.current?.focus(), 50);
  }

  const accent = bot?.accent || "#2563eb";
  const needsIntake = questions.length > 0 && profile == null;
  const showChips = messages.length === 0 && !busy && !needsIntake;

  return (
    <div className={`widget-shell ${panelMode ? "panel-mode" : ""} ${inFrame ? "in-frame" : ""}`}>
      {!inFrame && !panelMode && (
        <div className="widget-demo">
          <h1>Website preview</h1>
          <p>The button sits on top of any page. Click it to open the chat.</p>
        </div>
      )}

      {(open || panelMode) && (
        <section className="widget-panel" style={{ "--accent": accent }}>
          <header className="widget-head">
            <div className="widget-logo" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="22" height="22">
                <path
                  fill="currentColor"
                  d="M19 11h-6V5h-2v6H5v2h6v6h2v-6h6z"
                />
              </svg>
            </div>
            <div className="widget-id">
              <strong>{bot?.name || "Assistant"}</strong>
              <span>
                <i className="widget-online" /> Online
              </span>
            </div>
            {!panelMode && (
              <button className="widget-close" onClick={() => toggle(false)} aria-label="Close chat">
                ×
              </button>
            )}
          </header>

          <div className="widget-body">
            {error && <div className="widget-error">{error}</div>}
            <article className="widget-row bot">
              <div className="widget-avatar" aria-hidden="true">
                <svg viewBox="0 0 24 24" width="16" height="16">
                  <path fill="currentColor" d="M19 11h-6V5h-2v6H5v2h6v6h2v-6h6z" />
                </svg>
              </div>
              <div className="widget-bubble">
                <p>{bot?.greeting || "Hello! How can I help you today?"}</p>
                {showChips && bot?.quick_replies?.length > 0 && (
                  <div className="widget-chips">
                    {bot.quick_replies.map((reply) => (
                      <button key={reply} onClick={() => send(reply)}>
                        <span aria-hidden="true">★</span> {reply}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </article>
            {needsIntake && (
              <IntakeForm questions={questions} onSubmit={saveIntake} error={profileError} />
            )}

            {messages.map((message) => (
              <article key={message.id} className={`widget-row ${message.role === "user" ? "user" : "bot"}`}>
                {message.role !== "user" && (
                  <div className="widget-avatar" aria-hidden="true">
                    <svg viewBox="0 0 24 24" width="16" height="16">
                      <path fill="currentColor" d="M19 11h-6V5h-2v6H5v2h6v6h2v-6h6z" />
                    </svg>
                  </div>
                )}
                <div className="widget-bubble">
                  {message.role === "user" && <span className="widget-who">You</span>}
                  <p>{message.content}</p>
                </div>
              </article>
            ))}

            {busy && (
              <article className="widget-row bot">
                <div className="widget-avatar" aria-hidden="true" />
                <div className="widget-bubble typing">
                  <span />
                  <span />
                  <span />
                </div>
              </article>
            )}
            <div ref={endRef} />
          </div>

          <form
            className="widget-compose"
            onSubmit={(event) => {
              event.preventDefault();
              send();
            }}
          >
            <input
              ref={inputRef}
              value={text}
              onChange={(event) => setText(event.target.value)}
              placeholder="Type a message…"
              disabled={busy || !bot || needsIntake}
              style={{ "color": "black" }}
            />
            <button type="submit" disabled={busy || !text.trim()} aria-label="Send">
              <svg viewBox="0 0 24 24" width="18" height="18">
                <path fill="currentColor" d="M3 11.5 21 3l-7.5 18-2.2-7.3L3 11.5z" />
              </svg>
            </button>
          </form>
        </section>
      )}

      {!panelMode && (
        <button
          className={`widget-launcher ${open ? "open" : ""}`}
          style={{ background: accent }}
          onClick={() => toggle(!open)}
          aria-label={open ? "Close chat" : "Open chat"}
        >
          {open ? (
            <svg viewBox="0 0 24 24" width="26" height="26">
              <path fill="#fff" d="M6 6l12 12M18 6 6 18" stroke="#fff" strokeWidth="2" />
            </svg>
          ) : (
            <svg viewBox="0 0 24 24" width="28" height="28">
              <path
                fill="#fff"
                d="M4 5.5A2.5 2.5 0 0 1 6.5 3h11A2.5 2.5 0 0 1 20 5.5v8A2.5 2.5 0 0 1 17.5 16H9l-4.2 3.2c-.6.4-1.3 0-1.3-.7V5.5z"
              />
            </svg>
          )}
        </button>
      )}
    </div>
  );
}
