import { Fragment, useEffect, useState } from "react";
import { api } from "../api/client";

const EMPTY = { name: "", url: "", max_pages: 300, enabled: true };

function rowsOf(data) {
  return data?.results || data || [];
}

export default function WebsitesPage() {
  const [rows, setRows] = useState([]);
  const [form, setForm] = useState(EMPTY);
  const [editing, setEditing] = useState(null);
  const [openId, setOpenId] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    setRows(rowsOf(await api.listWebsites()));
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
  }, []);

  const crawling = rows.some((row) => row.status === "crawling" || row.status === "pending");
  useEffect(() => {
    if (!crawling) return undefined;
    const timer = setInterval(() => {
      load().catch(() => {});
    }, 3000);
    return () => clearInterval(timer);
  }, [crawling]);

  function edit(row) {
    setEditing(row.id);
    setForm({
      name: row.name,
      url: row.url,
      max_pages: row.max_pages,
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
      await api.saveWebsite(
        {
          name: form.name,
          url: form.url,
          max_pages: Number(form.max_pages) || 300,
          enabled: form.enabled,
        },
        editing
      );
      setForm(EMPTY);
      setEditing(null);
      await load();
      setNotice(editing ? "Website saved." : "Reading the website. This page updates as pages are stored.");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function reread(row) {
    setError("");
    setNotice("");
    try {
      await api.recrawlWebsite(row.id);
      await load();
      setNotice(`Reading ${row.url} again.`);
    } catch (err) {
      setError(err.message);
    }
  }

  async function remove(row) {
    if (!window.confirm(`Delete ${row.name}? Its pages are removed from this account's vector database.`)) return;
    setError("");
    try {
      await api.deleteWebsite(row.id);
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
          <h1>Website RAG</h1>
          <p className="muted">
            Add a public website, for example https://rtiguru.com/. The crawl reads its pages
            and stores them in this account's vector database. Chat answers from those pages.
          </p>
        </div>
      </header>
      {error && <div className="form-error">{error}</div>}
      {notice && <p className="form-ok">{notice}</p>}
      <form className="studio-card studio-form" onSubmit={save}>
        <label>
          Name
          <input
            value={form.name}
            placeholder="RTI Guru"
            onChange={(event) => setForm({ ...form, name: event.target.value })}
          />
        </label>
        <label>
          Website
          <input
            type="url"
            required
            value={form.url}
            placeholder="https://rtiguru.com/"
            onChange={(event) => setForm({ ...form, url: event.target.value })}
          />
        </label>
        <label>
          Page limit
          <input
            type="number"
            min="1"
            max="400"
            value={form.max_pages}
            onChange={(event) => setForm({ ...form, max_pages: event.target.value })}
          />
        </label>
        <label className="check-row">
          <input
            type="checkbox"
            checked={form.enabled}
            onChange={(event) => setForm({ ...form, enabled: event.target.checked })}
          />
          Enabled for chat
        </label>
        <div className="form-actions">
          <button className="primary" type="submit" disabled={busy}>
            {busy ? "Saving…" : editing ? "Update" : "Add website"}
          </button>
          {editing && (
            <button
              type="button"
              className="link"
              onClick={() => {
                setEditing(null);
                setForm(EMPTY);
              }}
            >
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
              <th>Website</th>
              <th>Pages</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <Fragment key={row.id}>
                <tr>
                  <td>
                    {row.name}
                    {!row.enabled && <div className="muted">Off</div>}
                  </td>
                  <td><a href={row.url} target="_blank" rel="noreferrer">{row.url}</a></td>
                  <td>{row.page_count}</td>
                  <td>
                    <span className={`status status-${row.status}`}>{row.status}</span>
                    {row.message && <div className="muted">{row.message}</div>}
                    {row.error && <div className="form-error">{row.error}</div>}
                  </td>
                  <td className="row-actions">
                    <button type="button" className="link" onClick={() => setOpenId(openId === row.id ? null : row.id)}>
                      Pages
                    </button>
                    <button type="button" className="link" onClick={() => reread(row)}>Read again</button>
                    <button type="button" className="link" onClick={() => edit(row)}>Edit</button>
                    <button type="button" className="link danger" onClick={() => remove(row)}>Delete</button>
                  </td>
                </tr>
                {openId === row.id && (
                  <tr>
                    <td colSpan={5}>
                      {row.pages?.length ? (
                        <ul className="page-list">
                          {row.pages.map((page) => (
                            <li key={page.id}>
                              <a href={page.url} target="_blank" rel="noreferrer">{page.title || page.url}</a>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <span className="muted">No pages stored yet.</span>
                      )}
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={5} className="muted">No website added yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
