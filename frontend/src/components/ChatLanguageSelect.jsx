export default function ChatLanguageSelect({
  languageConfig,
  value,
  onChange,
  className = "field chat-language-field",
  id = "chat-language",
}) {
  if (!languageConfig?.enabled || !(languageConfig.options || []).length) {
    return null;
  }
  const required = Boolean(languageConfig.required);
  return (
    <label className={className} htmlFor={id}>
      <span className="chat-language-label">Language</span>
      <select
        id={id}
        value={value}
        required={required}
        onChange={(event) => onChange(event.target.value)}
      >
        {!required && (
          <option value="">
            {languageConfig.default_code
              ? `Default (${languageConfig.default_code})`
              : "Default"}
          </option>
        )}
        {(languageConfig.options || []).map((item) => (
          <option key={item.code} value={item.code}>
            {item.display || item.label}
          </option>
        ))}
      </select>
    </label>
  );
}
