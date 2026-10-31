import { Fragment, useEffect, useState } from "react";
import { api } from "../api/client";

const EMPTY = { name: "", url: "", max_pages: 300, enabled: true };
const CRAWL_PAGE_MAX = 400;

function rowsOf(data) {
  return data?.results || data || [];
}

function pageLimitLabel(cap, used) {
  if (!cap || cap <= 0) {
    return `${used} page${used === 1 ? "" : "s"} indexed (unlimited plan)`;
  }
  return `${used} / ${cap} RAG page${cap === 1 ? "" : "s"} on your plan`;
}

export default function WebsitesPage() {
  const [rows, setRows] = useState([]);
  const [ragPages, setRagPages] = useState([]);
  const [paste, setPaste] = useState("");
  const [form, setForm] = useState(EMPTY);
  const [editing, setEditing] = useState(null);
  const [openId, setOpenId] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [pasteBusy, setPasteBusy] = useState(false);
  const [pageLimit, setPageLimit] = useState(0);

  async function loadWebsites() {
    setRows(rowsOf(await api.listWebsites()));
  }

  async function loadRagPages() {
    setRagPages(rowsOf(await api.listWebRagPages()));
  }

  async function loadAll() {
    await Promise.all([loadWebsites(), loadRagPages()]);
  }

  useEffect(() => {
    api
      .myPlan()
      .then((data) => {
        const cap = Number(data?.limits?.website_max_pages);
        setPageLimit(Number.isFinite(cap) ? Math.max(0, cap) : 0);
      })
      .catch(() => {});
    loadAll().catch((err) => setError(err.message));
  }, []);

  const indexing =
    rows.some((row) => row.status === "crawling" || row.status === "pending") ||
    ragPages.some((row) => row.status === "crawling" || row.status === "pending");

  useEffect(() => {
    if (!indexing) return undefined;
    const timer = setInterval(() => {
      loadAll().catch(() => {});
    }, 3000);
    return () => clearInterval(timer);
  }, [indexing]);

  const atPageLimit = pageLimit > 0 && ragPages.length >= pageLimit;

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

  async function saveWebsite(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api.saveWebsite(
        {
          name: form.name,
          url: form.url,
          max_pages: Math.min(Number(form.max_pages) || 300, CRAWL_PAGE_MAX),
          enabled: form.enabled,
        },
        editing
      );
      setForm(EMPTY);
      setEditing(null);
      await loadWebsites();
      setNotice(editing ? "Website saved." : "Reading the website. This page updates as pages are stored.");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function addPastedPages(event) {
    event.preventDefault();
    if (!paste.trim()) {
      setError("Paste one or more page addresses.");
      return;
    }
    setPasteBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await api.bulkWebRagPages(paste);
      setPaste("");
      await loadRagPages();
      const created = result?.created?.length || 0;
      const dup = result?.duplicates?.length || 0;
      const over = result?.over_limit?.length || 0;
      const parts = [];
      if (created) parts.push(`${created} page${created === 1 ? "" : "s"} queued for indexing (high priority).`);
      if (dup) parts.push(`${dup} duplicate${dup === 1 ? "" : "s"} skipped.`);
      if (over) parts.push(`${over} over plan limit skipped.`);
      setNotice(parts.join(" ") || "Nothing new to add.");
    } catch (err) {
      try {
        const body = JSON.parse(err.message);
        await loadRagPages();
        const created = body?.created?.length || 0;
        if (created) {
          setPaste("");
          setNotice(`${created} page(s) queued. ${body.over_limit?.length ? "Some URLs were over your plan limit." : ""}`);
          return;
        }
      } catch {
        /* not JSON */
      }
      setError(err.message);
    } finally {
      setPasteBusy(false);
    }
  }

  async function reread(row) {
    setError("");
    setNotice("");
    try {
      await api.recrawlWebsite(row.id);
      await loadWebsites();
      setNotice(`Reading ${row.url} again.`);
    } catch (err) {
      setError(err.message);
    }
  }

  async function reindexPage(row) {
    setError("");
    try {
      await api.reindexWebRagPage(row.id);
      await loadRagPages();
      setNotice(`Re-indexing ${row.url}.`);
    } catch (err) {
      setError(err.message);
    }
  }

  async function removeWebsite(row) {
    if (!window.confirm(`Delete ${row.name}? Its pages are removed from this account's vector database.`)) return;
    setError("");
    try {
      await api.deleteWebsite(row.id);
      if (editing === row.id) {
        setEditing(null);
        setForm(EMPTY);
      }
      await loadWebsites();
    } catch (err) {
      setError(err.message);
    }
  }

  async function removeRagPage(row) {
    if (!window.confirm(`Remove ${row.url} from RAG?`)) return;
    setError("");
    try {
      await api.deleteWebRagPage(row.id);
      await loadRagPages();
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
            Paste individual page links for fast, high-priority indexing, or add a whole website to crawl. Chat
            uses both in this account's vector database.
          </p>
        </div>
      </header>
      {error && <div className="form-error">{error}</div>}
      {notice && <p className="form-ok">{notice}</p>}

      <div className="studio-card website-rag-list">
        <div className="website-rag-list-head">
          <h2>RAG pages (paste URLs)</h2>
          <p className="muted">{pageLimitLabel(pageLimit, ragPages.length)}</p>
        </div>
        <form className="website-rag-paste" onSubmit={addPastedPages}>
          <label className="span-2">
            Paste page addresses
            <textarea
              rows={4}
              value={paste}
              placeholder="Paste one or many https:// links (even back-to-back). Example: https://varta.astrosage.com/?lang=en"
              onChange={(event) => setPaste(event.target.value)}
              disabled={atPageLimit}
            />
            <span className="muted">
              Each distinct URL is indexed on its own with high priority for chat. Plan limit is set in Admin →
              Global (Basic 1, Silver 2, Gold 5, Diamond 10; 0 = unlimited).
            </span>
          </label>
          <div className="form-actions">
            <button className="primary" type="submit" disabled={pasteBusy || atPageLimit}>
              {pasteBusy ? "Adding…" : "Add pages to RAG"}
            </button>
          </div>
          {atPageLimit && (
            <p className="form-error">
              Plan limit reached. Delete a page below or ask an admin to raise Website RAG page limit.
            </p>
          )}
        </form>
        <ul className="website-rag-items">
          {ragPages.map((row) => (
            <li key={row.id} className="website-rag-item">
              <div className="website-rag-item-main">
                <a href={row.url} target="_blank" rel="noreferrer">
                  {row.title || row.url}
                </a>
                {!row.enabled && <span className="muted"> · disabled</span>}
                <div className="muted">
                  {row.chunk_count} section{row.chunk_count === 1 ? "" : "s"} ·{" "}
                  <span className={`status status-${row.status}`}>{row.status}</span>
                  {row.message && ` · ${row.message}`}
                </div>
                {row.error && <div className="form-error">{row.error}</div>}
              </div>
              <div className="row-actions website-rag-item-actions">
                <button type="button" className="link" onClick={() => reindexPage(row)}>
                  Re-index
                </button>
                <button type="button" className="link danger" onClick={() => removeRagPage(row)}>
                  Delete
                </button>
              </div>
            </li>
          ))}
          {ragPages.length === 0 && (
            <li className="muted website-rag-empty">No RAG pages yet. Paste URLs above.</li>
          )}
        </ul>
      </div>

      <form className="studio-card studio-form" onSubmit={saveWebsite}>
        <h2>{editing ? "Edit website crawl" : "Add whole website (crawl)"}</h2>
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
          Pages to crawl
          <input
            type="number"
            min="1"
            max={CRAWL_PAGE_MAX}
            value={form.max_pages}
            onChange={(event) => setForm({ ...form, max_pages: event.target.value })}
          />
          <span className="muted">Up to {CRAWL_PAGE_MAX} pages per site (separate from pasted RAG page limit).</span>
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
        <h2>Crawled websites</h2>
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
                  <td>
                    <a href={row.url} target="_blank" rel="noreferrer">
                      {row.url}
                    </a>
                  </td>
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
                    <button type="button" className="link" onClick={() => reread(row)}>
                      Read again
                    </button>
                    <button type="button" className="link" onClick={() => edit(row)}>
                      Edit
                    </button>
                    <button type="button" className="link danger" onClick={() => removeWebsite(row)}>
                      Delete
                    </button>
                  </td>
                </tr>
                {openId === row.id && (
                  <tr>
                    <td colSpan={5}>
                      {row.pages?.length ? (
                        <ul className="page-list">
                          {row.pages.map((page) => (
                            <li key={page.id}>
                              <a href={page.url} target="_blank" rel="noreferrer">
                                {page.title || page.url}
                              </a>
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
                <td colSpan={5} className="muted">
                  No whole-site crawl yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
