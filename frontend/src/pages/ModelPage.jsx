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
  return Number(limit) > 0 ? String(limit) : "off";
}

export default function ModelPage() {
  const [plan, setPlan] = useState(null);
  const [selected, setSelected] = useState("");
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
      const data = await api.saveMyPlan(selected);
      setPlan(data);
      setSelected(data.selected_model || "");
      setNotice("Saved.");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const models = plan?.models || [];

  return (
    <section className="studio model-page">
      <h1>Model</h1>
      {error && <div className="form-error">{error}</div>}
      {notice && <p className="form-ok">{notice}</p>}
      {!plan && !error && <p className="muted">Loading…</p>}
      {plan && (
        <form onSubmit={save} className="model-form">
          <div className="model-card">
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
            <button className="primary" disabled={busy || !selected}>
              {busy ? "Saving…" : "Save"}
            </button>
          </div>
          <p className="usage-line">
            This month — Requests{" "}
            {Number(plan.limits.monthly_requests) > 0
              ? `${plan.usage.requests}/${plan.limits.monthly_requests}`
              : plan.usage.requests}
            <span>
              Per message — Input max {perRequest(plan.limits.input_tokens)} · Output max{" "}
              {perRequest(plan.limits.output_tokens)}
            </span>
          </p>
        </form>
      )}
    </section>
  );
}
