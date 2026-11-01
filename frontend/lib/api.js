const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000/api";

/**
 * Every request in the app goes through here. One place to attach the JWT,
 * one place to normalize errors - new modules just call `api.get/post/...`.
 *
 * The FastAPI backend replies to errors with `{ error: string, detail: ... }`
 * (see backend/app/main.py). `detail` is only used as a fallback.
 */
function errorMessage(data, status) {
  if (typeof data?.error === "string" && data.error) return data.error;
  if (typeof data?.detail === "string" && data.detail) return data.detail;
  if (typeof data?.detail?.message === "string") return data.detail.message;
  return `Request failed (${status})`;
}

async function request(path, { method = "GET", body, token } = {}) {
  let res;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      method,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new Error(
      "Can't reach the IntelliTwin server. Make sure the backend is running."
    );
  }

  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    // An expired or invalid token on an authenticated request: sign out
    // locally and send the user back to the login page.
    if (res.status === 401 && token && typeof window !== "undefined") {
      try {
        localStorage.removeItem("intellitwin_token");
        localStorage.removeItem("intellitwin_user");
      } catch {}
      window.location.assign("/login");
    }

    const err = new Error(errorMessage(data, res.status));
    err.status = res.status;
    err.data = data;
    throw err;
  }

  return data;
}

export const api = {
  get: (path, token) => request(path, { token }),
  post: (path, body, token) => request(path, { method: "POST", body, token }),
  put: (path, body, token) => request(path, { method: "PUT", body, token }),
  del: (path, token) => request(path, { method: "DELETE", token }),
};
