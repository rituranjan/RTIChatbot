import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import IssuesPanel from "./IssuesPanel";
import PromptsPanel from "./PromptsPanel";
import UsagePanel from "./UsagePanel";
import { PLANS, engineLabel, planLabel } from "../plans";

const SETTINGS_MENUS = [
  { id: "global", label: "Global", hint: "Models and limits" },
  { id: "mail", label: "Mail", hint: "Limit emails" },
  { id: "users", label: "Users", hint: "Accounts" },
  { id: "prompts", label: "Prompts", hint: "LLM text" },
  { id: "usage", label: "Usage", hint: "Tokens" },
  { id: "issues", label: "Issues", hint: "Call stacks" },
];

const REQUESTS = { basic: 10, silver: 20, gold: 30, diamond: 40 };

const EMPTY_LLM_POLICY = {
  default_max_output_tokens: 2048,
  default_max_input_tokens_per_request: 0,
  missing_plan_policy: "defaults",
};

const EMPTY_LANGUAGE_SETTINGS = {
  enabled: true,
  required: false,
  default_code: "en",
  enabled_codes: [],
  languages: [],
};

function blankAccess() {
  return Object.fromEntries(
    PLANS.map((plan) => [
      plan.id,
      {
        days: 0,
        models: [],
        model_names: {},
        monthly_requests: REQUESTS[plan.id],
        input_tokens: 0,
        output_tokens: 0,
        cached_tokens: 0,
        website_max_pages: { basic: 50, silver: 100, gold: 200, diamond: 400 }[plan.id],
        language_enabled: plan.id !== "basic",
        limit_message: `You have reached the ${plan.label} plan limit for this month.`,
      },
    ])
  );
}

const EMPTY_MAIL = {
  host: "",
  port: 587,
  username: "",
  password: "",
  from_email: "",
  use_tls: true,
  password_set: false,
  subject: "Your chat plan limit was reached",
};

function ModelAdd({ planId, onAdd }) {
  const [value, setValue] = useState("");
  function submit() {
    onAdd(planId, value);
    setValue("");
  }
  return (
    <div className="model-add">
      <input
        value={value}
        placeholder="openai/gpt-4o"
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            submit();
          }
        }}
      />
      <button type="button" className="ghost" onClick={submit}>
        Add
      </button>
    </div>
  );
}

function rowsOf(data) {
  return data?.users || [];
}

