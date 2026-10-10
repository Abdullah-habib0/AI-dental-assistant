"use client";

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { MessageCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type ChatControls = {
  isOpen: boolean;
  /** Open the chat. A suggested message goes into the input box - it is never sent
   *  for the patient, so they can change it first. */
  open: (suggestedMessage?: string) => void;
  close: () => void;
  /** What's typed in the chat's input box. Kept here, not in the chat itself, so a
   *  "Book this treatment" button anywhere on the site can fill it in. */
  draft: string;
  setDraft: (text: string) => void;
};

const ChatContext = createContext<ChatControls | null>(null);

export function ChatProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  const [draft, setDraft] = useState("");

  const open = useCallback((suggestedMessage?: string) => {
    if (suggestedMessage) setDraft(suggestedMessage);
    setIsOpen(true);
  }, []);
  const close = useCallback(() => setIsOpen(false), []);

  const value = useMemo(() => ({ isOpen, open, close, draft, setDraft }), [isOpen, open, close, draft]);
  return <ChatContext value={value}>{children}</ChatContext>;
}

export function useChat(): ChatControls {
  const controls = useContext(ChatContext);
  if (!controls) throw new Error("useChat must be used inside <ChatProvider>");
  return controls;
}

/** A button anywhere on the site that opens the chat, optionally with a suggested message. */
export function OpenChatButton({
  children,
  message,
  variant = "default",
  size = "xl",
  className,
  showIcon = true,
}: {
  children: ReactNode;
  message?: string;
  variant?: "default" | "outline" | "secondary" | "ghost" | "link";
  size?: "default" | "sm" | "lg" | "xl";
  className?: string;
  showIcon?: boolean;
}) {
  const { open } = useChat();
  return (
    <Button variant={variant} size={size} className={cn(className)} onClick={() => open(message)}>
      {showIcon && <MessageCircle data-icon="inline-start" />}
      {children}
    </Button>
  );
}
