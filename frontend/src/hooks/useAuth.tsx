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
  register: (
    tenantName: string,
    slug: string,
    email: string,
    password: string,
  ) => Promise<string>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

// In-memory session only — no localStorage (unsupported in this runtime, and
// keeping tokens out of storage is the safer default anyway).
export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);

  const login = useCallback(
    async (tenantId: string, email: string, password: string) => {
      const { access_token } = await api.login(tenantId, email, password);
      setToken(access_token);
      setSession({ token: access_token, tenantId, email });
    },
    [],
  );

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

  const value = useMemo(
    () => ({ session, login, register, logout }),
    [session, login, register, logout],
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
