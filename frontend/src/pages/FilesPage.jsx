import { useEffect, useState } from "react";
import { api } from "../api/client";

function rowsOf(data) {
  return data?.results || data || [];
}

function formatSize(size) {
  if (!size) return "0 B";
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${Math.round(size / 1024)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

export default function FilesPage() {
  const [documents, setDocuments] = useState([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    const data = await api.listDocuments();
    setDocuments(rowsOf(data));
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
  }, []);

  async function upload(event) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      await api.uploadDocument(file);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function rename(document) {
    const title = window.prompt("File name", document.title);
    if (!title || title.trim() === document.title) return;
    setError("");
    try {
      await api.renameDocument(document.id, title.trim());
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function remove(document) {
    if (!window.confirm(`Delete ${document.title}?`)) return;
    setError("");
    try {
      await api.deleteDocument(document.id);
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function reindex(document) {
    setError("");
    try {
      await api.reindexDocument(document.id);
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <section className="studio">
      <header className="studio-head">
        <div>
          <h1>Files</h1>
          <p className="muted">Upload the files this chatbot is allowed to answer from. Download, rename, or delete them here.</p>
        </div>
        <label className="primary file-button">
          {busy ? "Uploading…" : "Upload file"}
          <input type="file" hidden disabled={busy} onChange={upload} accept=".pdf,.docx,.xlsx,.csv,.txt,.md,.json,.png,.jpg,.jpeg,.webp" />
        </label>
      </header>
      {error && <div className="form-error">{error}</div>}
      <div className="studio-card">
        <table className="data-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Size</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {documents.map((document) => (
              <tr key={document.id}>
                <td>{document.title}</td>
                <td>{document.file_type || "—"}</td>
                <td>{formatSize(document.size)}</td>
                <td><span className={`status status-${document.status}`}>{document.status}</span></td>
                <td className="row-actions">
                  <button type="button" className="link" onClick={() => api.downloadDocument(document.id, document.title).catch((err) => setError(err.message))}>
                    Download
                  </button>
                  {!document.is_shared && (
                    <>
                      <button type="button" className="link" onClick={() => rename(document)}>Rename</button>
                      <button type="button" className="link" onClick={() => reindex(document)}>Reindex</button>
                      <button type="button" className="link danger" onClick={() => remove(document)}>Delete</button>
                    </>
                  )}
                </td>
              </tr>
            ))}
            {documents.length === 0 && (
              <tr>
                <td colSpan={5} className="muted">No files yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
