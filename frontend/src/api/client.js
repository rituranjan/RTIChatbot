import { reportUiError } from "../reportUiError";

async function getCsrfToken() {
  await fetch("/api/auth/csrf/", { credentials: "include" });
  const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : "";
}

async function request(path, { method = "GET", body, headers = {}, isForm = false } = {}) {
  const opts = { method, credentials: "include", headers: { ...headers } };

  if (body !== undefined && body !== null) {
    if (isForm) {
      opts.body = body;
    } else {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
  }

  if (method !== "GET" && method !== "HEAD") {
    const token = await getCsrfToken();
    if (token) opts.headers["X-CSRFToken"] = token;
  }

  const res = await fetch(path, opts);
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!res.ok) {
    const detail =
      (data && (data.detail || data.error)) || `Request failed (${res.status})`;
    const error = new Error(detail);
    error.status = res.status;
    if (res.status >= 500 && !path.includes("/api/client-errors")) {
      reportUiError(error, { path });
    }
    throw error;
  }
  return data;
}

export const api = {
  register: (payload) => request("/api/auth/register/", { method: "POST", body: payload }),
  login: (payload) => request("/api/auth/login/", { method: "POST", body: payload }),
  logout: () => request("/api/auth/logout/", { method: "POST" }),
  me: () => request("/api/auth/me/"),

  listConversations: () => request("/api/conversations/"),
  createConversation: (title = "New conversation", answers) =>
    request("/api/conversations/", {
      method: "POST",
      body: answers ? { title, answers } : { title },
    }),
  getConversation: (id) => request(`/api/conversations/${id}/`),
  renameConversation: (id, title) =>
    request(`/api/conversations/${id}/`, { method: "PATCH", body: { title } }),
  deleteConversation: (id) =>
    request(`/api/conversations/${id}/`, { method: "DELETE" }),

  sendMessage: (conversationId, message, language = "") =>
    request("/api/chat/", {
      method: "POST",
      body: { conversation_id: conversationId, message, language },
    }),

  listDocuments: () => request("/api/documents/"),
  uploadDocument: (file) => {
    const form = new FormData();
    form.append("file", file);
    return request("/api/documents/", { method: "POST", body: form, isForm: true });
  },
  deleteDocument: (id) => request(`/api/documents/${id}/`, { method: "DELETE" }),
  reindexDocument: (id) => request(`/api/documents/${id}/reindex/`, { method: "POST" }),

  listFolderSources: () => request("/api/folder-sources/"),
  indexFolderSource: (id) =>
    request(`/api/folder-sources/${id}/index/`, { method: "POST" }),

  health: () => request("/api/system/health/"),
  ollamaStatus: () => request("/api/system/ollama/"),

  myEmbed: () => request("/api/embed/mine/"),
  saveEmbed: (payload) => request("/api/embed/mine/", { method: "PATCH", body: payload }),

  renameDocument: (id, title) =>
    request(`/api/documents/${id}/`, { method: "PATCH", body: { title } }),
  downloadDocument: async (id, filename) => {
    const res = await fetch(`/api/documents/${id}/download/`, { credentials: "include" });
    if (!res.ok) throw new Error("Download failed.");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename || "download";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  },

  listErrors: () => request("/api/admin-settings/errors/"),
  errorScreenshot: async (id) => {
    const res = await fetch(`/api/admin-settings/errors/${id}/screenshot/`, { credentials: "include" });
    if (!res.ok) throw new Error("Screenshot unavailable.");
    return res.blob();
  },
  llmUsage: () => request("/api/admin-settings/usage/"),
  listPrompts: () => request("/api/admin-settings/prompts/"),
  savePrompt: (slug, payload) =>
    request(`/api/admin-settings/prompts/${encodeURIComponent(slug)}/`, {
      method: "PATCH",
      body: payload,
    }),
  adminSettings: () => request("/api/admin-settings/"),
  saveAdminSettings: (payload) =>
    request("/api/admin-settings/", { method: "PATCH", body: payload }),
  purgeAdminSettings: () => request("/api/admin-settings/purge/", { method: "POST" }),
  openRouterModels: (query) =>
    request(`/api/admin-settings/models/${query ? `?q=${encodeURIComponent(query)}` : ""}`),
  myPlan: () => request("/api/my-plan/"),
  saveMyPlan: (payload) =>
    request("/api/my-plan/", {
      method: "PATCH",
      body: typeof payload === "string" ? { selected_model: payload } : payload,
    }),

  listAccounts: () => request("/api/admin/accounts/"),
  createAccount: (payload) =>
    request("/api/admin/accounts/", { method: "POST", body: payload }),
  updateAccount: (id, payload) =>
    request(`/api/admin/accounts/${id}/`, { method: "PATCH", body: payload }),
  deleteAccount: (id) => request(`/api/admin/accounts/${id}/`, { method: "DELETE" }),
  provisionAccount: (id) =>
    request(`/api/admin/accounts/${id}/provision/`, { method: "POST", body: {} }),
  actAs: (userId) =>
    request("/api/admin/act-as/", { method: "POST", body: { user_id: userId } }),

  listWebsites: () => request("/api/websites/"),
  saveWebsite: (payload, id) =>
    request(id ? `/api/websites/${id}/` : "/api/websites/", {
      method: id ? "PATCH" : "POST",
      body: payload,
    }),
  deleteWebsite: (id) => request(`/api/websites/${id}/`, { method: "DELETE" }),
  recrawlWebsite: (id) => request(`/api/websites/${id}/recrawl/`, { method: "POST" }),

  listConnections: () => request("/api/connections/"),
  saveConnection: (payload, id) =>
    request(id ? `/api/connections/${id}/` : "/api/connections/", {
      method: id ? "PATCH" : "POST",
      body: payload,
    }),
  deleteConnection: (id) => request(`/api/connections/${id}/`, { method: "DELETE" }),
  testConnection: (payload) =>
    request("/api/connections/test/", { method: "POST", body: payload }),

  listSqlQueries: () => request("/api/sql-queries/"),
  saveSqlQuery: (payload, id) =>
    request(id ? `/api/sql-queries/${id}/` : "/api/sql-queries/", {
      method: id ? "PATCH" : "POST",
      body: payload,
    }),
  deleteSqlQuery: (id) => request(`/api/sql-queries/${id}/`, { method: "DELETE" }),
  testSqlQuery: (id) => request(`/api/sql-queries/${id}/test/`, { method: "POST" }),

  listIntake: () => request("/api/intake/"),
  saveIntake: (payload, id) =>
    request(id ? `/api/intake/${id}/` : "/api/intake/", {
      method: id ? "PATCH" : "POST",
      body: payload,
    }),
  deleteIntake: (id) => request(`/api/intake/${id}/`, { method: "DELETE" }),
  saveProfile: (conversationId, answers) =>
    request(`/api/conversations/${conversationId}/profile/`, {
      method: "POST",
      body: { answers },
    }),

  insights: (params) => {
    const query = new URLSearchParams();
    if (params.start) query.set("start", params.start);
    if (params.end) query.set("end", params.end);
    if (params.q) query.set("q", params.q);
    const suffix = query.toString();
    return request(`/api/insights/${suffix ? `?${suffix}` : ""}`);
  },
};