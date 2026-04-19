/**
 * Cliente HTTP de la API backend.
 *
 * Convención única: TODOS los endpoints del admin panel viven bajo `/api/*`
 * en FastAPI (auth, inbox, admin/*, templates, widget-config, etc). Este
 * wrapper antepone `/api` a cualquier path que pases — no hay casos
 * especiales.
 *
 * Endpoints públicos (widget embebible, webhooks, LMS) NO pasan por este
 * cliente — los consume el chat.js standalone o sistemas externos.
 *
 * Seguridad: este cliente NO manda `X-Admin-Key`. El admin key es un
 * secret server-side (para scripts/cron/curl manual). Lo que va en el
 * header es `x-session-token` — el JWT de Supabase emitido por
 * POST /api/auth/login.
 */

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("msk_console_token");
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init.headers as Record<string, string> || {}),
  };
  if (token) headers["x-session-token"] = token;

  // Prefijo único. `path` debe empezar con `/` (por ej `/inbox/conversations`
  // o `/auth/users`). Construimos `/api/inbox/conversations` etc.
  const url = `/api${path}`;
  const res = await fetch(url, { ...init, headers });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new ApiError(res.status, `HTTP ${res.status}: ${text || res.statusText}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  get:    <T,>(path: string) => request<T>(path, { method: "GET" }),
  post:   <T,>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  put:    <T,>(path: string, body?: unknown) =>
    request<T>(path, { method: "PUT", body: body ? JSON.stringify(body) : undefined }),
  delete: <T,>(path: string) => request<T>(path, { method: "DELETE" }),
};

export { ApiError };
