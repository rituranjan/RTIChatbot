import { useEffect, useState } from "react";
import { api } from "../api/client";

export default function EmbedShare({ onClose, inline = false }) {
  const [bot, setBot] = useState(null);
  const [name, setName] = useState("");
  const [greeting, setGreeting] = useState("");
  const [replies, setReplies] = useState("");
  const [copied, setCopied] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .myEmbed()
      .then((data) => {
        setBot(data);
        setName(data.name || "");
        setGreeting(data.greeting || "");
        setReplies((data.quick_replies || []).join("\n"));
      })
      .catch((err) => setError(err.message));
  }, []);

  const origin = window.location.origin;
  const panelUrl = bot ? `${origin}/embed?bot=${bot.id}&mode=panel` : "";
  const launcherUrl = bot ? `${origin}/embed?bot=${bot.id}` : "";
  const iframe = bot
    ? `<iframe src="${panelUrl}" title="${name || "Chat"}" style="width:380px;height:640px;border:0;border-radius:18px;"></iframe>`
    : "";
  const script = bot
    ? `<script src="${origin}/widget.js" data-bot="${bot.id}"></script>`
    : "";

  async function copy(label, value) {
    await navigator.clipboard.writeText(value);
    setCopied(label);
  }

  async function save(event) {
    event.preventDefault();
    setError("");
    try {
      const saved = await api.saveEmbed({
        name,
        greeting,
        quick_replies: replies
          .split("\n")
          .map((line) => line.trim())
          .filter(Boolean),
      });
      setBot(saved);
      setCopied("Saved");
    } catch (err) {
      setError(err.message);
    }
  }

  const card = (
      <div className={inline ? "studio-card share-inline" : "share-modal"} onClick={(event) => event.stopPropagation()}>
        <div className="share-head">
          <h2>Add this chat to a website</h2>
          {!inline && (
            <button className="link" onClick={onClose}>
              Close
            </button>
          )}
        </div>
        <p className="muted">
          Put the script on any page. A button appears in the corner and opens this chatbot.
          Or paste the iframe where you want the chat box itself.
        </p>
        {error && <div className="form-error">{error}</div>}

        <form onSubmit={save} className="share-form">
          <label>
            Chatbot name
            <input value={name} onChange={(event) => setName(event.target.value)} />
          </label>
          <label>
            Greeting
            <textarea rows={2} value={greeting} onChange={(event) => setGreeting(event.target.value)} />
          </label>
          <label>
            Quick replies, one per line
            <textarea rows={3} value={replies} onChange={(event) => setReplies(event.target.value)} />
          </label>
          <button className="primary" type="submit">
            Save chatbot
          </button>
        </form>

        <label className="share-code">
          Button for any website
          <textarea readOnly rows={2} value={script} />
          <button type="button" className="link" onClick={() => copy("Script copied", script)}>
            Copy script
          </button>
        </label>
        <label className="share-code">
          Iframe
          <textarea readOnly rows={3} value={iframe} />
          <button type="button" className="link" onClick={() => copy("Iframe copied", iframe)}>
            Copy iframe
          </button>
        </label>
        {bot && (
          <p className="muted">
            Chatbot id <code>{bot.id}</code>
            {" · "}
            <a href={launcherUrl} target="_blank" rel="noreferrer">
              Open preview
            </a>
          </p>
        )}
        {copied && <p className="share-copied">{copied}</p>}
      </div>
  );

  if (inline) return card;
  return (
    <div className="share-backdrop" onClick={onClose}>
      {card}
    </div>
  );
}
