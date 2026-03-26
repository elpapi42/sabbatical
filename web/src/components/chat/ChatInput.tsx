import { useState, useRef } from "react";
import { Send } from "lucide-react";

interface Props {
  onSend: (content: string) => void;
  disabled: boolean;
}

export default function ChatInput({ onSend, disabled }: Props) {
  const [content, setContent] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = () => {
    if (!content.trim() || disabled) return;
    onSend(content.trim());
    setContent("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div
      className={`flex items-end gap-2 rounded-lg border bg-neutral-900/50 ${
        disabled
          ? "border-neutral-800 opacity-60"
          : "border-neutral-700 focus-within:border-primary-500/50"
      }`}
    >
      <textarea
        ref={textareaRef}
        value={content}
        onChange={(e) => setContent(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        placeholder={disabled ? "Waiting for response..." : "Type a message..."}
        rows={2}
        className="flex-1 resize-none bg-transparent px-4 py-3 text-sm text-neutral-100 placeholder:text-neutral-600 focus:outline-none disabled:cursor-not-allowed"
      />
      <button
        onClick={handleSubmit}
        disabled={disabled || !content.trim()}
        className="mb-2.5 mr-2.5 rounded-md bg-primary-600 p-2 text-white hover:bg-primary-500 disabled:opacity-30"
      >
        <Send size={16} />
      </button>
    </div>
  );
}
