import { Link } from "react-router";
import { useSessions } from "@/api/queries";
import { useCurrentOrg } from "@/context/OrgContext";
import { useOrgLinks } from "@/lib/orgLinks";
import CostDisplay from "@/components/shared/CostDisplay";
import RelativeTime from "@/components/shared/RelativeTime";
import EmptyState from "@/components/shared/EmptyState";
import PageSkeleton from "@/components/shared/PageSkeleton";
import { MessageSquare } from "lucide-react";

interface Props {
  onNew: () => void;
}

export default function SessionList({ onNew }: Props) {
  const { orgName } = useCurrentOrg();
  const links = useOrgLinks();
  const { data: sessions, isLoading } = useSessions(orgName);

  if (isLoading) return <PageSkeleton variant="list" />;

  if (!sessions || sessions.length === 0) {
    return (
      <EmptyState
        icon={MessageSquare}
        title="No chat sessions"
        description="Start a conversation with The Assistant to plan work, design organizations, and bootstrap agents."
        action={{ label: "New Chat", onClick: onNew }}
      />
    );
  }

  return (
    <div className="space-y-2">
      {sessions.map((session) => (
        <Link
          key={session.id}
          to={links.chatSession(session.id)}
          className="block rounded-lg border border-border-default px-4 py-3 transition-colors hover:border-border-subtle hover:bg-surface-raised/50"
        >
          <div className="flex items-start justify-between">
            <div>
              <h3 className="font-medium text-text-primary">
                {session.title ?? "Untitled"}
              </h3>
              <div className="mt-1 flex items-center gap-2 text-xs text-text-muted">
                <CostDisplay value={session.total_cost} className="text-xs" />
              </div>
            </div>
            <RelativeTime datetime={session.created_at} className="text-xs" />
          </div>
        </Link>
      ))}
    </div>
  );
}
