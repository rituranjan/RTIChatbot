import { useState } from "react";

export default function IntakeForm({ questions, onSubmit, busy, error }) {
  const [values, setValues] = useState({});

  function submit(event) {
    event.preventDefault();
    onSubmit(values);
  }

  return (
    <form className="intake-form" onSubmit={submit}>
      <strong>Before we start</strong>
      <p className="muted">Please answer these questions. Then you can chat.</p>
      {questions.map((question) => (
        <label key={question.field_key}>
          {question.label}
          {question.required ? " *" : ""}
          <input
            value={values[question.field_key] || ""}
            placeholder={question.placeholder || ""}
            required={question.required}
            onChange={(event) =>
              setValues((current) => ({ ...current, [question.field_key]: event.target.value }))
            }
          />
        </label>
      ))}
      {error && <div className="form-error">{error}</div>}
      <button className="primary" type="submit" disabled={busy}>
        {busy ? "Saving…" : "Start chat"}
      </button>
    </form>
  );
}
