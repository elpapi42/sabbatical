import { useState } from "react";
import { Brain, ChevronDown, ChevronRight } from "lucide-react";
import type { ExecutionStep } from "@/api/types";
import MarkdownRenderer from "@/components/shared/MarkdownRenderer";

interface Props {
  step: ExecutionStep;
  defaultExpanded?: boolean;
}

export default function RunStepReasoning({
  step,
  defaultExpanded = false,
}: Props) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const content = step.content ?? "";
  const lineCount = content.split("\n").length;
  const isLong = lineCount > 10;

  return (
    <div className="rounded-md border border-purple-500/20 bg-purple-500/5">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-2 px-4 py-2.5 text-sm text-purple-300 hover:bg-purple-500/10"
      >
        <Brain size={14} />
        <span className="font-medium">Reasoning</span>
        {isLong &&
          (expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />)}
      </button>
      {(expanded || !isLong) && (
        <div className="border-t border-purple-500/10 px-4 py-3">
          <MarkdownRenderer content={content} />
        </div>
      )}
    </div>
  );
}
