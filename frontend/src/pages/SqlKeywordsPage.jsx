import { useEffect, useState } from "react";
import { api } from "../api/client";

const EMPTY = { name: "", connection: "", keywords: "", sql_text: "", enabled: true };

function rowsOf(data) {
  return data?.results || data || [];
}

export default function SqlKeywordsPage() {
  const [connections, setConnections] = useState([]);
  const [rows, setRows] = useState([]);
  const [form, setForm] = useState(EMPTY);
  const [editing, setEditing] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [preview, setPreview] = useState("");
  const [semantic, setSemantic] = useState(null);

  async function load() {
    const [connectionData, queryData, engine] = await Promise.all([
      api.listConnections(),
      api.listSqlQueries(),
      api.semanticEngine().catch(() => null),
    ]);
    setConnections(rowsOf(connectionData));
    setRows(rowsOf(queryData));
    setSemantic(engine);
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
  }, []);

  const semCfg = semantic?.config || {};

  async function saveSemantic(patch) {
    setError("");
    try {
      const data = await api.saveSemanticEngine(patch);
      setSemantic((prev) => ({ ...prev, config: data }));
      setNotice("Semantic SQL settings saved.");
    } catch (err) {
      setError(err.message);
    }
  }

  function payload() {
    return {
      name: form.name,
      connection: form.connection,
      keywords: form.keywords.split(",").map((item) => item.trim()).filter(Boolean),
      sql_text: form.sql_text,
      enabled: form.enabled,
    };
  }

  async function save(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    setPreview("");
    try {
      await api.saveSqlQuery(payload(), editing);
      setForm({ ...EMPTY, connection: form.connection });
      setEditing(null);
      await load();
      setNotice("Keyword query saved.");
    } catch (err) {
      setError(err.message);
    }
  }

  function edit(row) {
    setEditing(row.id);
    setForm({
      name: row.name,
      connection: row.connection,
      keywords: (row.keywords || []).join(", "),
      sql_text: row.sql_text,
      enabled: row.enabled,
    });
    setPreview("");
  }

  async function remove(row) {
    if (!window.confirm(`Delete ${row.name}?`)) return;
    try {
      await api.deleteSqlQuery(row.id);
      if (editing === row.id) {
        setEditing(null);
        setForm(EMPTY);
      }
      if (semCfg.report_query === row.id) {
        await saveSemantic({ report_query: null });
      }
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function test(id) {
    setError("");
    setNotice("");
    try {
      const result = await api.testSqlQuery(id);
      const lines = (result.rows || []).map((row) => JSON.stringify(row));
      setPreview(lines.length ? lines.join("\n") : "The query returned no rows.");
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <section className="studio">
      <header className="studio-head">
        <div>
          <h1>SQL keywords</h1>
          <p className="muted">
            Connect a database under Databases, save SELECT queries here, then pick one as the semantic report
            query. Chat uses the same connection string—nothing is hardcoded in the app.
          </p>
        </div>
      </header>
      {error && <div className="form-error">{error}</div>}
      {notice && <p className="form-ok">{notice}</p>}

      <div className="studio-card studio-form">
        <h2>Semantic Text-to-SQL</h2>
        <p className="muted span-2">
          Dictionary columns: {semantic?.column_count ?? 0}. Configure synonyms under Knowledge → Semantic
          Text-to-SQL.
        </p>
        <label className="check-row span-2">
          <input
            type="checkbox"
            checked={Boolean(semCfg.enabled)}
            onChange={(event) => saveSemantic({ enabled: event.target.checked })}
          />
          Enable semantic SQL for this workspace (uses database from report query below)
        </label>
        <label className="span-2">
          Report SQL query (canonical SELECT)
          <select
            value={semCfg.report_query || ""}
            onChange={(event) => saveSemantic({ report_query: event.target.value || null })}
          >
            <option value="">Choose a saved query</option>
            {rows.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name} ({item.connection_name})
              </option>
            ))}
          </select>
        </label>
        <label className="check-row">
          <input
            type="checkbox"
            checked={semCfg.fallback_keyword_sql !== false}
            onChange={(event) => saveSemantic({ fallback_keyword_sql: event.target.checked })}
          />
          Fallback to keyword SQL below
        </label>
      </div>

      <form className="studio-card studio-form" onSubmit={save}>
        <label>
          Name
          <input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} required placeholder="Payment status" />
        </label>
        <label>
          Database
          <select value={form.connection} onChange={(event) => setForm({ ...form, connection: event.target.value })} required>
            <option value="">Choose</option>
            {connections.map((item) => (
              <option key={item.id} value={item.id}>{item.name}</option>
            ))}
          </select>
        </label>
        <label className="span-2">
          Keywords, separated by commas
          <input
            value={form.keywords}
            onChange={(event) => setForm({ ...form, keywords: event.target.value })}
            required
            placeholder="Payment, Status, AccountNo"
          />
        </label>
        <label className="span-2">
          SQL query
          <textarea rows={5} value={form.sql_text} onChange={(event) => setForm({ ...form, sql_text: event.target.value })} required />
        </label>
        <label className="check-row">
          <input type="checkbox" checked={form.enabled} onChange={(event) => setForm({ ...form, enabled: event.target.checked })} />
          Enabled
        </label>
        <div className="form-actions">
          <button className="primary" type="submit">{editing ? "Update" : "Save"}</button>
          {editing && <button type="button" className="link" onClick={() => { setEditing(null); setForm(EMPTY); }}>Cancel</button>}
        </div>
      </form>
      {preview && <pre className="studio-card sql-preview">{preview}</pre>}
      <div className="studio-card">
        <table className="data-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Database</th>
              <th>Keywords</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>
                  {row.name}
                  {!row.enabled && <span className="muted"> · off</span>}
                  {semCfg.report_query === row.id && <span className="muted"> · semantic report</span>}
                </td>
                <td>{row.connection_name}</td>
                <td>{(row.keywords || []).join(", ")}</td>
                <td className="row-actions">
                  <button type="button" className="link" onClick={() => test(row.id)}>Run</button>
                  <button type="button" className="link" onClick={() => edit(row)}>Edit</button>
                  <button type="button" className="link danger" onClick={() => remove(row)}>Delete</button>
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr><td colSpan={4} className="muted">No keyword queries yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
