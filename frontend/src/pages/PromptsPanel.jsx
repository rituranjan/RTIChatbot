import { useEffect, useState } from "react";
import { api } from "../api/client";

export default function PromptsPanel() {
  const [rows, setRows] = useState([]);
  const [slug, setSlug] = useState("");
  const [content, setContent] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api
      .listPrompts()
      .then((data) => {
        const list = data.prompts || [];
        setRows(list);
        if (list.length && !slug) {
          setSlug(list[0].slug);
          setContent(list[0].content || "");
        }
      })
      .catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    const row = rows.find((item) => item.slug === slug);
    if (row) setContent(row.content || "");
  }, [slug, rows]);

  async function save() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const data = await api.savePrompt(slug, { content, note: "Admin edit" });
      setRows(data.prompts || []);
      setNotice("Saved as a new version.");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const active = rows.find((item) => item.slug === slug);

  return (
    <div className="issue-panel">
      <div className="studio-card">
        <h2>LLM prompts</h2>
        <p className="muted">
          Chat and RAG instructions are stored in the admin database. Use {"{{variable}}"} placeholders only.
        </p>
        {error && <div className="form-error">{error}</div>}
        {notice && <p className="form-ok">{notice}</p>}
        <label className="field">
          Prompt
          <select value={slug} onChange={(event) => setSlug(event.target.value)}>
            {rows.map((row) => (
              <option key={row.slug} value={row.slug}>
                {row.name} ({row.slug})
              </option>
            ))}
          </select>
        </label>
        {active && (
          <p className="muted">
            Version {active.active_version}
            {active.variables?.length ? ` · variables: ${active.variables.join(", ")}` : ""}
          </p>
        )}
        <label className="field">
          Content
          <textarea rows={12} value={content} onChange={(event) => setContent(event.target.value)} />
        </label>
        <div className="form-actions">
          <button type="button" disabled={busy || !slug} onClick={save}>
            {busy ? "Saving…" : "Save new version"}
          </button>
        </div>
      </div>
    </div>
  );
}
