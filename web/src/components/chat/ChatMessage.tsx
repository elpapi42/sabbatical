import type { SessionMessage } from "@/api/types";
import MarkdownRenderer from "@/components/shared/MarkdownRenderer";
import RelativeTime from "@/components/shared/RelativeTime";

interface Props {
  message: SessionMessage;
  isStreaming?: boolean;
}

export default function ChatMessage({ message, isStreaming = false }: Props) {
  const isUser = message.role === "user";

  return (
    <div className={`flex gap-3 ${isUser ? "" : ""}`}>
      <div
        className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
          isUser
            ? "bg-blue-500/20 text-blue-400"
            : "bg-primary-500/20 text-primary-400"
        }`}
      >
        {isUser ? "U" : "A"}
      </div>
      <div className="flex-1 min-w-0">
        <div className="mb-1 flex items-center gap-2 text-xs text-neutral-500">
          <span className="font-medium">
            {isUser ? "you" : "assistant"}
          </span>
          {!isStreaming && message.created_at && (
            <>
              <span>·</span>
              <RelativeTime
                datetime={message.created_at}
                className="text-xs"
              />
            </>
          )}
          {isStreaming && (
            <span className="text-primary-400 animate-pulse">
              streaming...
            </span>
          )}
        </div>
        <div
          className={`rounded-lg px-4 py-3 ${
            isUser
              ? "bg-blue-500/10 border border-blue-500/20"
              : "bg-neutral-800/50 border border-neutral-800"
          }`}
        >
          <MarkdownRenderer content={message.content} />
          {isStreaming && (
            <span className="inline-block w-2 h-4 bg-primary-400 animate-pulse ml-0.5" />
          )}
        </div>
      </div>
    </div>
  );
}
