import { createContext, useContext, type ReactNode } from "react";
import { useParams } from "react-router";
import { useOrganization, useAgents } from "@/api/queries";
import type { OrganizationDetail, AgentSummary } from "@/api/types";

interface OrgContextValue {
  orgName: string;
  org: OrganizationDetail | undefined;
  agents: AgentSummary[] | undefined;
  isLoading: boolean;
}

const OrgContext = createContext<OrgContextValue | null>(null);

export function useCurrentOrg() {
  const ctx = useContext(OrgContext);
  if (!ctx) throw new Error("useCurrentOrg must be used within OrgProvider");
  return ctx;
}

export function OrgProvider({ children }: { children: ReactNode }) {
  const { name } = useParams<{ name: string }>();
  const orgName = name ?? "";
  const { data: org, isLoading: orgLoading } = useOrganization(orgName);
  const { data: agents, isLoading: agentsLoading } = useAgents(orgName);

  return (
    <OrgContext.Provider
      value={{
        orgName,
        org,
        agents,
        isLoading: orgLoading || agentsLoading,
      }}
    >
      {children}
    </OrgContext.Provider>
  );
}
