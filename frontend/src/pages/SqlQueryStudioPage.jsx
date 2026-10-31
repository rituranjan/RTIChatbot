import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";

const TABS = [
  { id: "setup", label: "Setup & mode" },
  { id: "keywords", label: "SQL keyword queries" },
  { id: "mappings", label: "Column mappings" },
  { id: "test", label: "Test natural language" },
];

const EMPTY_QUERY = { name: "", connection: "", keywords: "", sql_text: "", enabled: true };

const EMPTY_COLUMN = {
  semantic_table: "",
  physical_column: "",
  sql_alias: "",
  display_name: "",
  description: "",
  searchable: true,
  filterable: true,
  is_active: true,
  synonymText: "",
};

function rowsOf(data) {
  return data?.results || data || [];
}

function synonymText(col) {
  return (col.synonyms || [])
    .filter((s) => s.is_active !== false)
    .map((s) => s.synonym)
    .join(", ");
}

function resolveMode(cfg) {
  if (cfg.chat_sql_mode === "semantic" || cfg.chat_sql_mode === "keywords") {
    return cfg.chat_sql_mode;
  }
  return cfg.enabled ? "semantic" : "keywords";
}

export default function SqlQueryStudioPage({ defaultTab = "setup" }) {
  const [tab, setTab] = useState(defaultTab);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const [connections, setConnections] = useState([]);
  const [queries, setQueries] = useState([]);
  const [engine, setEngine] = useState(null);
  const [tables, setTables] = useState([]);

  const [queryForm, setQueryForm] = useState(EMPTY_QUERY);
  const [queryEditing, setQueryEditing] = useState(null);
  const [queryPreview, setQueryPreview] = useState("");

  const [columnForm, setColumnForm] = useState(EMPTY_COLUMN);
  const [mappingEdits, setMappingEdits] = useState({});
  const [mappingEditingId, setMappingEditingId] = useState(null);

  const [question, setQuestion] = useState("Show applicants from postal code 700053");
  const [nlPreview, setNlPreview] = useState(null);

  const semCfg = engine?.config || {};
  const plan = engine?.plan || {};
  const canKeywords = plan.sql_keyword_enabled !== false;
  const canSemantic = plan.semantic_sql_enabled !== false;
  const chatMode = resolveMode(semCfg);

  const flatColumns = useMemo(() => {
    const out = [];
    for (const table of tables) {
      for (const col of table.columns || []) {
        out.push({
          ...col,
          table_label: table.display_name || table.table_name,
          semantic_table: table.id,
        });
      }
    }
    return out.sort((a, b) =>
      `${a.table_label}.${a.display_name}`.localeCompare(`${b.table_label}.${b.display_name}`)
    );
  }, [tables]);

  async function load() {
    const [connectionData, queryData, eng, tbl] = await Promise.all([
      api.listConnections(),
      api.listSqlQueries(),
      api.semanticEngine().catch(() => null),
      api.listSemanticTables().catch(() => ({ results: [] })),
    ]);
    setConnections(rowsOf(connectionData));
    setQueries(rowsOf(queryData));
    setEngine(eng);
    setTables(rowsOf(tbl));
    setMappingEdits({});
    setMappingEditingId(null);
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    setTab(defaultTab);
  }, [defaultTab]);

  async function saveEngine(patch) {
    setError("");
    try {
      const data = await api.saveSemanticEngine(patch);
      setEngine((prev) => ({ ...prev, config: data }));
      setNotice("Workspace SQL settings saved.");
    } catch (err) {
      setError(err.message);
    }
  }

  async function setChatMode(mode) {
    if (mode === "keywords" && !canKeywords) return;
    if (mode === "semantic" && !canSemantic) return;
    await saveEngine({ chat_sql_mode: mode });
  }

  function queryPayload() {
    return {
      name: queryForm.name,
      connection: queryForm.connection,
      keywords: queryForm.keywords.split(",").map((item) => item.trim()).filter(Boolean),
      sql_text: queryForm.sql_text,
      enabled: queryForm.enabled,
    };
  }

  async function saveQuery(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    setQueryPreview("");
    try {
      await api.saveSqlQuery(queryPayload(), queryEditing);
      setQueryForm({ ...EMPTY_QUERY, connection: queryForm.connection });
      setQueryEditing(null);
      await load();
      setNotice("Keyword query saved.");
    } catch (err) {
      setError(err.message);
    }
  }

  function editQuery(row) {
    setQueryEditing(row.id);
    setQueryForm({
      name: row.name,
      connection: row.connection,
      keywords: (row.keywords || []).join(", "),
      sql_text: row.sql_text,
      enabled: row.enabled,
    });
    setQueryPreview("");
  }

  async function removeQuery(row) {
    if (!window.confirm(`Delete ${row.name}?`)) return;
    try {
      await api.deleteSqlQuery(row.id);
      if (queryEditing === row.id) {
        setQueryEditing(null);
        setQueryForm(EMPTY_QUERY);
      }
      if (semCfg.report_query === row.id) {
        await saveEngine({ report_query: null });
      }
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function runQueryTest(id) {
    setError("");
    setNotice("");
    try {
      const result = await api.testSqlQuery(id);
      const lines = (result.rows || []).map((row) => JSON.stringify(row));
      setQueryPreview(lines.length ? lines.join("\n") : "The query returned no rows.");
    } catch (err) {
      setError(err.message);
    }
  }

  function mappingDraft(col) {
    if (mappingEdits[col.id]) return mappingEdits[col.id];
    return {
      display_name: col.display_name || "",
      physical_column: col.physical_column || "",
      sql_alias: col.sql_alias || "",
      description: col.description || "",
      searchable: col.searchable !== false,
      filterable: col.filterable !== false,
      is_active: col.is_active !== false,
      synonymText: synonymText(col),
    };
  }

  function patchMappingDraft(id, patch) {
    setMappingEdits((current) => ({
      ...current,
      [id]: { ...(current[id] || {}), ...patch },
    }));
  }

  async function syncSynonyms(columnId, before, text) {
    const wanted = text
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    const existing = before || [];
    for (const row of existing) {
      if (!wanted.includes(row.synonym)) {
        await api.deleteSemanticSynonym(row.id);
      }
    }
    const have = new Set(existing.map((r) => r.synonym));
    for (const word of wanted) {
      if (!have.has(word)) {
        await api.saveSemanticSynonym({ semantic_column: columnId, synonym: word, is_active: true });
      }
    }
  }

  async function saveMappingRow(col) {
    setBusy(true);
    setError("");
    try {
      const draft = mappingDraft(col);
      await api.saveSemanticColumn(
        {
          display_name: draft.display_name,
          physical_column: draft.physical_column,
          sql_alias: draft.sql_alias,
          description: draft.description,
          searchable: draft.searchable,
          filterable: draft.filterable,
          is_active: draft.is_active,
        },
        col.id
      );
      await syncSynonyms(col.id, col.synonyms, draft.synonymText);
      setNotice("Column mapping saved.");
      setMappingEditingId(null);
      setMappingEdits((current) => {
        const next = { ...current };
        delete next[col.id];
        return next;
      });
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function addColumn(event) {
    event.preventDefault();
    if (!columnForm.semantic_table) {
      setError("Choose a table for the new column.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const created = await api.saveSemanticColumn({
        semantic_table: columnForm.semantic_table,
        physical_column: columnForm.physical_column,
        sql_alias: columnForm.sql_alias,
        display_name: columnForm.display_name,
        description: columnForm.description,
        searchable: columnForm.searchable,
        filterable: columnForm.filterable,
        is_active: columnForm.is_active,
      });
      if (columnForm.synonymText.trim()) {
        await syncSynonyms(created.id, [], columnForm.synonymText);
      }
      setColumnForm(EMPTY_COLUMN);
      setNotice("Column added.");
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function removeColumn(col) {
    if (!window.confirm(`Remove mapping for ${col.display_name || col.physical_column}?`)) return;
    try {
      await api.deleteSemanticColumn(col.id);
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function bootstrapMappings() {
    if (
      !window.confirm(
        "Import starter column mappings (synonyms only)? Your saved mappings stay unless you choose replace on a full re-import."
      )
    ) {
      return;
    }
    setBusy(true);
    try {
      const result = await api.semanticBootstrap(false);
      setNotice(`Imported ${result.columns} column mappings.`);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function runNlPreview(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      setNlPreview(await api.semanticPreview(question));
    } catch (err) {
      if (err.payload && (err.payload.sql || err.payload.error)) {
        setNlPreview(err.payload);
      } else {
        setError(err.message || `Request failed (${err.status || ""})`);
        setNlPreview(null);
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="studio">
      <header className="studio-head">
        <div>
          <h1>SQL &amp; natural language</h1>
          <p className="muted">
            One place for keyword SQL, semantic Text-to-SQL, and column-to-field mappings. Chat uses exactly one mode
            at a time on the server—pick it below. Mappings are saved in your workspace (no re-import each time).
          </p>
        </div>
      </header>
      {error && <div className="form-error">{error}</div>}
      {notice && <p className="form-ok">{notice}</p>}

      <div className="semantic-tabs">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={tab === item.id ? "nav-link active" : "nav-link"}
            onClick={() => setTab(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>

      {tab === "setup" && (
        <>
          <div className="studio-card studio-form">
            <h2>Chat server mode</h2>
            <p className="muted span-2">
              Plan capabilities: SQL keywords {canKeywords ? "on" : "off"} · Semantic NL{" "}
              {canSemantic ? "on" : "off"} (admin can change per plan under Settings → Global).
            </p>
            <fieldset className="span-2 mode-picker">
              <label className="check-row">
                <input
                  type="radio"
                  name="chat_sql_mode"
                  checked={chatMode === "keywords"}
                  disabled={!canKeywords}
                  onChange={() => setChatMode("keywords")}
                />
                SQL keyword matching — chat runs saved keyword queries only
              </label>
              <label className="check-row">
                <input
                  type="radio"
                  name="chat_sql_mode"
                  checked={chatMode === "semantic"}
                  disabled={!canSemantic}
                  onChange={() => setChatMode("semantic")}
                />
                Semantic Text-to-SQL — chat uses natural language + column mappings
              </label>
            </fieldset>
            <label className="span-2">
              Report SQL query (canonical SELECT for semantic mode)
              <select
                value={semCfg.report_query || ""}
                onChange={(event) => saveEngine({ report_query: event.target.value || null })}
              >
                <option value="">Choose a saved keyword query</option>
                {queries.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name} ({item.connection_name})
                  </option>
                ))}
              </select>
            </label>
            <p className="muted span-2">
              Dictionary columns: {engine?.column_count ?? 0}. Active mode:{" "}
              <strong>{chatMode === "semantic" ? "Semantic Text-to-SQL" : "SQL keywords"}</strong>
            </p>
          </div>
        </>
      )}

      {tab === "keywords" && (
        <>
          <form className="studio-card studio-form" onSubmit={saveQuery}>
            <h2 className="span-2">{queryEditing ? "Edit keyword query" : "New keyword query"}</h2>
            <label>
              Name
              <input
                value={queryForm.name}
                onChange={(event) => setQueryForm({ ...queryForm, name: event.target.value })}
                required
                placeholder="Payment status"
              />
            </label>
            <label>
              Database
              <select
                value={queryForm.connection}
                onChange={(event) => setQueryForm({ ...queryForm, connection: event.target.value })}
                required
              >
                <option value="">Choose</option>
                {connections.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="span-2">
              Keywords, separated by commas
              <input
                value={queryForm.keywords}
                onChange={(event) => setQueryForm({ ...queryForm, keywords: event.target.value })}
                required
                placeholder="Payment, Status, AccountNo"
              />
            </label>
            <label className="span-2">
              SQL query
              <textarea
                rows={5}
                value={queryForm.sql_text}
                onChange={(event) => setQueryForm({ ...queryForm, sql_text: event.target.value })}
                required
              />
            </label>
            <label className="check-row">
              <input
                type="checkbox"
                checked={queryForm.enabled}
                onChange={(event) => setQueryForm({ ...queryForm, enabled: event.target.checked })}
              />
              Enabled
            </label>
            <div className="form-actions">
              <button className="primary" type="submit">
                {queryEditing ? "Update" : "Save"}
              </button>
              {queryEditing && (
                <button
                  type="button"
                  className="link"
                  onClick={() => {
                    setQueryEditing(null);
                    setQueryForm(EMPTY_QUERY);
                  }}
                >
                  Cancel
                </button>
              )}
            </div>
          </form>
          {queryPreview && <pre className="studio-card sql-preview">{queryPreview}</pre>}
          <div className="studio-card">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Database</th>
                  <th>Keywords</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {queries.map((row) => (
                  <tr key={row.id}>
                    <td>
                      {row.name}
                      {!row.enabled && <span className="muted"> · off</span>}
                      {semCfg.report_query === row.id && <span className="muted"> · semantic report</span>}
                    </td>
                    <td>{row.connection_name}</td>
                    <td>{(row.keywords || []).join(", ")}</td>
                    <td className="row-actions">
                      <button type="button" className="link" onClick={() => runQueryTest(row.id)}>
                        Run
                      </button>
                      <button type="button" className="link" onClick={() => editQuery(row)}>
                        Edit
                      </button>
                      <button type="button" className="link danger" onClick={() => removeQuery(row)}>
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
                {queries.length === 0 && (
                  <tr>
                    <td colSpan={4} className="muted">
                      No keyword queries yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}

      {tab === "mappings" && (
        <>
          <div className="studio-card">
            <div className="form-actions" style={{ marginBottom: 12 }}>
              <button type="button" className="primary" disabled={busy} onClick={bootstrapMappings}>
                Import starter mappings
              </button>
            </div>
            <p className="muted">
              Map each business field to a SQL column alias. Synonyms help the semantic engine match user phrases.
              Edits are stored here—bootstrap is optional.
            </p>
          </div>

          <form className="studio-card studio-form" onSubmit={addColumn}>
            <h2 className="span-2">Add column mapping</h2>
            <label>
              Table
              <select
                value={columnForm.semantic_table}
                onChange={(event) => setColumnForm({ ...columnForm, semantic_table: event.target.value })}
              >
                <option value="">Choose</option>
                {tables.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.display_name || t.table_name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Display name (field label)
              <input
                value={columnForm.display_name}
                onChange={(event) => setColumnForm({ ...columnForm, display_name: event.target.value })}
                required
              />
            </label>
            <label>
              Physical column
              <input
                value={columnForm.physical_column}
                onChange={(event) => setColumnForm({ ...columnForm, physical_column: event.target.value })}
                required
              />
            </label>
            <label>
              SQL alias (in report query)
              <input
                value={columnForm.sql_alias}
                onChange={(event) => setColumnForm({ ...columnForm, sql_alias: event.target.value })}
                required
              />
            </label>
            <label className="span-2">
              Synonyms (comma-separated)
              <input
                value={columnForm.synonymText}
                onChange={(event) => setColumnForm({ ...columnForm, synonymText: event.target.value })}
                placeholder="tracking number, consignment no"
              />
            </label>
            <div className="form-actions span-2">
              <button type="submit" className="primary" disabled={busy}>
                Add mapping
              </button>
            </div>
          </form>

          <div className="studio-card">
            <table className="data-table mapping-table">
              <thead>
                <tr>
                  <th>Table</th>
                  <th>Field / SQL</th>
                  <th>Synonyms</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {flatColumns.map((col) => {
                  const editing = mappingEditingId === col.id;
                  const draft = mappingDraft(col);
                  return (
                    <tr key={col.id}>
                      <td>{col.table_label}</td>
                      <td>
                        {editing ? (
                          <div className="mapping-edit-fields">
                            <input
                              placeholder="Display name"
                              value={draft.display_name}
                              onChange={(e) => patchMappingDraft(col.id, { display_name: e.target.value })}
                            />
                            <input
                              placeholder="Physical column"
                              value={draft.physical_column}
                              onChange={(e) => patchMappingDraft(col.id, { physical_column: e.target.value })}
                            />
                            <input
                              placeholder="SQL alias"
                              value={draft.sql_alias}
                              onChange={(e) => patchMappingDraft(col.id, { sql_alias: e.target.value })}
                            />
                          </div>
                        ) : (
                          <>
                            <strong>{col.display_name}</strong>
                            <div className="muted">
                              {col.physical_column} → {col.sql_alias}
                            </div>
                          </>
                        )}
                      </td>
                      <td>
                        {editing ? (
                          <input
                            value={draft.synonymText}
                            onChange={(e) => patchMappingDraft(col.id, { synonymText: e.target.value })}
                          />
                        ) : (
                          synonymText(col) || "—"
                        )}
                      </td>
                      <td className="row-actions">
                        {editing ? (
                          <>
                            <button type="button" className="link" disabled={busy} onClick={() => saveMappingRow(col)}>
                              Save
                            </button>
                            <button
                              type="button"
                              className="link"
                              onClick={() => {
                                setMappingEditingId(null);
                                setMappingEdits((c) => {
                                  const n = { ...c };
                                  delete n[col.id];
                                  return n;
                                });
                              }}
                            >
                              Cancel
                            </button>
                          </>
                        ) : (
                          <>
                            <button type="button" className="link" onClick={() => setMappingEditingId(col.id)}>
                              Edit
                            </button>
                            <button type="button" className="link danger" onClick={() => removeColumn(col)}>
                              Delete
                            </button>
                          </>
                        )}
                      </td>
                    </tr>
                  );
                })}
                {flatColumns.length === 0 && (
                  <tr>
                    <td colSpan={4} className="muted">
                      No mappings yet. Import starter mappings or add a column (requires a semantic table from
                      bootstrap).
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}

      {tab === "test" && (
        <form className="studio-card studio-form" onSubmit={runNlPreview}>
          <p className="muted span-2">
            Preview uses semantic mode settings. Switch mode on the Setup tab if chat should use keywords instead.
          </p>
          <label className="span-2">
            Natural-language question
            <textarea rows={3} value={question} onChange={(event) => setQuestion(event.target.value)} />
          </label>
          <div className="form-actions span-2">
            <button type="submit" className="primary" disabled={busy}>
              {busy ? "Running…" : "Preview SQL & run"}
            </button>
          </div>
          {nlPreview && (
            <div className="span-2 semantic-preview">
              {nlPreview.error && <div className="form-error">{nlPreview.error}</div>}
              {nlPreview.run_error && <div className="form-error">{nlPreview.run_error}</div>}
              {nlPreview.run_hint && <p className="muted">{nlPreview.run_hint}</p>}
              <pre>{nlPreview.sql || "(no SQL generated)"}</pre>
              <p className="muted">Params: {JSON.stringify(nlPreview.params || [])}</p>
              <pre>{JSON.stringify(nlPreview.rows || [], null, 2)}</pre>
            </div>
          )}
        </form>
      )}
    </section>
  );
}
