import { Link, useLocation } from "react-router";
import { useState } from "react";
import {
  LayoutDashboard,
  ListTodo,
  MessageSquare,
  Users,
  ChevronDown,
  ChevronRight,
  User,
  Activity,
  DollarSign,
  Settings,
  X,
} from "lucide-react";
import { useCurrentOrg } from "@/context/OrgContext";
import { useOrgLinks } from "@/lib/orgLinks";
import { useSidebar } from "@/context/SidebarContext";
import { formatCost } from "@/lib/format";
import type { AgentSummary } from "@/api/types";

function NavLink({
  to,
  icon: Icon,
  label,
  isActive,
}: {
  to: string;
  icon: typeof LayoutDashboard;
  label: string;
  isActive: boolean;
}) {
  return (
    <Link
      to={to}
      className={`mx-2 mb-0.5 flex items-center gap-3 rounded-md px-3 py-2 text-[13px] font-medium transition-colors ${
        isActive
          ? "bg-primary-600/15 text-primary-300"
          : "text-text-secondary hover:bg-surface-overlay hover:text-text-primary"
      }`}
    >
      <Icon size={16} className={isActive ? "text-primary-400" : ""} />
      {label}
    </Link>
  );
}

function AgentList({ agents }: { agents: AgentSummary[] }) {
  const links = useOrgLinks();
  const location = useLocation();

  return (
    <div className="ml-5 space-y-0.5">
      {agents
        .filter((a) => !a.is_removed)
        .map((agent) => {
          const href = links.agent(agent.name);
          const isActive = location.pathname === href;
          return (
            <Link
              key={agent.name}
              to={href}
              className={`flex items-center gap-2 rounded-md px-3 py-1.5 text-[13px] transition-colors ${
                isActive
                  ? "text-primary-300 bg-primary-600/10"
                  : "text-text-muted hover:text-text-secondary hover:bg-surface-overlay"
              }`}
            >
              <User size={12} />
              {agent.name}
            </Link>
          );
        })}
    </div>
  );
}

export default function OrgSidebar() {
  const { orgName, org, agents } = useCurrentOrg();
  const links = useOrgLinks();
  const location = useLocation();
  const { isOpen, isMobile, close } = useSidebar();
  const [agentsExpanded, setAgentsExpanded] = useState(true);

  const isActiveExact = (path: string) => location.pathname === path;
  const isActivePrefix = (path: string) => location.pathname.startsWith(path);

  const sidebarContent = (
    <aside className="flex h-full w-56 flex-col border-r border-border-default bg-surface">
      {/* Org header */}
      <div className="flex h-12 shrink-0 items-center justify-between px-4">
        <Link
          to={links.overview()}
          className="text-sm font-semibold text-text-primary truncate"
        >
          {orgName}
        </Link>
        <div className="flex items-center gap-0.5">
          <Link
            to={links.overview()}
            className="rounded p-1 text-text-muted hover:bg-surface-overlay hover:text-text-secondary"
            title="Settings"
          >
            <Settings size={14} />
          </Link>
          {isMobile && (
            <button
              onClick={close}
              className="rounded p-1 text-text-muted hover:bg-surface-overlay hover:text-text-secondary"
            >
              <X size={16} />
            </button>
          )}
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 min-h-0 overflow-y-auto scrollbar-auto-hide py-1">
        <NavLink
          to={links.overview()}
          icon={LayoutDashboard}
          label="Overview"
          isActive={isActiveExact(links.overview())}
        />

        {/* Agents section */}
        <div className="mt-1">
          <button
            onClick={() => setAgentsExpanded(!agentsExpanded)}
            className={`mx-2 mb-0.5 flex w-[calc(100%-1rem)] items-center gap-3 rounded-md px-3 py-2 text-[13px] font-medium transition-colors ${
              isActivePrefix(links.overview() + "/agents")
                ? "bg-primary-600/15 text-primary-300"
                : "text-text-secondary hover:bg-surface-overlay hover:text-text-primary"
            }`}
          >
            <Users
              size={16}
              className={
                isActivePrefix(links.overview() + "/agents")
                  ? "text-primary-400"
                  : ""
              }
            />
            <span className="flex-1 text-left">Agents</span>
            {agentsExpanded ? (
              <ChevronDown size={14} className="text-text-muted" />
            ) : (
              <ChevronRight size={14} className="text-text-muted" />
            )}
          </button>
          {agentsExpanded && agents && <AgentList agents={agents} />}
        </div>

        <NavLink
          to={links.tasks()}
          icon={ListTodo}
          label="Tasks"
          isActive={isActivePrefix(links.tasks())}
        />
        <NavLink
          to={links.chat()}
          icon={MessageSquare}
          label="Chat"
          isActive={isActivePrefix(links.chat())}
        />
      </nav>

      {/* Footer */}
      {org && (
        <div className="shrink-0 border-t border-border-default px-4 py-3">
          <div className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-1.5 text-text-muted">
              <Activity size={12} />
              <span>Agents</span>
            </div>
            <span className="font-mono text-text-secondary">
              {org.agents.length}
            </span>
          </div>
          <div className="mt-2 flex items-center justify-between text-xs">
            <div className="flex items-center gap-1.5 text-text-muted">
              <DollarSign size={12} />
              <span>Cost</span>
            </div>
            <span className="font-mono text-text-secondary">
              {formatCost(org.total_cost)}
            </span>
          </div>
        </div>
      )}
    </aside>
  );

  // Mobile: overlay drawer
  if (isMobile) {
    return (
      <>
        {isOpen && (
          <div
            className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm animate-fade-in"
            onClick={close}
          />
        )}
        <div
          className={`fixed inset-y-0 left-14 z-50 transition-transform duration-200 ease-out ${
            isOpen ? "translate-x-0" : "-translate-x-full"
          }`}
        >
          {sidebarContent}
        </div>
      </>
    );
  }

  // Desktop
  return (
    <div
      className={`shrink-0 transition-[width] duration-150 ease-out ${
        isOpen ? "w-56" : "w-0"
      } overflow-hidden`}
    >
      {sidebarContent}
    </div>
  );
}
