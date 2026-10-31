const configuredUrl = import.meta.env.VITE_API_URL?.trim() || "/api";
const normalizedUrl = configuredUrl.replace(/\/+$/, "");
const API_ROOT = /\/api$/i.test(normalizedUrl) ? normalizedUrl : `${normalizedUrl}/api`;

const TOKEN_KEY = "access";
const REFRESH_KEY = "refresh";
const USER_KEY = "user";
let refreshInFlight;

function readStorage(key) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStorage(key, value) {
  try {
    if (value == null || value === "") localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    // Keep the session usable if browser storage is unavailable.
  }
}

export const getToken = () => readStorage(TOKEN_KEY);
export const setToken = (value) => writeStorage(TOKEN_KEY, value);
export const getRefresh = () => readStorage(REFRESH_KEY);
export const setRefresh = (value) => writeStorage(REFRESH_KEY, value);
export const getStoredUser = () => {
  try {
    return JSON.parse(readStorage(USER_KEY) || "null");
  } catch {
    return null;
  }
};
export const setStoredUser = (user) =>
  writeStorage(USER_KEY, user == null ? null : JSON.stringify(user));
export const clearSession = () => {
  setToken(null);
  setRefresh(null);
  setStoredUser(null);
};

export class ApiError extends Error {
  constructor(status, data) {
    const detail = data?.detail || data?.message;
    const fields = data && typeof data === "object"
      ? Object.entries(data).map(([key, value]) =>
        `${key}: ${Array.isArray(value) ? value.join(" ") : value}`,
      ).join(" ")
      : data;
    super(detail || fields || "Something went wrong. Please try again.");
    this.status = status;
    this.data = data;
  }
}

function apiUrl(path) {
  if (/^https?:\/\//i.test(path)) return path;
  return `${API_ROOT}/${String(path).replace(/^\//, "")}`;
}

async function readResponse(response) {
  if (response.status === 204) return null;
  const type = response.headers.get("content-type") || "";
  if (type.includes("json")) return response.json();
  const text = await response.text();
  return text || null;
}

function includesDraft(value) {
  if (Array.isArray(value)) return value.some(includesDraft);
  if (value && typeof value === "object") {
    if (value.draft_content === true || value.is_dummy === true || value.status === "ai_draft") {
      return true;
    }
    return Object.values(value).some(includesDraft);
  }
  return false;
}

async function refreshAccessToken() {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      const refresh = getRefresh();
      if (!refresh) throw new ApiError(401, { detail: "Session expired." });
      const response = await fetch(apiUrl("accounts/auth/token/refresh/"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh }),
      });
      const data = await readResponse(response);
      if (!response.ok || !data?.access) throw new ApiError(response.status, data);
      setToken(data.access);
      // SimpleJWT rotates refresh tokens when rotation is configured.
      if (data.refresh) setRefresh(data.refresh);
      return data.access;
    })().finally(() => {
      refreshInFlight = undefined;
    });
  }
  return refreshInFlight;
}

function announceExpiredSession() {
  clearSession();
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event("auth-expired"));
  }
}

export async function request(path, options = {}) {
  const { method = "GET", body, auth = true, headers = {}, _retried = false } = options;
  const requestHeaders = { ...headers };
  const isFormData = typeof FormData !== "undefined" && body instanceof FormData;
  if (body !== undefined && !isFormData) {
    requestHeaders["Content-Type"] ||= "application/json";
  }
  const token = auth ? getToken() : null;
  if (token) requestHeaders.Authorization = `Bearer ${token}`;
  let response;
  try {
    response = await fetch(apiUrl(path), {
      method,
      headers: requestHeaders,
      body: body === undefined ? undefined
        : isFormData ? body : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "Can't reach the server. Check your internet connection.");
  }
  const data = await readResponse(response);
  // #region agent log
  if (String(path).includes("outcome")) {
    fetch('http://127.0.0.1:7816/ingest/8bb20365-a0a3-4b4d-a21c-d7b89d72ef0a',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'5fc7e1'},body:JSON.stringify({sessionId:'5fc7e1',runId:'pre-fix',hypothesisId:'D',location:'api/client.js:request',message:'outcome API response',data:{path,method,status:response.status,ok:response.ok,detail:data&&data.detail,hasId:Boolean(data&&data.id)},timestamp:Date.now()})}).catch(()=>{});
  }
  // #endregion
  if (response.status === 401 && auth && !_retried && !/token\/refresh\/?$/.test(path)) {
    try {
      await refreshAccessToken();
      return request(path, { ...options, _retried: true });
    } catch (error) {
      announceExpiredSession();
      throw error instanceof ApiError ? error : new ApiError(401, error.message);
    }
  }
  if (!response.ok) throw new ApiError(response.status, data);
  if (includesDraft(data) && typeof window !== "undefined") {
    window.dispatchEvent(new Event("draft-content-received"));
  }
  return data;
}

export const apiClient = { request };

