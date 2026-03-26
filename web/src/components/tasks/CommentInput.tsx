import { useState, useRef } from "react";
import { Send } from "lucide-react";
import { useCommentTask } from "@/api/mutations";
import { useToast } from "@/components/shared/Toast";
import MentionAutocomplete from "./MentionAutocomplete";

interface Props {
  taskId: string;
  organization: string;
  disabled: boolean;
  disabledReason?: string;
}

export default function CommentInput({
  taskId,
  organization,
  disabled,
  disabledReason,
}: Props) {
  const [body, setBody] = useState("");
  const [mentionQuery, setMentionQuery] = useState("");
  const [showMentions, setShowMentions] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const commentMut = useCommentTask(taskId);
  const { toast } = useToast();

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value;
    setBody(val);

    // Check for @mention
    const cursorPos = e.target.selectionStart;
    const textBeforeCursor = val.slice(0, cursorPos);
    const match = textBeforeCursor.match(/@([a-z0-9_]*)$/);
    if (match) {
      setMentionQuery(match[1]);
      setShowMentions(true);
    } else {
      setShowMentions(false);
    }
  };

  const handleMentionSelect = (name: string) => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    const cursorPos = textarea.selectionStart;
    const textBeforeCursor = body.slice(0, cursorPos);
    const atIndex = textBeforeCursor.lastIndexOf("@");
    const newBody = body.slice(0, atIndex) + `@${name} ` + body.slice(cursorPos);
    setBody(newBody);
    setShowMentions(false);

    // Refocus
    setTimeout(() => {
      const newPos = atIndex + name.length + 2;
      textarea.focus();
      textarea.setSelectionRange(newPos, newPos);
    }, 0);
  };

  const handleSubmit = async () => {
    if (!body.trim() || disabled) return;
    try {
      await commentMut.mutateAsync({ body: body.trim() });
      setBody("");
    } catch (err) {
      toast(err instanceof Error ? err.message : "Failed to comment", "error");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (showMentions) return; // Let autocomplete handle keys
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="relative">
      <MentionAutocomplete
        organization={organization}
        query={mentionQuery}
        onSelect={handleMentionSelect}
        visible={showMentions}
      />
      <div
        className={`flex items-end gap-2 rounded-md border bg-neutral-900/50 ${
          disabled
            ? "border-neutral-800 opacity-60"
            : "border-neutral-700 focus-within:border-primary-500/50"
        }`}
        title={disabled ? disabledReason : undefined}
      >
        <textarea
          ref={textareaRef}
          value={body}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          placeholder={
            disabled
              ? disabledReason ?? "Cannot comment"
              : "Type a comment... @mention to assign"
          }
          rows={2}
          className="flex-1 resize-none bg-transparent px-3 py-2.5 text-sm text-neutral-100 placeholder:text-neutral-600 focus:outline-none disabled:cursor-not-allowed"
        />
        <button
          onClick={handleSubmit}
          disabled={disabled || !body.trim() || commentMut.isPending}
          className="mb-2 mr-2 rounded-md bg-primary-600 p-2 text-white hover:bg-primary-500 disabled:opacity-30 disabled:hover:bg-primary-600"
        >
          <Send size={16} />
        </button>
      </div>
    </div>
  );
}
