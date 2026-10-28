import { useEffect, useState } from "react";
import { api } from "../api/client";

function when(value) {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

export default function IssuesPanel() {
  const [rows, setRows] = useState([]);
  const [error, setError] = useState("");
  const [shot, setShot] = useState("");
  const [openId, setOpenId] = useState("");

  useEffect(() => {
    let cancelled = false;
    api
      .listErrors()
      .then((data) => {
        if (!cancelled) setRows(data.errors || []);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    return () => {
      if (shot) URL.revokeObjectURL(shot);
    };
  }, [shot]);

  async function showShot(id) {
    setError("");
    try {
      const blob = await api.errorScreenshot(id);
      if (shot) URL.revokeObjectURL(shot);
      setShot(URL.createObjectURL(blob));
      setOpenId(id);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="issue-panel">
      <div className="studio-card">
        <h2>Call stacks</h2>
        <p className="muted">
          Backend failures and UI failures are stored in the admin database. Screenshots are files on the server volume.
        </p>
        {error && <div className="form-error">{error}</div>}
        {rows.length === 0 && !error && <p className="muted">No issues stored yet.</p>}
        {rows.length > 0 && (
          <div className="issue-scroll">
            <table className="issue-table">
              <thead>
                <tr>
                  <th>When</th>
                  <th>User</th>
                  <th>Where</th>
                  <th>Message</th>
                  <th>Call stack</th>
                  <th>Screenshot</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td>
                      {when(row.created_at)}
                      <small>{row.source}{row.status_code ? ` · ${row.status_code}` : ""}</small>
                    </td>
                    <td>
                      {row.username || "Visitor"}
                      {row.email ? <small>{row.email}</small> : null}
                      {row.user_id ? <small>id {row.user_id}</small> : null}
                    </td>
                    <td>{row.path || row.method || "—"}</td>
                    <td>{row.message}</td>
                    <td>
                      <pre className="issue-stack">{row.stack || "No stack was captured."}</pre>
                    </td>
                    <td>
                      {row.screenshot_path ? (
                        <button type="button" className="link" onClick={() => showShot(row.id)}>
                          {openId === row.id ? "Showing" : "View"}
                        </button>
                      ) : (
                        "—"
                      )}
                      {row.screenshot_path ? <small>{row.screenshot_path}</small> : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {shot && <img className="issue-shot" src={shot} alt="UI screenshot from the stored error" />}
      </div>
    </div>
  );
}
