import { useState, useRef, useEffect, useCallback } from "react";
import { useSession } from "@/api/queries";
import { sendMessage } from "@/api/client";
import { useQueryClient } from "@tanstack/react-query";
import type { SessionMessage } from "@/api/types";
import ChatMessage from "./ChatMessage";
import ChatInput from "./ChatInput";
import CostDisplay from "@/components/shared/CostDisplay";
import { useToast } from "@/components/shared/Toast";

interface Props {
  sessionId: string;
}

export default function ChatInterface({ sessionId }: Props) {
  const { data: session } = useSession(sessionId);
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const [isStreaming, setIsStreaming] = useState(false);
  const [streamedContent, setStreamedContent] = useState("");
  const [allMessages, setAllMessages] = useState<SessionMessage[]>([]);

  // Sync messages from API
  useEffect(() => {
    if (session?.messages && !isStreaming) {
      setAllMessages(session.messages);
    }
  }, [session?.messages, isStreaming]);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [allMessages, streamedContent]);

  const handleSend = useCallback(
    async (content: string) => {
      const userMsg: SessionMessage = {
        role: "user",
        content,
        created_at: new Date().toISOString(),
      };
      setAllMessages((prev) => [...prev, userMsg]);
      setIsStreaming(true);
      setStreamedContent("");

      try {
        const response = await sendMessage(sessionId, { content });

        if (!response.ok) {
          const err = await response.json().catch(() => ({ detail: "Request failed" }));
          throw new Error(err.detail || "Request failed");
        }

        const reader = response.body!.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let currentEvent = "";
        let fullContent = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop()!;

          for (const line of lines) {
            if (line.startsWith("event: ")) {
              currentEvent = line.slice(7).trim();
            } else if (line.startsWith("data: ")) {
              try {
                const data = JSON.parse(line.slice(6));
                if (currentEvent === "token" && data.content) {
                  fullContent += data.content;
                  setStreamedContent(fullContent);
                } else if (currentEvent === "done") {
                  const assistantMsg: SessionMessage = {
                    role: "assistant",
                    content: data.message?.content ?? fullContent,
                    created_at:
                      data.message?.created_at ?? new Date().toISOString(),
                  };
                  setAllMessages((prev) => [...prev, assistantMsg]);
                  setStreamedContent("");
                }
              } catch {
                // Skip malformed JSON
              }
            }
          }
        }

        queryClient.invalidateQueries({ queryKey: ["sessions", sessionId] });
        queryClient.invalidateQueries({ queryKey: ["sessions"] });
      } catch (err) {
        toast(
          err instanceof Error ? err.message : "Failed to send message",
          "error",
        );
        if (streamedContent) {
          const partialMsg: SessionMessage = {
            role: "assistant",
            content: streamedContent + "\n\n*[Stream interrupted]*",
            created_at: new Date().toISOString(),
          };
          setAllMessages((prev) => [...prev, partialMsg]);
        }
      } finally {
        setIsStreaming(false);
        setStreamedContent("");
      }
    },
    [sessionId, queryClient, toast],
  );

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="shrink-0 flex items-center justify-between border-b border-border-default px-4 py-2.5 md:px-6">
        <div>
          <h1 className="text-sm font-semibold text-text-primary">
            {session?.title ?? "New Chat"}
          </h1>
          <div className="flex items-center gap-2 text-xs text-text-muted">
            <span className="rounded bg-surface-overlay px-1.5 py-0.5">
              {session?.organization_scope ?? "Global"}
            </span>
          </div>
        </div>
        {session && <CostDisplay value={session.total_cost} />}
      </div>

      {/* Messages */}
      <div className="flex-1 min-h-0 overflow-y-auto px-4 py-4 space-y-4 md:px-6">
        {allMessages.map((msg, i) => (
          <ChatMessage key={i} message={msg} />
        ))}
        {isStreaming && streamedContent && (
          <ChatMessage
            message={{
              role: "assistant",
              content: streamedContent,
              created_at: new Date().toISOString(),
            }}
            isStreaming
          />
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="shrink-0 border-t border-border-default px-4 py-3 md:px-6">
        <ChatInput onSend={handleSend} disabled={isStreaming} />
      </div>
    </div>
  );
}
