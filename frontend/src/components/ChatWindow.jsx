import { useEffect, useRef } from "react";
import Composer from "./Composer";
import MessageBubble from "./MessageBubble";

export default function ChatWindow({
  messages,
  busy,
  onSend,
  languageConfig,
  chatLanguage,
  onLanguageChange,
}) {
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  return (
    <div className="chat-window">
      <div className="messages">
        {messages.length === 0 && !busy && (
          <div className="empty-state">
            <h2>Ask anything</h2>
            <p>
              Your messages never leave this machine. Documents are embedded
              locally with Ollama.
            </p>
          </div>
        )}

        {messages.map((m) => (
          <MessageBubble key={m.id} message={m} />
        ))}

        {busy && (
          <div className="msg assistant">
            <div className="avatar">AI</div>
            <div className="bubble typing">…thinking</div>
          </div>
        )}

        <div ref={endRef} />
      </div>

      <Composer
        onSend={onSend}
        disabled={busy}
        languageConfig={languageConfig}
        chatLanguage={chatLanguage}
        onLanguageChange={onLanguageChange}
      />
    </div>
  );
}