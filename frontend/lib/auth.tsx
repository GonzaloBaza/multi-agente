"use client";

/**
 * AuthProvider + hooks de auth.
 *
 * Cambio clave vs versión anterior: ya NO usamos localStorage para
 * guardar el token. La sesión vive en una cookie httpOnly que el backend
 * setea en `/api/v1/auth/login` y el browser manda automáticamente.
 *
 * Flujo:
 *   - Mount     → fetch `/api/v1/auth/me` (con cookie). Si 200, user
 *                  logueado. Si 401, redirect a `/login`.
 *   - Login     → POST `/api/v1/auth/login` con creds. Backend setea
 *                  cookie + devuelve user en body. Guardamos user en
 *                  state; la cookie la maneja el browser.
 *   - Logout    → POST `/api/v1/auth/logout` (borra cookie en backend)
 *                  + limpiamos state.
 *   - getAuthToken — legacy, no se usa; retorna null para compat.
 */
import { createContext, useContext, useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";

export type Role = "admin" | "supervisor" | "agente";

export type User = {
  id: string;
  email: string;
  name: string;
  role: Role;
  queues: string[];
};

type AuthCtx = {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  // Rutas que NO requieren auth — las únicas accesibles sin sesión.
  const PUBLIC_ROUTES = ["/login", "/forgot-password", "/reset-password"];
  const isPublicRoute = PUBLIC_ROUTES.some((p) => pathname?.startsWith(p));

  useEffect(() => {
    // Validamos la sesión contra el backend. Si hay cookie válida,
    // /me devuelve el user. Si no, 401 → redirect a login.
    fetch("/api/v1/auth/me", { credentials: "include" })
      .then(async (r) => {
        if (!r.ok) throw new Error("No session");
        const data = await r.json();
        setUser(data);
      })
      .catch(() => {
        if (!isPublicRoute) router.replace("/login");
      })
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const login = async (email: string, password: string) => {
    const res = await fetch("/api/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const txt = await res.text().catch(() => "");
      throw new Error(`Login falló: ${res.status} ${txt}`);
    }
    const data = await res.json();
    setUser(data.user);
    router.replace("/inbox");
  };

  const logout = () => {
    fetch("/api/v1/auth/logout", { method: "POST", credentials: "include" }).catch(() => {});
    setUser(null);
    router.replace("/login");
  };

  return <AuthContext.Provider value={{ user, loading, login, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth fuera de AuthProvider");
  return ctx;
}

/**
 * Legacy — devuelve null. La cookie httpOnly no es accesible desde JS.
 * Mantenemos el export para no romper imports en archivos que lo
 * referencian pero ya no usamos el valor.
 */
export function getAuthToken(): null {
  return null;
}

// ── Role helpers ─────────────────────────────────────────────────────────────

const ROLE_RANK: Record<Role, number> = { agente: 1, supervisor: 2, admin: 3 };

export function hasRole(user: User | null, min: Role): boolean {
  if (!user) return false;
  return (ROLE_RANK[user.role] ?? 0) >= ROLE_RANK[min];
}

export function hasAnyRole(user: User | null, allowed: Role[]): boolean {
  if (!user) return false;
  return allowed.includes(user.role);
}

export function useRole() {
  const { user, loading } = useAuth();
  return {
    user,
    loading,
    role: user?.role ?? null,
    isAdmin: user?.role === "admin",
    isSupervisor: user?.role === "supervisor" || user?.role === "admin",
    isAgente: !!user,
    hasRole: (min: Role) => hasRole(user, min),
    hasAnyRole: (allowed: Role[]) => hasAnyRole(user, allowed),
  };
}

/**
 * Envoltorio declarativo para ocultar contenido según rol.
 * Ver comentario del patron en la versión anterior.
 */
export function RoleGate({
  children,
  min,
  anyOf,
  denyFallback = null,
  loadingFallback = null,
}: {
  children: React.ReactNode;
  min?: Role;
  anyOf?: Role[];
  denyFallback?: React.ReactNode;
  loadingFallback?: React.ReactNode;
}) {
  const { user, loading } = useAuth();
  if (loading) return <>{loadingFallback}</>;
  const ok = anyOf ? hasAnyRole(user, anyOf) : min ? hasRole(user, min) : !!user;
  if (!ok) return <>{denyFallback}</>;
  return <>{children}</>;
}
