import { useRef, useState } from "react";
import { api } from "../api/client";

export default function DocumentsPanel({ documents, onChange, onClose }) {
  const fileRef = useRef(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function upload(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError("");
    setBusy(true);
    try {
      await api.uploadDocument(file);
      await onChange();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function remove(id) {
    if (!confirm("Delete this document?")) return;
    try {
      await api.deleteDocument(id);
      await onChange();
    } catch (err) {
      setError(err.message);
    }
  }

  async function reindex(id) {
    try {
      await api.reindexDocument(id);
      await onChange();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <aside className="docs-panel">
      <div className="docs-header">
        <h3>Documents</h3>
        <button className="link" onClick={onClose}>
          Close
        </button>
      </div>

      <div className="docs-upload">
        <input
          ref={fileRef}
          type="file"
          onChange={upload}
          accept=".pdf,.docx,.xlsx,.csv,.txt,.md,.json,.png,.jpg,.jpeg,.webp"
        />
        {busy && <p className="muted">Uploading…</p>}
        {error && <div className="form-error">{error}</div>}
      </div>

      <ul className="docs-list">
        {documents.map((d) => (
          <li key={d.id}>
            <div className="doc-title">{d.title}</div>
            <div className="doc-meta">
              <span className={`status status-${d.status}`}>{d.status}</span>
              {d.is_shared && <span className="badge">shared</span>}
            </div>
            <div className="doc-actions">
              {!d.is_shared && (
                <button className="link" onClick={() => reindex(d.id)}>
                  Reindex
                </button>
              )}
              {!d.is_shared && (
                <button
                  className="link danger"
                  onClick={() => remove(d.id)}
                >
                  Delete
                </button>
              )}
            </div>
            {d.error && <div className="doc-error">{d.error}</div>}
          </li>
        ))}
        {documents.length === 0 && (
          <li className="muted">No documents yet.</li>
        )}
      </ul>
    </aside>
  );
}