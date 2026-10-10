"use server";

import { refresh } from "next/cache";
import { redirect } from "next/navigation";

import { backendFetch, errorDetail } from "@/lib/backend";
import { clearTokens, getAccessToken, getRefreshToken, saveTokens } from "@/lib/session";

/**
 * Server Actions: the forms call these, and they run on this website's server. They are
 * the only places that set or clear the login cookies.
 *
 * Every action checks its own inputs and the login itself. A Server Action is a public
 * endpoint - anyone can call it with anything - so nothing the browser sends is trusted.
 */

export type FormState = { error: string | null; email?: string; fullName?: string };

type Tokens = { access_token: string; refresh_token: string };

export async function login(_previous: FormState, form: FormData): Promise<FormState> {
  const email = String(form.get("email") ?? "").trim();
  const password = String(form.get("password") ?? "");
  if (!email || !password) return { error: "Enter your email and password.", email };

  const response = await backendFetch("/auth/login", { method: "POST", body: { email, password } });
  if (!response.ok) {
    const error =
      response.status === 401
        ? "That email and password don't match an account."
        : await errorDetail(response, "Couldn't log you in just now. Please try again.");
    return { error, email };
  }
  const tokens = (await response.json()) as Tokens;
  await saveTokens(tokens.access_token, tokens.refresh_token);
  redirect(safeNextPage(form.get("next")));
}

export async function register(_previous: FormState, form: FormData): Promise<FormState> {
  const fullName = String(form.get("full_name") ?? "").trim();
  const email = String(form.get("email") ?? "").trim();
  const password = String(form.get("password") ?? "");
  if (!fullName || !email) return { error: "Enter your name and email.", email, fullName };
  if (password.length < 8) return { error: "Choose a password of at least 8 characters.", email, fullName };

  const response = await backendFetch("/auth/register", {
    method: "POST",
    body: { email, password, full_name: fullName },
  });
  if (!response.ok) {
    const error =
      response.status === 409
        ? "There's already an account with that email. Try logging in instead."
        : await errorDetail(response, "Couldn't create your account just now. Please try again.");
    return { error, email, fullName };
  }
  const tokens = (await response.json()) as Tokens;
  await saveTokens(tokens.access_token, tokens.refresh_token);
  redirect(safeNextPage(form.get("next")));
}

export async function logout() {
  const refreshToken = await getRefreshToken();
  if (refreshToken) {
    // Ends the session on the backend too, so a copied token stops working - not just
    // forgotten by this browser.
    await backendFetch("/auth/logout", { method: "POST", body: { refresh_token: refreshToken } }).catch(() => {});
  }
  await clearTokens();
  redirect("/");
}

export async function cancelAppointment(appointmentId: number): Promise<{ error: string | null }> {
  if (!Number.isInteger(appointmentId) || appointmentId < 1) return { error: "That isn't a valid appointment." };
  const token = await getAccessToken();
  if (!token) redirect("/login?next=/account");

  // The backend checks the appointment belongs to this account; nothing here decides that.
  const response = await backendFetch(`/appointments/${appointmentId}/cancel`, { method: "POST", body: {}, token });
  if (!response.ok) return { error: await errorDetail(response, "Couldn't cancel that appointment. Please try again.") };
  refresh();
  return { error: null };
}

/**
 * Where to go after logging in. Only a path on this site: "/account", never
 * "https://elsewhere" or "//elsewhere", or a link could log someone in and then quietly
 * send them to a look-alike site.
 */
function safeNextPage(next: FormDataEntryValue | null): string {
  const path = typeof next === "string" ? next : "";
  return path.startsWith("/") && !path.startsWith("//") && !path.startsWith("/\\") ? path : "/account";
}
