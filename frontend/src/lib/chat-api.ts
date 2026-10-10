/**
 * Talking to the chat endpoints, from the browser.
 *
 * NEXT_PUBLIC_API_URL is built into the page, so it must be set when the site is built.
 * The backend only accepts browser requests from the addresses in its CORS_ORIGINS.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Urgency = "routine" | "urgent" | "emergency" | "unavailable";

export type ChatReply = { conversation_id: string; reply: string; urgency: Urgency };

export type StoredMessage = { role: "patient" | "assistant"; content: string; created_at: string };

/** A problem worth showing the patient, with a message written for them. */
export class ChatError extends Error {
  constructor(
    message: string,
    readonly forgetConversation = false,
  ) {
    super(message);
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}/api/v1${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ChatError("I couldn't reach the clinic's assistant. Please check your connection and try again.");
  }
  if (response.ok) return response.json() as Promise<T>;

  const detail = await response
    .json()
    .then((body) => (typeof body?.detail === "string" ? body.detail : null))
    .catch(() => null);

  switch (response.status) {
    case 404:
      // The conversation no longer exists (or belongs to someone else): start afresh.
      throw new ChatError("That conversation has ended. Let's start a new one.", true);
    case 429:
      throw new ChatError(detail ?? "You're sending messages quickly - please wait a moment and try again.");
    case 503:
      throw new ChatError("The assistant is unavailable right now. Please call the practice instead.");
    default:
      throw new ChatError("Something went wrong. Please try again.");
  }
}

export function sendMessage(message: string, conversationId: string | null): Promise<ChatReply> {
  return call<ChatReply>("/chat", {
    method: "POST",
    body: JSON.stringify(conversationId ? { message, conversation_id: conversationId } : { message }),
  });
}

export async function loadConversation(conversationId: string): Promise<StoredMessage[]> {
  const conversation = await call<{ messages: StoredMessage[] }>(`/chat/${encodeURIComponent(conversationId)}`);
  return conversation.messages;
}
