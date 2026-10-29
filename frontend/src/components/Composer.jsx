import { useRef, useState } from "react";
import ChatLanguageSelect from "./ChatLanguageSelect";

export default function Composer({
  onSend,
  disabled,
  languageConfig,
  chatLanguage,
  onLanguageChange,
}) {
  const [value, setValue] = useState("");
  const ref = useRef(null);
  const languageOn = languageConfig?.enabled && (languageConfig.options || []).length > 0;
  const languageRequired = languageOn && languageConfig.required;
  const languageOk = !languageRequired || Boolean(chatLanguage);
  const sendDisabled = disabled || !value.trim() || !languageOk;

  function submit() {
    const text = value.trim();
    if (!text || sendDisabled) return;
    onSend(text, chatLanguage);
    setValue("");
    requestAnimationFrame(() => ref.current?.focus());
  }

  function handleKey(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  return (
    <div className="composer">
      {languageOn && (
        <ChatLanguageSelect
          languageConfig={languageConfig}
          value={chatLanguage}
          onChange={onLanguageChange}
        />
      )}
      <textarea
        ref={ref}
        rows={2}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKey}
        disabled={disabled || (languageRequired && !chatLanguage)}
        placeholder={
          languageRequired && !chatLanguage
            ? "Choose a language, then type your message."
            : "Send a message. Enter to send, Shift+Enter for newline."
        }
      />
      <button className="primary" onClick={submit} disabled={sendDisabled}>
        Send
      </button>
    </div>
  );
}
