import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import { PLANS, engineLabel, planLabel } from "../plans";

const EMPTY_PLANS = { basic: 0, silver: 0, gold: 0, diamond: 0 };

function rowsOf(data) {
  return data?.users || [];
}

export default function AdminSettingsPage({ actingId, onDirectoryChange, onActingChange }) {
  const [tab, setTab] = useState("global");
  const [plans, setPlans] = useState(EMPTY_PLANS);
  const [databaseMode, setDatabaseMode] = useState("sqlite");
  const [notFoundMessage, setNotFoundMessage] = useState("");
  const [users, setUsers] = useState([]);
  const [lastPurge, setLastPurge] = useState("Not run yet");
  const [query, setQuery] = useState("");
  const [planFilter, setPlanFilter] = useState("all");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [editor, setEditor] = useState(null);
  const [pendingDelete, setPendingDelete] = useState(null);
  const [confirmName, setConfirmName] = useState("");

  function apply(data) {
    setPlans({ ...EMPTY_PLANS, ...(data.plans || {}) });
    setDatabaseMode(data.database_mode || "sqlite");
    setNotFoundMessage(data.not_found_message || "");
    setUsers(rowsOf(data));
    setLastPurge(data.last_purge_at ? new Date(data.last_purge_at).toLocaleString() : "Not run yet");
  }

  function reload() {
    return api.adminSettings().then((data) => {
      apply(data);
      onDirectoryChange?.();
      return data;
    });
  }

  useEffect(() => {
    reload().catch((err) => setError(err.message));
    // Load once when the settings screen opens.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return users.filter((row) => {
      if (planFilter !== "all" && (row.plan || "basic") !== planFilter) return false;
      if (!needle) return true;
      return [row.username, row.email, row.database_name].join(" ").toLowerCase().includes(needle);
    });
  }, [users, query, planFilter]);

  function updateUser(id, value) {
    setUsers((rows) => rows.map((row) => (row.id === id ? { ...row, not_found_message: value } : row)));
  }

  async function savePlans(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      apply(
        await api.saveAdminSettings({
          plans: {
            basic: Number(plans.basic) || 0,
            silver: Number(plans.silver) || 0,
            gold: Number(plans.gold) || 0,
            diamond: Number(plans.diamond) || 0,
          },
        })
      );
      setNotice("Retention schedule saved.");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function saveSentences(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      apply(
        await api.saveAdminSettings({
          not_found_message: notFoundMessage,
          users: users.map((row) => ({ id: row.id, not_found_message: row.not_found_message })),
        })
      );
      setNotice("Replies saved.");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function purgeNow() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const data = await api.purgeAdminSettings();
      apply(data);
      const removed = data.purge || {};
      setNotice(`Removed ${removed.conversations || 0} chats and ${removed.uploaded_files || removed.documents || 0} files.`);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function saveEditor(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      if (editor.id) {
        await api.updateAccount(editor.id, {
          email: editor.email,
          plan: editor.plan,
          password: editor.password,
          not_found_message: editor.not_found_message,
        });
        setNotice(`${editor.username} updated.`);
      } else {
        await api.createAccount({
          username: editor.username,
          email: editor.email,
          password: editor.password,
          plan: editor.plan,
        });
        setNotice(`${editor.username} created with a private database.`);
      }
      setEditor(null);
      await reload();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function removeAccount() {
    if (!pendingDelete || confirmName !== pendingDelete.username) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api.deleteAccount(pendingDelete.id);
      if (actingId === pendingDelete.id) onActingChange?.(null);
      setNotice(`${pendingDelete.username} and their data were deleted.`);
      setPendingDelete(null);
      setConfirmName("");
      await reload();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function retryDatabase(row) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api.provisionAccount(row.id);
      setNotice(`Database ready for ${row.username}.`);
      await reload();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="studio admin-console">
      <header className="studio-head">
        <div>
          <p className="eyebrow">Administration</p>
          <h1>Settings</h1>
          <p className="muted">
            Global rules follow the account plan. User rules are the sentence each chatbot says when it cannot find an answer.
          </p>
        </div>
      </header>

      <div className="admin-tabs" role="tablist" aria-label="Settings">
        <button type="button" role="tab" aria-selected={tab === "global"} className={tab === "global" ? "active" : ""} onClick={() => setTab("global")}>
          Global
        </button>
        <button type="button" role="tab" aria-selected={tab === "users"} className={tab === "users" ? "active" : ""} onClick={() => setTab("users")}>
          Users
        </button>
      </div>

      {error && <div className="form-error">{error}</div>}
      {notice && <p className="form-ok">{notice}</p>}

      {tab === "global" && (
        <form onSubmit={savePlans}>
          <div className="studio-card mode-note">
            <strong>{databaseMode === "postgresql" ? "PostgreSQL" : "Private database file"}</strong>
            <p className="muted">
              {databaseMode === "postgresql"
                ? "Creating an account creates a PostgreSQL database. Chats, filters, and search for that account stay in that database."
                : "PostgreSQL is not configured on this server, so each new account gets its own database file. Set TENANT_PG_HOST when you want a real PostgreSQL database per account."}
            </p>
          </div>
          <div className="plan-grid">
            {PLANS.map((plan) => (
              <article className="plan-card" data-plan={plan.id} key={plan.id}>
                <header>
                  <span className={`plan-pill plan-${plan.id}`}>{plan.label}</span>
                  <p>{Number(plans[plan.id]) > 0 ? `Delete chats after ${plans[plan.id]} days` : "Keep chats"}</p>
                </header>
                <label className="field">
                  Days before chat data is deleted
                  <input
                    type="number"
                    min="0"
                    max="3650"
                    value={plans[plan.id]}
                    onChange={(event) => setPlans((current) => ({ ...current, [plan.id]: event.target.value }))}
                  />
                </label>
                <p className="muted">0 keeps every chat for this plan.</p>
              </article>
            ))}
          </div>
          <div className="studio-card">
            <p className="muted">
              The saved schedule deletes chats, visitor answers, and uploaded files. Websites, SQL keywords, and questions stay. Last run: {lastPurge}.
            </p>
            <div className="form-actions">
              <button className="primary" type="submit" disabled={busy}>
                {busy ? "Saving…" : "Save schedule"}
              </button>
              <button type="button" className="ghost" onClick={purgeNow} disabled={busy}>
                Delete expired data now
              </button>
            </div>
          </div>
        </form>
      )}

      {tab === "users" && (
        <form onSubmit={saveSentences}>
          <div className="user-toolbar">
            <label className="field grow">
              Search
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Name, email, or database" />
            </label>
            <div className="plan-filters" role="group" aria-label="Filter by plan">
              <button type="button" className={planFilter === "all" ? "active" : ""} onClick={() => setPlanFilter("all")}>
                All
              </button>
              {PLANS.map((plan) => (
                <button type="button" key={plan.id} className={planFilter === plan.id ? "active" : ""} onClick={() => setPlanFilter(plan.id)}>
                  {plan.label}
                </button>
              ))}
            </div>
            <button
              type="button"
              className="primary"
              onClick={() => setEditor({ username: "", email: "", password: "", plan: "basic", not_found_message: "" })}
            >
              New account
            </button>
          </div>

          <div className="studio-card">
            <h2>Default reply</h2>
            <p className="muted">Used when an account does not have its own sentence.</p>
            <label className="field">
              Sentence when nothing is found
              <textarea rows={3} required value={notFoundMessage} onChange={(event) => setNotFoundMessage(event.target.value)} />
            </label>
          </div>

          <div className="account-list">
            {visible.map((row) => (
              <article className="account-card" key={row.id}>
                <header>
                  <div>
                    <strong>{row.username}</strong>
                    {row.is_menu_admin && <span className="mini-tag">Admin</span>}
                    {row.plan && <span className={`plan-pill plan-${row.plan}`}>{planLabel(row.plan)}</span>}
                  </div>
                  <div className="row-actions">
                    <button
                      type="button"
                      className="link"
                      onClick={() =>
                        setEditor({
                          id: row.id,
                          username: row.username,
                          email: row.email || "",
                          password: "",
                          plan: row.plan || "basic",
                          not_found_message: row.not_found_message || "",
                        })
                      }
                    >
                      Edit
                    </button>
                    {row.can_delete && (
                      <button
                        type="button"
                        className="link danger"
                        onClick={() => {
                          setPendingDelete(row);
                          setConfirmName("");
                        }}
                      >
                        Delete
                      </button>
                    )}
                  </div>
                </header>
                <p className="muted account-mail">{row.email || "No email"}</p>
                <div className="db-line">
                  <code>{row.database_name || "No database yet"}</code>
                  <span className={row.database_ready ? "status-ok" : "status-wait"}>
                    {row.database_name ? engineLabel(row.database_engine) : "Missing"}
                    {row.database_name ? (row.database_ready ? " · Ready" : " · Needs attention") : ""}
                  </span>
                  {!row.database_ready && (
                    <button type="button" className="link" onClick={() => retryDatabase(row)} disabled={busy}>
                      {row.database_name ? "Retry database" : "Create database"}
                    </button>
                  )}
                </div>
                {row.database_error && <p className="form-error">{row.database_error}</p>}
                <label className="field">
                  Sentence when nothing is found
                  <textarea
                    rows={2}
                    value={row.not_found_message}
                    placeholder="Use the default sentence"
                    onChange={(event) => updateUser(row.id, event.target.value)}
                  />
                </label>
              </article>
            ))}
            {visible.length === 0 && <p className="muted empty-copy">No accounts match this filter.</p>}
          </div>
          <div className="form-actions">
            <button className="primary" type="submit" disabled={busy}>
              {busy ? "Saving…" : "Save replies"}
            </button>
          </div>
        </form>
      )}

      {editor && (
        <div className="modal-back" role="presentation" onMouseDown={() => !busy && setEditor(null)}>
          <form className="modal-card" onSubmit={saveEditor} onMouseDown={(event) => event.stopPropagation()}>
            <h2>{editor.id ? `Edit ${editor.username}` : "New account"}</h2>
            <p className="muted">
              {editor.id
                ? "Change the plan, email, or password. Leave the password blank to keep the current one."
                : "A private database is created with the account. Chats, filters, and search use that database."}
            </p>
            {!editor.id && (
              <label className="field">
                Username
                <input required value={editor.username} onChange={(event) => setEditor({ ...editor, username: event.target.value })} />
              </label>
            )}
            <label className="field">
              Email
              <input type="email" value={editor.email} onChange={(event) => setEditor({ ...editor, email: event.target.value })} />
            </label>
            <label className="field">
              {editor.id ? "New password" : "Password"}
              <input
                type="password"
                minLength={editor.id ? undefined : 8}
                required={!editor.id}
                value={editor.password}
                autoComplete="new-password"
                onChange={(event) => setEditor({ ...editor, password: event.target.value })}
              />
            </label>
            <label className="field">
              Plan
              <select value={editor.plan} onChange={(event) => setEditor({ ...editor, plan: event.target.value })}>
                {PLANS.map((plan) => (
                  <option key={plan.id} value={plan.id}>
                    {plan.label}
                  </option>
                ))}
              </select>
            </label>
            {editor.id && (
              <label className="field">
                Sentence when nothing is found
                <textarea
                  rows={3}
                  value={editor.not_found_message}
                  placeholder="Use the default sentence"
                  onChange={(event) => setEditor({ ...editor, not_found_message: event.target.value })}
                />
              </label>
            )}
            <div className="form-actions">
              <button className="primary" disabled={busy}>
                {busy ? "Saving…" : editor.id ? "Save account" : "Create account"}
              </button>
              <button type="button" className="ghost" onClick={() => setEditor(null)} disabled={busy}>
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {pendingDelete && (
        <div className="modal-back" role="presentation">
          <div className="modal-card danger-card">
            <h2>Delete {pendingDelete.username}?</h2>
            <p>
              This removes the account, the private database, chats, uploaded files, website data, SQL keywords, and questions.
              It cannot be undone.
            </p>
            <label className="field">
              Type <strong>{pendingDelete.username}</strong> to confirm
              <input value={confirmName} onChange={(event) => setConfirmName(event.target.value)} autoFocus />
            </label>
            <div className="form-actions">
              <button
                type="button"
                className="danger"
                disabled={busy || confirmName !== pendingDelete.username}
                onClick={removeAccount}
              >
                {busy ? "Deleting…" : "Delete everything"}
              </button>
              <button
                type="button"
                className="ghost"
                disabled={busy}
                onClick={() => {
                  setPendingDelete(null);
                  setConfirmName("");
                }}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
