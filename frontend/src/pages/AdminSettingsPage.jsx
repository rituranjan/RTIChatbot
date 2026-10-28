import { useEffect, useState } from "react";
import { api } from "../api/client";

export default function AdminSettingsPage() {
  const [retentionDays, setRetentionDays] = useState(0);
  const [notFoundMessage, setNotFoundMessage] = useState("");
  const [users, setUsers] = useState([]);
  const [lastPurge, setLastPurge] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  function apply(data) {
    setRetentionDays(data.retention_days ?? 0);
    setNotFoundMessage(data.not_found_message || "");
    setUsers(data.users || []);
    setLastPurge(data.last_purge_at ? new Date(data.last_purge_at).toLocaleString() : "Not run yet");
  }

  useEffect(() => {
    api.adminSettings().then(apply).catch((err) => setError(err.message));
  }, []);

  function updateUser(id, value) {
    setUsers((rows) => rows.map((row) => (row.id === id ? { ...row, not_found_message: value } : row)));
  }

  async function save(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const data = await api.saveAdminSettings({
        retention_days: Number(retentionDays) || 0,
        not_found_message: notFoundMessage,
        users: users.map((row) => ({ id: row.id, not_found_message: row.not_found_message })),
      });
      apply(data);
      setNotice("Settings saved.");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function purgeNow() {
    if (!window.confirm("Delete chats and uploaded files older than the saved number of days for every user?")) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const data = await api.purgeAdminSettings();
      apply(data);
      const removed = data.purge || {};
      setNotice(
        `Removed ${removed.conversations || 0} chats and ${removed.documents || 0} files.`
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="studio">
      <header className="studio-head">
        <div>
          <h1>Admin settings</h1>
          <p className="muted">
            Global rules apply to every account. A user-wise sentence is what that account's chatbot says when it cannot find an answer.
          </p>
        </div>
      </header>
      {error && <div className="form-error">{error}</div>}
      {notice && <p className="form-ok">{notice}</p>}
      <form onSubmit={save}>
        <div className="studio-card">
          <h2>Global setting</h2>
          <p className="muted">
            After this many days, chats, visitor answers, and uploaded files are deleted automatically for every user. Websites, SQL keywords, and questions are kept. Use 0 to turn deletion off. Last run: {lastPurge}.
          </p>
          <div className="studio-form">
            <label>
              Delete data after (days)
              <input
                type="number"
                min="0"
                max="3650"
                value={retentionDays}
                onChange={(event) => setRetentionDays(event.target.value)}
              />
            </label>
            <div className="form-actions">
              <button className="primary" type="submit" disabled={busy}>
                {busy ? "Saving…" : "Save"}
              </button>
              <button type="button" className="link" onClick={purgeNow} disabled={busy}>
                Delete expired data now
              </button>
            </div>
          </div>
        </div>
        <div className="studio-card">
          <h2>User wise</h2>
          <p className="muted">
            This sentence is shown when the chatbot cannot find the answer in files, websites, or the database. A blank user row uses the default sentence.
          </p>
          <label>
            Default sentence
            <textarea
              rows={3}
              required
              value={notFoundMessage}
              onChange={(event) => setNotFoundMessage(event.target.value)}
            />
          </label>
          <table className="data-table">
            <thead>
              <tr>
                <th>User</th>
                <th>Sentence when nothing is found</th>
              </tr>
            </thead>
            <tbody>
              {users.map((row) => (
                <tr key={row.id}>
                  <td>{row.username}</td>
                  <td>
                    <textarea
                      rows={2}
                      value={row.not_found_message}
                      placeholder="Use the default sentence"
                      onChange={(event) => updateUser(row.id, event.target.value)}
                    />
                  </td>
                </tr>
              ))}
              {users.length === 0 && (
                <tr>
                  <td colSpan={2} className="muted">No users yet.</td>
                </tr>
              )}
            </tbody>
          </table>
          <div className="form-actions">
            <button className="primary" type="submit" disabled={busy}>
              {busy ? "Saving…" : "Save"}
            </button>
          </div>
        </div>
      </form>
    </section>
  );
}
