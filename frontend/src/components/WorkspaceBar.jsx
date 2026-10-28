import { useEffect, useState } from "react";
import { api } from "../api/client";
import { engineLabel, planLabel } from "../plans";

export default function WorkspaceBar({ user, acting, onChange, version }) {
  const [users, setUsers] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    api
      .listAccounts()
      .then((data) => {
        if (!cancelled) setUsers(data.users || []);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [version]);

  const selected = acting
    ? users.find((row) => row.id === acting.id) || acting
    : null;
  const databaseName = selected?.database_name || (!acting ? user.database_name : "");
  const ready = selected ? selected.database_ready : user.database_ready;
  const engine = selected?.database_engine || (!acting ? user.database_engine : "");
  const who = selected?.username || user.username;

  async function choose(event) {
    setError("");
    try {
      const value = event.target.value;
      const data = await api.actAs(value ? Number(value) : null);
      onChange(data.acting_as || null);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="workspace-bar">
      <label className="workspace-pick">
        <span>Workspace</span>
        <select value={acting?.id || ""} onChange={choose}>
          <option value="">My account · {user.username}</option>
          {users
            .filter((row) => row.id !== user.id)
            .map((row) => (
              <option key={row.id} value={row.id}>
                {row.username}
                {row.plan ? ` · ${planLabel(row.plan)}` : ""}
              </option>
            ))}
        </select>
      </label>
      <p>
        Working as <strong>{who}</strong>
        {selected?.plan ? <span className={`plan-pill plan-${selected.plan}`}>{planLabel(selected.plan)}</span> : null}
        {!selected && user.plan ? <span className={`plan-pill plan-${user.plan}`}>{planLabel(user.plan)}</span> : null}
        . Files, databases, SQL keywords, chats, and search use this account.
        {databaseName ? (
          <>
            {" "}
            Database <code>{databaseName}</code>
            {engine ? ` (${engineLabel(engine)})` : ""}
            {ready === false ? " is not ready." : "."}
          </>
        ) : (
          " This account does not have a private database yet."
        )}
      </p>
      {error && <span className="form-error">{error}</span>}
    </div>
  );
}
