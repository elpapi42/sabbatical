import { useParams } from "react-router";
import BreadcrumbBar from "@/components/layout/BreadcrumbBar";
import AgentDetail from "@/components/agents/AgentDetail";
import { useCurrentOrg } from "@/context/OrgContext";
import { useOrgLinks } from "@/lib/orgLinks";

export default function AgentDetailPage() {
  const { agentName } = useParams<{ agentName: string }>();
  const { orgName } = useCurrentOrg();
  const links = useOrgLinks();
  if (!agentName) return null;

  return (
    <>
      <BreadcrumbBar
        items={[
          { label: "Overview", to: links.overview() },
          { label: agentName },
        ]}
      />
      <div className="p-4 md:p-6">
        <AgentDetail organization={orgName} agentName={agentName} />
      </div>
    </>
  );
}
