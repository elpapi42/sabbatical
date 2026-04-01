import { useState } from "react";
import { Wrench, MessageSquare, ChevronDown, ChevronRight } from "lucide-react";
import type { ExecutionStep } from "@/api/types";
import MarkdownRenderer from "@/components/shared/MarkdownRenderer";

interface Props {
  step: ExecutionStep;
}

export default function RunStepToolCall({ step }: Props) {
  const [argsExpanded, setArgsExpanded] = useState(false);
  const [outputExpanded, setOutputExpanded] = useState(false);
  const [fullOutput, setFullOutput] = useState(false);

  const output = step.output ?? "";
  const isLongOutput = output.length > 500;
  const displayOutput = fullOutput ? output : output.slice(0, 500);

  const isComment = step.tool === "add_comment";
  const commentBody = isComment ? (step.arguments?.message as string) ?? "" : "";
  const Icon = isComment ? MessageSquare : Wrench;
  const borderColor = isComment ? "border-blue-500/20" : "border-amber-500/20";
  const bgColor = isComment ? "bg-blue-500/5" : "bg-amber-500/5";
  const badgeBg = isComment ? "bg-blue-500/20" : "bg-amber-500/20";
  const badgeText = isComment ? "text-blue-300" : "text-amber-300";
  const iconColor = isComment ? "text-blue-400" : "text-amber-400";
  const dividerColor = isComment ? "border-blue-500/10" : "border-amber-500/10";
  const hoverBg = isComment ? "hover:bg-blue-500/5" : "hover:bg-amber-500/5";

  return (
    <div className={`rounded-md border ${borderColor} ${bgColor}`}>
      <div className="flex items-center gap-2 px-4 py-2.5 text-sm">
        <Icon size={14} className={iconColor} />
        <span className={`rounded ${badgeBg} px-1.5 py-0.5 text-xs font-medium ${badgeText}`}>
          {step.tool}
        </span>
      </div>

      {isComment && commentBody ? (
        <div className={`border-t ${dividerColor} px-4 py-3`}>
          <MarkdownRenderer content={commentBody} />
        </div>
      ) : step.arguments ? (
        <div className={`border-t ${dividerColor}`}>
          <button
            onClick={() => setArgsExpanded(!argsExpanded)}
            className={`flex w-full items-center gap-2 px-4 py-2 text-xs text-neutral-400 ${hoverBg}`}
          >
            {argsExpanded ? (
              <ChevronDown size={12} />
            ) : (
              <ChevronRight size={12} />
            )}
            Arguments
          </button>
          {argsExpanded && (
            <pre className={`overflow-x-auto border-t ${dividerColor} bg-neutral-900/50 px-4 py-3 text-xs text-neutral-300`}>
              {JSON.stringify(step.arguments, null, 2)}
            </pre>
          )}
        </div>
      ) : null}

      {output && !isComment && (
        <div className={`border-t ${dividerColor}`}>
          <button
            onClick={() => setOutputExpanded(!outputExpanded)}
            className={`flex w-full items-center gap-2 px-4 py-2 text-xs text-neutral-400 ${hoverBg}`}
          >
            {outputExpanded ? (
              <ChevronDown size={12} />
            ) : (
              <ChevronRight size={12} />
            )}
            Output ({output.length} chars)
          </button>
          {outputExpanded && (
            <div className={`border-t ${dividerColor} bg-neutral-900/50 px-4 py-3`}>
              <pre className="overflow-x-auto whitespace-pre-wrap text-xs text-neutral-300">
                {displayOutput}
                {isLongOutput && !fullOutput && "..."}
              </pre>
              {isLongOutput && (
                <button
                  onClick={() => setFullOutput(!fullOutput)}
                  className="mt-2 text-xs text-primary-400 hover:text-primary-300"
                >
                  {fullOutput ? "Show less" : "Show full output"}
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
