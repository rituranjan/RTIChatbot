export default function Sidebar({
  conversations,
  activeId,
  onSelect,
  onNew,
  onDelete,
  onRename,
  onLogout,
}) {
  function promptRename(e, conv) {
    e.stopPropagation();
    const title = prompt("Rename conversation", conv.title || "");
    if (title && title.trim()) onRename(conv.id, title.trim());
  }

  function confirmDelete(e, conv) {
    e.stopPropagation();
    onDelete(conv.id);
  }

  return (
    <aside className="sidebar">
      <button className="primary wide" onClick={onNew}>
        + New chat
      </button>

      <ul className="conv-list">
        {conversations.map((c) => (
          <li
            key={c.id}
            className={c.id === activeId ? "active" : ""}
            onClick={() => onSelect(c.id)}
          >
            <span className="conv-title">{c.title || "Untitled"}</span>
            <span className="conv-actions">
              <button
                className="link"
                title="Rename"
                onClick={(e) => promptRename(e, c)}
              >
                ✎
              </button>
              <button
                className="link danger"
                title="Delete"
                onClick={(e) => confirmDelete(e, c)}
              >
                🗑
              </button>
            </span>
          </li>
        ))}
        {conversations.length === 0 && (
          <li className="muted empty">No conversations yet.</li>
        )}
      </ul>

      <button className="link logout" onClick={onLogout}>
        Sign out
      </button>
    </aside>
  );
}