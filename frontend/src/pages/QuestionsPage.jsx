import { useEffect, useState } from "react";
import { api } from "../api/client";

const EMPTY = { label: "", placeholder: "", required: true, enabled: true };

function rowsOf(data) {
  return data?.results || data || [];
}

export default function QuestionsPage() {
  const [rows, setRows] = useState([]);
  const [form, setForm] = useState(EMPTY);
  const [editing, setEditing] = useState(null);
  const [error, setError] = useState("");

  async function load() {
    setRows(rowsOf(await api.listIntake()));
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
  }, []);

  async function save(event) {
    event.preventDefault();
    setError("");
    try {
      await api.saveIntake(
        {
          label: form.label,
          placeholder: form.placeholder,
          required: form.required,
          enabled: form.enabled,
          position: editing ? undefined : rows.length,
        },
        editing
      );
      setForm(EMPTY);
      setEditing(null);
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function addDefaults() {
    setError("");
    const existing = new Set(rows.map((row) => row.field_key));
    const defaults = [
      ["Name", "name", "Your name"],
      ["Email", "email", "you@example.com"],
      ["Phone", "phone", "Phone number"],
    ];
    try {
      for (const [label, field_key, placeholder] of defaults) {
        if (existing.has(field_key)) continue;
        await api.saveIntake({ label, field_key, placeholder, required: true, enabled: true, position: rows.length });
      }
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function remove(row) {
    if (!window.confirm(`Remove ${row.label}?`)) return;
    try {
      await api.deleteIntake(row.id);
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <section className="studio">
      <header className="studio-head">
        <div>
          <h1>Questions before chat</h1>
          <p className="muted">The chatbot asks these before a conversation starts. Answers are stored with that chat.</p>
        </div>
        <button type="button" className="link" onClick={addDefaults}>Add name, email, and phone</button>
      </header>
      {error && <div className="form-error">{error}</div>}
      <form className="studio-card studio-form" onSubmit={save}>
        <label>
          Question
          <input value={form.label} onChange={(event) => setForm({ ...form, label: event.target.value })} required placeholder="Email" />
        </label>
        <label>
          Placeholder
          <input value={form.placeholder} onChange={(event) => setForm({ ...form, placeholder: event.target.value })} placeholder="you@example.com" />
        </label>
        <label className="check-row">
          <input type="checkbox" checked={form.required} onChange={(event) => setForm({ ...form, required: event.target.checked })} />
          Required
        </label>
        <label className="check-row">
          <input type="checkbox" checked={form.enabled} onChange={(event) => setForm({ ...form, enabled: event.target.checked })} />
          Enabled
        </label>
        <div className="form-actions">
          <button className="primary" type="submit">{editing ? "Update" : "Add question"}</button>
        </div>
      </form>
      <div className="studio-card">
        <table className="data-table">
          <thead>
            <tr>
              <th>Question</th>
              <th>Key</th>
              <th>Required</th>
              <th>Enabled</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>{row.label}</td>
                <td>{row.field_key}</td>
                <td>{row.required ? "Yes" : "No"}</td>
                <td>{row.enabled ? "Yes" : "No"}</td>
                <td className="row-actions">
                  <button
                    type="button"
                    className="link"
                    onClick={() => {
                      setEditing(row.id);
                      setForm({
                        label: row.label,
                        placeholder: row.placeholder || "",
                        required: row.required,
                        enabled: row.enabled,
                      });
                    }}
                  >
                    Edit
                  </button>
                  <button type="button" className="link danger" onClick={() => remove(row)}>Delete</button>
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr><td colSpan={5} className="muted">No questions yet. Visitors can chat immediately until you add some.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
