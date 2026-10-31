import { useEffect, useState } from "react";
import { api } from "../api/client";

const TABS = [
  { id: "dictionary", label: "Dictionary" },
  { id: "test", label: "Test & preview" },
];

export default function SemanticSqlPage() {
  const [tab, setTab] = useState("dictionary");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [engine, setEngine] = useState(null);
  const [tables, setTables] = useState([]);
  const [question, setQuestion] = useState("Show applicants from postal code 700053");
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    const [eng, tbl] = await Promise.all([api.semanticEngine(), api.listSemanticTables()]);
    setEngine(eng);
    setTables(tbl.results || tbl || []);
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
  }, []);

  async function bootstrap() {
    if (!window.confirm("Import starter column mappings (synonyms only)? Connection/SQL stay on SQL keywords page.")) return;
    setBusy(true);
    try {
      const result = await api.semanticBootstrap(false);
      setNotice(`Imported ${result.columns} column mappings.`);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function runPreview(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      setPreview(await api.semanticPreview(question));
    } catch (err) {
      if (err.payload && (err.payload.sql || err.payload.error)) {
        setPreview(err.payload);
      } else {
        setError(err.message || `Request failed (${err.status || ""})`);
        setPreview(null);
      }
    } finally {
      setBusy(false);
    }
  }

  const cfg = engine?.config || {};
  const colCount = engine?.column_count || 0;

  return (
    <section className="studio">
      <header className="studio-head">
        <div>
          <h1>Semantic Text-to-SQL Engine</h1>
          <p className="muted">
            Column mappings and synonyms for natural language. Database connection and canonical SELECT are configured
            under <strong>SQL keywords</strong> (same workspace): choose a saved query as the report SQL.
          </p>
        </div>
      </header>
      {error && <div className="form-error">{error}</div>}
      {notice && <p className="form-ok">{notice}</p>}

      <div className="studio-card">
        <p className="muted">
          Report query: {cfg.report_query_name || "— not set (use SQL keywords page)"} · Enabled:{" "}
          {cfg.enabled ? "yes" : "no"} · Dictionary columns: {colCount}
        </p>
      </div>

      <div className="semantic-tabs">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={tab === item.id ? "nav-link active" : "nav-link"}
            onClick={() => setTab(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>

      {tab === "dictionary" && (
        <div className="studio-card">
          <div className="form-actions" style={{ marginBottom: 12 }}>
            <button type="button" className="primary" disabled={busy} onClick={bootstrap}>
              Import starter dictionary (mappings only)
            </button>
          </div>
          <ul className="page-list">
            {tables.map((table) => (
              <li key={table.id}>
                <strong>{table.display_name}</strong> ({table.table_name}) — {table.columns?.length || 0} columns
              </li>
            ))}
            {tables.length === 0 && <li className="muted">No tables yet. Import starter mappings or add via API.</li>}
          </ul>
        </div>
      )}

      {tab === "test" && (
        <form className="studio-card studio-form" onSubmit={runPreview}>
          <label className="span-2">
            Natural-language question
            <textarea rows={3} value={question} onChange={(event) => setQuestion(event.target.value)} />
          </label>
          <div className="form-actions span-2">
            <button type="submit" className="primary" disabled={busy}>
              {busy ? "Running…" : "Preview SQL & run"}
            </button>
          </div>
          {preview && (
            <div className="span-2 semantic-preview">
              {preview.error && <div className="form-error">{preview.error}</div>}
              {preview.run_error && <div className="form-error">{preview.run_error}</div>}
              {preview.run_hint && <p className="muted">{preview.run_hint}</p>}
              <pre>{preview.sql || "(no SQL generated)"}</pre>
              <p className="muted">Params: {JSON.stringify(preview.params || [])}</p>
              <pre>{JSON.stringify(preview.rows || [], null, 2)}</pre>
            </div>
          )}
        </form>
      )}
    </section>
  );
}