export default function AdminSettingsPage({ actingId, onDirectoryChange, onActingChange }) {
  const [tab, setTab] = useState("global");
  const [planTab, setPlanTab] = useState("basic");
  const [access, setAccess] = useState(blankAccess);
  const [apiKey, setApiKey] = useState("");
  const [keyNote, setKeyNote] = useState("");
  const [catalog, setCatalog] = useState([]);
  const [modelQuery, setModelQuery] = useState("");
  const [mail, setMail] = useState(EMPTY_MAIL);
  const [databaseMode, setDatabaseMode] = useState("sqlite");
  const [notFoundMessage, setNotFoundMessage] = useState("");
  const [users, setUsers] = useState([]);
  const [lastPurge, setLastPurge] = useState("Not run yet");
  const [query, setQuery] = useState("");
  const [planFilter, setPlanFilter] = useState("all");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [loadingModels, setLoadingModels] = useState(false);
  const [editor, setEditor] = useState(null);
  const [pendingDelete, setPendingDelete] = useState(null);
  const [confirmName, setConfirmName] = useState("");
  const [llmPolicy, setLlmPolicy] = useState(EMPTY_LLM_POLICY);
  const [languageSettings, setLanguageSettings] = useState(EMPTY_LANGUAGE_SETTINGS);

  function apply(data) {
    const next = blankAccess();
    const saved = data.plan_access || {};
    for (const plan of PLANS) {
      const row = saved[plan.id] || {};
      next[plan.id] = {
        ...next[plan.id],
        ...row,
        models: Array.isArray(row.models) ? row.models : [],
        model_names: row.model_names && typeof row.model_names === "object" ? { ...row.model_names } : {},
      };
    }
    setAccess(next);
    setApiKey("");
    setKeyNote(
      data.openrouter_configured
        ? data.openrouter_source === "settings"
          ? "A key is saved in settings. Type a new one only to replace it."
          : "Using the key from the server environment. Type a key here to replace it."
        : "Paste an OpenRouter API key. It is stored on the server and is not shown again."
    );
    setMail({ ...EMPTY_MAIL, ...(data.mail || {}), password: "" });
    setDatabaseMode(data.database_mode || "sqlite");
    setNotFoundMessage(data.not_found_message || "");
    setUsers(rowsOf(data));
    setLastPurge(data.last_purge_at ? new Date(data.last_purge_at).toLocaleString() : "Not run yet");
    setLlmPolicy({ ...EMPTY_LLM_POLICY, ...(data.llm_policy || {}) });
    const lang = data.language_settings;
    if (lang && Array.isArray(lang.languages)) {
      setLanguageSettings({
        enabled: true,
        required: Boolean(lang.required),
        default_code: lang.default_code || "en",
        enabled_codes: Array.isArray(lang.enabled_codes) ? lang.enabled_codes : [],
        languages: lang.languages,
      });
    } else {
      setLanguageSettings(EMPTY_LANGUAGE_SETTINGS);
    }
  }

  function updateLanguageField(field, value) {
    setLanguageSettings((current) => {
      const next = { ...current, [field]: value };
      if (field === "enabled" && !value) next.required = false;
      return next;
    });
  }

  function toggleLanguageCode(code, on) {
    setLanguageSettings((current) => {
      const languages = current.languages.map((row) =>
        row.code === code ? { ...row, enabled: on } : row
      );
      const enabled_codes = languages.filter((row) => row.enabled).map((row) => row.code);
      let default_code = current.default_code;
      if (enabled_codes.length && !enabled_codes.includes(default_code)) {
        default_code = enabled_codes[0];
      }
      return { ...current, languages, enabled_codes, default_code };
    });
  }

  function reload() {
    return api.adminSettings().then((data) => {
      apply(data);
      onDirectoryChange?.();
      return data;
    });
  }

  useEffect(() => {
    let cancelled = false;
    api
      .adminSettings()
      .then(async (data) => {
        if (cancelled) return;
        apply(data);
        onDirectoryChange?.();
        if (!data.openrouter_configured) return;
        try {
          const models = await api.openRouterModels("");
          if (!cancelled) setCatalog(models.models || []);
        } catch (err) {
          if (!cancelled) setError(err.message);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
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

  function updatePlan(planId, field, value) {
    setAccess((current) => ({ ...current, [planId]: { ...current[planId], [field]: value } }));
  }

  function toggleModel(planId, modelId, modelName) {
    setAccess((current) => {
      const selected = current[planId].models.includes(modelId);
      const models = selected
        ? current[planId].models.filter((item) => item !== modelId)
        : [...current[planId].models, modelId];
      const model_names = { ...(current[planId].model_names || {}) };
      if (selected) delete model_names[modelId];
      else model_names[modelId] = (modelName || modelId).trim() || modelId;
      return { ...current, [planId]: { ...current[planId], models, model_names } };
    });
  }

  function addModel(planId, raw, modelName) {
    const modelId = raw.trim();
    if (!modelId || /\s/.test(modelId)) {
      setError("Enter a model id such as openai/gpt-4o.");
      return;
    }
    setError("");
    setAccess((current) => {
      const models = current[planId].models.includes(modelId)
        ? current[planId].models
        : [...current[planId].models, modelId];
      return {
        ...current,
        [planId]: {
          ...current[planId],
          models,
          model_names: {
            ...(current[planId].model_names || {}),
            [modelId]: (modelName || modelId).trim() || modelId,
          },
        },
      };
    });
  }

  async function loadModels() {
    setLoadingModels(true);
    setError("");
    try {
      const data = await api.openRouterModels("");
      setCatalog(data.models || []);
      setNotice(
        data.models?.length
          ? `${data.models.length} OpenRouter models loaded. Select any of them on a plan.`
          : "OpenRouter returned no models."
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingModels(false);
    }
  }

  async function savePlans(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const payload = {
        plan_access: Object.fromEntries(
          PLANS.map((plan) => [
            plan.id,
            {
              ...access[plan.id],
              days: Number(access[plan.id].days) || 0,
              monthly_requests: Number(access[plan.id].monthly_requests) || 0,
              input_tokens: Number(access[plan.id].input_tokens) || 0,
              output_tokens: Number(access[plan.id].output_tokens) || 0,
              cached_tokens: Number(access[plan.id].cached_tokens) || 0,
              website_max_pages: Number(access[plan.id].website_max_pages) || 1,
              language_enabled: Boolean(access[plan.id].language_enabled),
            },
          ])
        ),
        llm_policy: {
          ...llmPolicy,
          default_max_output_tokens: Number(llmPolicy.default_max_output_tokens) || 2048,
          default_max_input_tokens_per_request:
            Number(llmPolicy.default_max_input_tokens_per_request) || 0,
        },
        language_settings: {
          required: languageSettings.required,
          default_code: languageSettings.default_code,
          languages: languageSettings.languages,
        },
      };
      if (apiKey.trim()) payload.openrouter_api_key = apiKey.trim();
      apply(await api.saveAdminSettings(payload));
      setNotice("Plan settings saved.");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function saveMail(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      apply(await api.saveAdminSettings({ mail }));
      setNotice("Mail settings saved.");
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

  const activePlan = PLANS.find((plan) => plan.id === planTab) || PLANS[0];
  const activeAccess = access[activePlan.id];
  const modelNeedle = modelQuery.trim().toLowerCase();
  const matchedModels = modelNeedle
    ? catalog.filter(
        (item) =>
          item.name.toLowerCase().includes(modelNeedle) || item.id.toLowerCase().includes(modelNeedle)
      )
    : catalog;
  const visibleModels = matchedModels.slice(0, 80);

  return (
    <section className="studio admin-console">
      <header className="studio-head">
        <div>
          <p className="eyebrow">Administration</p>
          <h1>Settings</h1>
          <p className="muted">
            Chat uses the OpenRouter model each person picks in User settings. Add another settings menu here when a new section is needed.
          </p>
        </div>
      </header>

      {error && <div className="form-error settings-banner">{error}</div>}
      {notice && <p className="form-ok settings-banner">{notice}</p>}

      <nav className="settings-menu" aria-label="Settings sections">
        {SETTINGS_MENUS.map((item) => (
          <button type="button" key={item.id} className={tab === item.id ? "active" : ""} onClick={() => setTab(item.id)}>
            <span>{item.label}</span>
            <small>{item.hint}</small>
          </button>
        ))}
      </nav>

      {tab === "global" && (
        <form onSubmit={savePlans}>
          <div className="studio-card mode-note">
            <strong>{databaseMode === "postgresql" ? "PostgreSQL" : "Private database file"}</strong>
            <p className="muted">
              {databaseMode === "postgresql"
                ? "Creating an account creates a PostgreSQL database. Chats, filters, and search for that account stay in that database."
                : "PostgreSQL is not configured on this server, so each new account gets its own database file. Set TENANT_PG_HOST when you want a real PostgreSQL database per account."}
            </p>
            <p className="muted">
              Replies are sent to OpenRouter with the model that person selected. The Azure chat model in the environment file is not used.
              File and website search still uses the embedding provider configured on the server.
            </p>
            <label className="field">
              OpenRouter API key
              <input
                type="password"
                value={apiKey}
                autoComplete="new-password"
                placeholder="sk-or-…"
                onChange={(event) => setApiKey(event.target.value)}
              />
            </label>
            <p className="muted">{keyNote}</p>
            <div className="limit-grid">
              <label className="field">
                Default max output tokens (per request)
                <input
                  type="number"
                  min={1}
                  max={8192}
                  value={llmPolicy.default_max_output_tokens}
                  onChange={(event) =>
                    setLlmPolicy((current) => ({
                      ...current,
                      default_max_output_tokens: Number(event.target.value),
                    }))
                  }
                />
              </label>
              <label className="field">
                Max input tokens per request (0 = use plan value only)
                <input
                  type="number"
                  min={0}
                  value={llmPolicy.default_max_input_tokens_per_request}
                  onChange={(event) =>
                    setLlmPolicy((current) => ({
                      ...current,
                      default_max_input_tokens_per_request: Number(event.target.value),
                    }))
                  }
                />
              </label>
            </div>
            <p className="muted">
              Used when a plan leaves input or output at 0. Monthly chat count limits still use each plan&apos;s
              request limit above.
            </p>
            <div className="language-admin">
              <h3>Chat languages</h3>
              <p className="muted">
                When a plan has chat languages enabled, users on that plan see the list below in the chat box. Default
                language, required-before-chat, and which languages appear apply to every plan that has languages
                turned on.
              </p>
              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={languageSettings.required}
                  onChange={(event) => updateLanguageField("required", event.target.checked)}
                />
                Require a language before chatting (plans with languages enabled)
              </label>
              <label className="field">
                Default when user does not choose
                <select
                  value={languageSettings.default_code}
                  onChange={(event) => updateLanguageField("default_code", event.target.value)}
                >
                  {(languageSettings.languages || [])
                    .filter((row) => row.enabled)
                    .map((row) => (
                      <option key={row.code} value={row.code}>
                        {row.label}
                        {row.native_label && row.native_label !== row.label ? ` (${row.native_label})` : ""}
                      </option>
                    ))}
                </select>
              </label>
              <div className="language-check-grid">
                {(languageSettings.languages || []).map((row) => (
                  <label key={row.code} className="checkbox-row">
                    <input
                      type="checkbox"
                      checked={Boolean(row.enabled)}
                      onChange={(event) => toggleLanguageCode(row.code, event.target.checked)}
                    />
                    <span>
                      {row.label}
                      {row.native_label && row.native_label !== row.label ? ` — ${row.native_label}` : ""}
                    </span>
                  </label>
                ))}
              </div>
            </div>
            <div className="model-search">
              <p className="muted grow">
                {catalog.length
                  ? `${catalog.length} models available from OpenRouter.`
                  : "Load the OpenRouter catalog, then tick every model this plan may use."}
              </p>
              <button type="button" className="ghost" onClick={loadModels} disabled={busy || loadingModels}>
                {loadingModels ? "Loading…" : "Load models"}
              </button>
            </div>
          </div>
          <div className="plan-workspace">
            <div className="plan-switch" role="tablist" aria-label="Plans">
              {PLANS.map((plan) => (
                <button
                  type="button"
                  key={plan.id}
                  role="tab"
                  aria-selected={activePlan.id === plan.id}
                  className={activePlan.id === plan.id ? "active" : ""}
                  data-plan={plan.id}
                  onClick={() => setPlanTab(plan.id)}
                >
                  {plan.label}
                  <small>
                    {access[plan.id].models.length
                      ? `${access[plan.id].models.length} models`
                      : "No models"}
                  </small>
                </button>
              ))}
            </div>
            <article className="plan-card" data-plan={activePlan.id}>
              <header>
                <span className={`plan-pill plan-${activePlan.id}`}>{activePlan.label}</span>
                <p>
                  {activeAccess.models.length
                    ? `${activeAccess.models.length} ${activeAccess.models.length === 1 ? "model" : "models"} selected`
                    : "No models yet"}
                  {Number(activeAccess.monthly_requests) > 0
                    ? ` · ${activeAccess.monthly_requests} requests / month`
                    : " · unlimited requests"}
                </p>
              </header>
              <div className="limit-grid">
                <label className="field">
                  Days before chat data is deleted
                  <input
                    type="number"
                    min="0"
                    max="3650"
                    value={activeAccess.days}
                    onChange={(event) => updatePlan(activePlan.id, "days", event.target.value)}
                  />
                </label>
                <label className="field">
                  Monthly request limit
                  <input
                    type="number"
                    min="0"
                    value={activeAccess.monthly_requests}
                    onChange={(event) => updatePlan(activePlan.id, "monthly_requests", event.target.value)}
                  />
                </label>
                <label className="field">
                  Input tokens (per request)
                  <input
                    type="number"
                    min="0"
                    value={activeAccess.input_tokens}
                    onChange={(event) => updatePlan(activePlan.id, "input_tokens", event.target.value)}
                  />
                </label>
                <label className="field">
                  Output tokens (per response)
                  <input
                    type="number"
                    min="0"
                    value={activeAccess.output_tokens}
                    onChange={(event) => updatePlan(activePlan.id, "output_tokens", event.target.value)}
                  />
                </label>
                <label className="field">
                  Website RAG page limit
                  <input
                    type="number"
                    min="1"
                    max="400"
                    value={activeAccess.website_max_pages ?? 300}
                    onChange={(event) => updatePlan(activePlan.id, "website_max_pages", event.target.value)}
                  />
                </label>
                <label className="checkbox-row plan-language-toggle">
                  <input
                    type="checkbox"
                    checked={Boolean(activeAccess.language_enabled)}
                    onChange={(event) => updatePlan(activePlan.id, "language_enabled", event.target.checked)}
                  />
                  Enable chat language dropdown
                </label>
              </div>
              <p className="muted">
                Monthly request limits are Basic 10, Silver 20, Gold 30, and Diamond 40. Input and output numbers
                apply to each single chat call only (0 turns that limit off). Website page limit caps how many pages
                are indexed per site for RAG (1–400). Turn on chat languages per plan to show the language list in chat.
              </p>
              <label className="field">
                Message when a limit is reached
                <textarea
                  rows={3}
                  required
                  value={activeAccess.limit_message}
                  onChange={(event) => updatePlan(activePlan.id, "limit_message", event.target.value)}
                />
              </label>
              <div className="model-picks">
                <span className="field-label">Models for this plan</span>
                <p className="muted">People on this plan can switch among the models you tick. The one they pick is the model OpenRouter runs.</p>
                <div className="chip-row">
                  {activeAccess.models.map((modelId) => (
                    <button
                      type="button"
                      className="model-chip"
                      key={modelId}
                      onClick={() => toggleModel(activePlan.id, modelId)}
                    >
                      {activeAccess.model_names?.[modelId] || modelId} ×
                    </button>
                  ))}
                  {activeAccess.models.length === 0 && <span className="muted">None selected</span>}
                </div>
                <label className="field">
                  Search the loaded models
                  <input
                    value={modelQuery}
                    placeholder="Name or id, such as gpt-4o"
                    onChange={(event) => setModelQuery(event.target.value)}
                  />
                </label>
                <div className="model-checklist" role="group" aria-label={`${activePlan.label} models`}>
                  {visibleModels.map((item) => {
                    const checked = activeAccess.models.includes(item.id);
                    return (
                      <label key={item.id} className={checked ? "checked" : ""}>
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => toggleModel(activePlan.id, item.id, item.name)}
                        />
                        <span>
                          {item.name}
                          <small>
                            {item.id}
                            {item.context_length ? ` · ${Number(item.context_length).toLocaleString()} context` : ""}
                          </small>
                        </span>
                      </label>
                    );
                  })}
                  {catalog.length === 0 && (
                    <p className="muted">No catalog yet. Load models above, or type an id below.</p>
                  )}
                  {catalog.length > 0 && visibleModels.length === 0 && (
                    <p className="muted">No loaded model matches that search.</p>
                  )}
                </div>
                {matchedModels.length > visibleModels.length && (
                  <p className="muted">Showing {visibleModels.length} of {matchedModels.length}. Narrow the search to see the rest.</p>
                )}
                <ModelAdd planId={activePlan.id} onAdd={addModel} />
              </div>
            </article>
          </div>
          <div className="studio-card">
            <p className="muted">
              The saved schedule deletes chats, visitor answers, and uploaded files. Websites, SQL keywords, and questions stay. Last run: {lastPurge}.
              When a request or token limit is reached, the chatbot shows that plan’s message and emails the account once that month.
              The Mail menu holds the server and subject. The account needs an email address.
            </p>
            <div className="form-actions">
              <button className="primary" type="submit" disabled={busy}>
                {busy ? "Saving…" : "Save plan settings"}
              </button>
              <button type="button" className="ghost" onClick={purgeNow} disabled={busy}>
                Delete expired data now
              </button>
            </div>
          </div>
        </form>
      )}

      {tab === "mail" && (
        <form onSubmit={saveMail}>
          <div className="studio-card">
            <h2>Limit emails</h2>
            <p className="muted">
              Sent once each month when an account reaches a request or token limit. Leave the password blank to keep the saved one.
            </p>
            <label className="field">
              SMTP host
              <input value={mail.host} onChange={(event) => setMail({ ...mail, host: event.target.value })} placeholder="smtp.example.com" />
            </label>
            <label className="field">
              Port
              <input type="number" min="1" max="65535" value={mail.port} onChange={(event) => setMail({ ...mail, port: event.target.value })} />
            </label>
            <label className="field">
              Username
              <input value={mail.username} onChange={(event) => setMail({ ...mail, username: event.target.value })} />
            </label>
            <label className="field">
              Password
              <input
                type="password"
                value={mail.password}
                autoComplete="new-password"
                placeholder={mail.password_set ? "Saved. Type a new password to replace it." : ""}
                onChange={(event) => setMail({ ...mail, password: event.target.value })}
              />
            </label>
            <label className="field">
              From address
              <input type="email" value={mail.from_email} onChange={(event) => setMail({ ...mail, from_email: event.target.value })} />
            </label>
            <label className="field">
              Email subject
              <input
                value={mail.subject}
                onChange={(event) => setMail({ ...mail, subject: event.target.value })}
                placeholder="Your chat plan limit was reached"
              />
            </label>
            <label className="check-line">
              <input type="checkbox" checked={Boolean(mail.use_tls)} onChange={(event) => setMail({ ...mail, use_tls: event.target.checked })} />
              Use TLS
            </label>
            <div className="form-actions">
              <button className="primary" disabled={busy}>
                {busy ? "Saving…" : "Save mail"}
              </button>
            </div>
          </div>
        </form>
      )}

      {tab === "issues" && <IssuesPanel />}
      {tab === "prompts" && <PromptsPanel />}
      {tab === "usage" && <UsagePanel />}

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
