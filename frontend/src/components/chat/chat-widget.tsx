"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { AlertTriangle, ArrowUp, Clock, MessageCircle, RotateCcw, Sparkles, X } from "lucide-react";

import { useChat } from "@/components/chat/chat-context";
import { Markdown } from "@/components/chat/markdown";
import { Button } from "@/components/ui/button";
import { ChatError, loadConversation, sendMessage, type Urgency } from "@/lib/chat-api";
import { site } from "@/lib/site";
import { cn } from "@/lib/utils";

type Message = { role: "patient" | "assistant"; content: string; urgency?: Urgency };

const STORAGE_KEY = "bright-smile:conversation-id";
const MAX_LENGTH = 2000; // the backend's limit

const SUGGESTIONS = [
  "What are your opening hours?",
  "I'd like to book a check-up",
  "How much is teeth whitening?",
  "What should I avoid after an extraction?",
];

// Browser storage can be blocked (private windows, strict settings). The chat still
// works without it - it just won't remember the conversation after a reload.
function readStoredId(): string | null {
  try {
    return window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}
function storeId(id: string | null) {
  try {
    if (id) window.localStorage.setItem(STORAGE_KEY, id);
    else window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // ignore - see readStoredId
  }
}

export function ChatWidget() {
  const { isOpen, open, close, draft: input, setDraft: setInput } = useChat();
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  const inputRef = useRef<HTMLTextAreaElement>(null);
  const endRef = useRef<HTMLDivElement>(null);

  // When the site loads, bring back the previous conversation, if there is one. The chat
  // lives in the root layout, so this happens once per visit, not on every page change.
  useEffect(() => {
    const storedId = readStoredId();
    if (!storedId) return;
    loadConversation(storedId)
      .then((stored) => {
        setConversationId(storedId);
        setMessages(stored.map((m) => ({ role: m.role, content: m.content })));
      })
      .catch((error: unknown) => {
        if (error instanceof ChatError && error.forgetConversation) storeId(null);
      });
  }, []);

  useEffect(() => {
    if (isOpen) inputRef.current?.focus();
  }, [isOpen]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, sending]);

  useEffect(() => {
    if (!isOpen) return;
    const onKey = (event: globalThis.KeyboardEvent) => event.key === "Escape" && close();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isOpen, close]);

  const send = useCallback(
    async (text: string) => {
      const message = text.trim();
      if (!message || sending) return;

      setProblem(null);
      setInput("");
      setMessages((current) => [...current, { role: "patient", content: message }]);
      setSending(true);
      try {
        const result = await sendMessage(message, conversationId);
        setConversationId(result.conversation_id);
        storeId(result.conversation_id);
        setMessages((current) => [
          ...current,
          { role: "assistant", content: result.reply, urgency: result.urgency },
        ]);
      } catch (error) {
        // Not delivered: take the message back out of the conversation and return it to
        // the box, so nothing the patient typed is lost.
        setMessages((current) => current.slice(0, -1));
        setInput(message);
        if (error instanceof ChatError && error.forgetConversation) {
          setConversationId(null);
          storeId(null);
        }
        setProblem(error instanceof ChatError ? error.message : "Something went wrong. Please try again.");
      } finally {
        setSending(false);
        inputRef.current?.focus();
      }
    },
    [conversationId, sending, setInput],
  );

  function startOver() {
    setMessages([]);
    setConversationId(null);
    storeId(null);
    setProblem(null);
    setInput("");
    inputRef.current?.focus();
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void send(input);
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter sends; Shift+Enter makes a new line.
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void send(input);
    }
  }

  if (!isOpen) {
    return (
      <button
        type="button"
        onClick={() => open()}
        className="fixed right-4 bottom-4 z-40 flex items-center gap-2 rounded-full bg-primary py-3.5 pr-5 pl-4 text-sm font-medium text-primary-foreground shadow-lg shadow-primary/25 transition hover:-translate-y-0.5 hover:shadow-xl hover:shadow-primary/30 focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none sm:right-6 sm:bottom-6"
      >
        <MessageCircle className="size-5" />
        Chat with us
      </button>
    );
  }

  return (
    <section
      role="dialog"
      aria-label={`${site.name} chat assistant`}
      className="fixed inset-0 z-50 flex flex-col bg-card sm:inset-auto sm:right-6 sm:bottom-6 sm:h-[min(680px,calc(100dvh-3rem))] sm:w-[400px] sm:overflow-hidden sm:rounded-2xl sm:border sm:shadow-2xl sm:shadow-foreground/10"
    >
      <header className="flex items-center gap-3 border-b bg-primary px-4 py-3 text-primary-foreground">
        <span className="flex size-9 items-center justify-center rounded-full bg-primary-foreground/15">
          <Sparkles className="size-4.5" />
        </span>
        <div className="mr-auto leading-tight">
          <p className="font-medium">{site.name}</p>
          <p className="text-xs text-primary-foreground/75">Assistant · answers and books appointments</p>
        </div>
        {messages.length > 0 && (
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={startOver}
            title="Start a new conversation"
            className="text-primary-foreground hover:bg-primary-foreground/15 hover:text-primary-foreground"
          >
            <RotateCcw />
            <span className="sr-only">Start a new conversation</span>
          </Button>
        )}
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={close}
          className="text-primary-foreground hover:bg-primary-foreground/15 hover:text-primary-foreground"
        >
          <X />
          <span className="sr-only">Close chat</span>
        </Button>
      </header>

      <div className="flex-1 space-y-3 overflow-y-auto bg-background/60 px-4 py-4" aria-live="polite">
        <AssistantBubble>
          <p className="leading-relaxed">
            Hello! I can answer questions about {site.name}, and book, move or cancel appointments for you.
            How can I help?
          </p>
        </AssistantBubble>

        {messages.length === 0 && (
          <div className="flex flex-wrap gap-2 pt-1">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => void send(s)}
                className="rounded-full border border-primary/25 bg-card px-3 py-1.5 text-left text-xs text-secondary-foreground transition hover:border-primary/50 hover:bg-secondary"
              >
                {s}
              </button>
            ))}
          </div>
        )}

        {messages.map((m, i) =>
          m.role === "patient" ? (
            <div key={i} className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-tr-md bg-primary px-3.5 py-2.5 text-sm text-primary-foreground whitespace-pre-wrap">
              {m.content}
            </div>
          ) : (
            <AssistantBubble key={i} urgency={m.urgency}>
              <Markdown>{m.content}</Markdown>
            </AssistantBubble>
          ),
        )}

        {sending && (
          <AssistantBubble>
            <span className="flex items-center gap-1 py-1" aria-label="The assistant is typing">
              {[0, 150, 300].map((delay) => (
                <span
                  key={delay}
                  className="size-1.5 animate-bounce rounded-full bg-secondary-foreground/50"
                  style={{ animationDelay: `${delay}ms` }}
                />
              ))}
            </span>
          </AssistantBubble>
        )}
        <div ref={endRef} />
      </div>

      <form onSubmit={onSubmit} className="border-t bg-card px-3 pt-3 pb-2">
        {problem && (
          <p role="alert" className="mb-2 rounded-lg bg-destructive/10 px-3 py-2 text-xs text-destructive">
            {problem}
          </p>
        )}
        <div className="flex items-end gap-2 rounded-xl border bg-background px-3 py-2 focus-within:border-primary/60 focus-within:ring-3 focus-within:ring-ring/15">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            maxLength={MAX_LENGTH}
            rows={1}
            placeholder="Ask a question or book an appointment…"
            aria-label="Your message"
            className="field-sizing-content max-h-32 min-h-6 flex-1 resize-none bg-transparent text-sm outline-none placeholder:text-muted-foreground"
          />
          <Button type="submit" size="icon-sm" disabled={!input.trim() || sending} className="rounded-lg">
            <ArrowUp />
            <span className="sr-only">Send</span>
          </Button>
        </div>
        <p className="px-1 pt-2 text-[11px] leading-snug text-muted-foreground">
          An AI assistant - it can make mistakes and can&apos;t give medical advice. In an emergency, call 999.
        </p>
      </form>
    </section>
  );
}

function AssistantBubble({ children, urgency }: { children: React.ReactNode; urgency?: Urgency }) {
  const emergency = urgency === "emergency";
  const urgent = urgency === "urgent";
  return (
    <div
      className={cn(
        "w-fit max-w-[88%] rounded-2xl rounded-tl-md px-3.5 py-2.5 text-sm",
        emergency && "border border-destructive/30 bg-destructive/10 text-foreground",
        urgent && "border border-warning/40 bg-warning/10 text-foreground",
        !emergency && !urgent && "bg-secondary text-secondary-foreground",
      )}
    >
      {(emergency || urgent) && (
        <p className={cn("mb-1.5 flex items-center gap-1.5 text-xs font-semibold", emergency ? "text-destructive" : "text-warning")}>
          {emergency ? <AlertTriangle className="size-3.5" /> : <Clock className="size-3.5" />}
          {emergency ? "Emergency advice" : "Needs attention today"}
        </p>
      )}
      {children}
    </div>
  );
}
