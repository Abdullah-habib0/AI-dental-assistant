import { forwardToChat } from "@/lib/chat-proxy";

/** Read back a conversation. See lib/chat-proxy.ts. */
export async function GET(request: Request, context: RouteContext<"/api/chat/[id]">) {
  const { id } = await context.params;
  return forwardToChat(request, `/chat/${encodeURIComponent(id)}`, "GET");
}
