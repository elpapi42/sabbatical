import { Link } from "react-router";
import type { TimelineComment as TComment } from "@/api/types";
import { useOrgLinks } from "@/lib/orgLinks";
import MarkdownRenderer from "@/components/shared/MarkdownRenderer";
import RelativeTime from "@/components/shared/RelativeTime";

interface Props {
  comment: TComment;
  organization: string;
}

export default function TimelineComment({ comment, organization }: Props) {
  const links = useOrgLinks();
  const isUser = comment.author === "user";
  const isSystem = comment.author === "system";

  if (isSystem) {
    return (
      <div className="rounded-md bg-neutral-800/30 px-4 py-2.5">
        <div className="flex items-center gap-2 text-xs text-text-muted">
          <span className="font-medium">system</span>
          <span>·</span>
          <RelativeTime datetime={comment.created_at} className="text-xs" />
        </div>
        <p className="mt-1 text-xs italic text-text-muted">{comment.body}</p>
      </div>
    );
  }

  const borderColor = isUser ? "border-l-blue-500/50" : "border-l-green-500/50";

  return (
    <div className={`rounded-md border border-border-default border-l-2 ${borderColor} bg-surface-raised px-4 py-3`}>
      <div className="flex items-center gap-2 text-xs text-text-muted">
        {isUser ? (
          <span className="font-medium text-blue-400">you</span>
        ) : (
          <Link
            to={links.agent(comment.author)}
            className="font-medium text-green-400 hover:text-green-300"
          >
            {comment.author}
          </Link>
        )}
        <span>·</span>
        <RelativeTime datetime={comment.created_at} className="text-xs" />
      </div>
      <div className="mt-2">
        <MarkdownRenderer content={comment.body} />
      </div>
    </div>
  );
}
