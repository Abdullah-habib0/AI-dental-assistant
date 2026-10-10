import "server-only";

import { cookies } from "next/headers";

import { backendFetch } from "@/lib/backend";

/**
 * The login session: two tokens from the backend, kept in httpOnly cookies.
 *
 * httpOnly means the browser sends them with requests to this website but page
 * JavaScript can never read them - so even a malicious script on the page couldn't steal
 * a login. The browser never talks to the backend directly with them; this server does,
 * on the visitor's behalf.
 *
 *   access token   short-lived (15 minutes); sent with every backend call
 *   refresh token  long-lived (7 days); only used to get a new access token
 */

const ACCESS = "bsd_access";
const REFRESH = "bsd_refresh";
const REFRESH_DAYS = 7; // matches the backend's refresh_token_days

export type User = { id: number; email: string; full_name: string };

const cookieOptions = {
  httpOnly: true,
  // Sent over HTTPS only once deployed. Locally the site runs on plain http.
  secure: process.env.NODE_ENV === "production",
  // Not sent along when another website posts to this one, which blocks most
  // cross-site request forgery.
  sameSite: "lax" as const,
  path: "/",
};

/** Store a fresh login. Only works in Server Actions and Route Handlers. */
export async function saveTokens(accessToken: string, refreshToken?: string) {
  const store = await cookies();
  store.set(ACCESS, accessToken, { ...cookieOptions, maxAge: secondsUntilExpiry(accessToken) });
  if (refreshToken) store.set(REFRESH, refreshToken, { ...cookieOptions, maxAge: REFRESH_DAYS * 24 * 60 * 60 });
}

export async function clearTokens() {
  const store = await cookies();
  store.delete(ACCESS);
  store.delete(REFRESH);
}

export async function getRefreshToken(): Promise<string | null> {
  return (await cookies()).get(REFRESH)?.value ?? null;
}

/** Whether there's a login at all - a cookie check only, no call to the backend. */
export async function hasSession(): Promise<boolean> {
  return (await getRefreshToken()) !== null;
}

/**
 * A usable access token, or null if not logged in.
 *
 * When the 15-minute access token has run out, the refresh token gets a new one. Saving
 * it to the cookie only works in Server Actions and Route Handlers - pages aren't allowed
 * to set cookies - so a page just uses it for that one render, and the next action or
 * chat message saves it.
 */
export async function getAccessToken(): Promise<string | null> {
  const store = await cookies();
  const current = store.get(ACCESS)?.value;
  if (current) return current;

  const refreshToken = store.get(REFRESH)?.value;
  if (!refreshToken) return null;

  const response = await backendFetch("/auth/refresh", { method: "POST", body: { refresh_token: refreshToken } });
  if (!response.ok) return null; // expired or logged out elsewhere: treat as logged out

  const { access_token: accessToken } = (await response.json()) as { access_token: string };
  try {
    await saveTokens(accessToken);
  } catch {
    // Called while rendering a page, where cookies can't be set. Fine - see above.
  }
  return accessToken;
}

/** The logged-in user, or null. */
export async function getCurrentUser(): Promise<User | null> {
  const token = await getAccessToken();
  if (!token) return null;
  const response = await backendFetch("/auth/me", { token });
  return response.ok ? ((await response.json()) as User) : null;
}

/** The cookie should disappear when the token stops working: read its expiry from the
 *  token itself (a JWT carries it), and leave 30 seconds' margin. */
function secondsUntilExpiry(jwt: string): number {
  try {
    const payload = JSON.parse(Buffer.from(jwt.split(".")[1], "base64url").toString("utf8"));
    return Math.max(0, Math.floor(payload.exp - Date.now() / 1000) - 30);
  } catch {
    return 10 * 60;
  }
}
