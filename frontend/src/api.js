import { apiClient, ApiError, getRefresh, getStoredUser, getToken, request,
  setRefresh, setStoredUser, setToken } from "./api/client.js";

// Compatibility wrapper used by the existing pages. All HTTP traffic goes
// through the shared client so auth refresh and draft detection stay global.
export { apiClient, ApiError, getRefresh, getStoredUser, getToken,
  setRefresh, setStoredUser, setToken };

export async function api(path, { method = "GET", body, auth = true } = {}) {
  return request(path, { method, body, auth });
}

function toPath(nextUrl) {
  const url = new URL(nextUrl, window.location.origin);
  return url.pathname.replace(/^\/api/, "") + url.search;
}

export async function getAll(path) {
  let items = [];
  let url = path;
  for (let page = 0; page < 20 && url; page += 1) {
    const data = await api(url);
    if (Array.isArray(data)) return data;
    items = items.concat(data.results || []);
    url = data.next ? toPath(data.next) : null;
  }
  return items;
}

export function trackEvent(name, sessionId = null, props = {}) {
  return api("/events/", { method: "POST", body: {
    name, ...(sessionId ? { session_id: Number(sessionId) } : {}), props,
  } }).catch(() => null);
}
