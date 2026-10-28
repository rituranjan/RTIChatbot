import { useEffect, useState } from "react";
import { api } from "../api/client";

export default function UsagePanel() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .llmUsage()
      .then(setData)
      .catch((err) => setError(err.message));
  }, []);

  const totals = data?.totals || {};

  return (
    <div className="issue-panel">
      <div className="studio-card">
        <h2>LLM usage</h2>
        <p className="muted">Estimated and actual tokens recorded for each OpenRouter chat completion.</p>
        {error && <div className="form-error">{error}</div>}
        {totals.requests != null && (
          <p>
            Requests {totals.requests || 0} · Input {totals.input_tokens || 0} · Output{" "}
            {totals.output_tokens || 0} · Cached {totals.cached_tokens || 0}
          </p>
        )}
        {(data?.by_workflow || []).length > 0 && (
          <ul className="usage-workflows">
            {data.by_workflow.map((row) => (
              <li key={row.workflow}>
                {row.workflow}: {row.count} calls, {row.input || 0} input tokens
              </li>
            ))}
          </ul>
        )}
        {(data?.recent || []).length > 0 && (
          <div className="issue-scroll">
            <table className="issue-table">
              <thead>
                <tr>
                  <th>When</th>
                  <th>User</th>
                  <th>Workflow</th>
                  <th>Model</th>
                  <th>In / Out</th>
                </tr>
              </thead>
              <tbody>
                {data.recent.map((row) => (
                  <tr key={row.id}>
                    <td>{new Date(row.created_at).toLocaleString()}</td>
                    <td>{row.user__username}</td>
                    <td>{row.workflow}</td>
                    <td>{row.model}</td>
                    <td>
                      {row.actual_input_tokens}/{row.actual_output_tokens}
                      {!row.success ? " · failed" : ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
