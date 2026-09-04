const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

const ACCESS_KEY = "gstflow_access";
const REFRESH_KEY = "gstflow_refresh";

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ACCESS_KEY);
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(REFRESH_KEY);
}

export function setTokens(access: string, refresh: string) {
  localStorage.setItem(ACCESS_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
}

export function clearTokens() {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

export class ApiError extends Error {
  status: number;
  data: unknown;
  constructor(status: number, data: unknown) {
    const detail =
      typeof data === "object" && data !== null && "detail" in data
        ? String((data as { detail: unknown }).detail)
        : JSON.stringify(data);
    super(detail || `Request failed with status ${status}`);
    this.status = status;
    this.data = data;
  }
}

async function refreshAccessToken(): Promise<string | null> {
  const refresh = getRefreshToken();
  if (!refresh) return null;
  const res = await fetch(`${API_BASE}/api/auth/refresh/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh }),
  });
  if (!res.ok) return null;
  const data = await res.json();
  localStorage.setItem(ACCESS_KEY, data.access);
  return data.access as string;
}

type RequestOptions = {
  method?: string;
  body?: unknown;
  isFormData?: boolean;
  auth?: boolean;
};

export async function apiFetch<T = unknown>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, isFormData = false, auth = true } = options;

  const doFetch = async (accessToken: string | null): Promise<Response> => {
    const headers: Record<string, string> = {};
    if (!isFormData) headers["Content-Type"] = "application/json";
    if (auth && accessToken) headers["Authorization"] = `Bearer ${accessToken}`;

    return fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : isFormData ? (body as FormData) : JSON.stringify(body),
    });
  };

  let res = await doFetch(getAccessToken());

  if (res.status === 401 && auth) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      res = await doFetch(newToken);
    }
  }

  if (!res.ok) {
    let data: unknown = null;
    try {
      data = await res.json();
    } catch {
      /* no JSON body */
    }
    throw new ApiError(res.status, data);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}
