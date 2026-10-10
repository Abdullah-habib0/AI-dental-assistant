import { forwardToChat } from "@/lib/chat-proxy";

/** Send a chat message. See lib/chat-proxy.ts. */
export async function POST(request: Request) {
  return forwardToChat(request, "/chat", "POST");
}
