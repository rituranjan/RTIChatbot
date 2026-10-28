import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export default function MessageBubble({ message }) {
  const isUser = message.role === "user";

  return (
    <div className={`msg ${isUser ? "user" : "assistant"}`}>
      <div className="avatar">{isUser ? "You" : "AI"}</div>
      <div className="bubble">
        {isUser ? (
          <p style={{ whiteSpace: "pre-wrap", margin: 0 }}>{message.content}</p>
        ) : (
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {message.content || ""}
          </ReactMarkdown>
        )}

        {message.sources && message.sources.length > 0 && (
          <div className="sources">
            <div className="sources-title">Sources</div>
            <ul>
              {message.sources.map((s, i) => (
                <li key={i}>
                  <span className="source-doc">{s.document_title}</span>
                  <span className="source-chunk">#{s.chunk_index}</span>
                  {s.score != null && (
                    <span className="source-score">score {s.score}</span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}