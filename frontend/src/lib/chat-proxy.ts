import "server-only";

import { backendFetch } from "@/lib/backend";
import { getAccessToken } from "@/lib/session";

/**
 * Passes a chat request from the browser to the backend, adding the login token from the
 * httpOnly cookie. The browser never sees the token: it only ever talks to this website.
 */
export async function forwardToChat(request: Request, path: string, method: "GET" | "POST"): Promise<Response> {
  if (!isSameSite(request)) {
    return Response.json({ detail: "Requests must come from this website." }, { status: 403 });
  }
  const token = await getAccessToken(); // null for guests - the chat works for them too
  const body = method === "POST" ? await request.text() : undefined;
  const response = await backendFetch(path, { method, body, token });
  return new Response(await response.text(), {
    status: response.status,
    headers: { "Content-Type": response.headers.get("Content-Type") ?? "application/json" },
  });
}

/**
 * The login cookie is sent with any request to this site, so a page on another website
 * could try to make a logged-in visitor's browser post chat messages here. The cookie's
 * SameSite=Lax setting already stops that in modern browsers; checking the Origin header
 * is a second lock on the same door.
 */
function isSameSite(request: Request): boolean {
  const origin = request.headers.get("origin");
  if (!origin) return request.method === "GET";
  try {
    return new URL(origin).host === request.headers.get("host");
  } catch {
    return false;
  }
}
