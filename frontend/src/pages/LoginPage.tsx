import { useState } from "react";
import { useAuth } from "../hooks/useAuth";

// Combined login / register screen. Registration creates a tenant + owner and
// logs straight in; login needs an existing tenant id.
export function LoginPage() {
  const { login, register } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("register");
  const [tenantId, setTenantId] = useState("");
  const [tenantName, setTenantName] = useState("");
  const [slug, setSlug] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      if (mode === "register") {
        await register(tenantName, slug, email, password);
      } else {
        await login(tenantId, email, password);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Authentication failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-wrap">
      <div className="auth-card" data-testid="auth-card">
        <div className="auth-brand">
          <div className="brand-mark" aria-hidden>
            ◎
          </div>
          <div>
            <div className="auth-title">PitchProof Vigil</div>
            <div className="brand-sub">AGENT RELIABILITY CONTROL ROOM</div>
          </div>
        </div>

        {error && (
          <div className="auth-error" data-testid="auth-error">
            {error}
          </div>
        )}

        {mode === "register" ? (
          <>
            <div className="field">
              <label>Organization name</label>
              <input
                className="input"
                data-testid="tenant-name"
                value={tenantName}
                onChange={(e) => setTenantName(e.target.value)}
                placeholder="World Cup Operations"
              />
            </div>
            <div className="field">
              <label>Slug (lowercase, hyphens)</label>
              <input
                className="input"
                data-testid="slug"
                value={slug}
                onChange={(e) => setSlug(e.target.value)}
                placeholder="wc-ops"
              />
            </div>
          </>
        ) : (
          <div className="field">
            <label>Tenant ID</label>
            <input
              className="input"
              data-testid="tenant-id"
              value={tenantId}
              onChange={(e) => setTenantId(e.target.value)}
              placeholder="tenant id from registration"
            />
          </div>
        )}

        <div className="field">
          <label>Email</label>
          <input
            className="input"
            data-testid="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@org.com"
          />
        </div>
        <div className="field">
          <label>Password (min 8 chars)</label>
          <input
            className="input"
            data-testid="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") submit();
            }}
          />
        </div>

        <button
          className="btn btn-primary"
          style={{ width: "100%" }}
          data-testid="auth-submit"
          onClick={submit}
          disabled={busy}
        >
          {busy ? "Working…" : mode === "register" ? "Create organization" : "Sign in"}
        </button>

        <div className="auth-toggle">
          {mode === "register" ? (
            <>
              Already have an organization?{" "}
              <button data-testid="to-login" onClick={() => setMode("login")}>
                Sign in
              </button>
            </>
          ) : (
            <>
              Need an organization?{" "}
              <button data-testid="to-register" onClick={() => setMode("register")}>
                Register
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
