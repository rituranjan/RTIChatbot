import { useEffect, useState } from "react";
import { api } from "../api/client";

const ENGINES = [
  ["sqlite", "SQLite"],
  ["mysql", "MySQL"],
  ["mssql", "SQL Server"],
  ["postgresql", "PostgreSQL"],
];

const EXAMPLES = {
  sqlite: "C:\\folder\\database.sqlite3",
  mysql: "mysql://user:password@host.docker.internal:3306/sales",
  mssql: "Server=host.docker.internal,1433;Database=sales;User Id=sa;Password=secret;",
  postgresql: "postgresql://user:password@host.docker.internal:5432/sales",
};

const EMPTY = { name: "", engine: "mysql", connection_string: "", enabled: true };

function rowsOf(data) {
  return data?.results || data || [];
}

export default function DatabasesPage() {
  const [rows, setRows] = useState([]);
  const [form, setForm] = useState(EMPTY);
  const [editing, setEditing] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    setRows(rowsOf(await api.listConnections()));
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
  }, []);

  function edit(row) {
    setEditing(row.id);
    setForm({
      name: row.name,
      engine: row.engine,
      connection_string: row.connection_string,
      enabled: row.enabled,
    });
    setNotice("");
    setError("");
  }

  async function save(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api.saveConnection(form, editing);
      setForm(EMPTY);
      setEditing(null);
      await load();
      setNotice("Database saved.");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function test(payload) {
    setError("");
    setNotice("");
    try {
      const result = await api.testConnection(payload);
      setNotice(result.detail || "Connected.");
    } catch (err) {
      setError(err.message);
    }
  }

  async function remove(row) {
    if (!window.confirm(`Remove ${row.name}? Keyword queries that use it are removed too.`)) return;
    setError("");
    try {
      await api.deleteConnection(row.id);
      if (editing === row.id) {
        setEditing(null);
        setForm(EMPTY);
      }
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <section className="studio">
      <header className="studio-head">
        <div>
          <h1>Databases</h1>
          <p className="muted">
            Connect SQLite, MySQL, SQL Server, or PostgreSQL with a connection string.
            A saved connection is used on the next chat message.
          </p>
        </div>
      </header>
      {error && <div className="form-error">{error}</div>}
      {notice && <p className="form-ok">{notice}</p>}
      <form className="studio-card studio-form" onSubmit={save}>
        <label>
          Name
          <input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} required />
        </label>
        <label>
          Engine
          <select value={form.engine} onChange={(event) => setForm({ ...form, engine: event.target.value })}>
            {ENGINES.map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </label>
        <label className="span-2">
          Connection string
          <textarea
            rows={3}
            value={form.connection_string}
            placeholder={EXAMPLES[form.engine]}
            onChange={(event) => setForm({ ...form, connection_string: event.target.value })}
            required
          />
        </label>
        <label className="check-row">
          <input
            type="checkbox"
            checked={form.enabled}
            onChange={(event) => setForm({ ...form, enabled: event.target.checked })}
          />
          Enabled
        </label>
        <div className="form-actions">
          <button className="primary" type="submit" disabled={busy}>{editing ? "Update" : "Save"}</button>
          <button type="button" className="link" onClick={() => test({ engine: form.engine, connection_string: form.connection_string })}>
            Test connection
          </button>
          {editing && (
            <button type="button" className="link" onClick={() => { setEditing(null); setForm(EMPTY); }}>
              Cancel
            </button>
          )}
        </div>
      </form>
      <div className="studio-card">
        <table className="data-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Engine</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>{row.name}</td>
                <td>{ENGINES.find(([value]) => value === row.engine)?.[1] || row.engine}</td>
                <td>{row.enabled ? "Enabled" : "Off"}</td>
                <td className="row-actions">
                  <button type="button" className="link" onClick={() => test({ engine: row.engine, connection_string: row.connection_string })}>Test</button>
                  <button type="button" className="link" onClick={() => edit(row)}>Edit</button>
                  <button type="button" className="link danger" onClick={() => remove(row)}>Delete</button>
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr><td colSpan={4} className="muted">No database connected yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
