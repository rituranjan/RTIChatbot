import { Fragment, useEffect, useState } from "react";
import { api } from "../api/client";

function today() {
  return new Date().toISOString().slice(0, 10);
}

function monthAgo() {
  const date = new Date();
  date.setDate(date.getDate() - 30);
  return date.toISOString().slice(0, 10);
}

export default function InsightsPage({ mode }) {
  const [start, setStart] = useState(monthAgo);
  const [end, setEnd] = useState(today);
  const [keyword, setKeyword] = useState("");
  const [rows, setRows] = useState([]);
  const [openId, setOpenId] = useState(null);
  const [transcript, setTranscript] = useState([]);
  const [error, setError] = useState("");

  async function load(event) {
    event?.preventDefault();
    setError("");
    try {
      const data = await api.insights({ start, end, q: keyword });
      setRows(mode === "visitors" ? data.visitors || [] : data.chats || []);
      setOpenId(null);
      setTranscript([]);
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    load();
    // Reload when switching between visitor answers and stored chats.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  async function openChat(id) {
    if (openId === id) {
      setOpenId(null);
      return;
    }
    setOpenId(id);
    try {
      const data = await api.getConversation(id);
      setTranscript(data.messages || []);
    } catch (err) {
      setError(err.message);
    }
  }

  const title = mode === "visitors" ? "Visitor answers" : "Stored chats";
  const intro = mode === "visitors"
    ? "Name, email, phone, and the other answers collected before chat. Filter by date and a keyword."
    : "Every app chat and website chat is stored here. Filter by date and a keyword in the messages or answers.";

  return (
    <section className="studio">
      <header className="studio-head">
        <div>
          <h1>{title}</h1>
          <p className="muted">{intro}</p>
        </div>
      </header>
      <form className="studio-card filter-bar" onSubmit={load}>
        <label>
          From
          <input type="date" value={start} onChange={(event) => setStart(event.target.value)} />
        </label>
        <label>
          To
          <input type="date" value={end} onChange={(event) => setEnd(event.target.value)} />
        </label>
        <label>
          Keyword
          <input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="Payment, email, account" />
        </label>
        <button className="primary" type="submit">Apply</button>
      </form>
      {error && <div className="form-error">{error}</div>}
      <div className="studio-card">
        <table className="data-table">
          <thead>
            <tr>
              <th>When</th>
              <th>Where</th>
              <th>Answers</th>
              <th>Messages</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <Fragment key={row.id}>
                <tr>
                  <td>{new Date(row.created_at).toLocaleString()}</td>
                  <td>{row.channel === "website" ? "Website" : "App"}</td>
                  <td>
                    {Object.keys(row.answers || {}).length === 0
                      ? "—"
                      : Object.entries(row.answers).map(([key, value]) => (
                          <div key={key}><strong>{key}:</strong> {value}</div>
                        ))}
                  </td>
                  <td>
                    {row.message_count}
                    {row.preview && <div className="muted">{row.preview}</div>}
                  </td>
                  <td>
                    <button type="button" className="link" onClick={() => openChat(row.id)}>
                      {openId === row.id ? "Hide" : "Open"}
                    </button>
                  </td>
                </tr>
                {openId === row.id && (
                  <tr>
                    <td colSpan={5}>
                      <div className="transcript">
                        {transcript.map((message) => (
                          <p key={message.id}>
                            <strong>{message.role === "user" ? "Visitor" : "Assistant"}:</strong> {message.content}
                          </p>
                        ))}
                        {transcript.length === 0 && <p className="muted">No messages yet.</p>}
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={5} className="muted">Nothing in this date range.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
