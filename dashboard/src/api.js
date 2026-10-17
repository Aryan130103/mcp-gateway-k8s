const KEY = "gw_session";

export const getSession = () => {
  try { return JSON.parse(sessionStorage.getItem(KEY)); } catch { return null; }
};
export const saveSession = (s) => {
  try { sessionStorage.setItem(KEY, JSON.stringify(s)); } catch { /* storage unavailable */ }
};
export const clearSession = () => {
  try { sessionStorage.removeItem(KEY); } catch { /* storage unavailable */ }
};

export async function api(path, { method = "GET", body } = {}) {
  const session = getSession();
  const res = await fetch(path, {
    method,
    headers: {
      ...(body ? { "Content-Type": "application/json" } : {}),
      ...(session ? { Authorization: `Bearer ${session.token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401 && session && path !== "/api/login") {
    clearSession();
    window.location.reload();
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = data.detail;
    const msg = Array.isArray(d) ? d.map((x) => x.msg).join("; ")
      : typeof d === "string" ? d : `Request failed (${res.status})`;
    throw new Error(msg);
  }
  return data;
}
