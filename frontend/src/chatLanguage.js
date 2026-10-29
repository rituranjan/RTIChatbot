const STORAGE_KEY = "chat-reply-language";

export function readStoredLanguage() {
  try {
    return localStorage.getItem(STORAGE_KEY) || "";
  } catch {
    return "";
  }
}

export function writeStoredLanguage(code) {
  try {
    if (code) localStorage.setItem(STORAGE_KEY, code);
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* ignored */
  }
}

export function initialChatLanguage(languageConfig) {
  if (!languageConfig?.enabled) return "";
  const options = languageConfig.options || [];
  const codes = new Set(options.map((item) => item.code));
  const stored = readStoredLanguage();
  if (stored && codes.has(stored)) return stored;
  if (languageConfig.required) return "";
  const fallback = languageConfig.default_code || "";
  return codes.has(fallback) ? fallback : options[0]?.code || "";
}
