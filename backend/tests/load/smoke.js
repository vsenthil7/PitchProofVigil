import http from "k6/http";
import { check, sleep } from "k6";
import { Trend, Rate } from "k6/metrics";

const askLatency = new Trend("ask_latency_ms");
const errorRate = new Rate("error_rate");

export const options = {
  vus: 20,
  duration: "30s",
  thresholds: {
    ask_latency_ms: ["p(99)<2000"],
    error_rate: ["rate<0.01"],
    http_req_failed: ["rate<0.01"],
  },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";

// Register a test tenant and obtain a bearer token before the test.
export function setup() {
  const slug = `k6-${Date.now()}`;
  const email = `${slug}@test.com`;
  const reg = http.post(
    `${BASE_URL}/api/auth/register`,
    JSON.stringify({
      tenant_name: "k6-tenant",
      slug: slug,
      owner_email: email,
      owner_password: "k6-password-123!",
    }),
    { headers: { "Content-Type": "application/json" } },
  );
  if (reg.status !== 201 && reg.status !== 200) {
    console.error("Registration failed:", reg.body);
    return { token: null };
  }
  const tenant_id = JSON.parse(reg.body).tenant_id || "";
  const login = http.post(
    `${BASE_URL}/api/auth/login`,
    JSON.stringify({ tenant_id: tenant_id, email: email, password: "k6-password-123!" }),
    { headers: { "Content-Type": "application/json" } },
  );
  const token = login.status === 200 ? JSON.parse(login.body).access_token : null;
  return { token };
}

export default function (data) {
  if (!data.token) return;
  const headers = {
    Authorization: `Bearer ${data.token}`,
    "Content-Type": "application/json",
  };

  const askStart = Date.now();
  const askRes = http.post(
    `${BASE_URL}/api/ask`,
    JSON.stringify({ text: "When does Spain vs Germany kick off?", language: "en" }),
    { headers },
  );
  askLatency.add(Date.now() - askStart);
  const askOk = check(askRes, {
    "ask status 200": (r) => r.status === 200,
    "ask has trace_id": (r) => JSON.parse(r.body).trace_id !== undefined,
    "ask has evaluations": (r) => JSON.parse(r.body).evaluations.length > 0,
  });
  errorRate.add(!askOk);

  sleep(0.5);

  const statsRes = http.get(`${BASE_URL}/api/stats`, { headers });
  check(statsRes, { "stats status 200": (r) => r.status === 200 });

  const analyticsRes = http.get(`${BASE_URL}/api/analytics/summary`, { headers });
  check(analyticsRes, { "analytics status 200": (r) => r.status === 200 });

  sleep(0.5);
}
