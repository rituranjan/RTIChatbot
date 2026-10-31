import { useEffect, useState } from "react";
import { api } from "../api/client";

function shortName(item) {
  const raw = String(item?.name || item?.id || "").trim();
  const cut = raw.includes(":") ? raw.split(":").slice(1).join(":").trim() : raw;
  return cut || item.id;
}

function optionLabel(item, models) {
  const label = shortName(item);
  const same = models.filter((other) => shortName(other) === label).length;
  return same > 1 ? `${label} (${item.id})` : label;
}

function perRequest(limit) {
  return Number(limit) > 0 ? String(limit) : "unlimited";
}

function capLabel(value) {
  return Number(value) > 0 ? String(value) : "unlimited";
}

export default function ModelPage() {
  const [plan, setPlan] = useState(null);
  const [selected, setSelected] = useState("");
  const [domains, setDomains] = useState([]);
  const [domainInput, setDomainInput] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .myPlan()
      .then((data) => {
        if (cancelled) return;
        setPlan(data);
        setSelected(data.selected_model || "");
        setDomains(Array.isArray(data.embed_domains) ? data.embed_domains : []);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function save(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const data = await api.saveMyPlan({
        selected_model: selected,
        embed_domains: domains,
      });
      setPlan(data);
      setSelected(data.selected_model || "");
      setDomains(Array.isArray(data.embed_domains) ? data.embed_domains : []);
      setNotice("Saved.");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function addDomain() {
    const value = domainInput.trim();
    if (!value) return;
    if (domains.includes(value)) {
      setDomainInput("");
      return;
    }
    const cap = Number(plan?.max_embed_domains ?? plan?.limits?.max_embed_domains) || 0;
    if (cap > 0 && domains.length >= cap) {
      setError(`Your plan allows at most ${cap} embed domains.`);
      return;
    }
    setError("");
    setDomains((rows) => [...rows, value]);
    setDomainInput("");
  }

  function removeDomain(host) {
    setDomains((rows) => rows.filter((item) => item !== host));
  }

  const models = plan?.models || [];
  const domainCap = Number(plan?.max_embed_domains ?? plan?.limits?.max_embed_domains) || 0;
  const concurrentCap = Number(plan?.limits?.concurrent_users) || 0;

  return (
    <section className="studio model-page">
      <h1>Model</h1>
      {error && <div className="form-error">{error}</div>}
      {notice && <p className="form-ok">{notice}</p>}
      {!plan && !error && <p className="muted">Loading…</p>}
      {plan && (
        <form onSubmit={save} className="model-form">
          <div className="model-card model-fields">
            <label className="field">
              {plan.plan_label}
              <select
                value={selected}
                onChange={(event) => setSelected(event.target.value)}
                disabled={models.length === 0}
              >
                {models.length === 0 && <option value="">No models yet</option>}
                {models.map((item) => (
                  <option key={item.id} value={item.id} title={item.id}>
                    {optionLabel(item, models)}
                  </option>
                ))}
              </select>
            </label>
            {plan.language?.enabled && (
              <p className="muted model-language-note">
                Reply language is chosen in the chat box when you send a message.
              </p>
            )}
          </div>

          <div className="model-card model-usage">
            <p className="usage-line">
              This month — Requests{" "}
              {Number(plan.limits.monthly_requests) > 0
                ? `${plan.usage.requests}/${plan.limits.monthly_requests}`
                : plan.usage.requests}
              <span>
                Per message — Input max {perRequest(plan.limits.input_tokens)} · Output max{" "}
                {perRequest(plan.limits.output_tokens)}
              </span>
              <span>
                Embed — Concurrent visitors {capLabel(concurrentCap)} · Domains {capLabel(domainCap)}
              </span>
            </p>
          </div>

          <div className="model-card embed-domains">
            <h2>Website embed domains</h2>
            <p className="muted">
              Add the domains where you will place the chat script. The widget only works on these sites
              {domainCap > 0 ? ` (up to ${domainCap} on your plan).` : " (unlimited on your plan)."}
            </p>
            <div className="domain-add-row">
              <input
                value={domainInput}
                placeholder="www.example.com"
                onChange={(event) => setDomainInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    addDomain();
                  }
                }}
              />
              <button type="button" className="ghost" onClick={addDomain}>
                Add
              </button>
            </div>
            <ul className="domain-list">
              {domains.map((host) => (
                <li key={host}>
                  <span>{host}</span>
                  <button type="button" className="link" onClick={() => removeDomain(host)}>
                    Remove
                  </button>
                </li>
              ))}
              {domains.length === 0 && <li className="muted">No domains yet.</li>}
            </ul>
          </div>

          <button className="primary model-save" disabled={busy || !selected}>
            {busy ? "Saving…" : "Save"}
          </button>
        </form>
      )}
    </section>
  );
}
