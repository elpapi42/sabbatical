import { Link } from "react-router";
import type { AgentNode } from "@/api/types";
import { useOrgLinks } from "@/lib/orgLinks";
import { User } from "lucide-react";

interface Props {
  agents: AgentNode[];
  organization: string;
  depth?: number;
}

function AgentTreeNode({
  agent,
  isLast,
  depth,
}: {
  agent: AgentNode;
  isLast: boolean;
  depth: number;
}) {
  const links = useOrgLinks();

  return (
    <div className={depth > 0 ? "ml-6" : ""}>
      <div className="flex items-start gap-2 py-1">
        {depth > 0 && (
          <span className="mt-2.5 inline-block w-4 border-b-2 border-l-2 border-border-default h-3 rounded-bl shrink-0" />
        )}
        <div className="flex-1 rounded-md border border-border-default bg-surface-raised px-3 py-2 hover:border-border-subtle transition-colors">
          <div className="flex items-center gap-2">
            <User size={14} className="text-text-muted shrink-0" />
            <Link
              to={links.agent(agent.name)}
              className="text-sm font-medium text-text-primary hover:text-primary-400 transition-colors"
            >
              {agent.name}
            </Link>
            {agent.model && (
              <span className="rounded bg-surface-overlay px-1.5 py-0.5 text-xs text-text-muted">
                {agent.model}
              </span>
            )}
          </div>
          {agent.description && (
            <p className="mt-0.5 text-xs text-text-muted">
              {agent.description}
            </p>
          )}
        </div>
      </div>
      {agent.subordinates.length > 0 && (
        <div className={depth > 0 ? "border-l-2 border-border-default ml-1" : ""}>
          {agent.subordinates.map((sub, i) => (
            <AgentTreeNode
              key={sub.name}
              agent={sub}
              isLast={i === agent.subordinates.length - 1}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function AgentTree({ agents, organization }: Props) {
  if (agents.length === 0) {
    return (
      <div className="py-8 text-center text-sm text-text-muted">
        No agents in this organization
      </div>
    );
  }

  return (
    <div className="space-y-1">
      {agents.map((agent, i) => (
        <AgentTreeNode
          key={agent.name}
          agent={agent}
          isLast={i === agents.length - 1}
          depth={0}
        />
      ))}
    </div>
  );
}
