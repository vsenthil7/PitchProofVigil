import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api, setToken } from "../lib/api";
import type { Session } from "../lib/types";

interface AuthState {
  session: Session | null;
  login: (tenantId: string, email: string, password: string) => Promise<void>;
  demoLogin: () => Promise<void>;
  register: (
    tenantName: string,
    slug: string,
    email: string,
    password: string,
  ) => Promise<string>;
  logout: () => void;
  switchTenant: (tenantId: string) => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

// In-memory session only â€” no localStorage (unsupported in this runtime, and
// keeping tokens out of storage is the safer default anyway).
export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);

  const login = useCallback(
    async (tenantId: string, email: string, password: string) => {
      const { access_token } = await api.login(tenantId, email, password);
      setToken(access_token);
      // Resolve the full identity (role + tenant list) so the UI can render a
      // role badge, a tenant switcher, and RBAC-aware navigation.
      const me = await api.me();
      setSession({
        token: access_token,
        tenantId: me.tenant_id,
        email: me.email ?? email,
        role: me.role,
        tenantName: me.tenant_name,
        tenants: me.tenants,
      });
    },
    [],
  );

  const demoLogin = useCallback(async () => {
    const { access_token } = await api.demoLogin();
    setToken(access_token);
    const me = await api.me();
    setSession({
      token: access_token,
      tenantId: me.tenant_id,
      email: me.email ?? "",
      role: me.role,
      tenantName: me.tenant_name,
      tenants: me.tenants,
    });
  }, []);

  const register = useCallback(
    async (tenantName: string, slug: string, email: string, password: string) => {
      const { tenant_id } = await api.register(tenantName, slug, email, password);
      await login(tenant_id, email, password);
      return tenant_id;
    },
    [login],
  );

  const logout = useCallback(() => {
    setToken(null);
    setSession(null);
  }, []);

  const switchTenant = useCallback(async (tenantId: string) => {
    // Re-scope the session by minting a tenant-scoped token on the backend,
    // then refreshing identity (role can differ per tenant for non-owners).
    const { access_token } = await api.switchTenant(tenantId);
    setToken(access_token);
    const me = await api.me();
    setSession({
      token: access_token,
      tenantId: me.tenant_id,
      email: me.email ?? "",
      role: me.role,
      tenantName: me.tenant_name,
      tenants: me.tenants,
    });
  }, []);

  const value = useMemo(
    () => ({ session, login, demoLogin, register, logout, switchTenant }),
    [session, login, demoLogin, register, logout, switchTenant],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (ctx === null) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
