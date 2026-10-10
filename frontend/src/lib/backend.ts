import "server-only";

import { headers } from "next/headers";

/**
 * Calls to the FastAPI backend made on a visitor's behalf - logging in, the chat, their
 * appointments. Only ever runs on the website's server (the "server-only" import makes
 * it a build error to use this in browser code), because it handles login tokens and the
 * shared secret.
 *
 * Every call passes on the visitor's own address with the shared secret, so the backend
 * still rate-limits each visitor separately even though all of these requests come from
 * this one server. See backend/app/core/rate_limiting.py.
 */

const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";

export async function backendFetch(
  path: string,
  { method = "GET", body, token }: { method?: string; body?: unknown; token?: string | null } = {},
): Promise<Response> {
  const forwarded: Record<string, string> = {};
  const secret = process.env.FRONTEND_SECRET;
  if (secret) {
    forwarded["X-Frontend-Secret"] = secret;
    forwarded["X-Visitor-IP"] = await visitorIp();
  }
  return fetch(`${API_URL}/api/v1${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...forwarded,
    },
    body: body === undefined ? undefined : typeof body === "string" ? body : JSON.stringify(body),
  });
}

/** The visitor's address, as reported by the hosting platform in front of this server. */
async function visitorIp(): Promise<string> {
  const all = await headers();
  // Vercel sets these itself and overwrites any value the visitor sends. Running locally
  // there's no platform in front, so every request is simply "this machine".
  const forwardedFor = all.get("x-forwarded-for")?.split(",")[0]?.trim();
  return forwardedFor || all.get("x-real-ip") || "127.0.0.1";
}

/** FastAPI's error message, or a fallback. Validation errors come back as a list. */
export async function errorDetail(response: Response, fallback: string): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") return body.detail;
    if (Array.isArray(body?.detail) && typeof body.detail[0]?.msg === "string") {
      return body.detail[0].msg.replace(/^Value error, /, "");
    }
  } catch {
    // not JSON - fall through
  }
  return fallback;
}
