import { Link } from "react-router";
import { useState } from "react";
import { Pencil, Trash2, ChevronDown, ChevronRight, User } from "lucide-react";
import { useAgent } from "@/api/queries";
import { useDeleteAgent } from "@/api/mutations";
import { useOrgLinks } from "@/lib/orgLinks";
import CostDisplay from "@/components/shared/CostDisplay";
import TokenDisplay from "@/components/shared/TokenDisplay";
import MarkdownRenderer from "@/components/shared/MarkdownRenderer";
import ConfirmDialog from "@/components/shared/ConfirmDialog";
import PageSkeleton from "@/components/shared/PageSkeleton";
import AgentForm from "./AgentForm";
import { useToast } from "@/components/shared/Toast";
import { useNavigate } from "react-router";

interface Props {
  organization: string;
  agentName: string;
}

export default function AgentDetail({ organization, agentName }: Props) {
  const { data: agent, isLoading } = useAgent(organization, agentName);
  const deleteMut = useDeleteAgent(organization);
  const navigate = useNavigate();
  const links = useOrgLinks();
  const { toast } = useToast();

  const [showEdit, setShowEdit] = useState(false);
  const [showDelete, setShowDelete] = useState(false);
  const [instructionsExpanded, setInstructionsExpanded] = useState(true);

  if (isLoading || !agent) return <PageSkeleton variant="detail" />;

  const handleDelete = async () => {
    try {
      await deleteMut.mutateAsync(agentName);
      toast("Agent removed", "success");
      navigate(links.overview());
    } catch (err) {
      toast(err instanceof Error ? err.message : "Failed to remove", "error");
    }
    setShowDelete(false);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-text-primary">
              {agent.name}
            </h1>
            {agent.is_removed && (
              <span className="rounded bg-red-500/15 px-2 py-0.5 text-xs font-medium text-red-400">
                REMOVED
              </span>
            )}
          </div>
          <div className="mt-1 flex items-center gap-3 text-sm text-text-muted">
            {agent.boss ? (
              <span>
                Boss:{" "}
                <Link
                  to={links.agent(agent.boss)}
                  className="text-primary-400 hover:text-primary-300"
                >
                  @{agent.boss}
                </Link>
              </span>
            ) : (
              <span className="rounded bg-surface-overlay px-1.5 py-0.5 text-xs">
                Root Agent
              </span>
            )}
          </div>
        </div>
        {!agent.is_removed && (
          <div className="flex gap-1">
            <button
              onClick={() => setShowEdit(true)}
              className="rounded p-2 text-text-muted hover:bg-surface-overlay hover:text-text-secondary"
            >
              <Pencil size={16} />
            </button>
            <button
              onClick={() => setShowDelete(true)}
              className="rounded p-2 text-text-muted hover:bg-surface-overlay hover:text-red-400"
            >
              <Trash2 size={16} />
            </button>
          </div>
        )}
      </div>

      {/* Info Section */}
      <div className="rounded-lg border border-border-default bg-surface-raised p-4">
        {agent.description && (
          <p className="mb-4 text-sm text-text-secondary">{agent.description}</p>
        )}
        <div className="grid grid-cols-2 gap-y-3 text-sm">
          <div>
            <span className="text-text-muted">Instructions Path</span>
            <div className="mt-0.5 font-mono text-xs text-text-secondary">
              {agent.instructions_path}
            </div>
          </div>
          <div>
            <span className="text-text-muted">Max Iterations</span>
            <div className="mt-0.5 text-text-primary">{agent.max_iterations}</div>
          </div>
          <div>
            <span className="text-text-muted">Model</span>
            <div className="mt-0.5 text-text-primary">
              {agent.model ?? "System default"}
            </div>
          </div>
          <div>
            <span className="text-text-muted">Cost</span>
            <div className="mt-0.5 flex items-center gap-2">
              <CostDisplay value={agent.total_cost} />
              <span className="text-border-default">·</span>
              <TokenDisplay
                count={agent.consumed_input_tokens + agent.consumed_output_tokens}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Instructions */}
      <div className="rounded-lg border border-border-default">
        <button
          onClick={() => setInstructionsExpanded(!instructionsExpanded)}
          className="flex w-full items-center justify-between px-4 py-3 text-sm font-semibold text-text-primary hover:bg-surface-raised/50 transition-colors"
        >
          <span>Instructions</span>
          {instructionsExpanded ? (
            <ChevronDown size={16} />
          ) : (
            <ChevronRight size={16} />
          )}
        </button>
        {instructionsExpanded && (
          <div className="border-t border-border-default px-4 py-4">
            {agent.instructions_content ? (
              <MarkdownRenderer content={agent.instructions_content} />
            ) : (
              <p className="text-sm italic text-text-muted">
                No instructions file found
              </p>
            )}
          </div>
        )}
      </div>

      {/* Subordinates */}
      {agent.subordinates.length > 0 && (
        <div className="rounded-lg border border-border-default bg-surface-raised p-4">
          <h3 className="mb-3 text-xs font-semibold text-text-muted uppercase tracking-wider">
            Direct Reports
          </h3>
          <div className="space-y-1">
            {agent.subordinates.map((sub) => (
              <Link
                key={sub.name}
                to={links.agent(sub.name)}
                className="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-text-secondary hover:bg-surface-overlay transition-colors"
              >
                <User size={14} className="text-text-muted" />
                {sub.name}
                {sub.description && (
                  <span className="text-xs text-text-muted">
                    — {sub.description}
                  </span>
                )}
              </Link>
            ))}
          </div>
        </div>
      )}

      <AgentForm
        mode="edit"
        organization={organization}
        agent={agent}
        open={showEdit}
        onClose={() => setShowEdit(false)}
      />

      <ConfirmDialog
        open={showDelete}
        onClose={() => setShowDelete(false)}
        onConfirm={handleDelete}
        title="Remove Agent"
        message={`Remove "${agentName}" from ${organization}? ${agent.subordinates.length > 0 ? `${agent.subordinates.length} subordinate(s) will be promoted to root.` : ""}`}
        confirmLabel="Remove"
        destructive
        loading={deleteMut.isPending}
      />
    </div>
  );
}
