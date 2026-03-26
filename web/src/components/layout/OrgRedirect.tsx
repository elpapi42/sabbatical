import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { useOrganizations } from "@/api/queries";
import { Building2 } from "lucide-react";
import EmptyState from "@/components/shared/EmptyState";
import OrgForm from "@/components/organizations/OrgForm";

export default function OrgRedirect() {
  const { data: orgs, isLoading } = useOrganizations();
  const navigate = useNavigate();
  const [showCreate, setShowCreate] = useState(false);

  useEffect(() => {
    if (orgs && orgs.length > 0) {
      navigate(`/org/${orgs[0].name}`, { replace: true });
    }
  }, [orgs, navigate]);

  if (isLoading) {
    return (
      <div className="flex h-dvh items-center justify-center bg-neutral-950">
        <div className="skeleton h-8 w-48" />
      </div>
    );
  }

  if (orgs && orgs.length === 0) {
    return (
      <div className="flex h-dvh items-center justify-center bg-neutral-950">
        <EmptyState
          icon={Building2}
          title="Welcome to Sabbatical"
          description="Create your first organization to start orchestrating AI agents."
          action={{
            label: "Create Organization",
            onClick: () => setShowCreate(true),
          }}
        />
        <OrgForm
          mode="create"
          open={showCreate}
          onClose={() => setShowCreate(false)}
          onSuccess={(name) => navigate(`/org/${name}`)}
        />
      </div>
    );
  }

  return null;
}
