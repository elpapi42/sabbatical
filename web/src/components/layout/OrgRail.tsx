import { Link, useParams, useNavigate } from "react-router";
import { Plus } from "lucide-react";
import { useState } from "react";
import { useOrganizations } from "@/api/queries";
import OrgForm from "@/components/organizations/OrgForm";

/** Deterministic color from org name */
const RAIL_COLORS = [
  "bg-violet-600",
  "bg-blue-600",
  "bg-emerald-600",
  "bg-amber-600",
  "bg-rose-600",
  "bg-cyan-600",
  "bg-pink-600",
  "bg-teal-600",
];

function hashColor(name: string) {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = (hash * 31 + name.charCodeAt(i)) | 0;
  }
  return RAIL_COLORS[Math.abs(hash) % RAIL_COLORS.length];
}

export default function OrgRail() {
  const { name: currentOrg } = useParams<{ name: string }>();
  const { data: orgs } = useOrganizations();
  const navigate = useNavigate();
  const [showCreate, setShowCreate] = useState(false);

  return (
    <>
      <aside className="flex h-full w-14 shrink-0 flex-col items-center border-r border-border-default bg-surface py-3 gap-2">
        {orgs?.map((org) => {
          const isActive = org.name === currentOrg;
          return (
            <Link
              key={org.name}
              to={`/org/${org.name}`}
              title={org.name}
              className="group relative"
            >
              {/* Active indicator */}
              <div
                className={`absolute -left-3 top-1/2 -translate-y-1/2 w-1 rounded-r-full bg-text-primary transition-all ${
                  isActive ? "h-6" : "h-0 group-hover:h-3"
                }`}
              />
              <div
                className={`flex h-10 w-10 items-center justify-center rounded-xl text-sm font-bold text-white transition-all ${hashColor(org.name)} ${
                  isActive
                    ? "rounded-lg ring-2 ring-text-primary/30"
                    : "opacity-60 hover:opacity-100 hover:rounded-lg"
                }`}
              >
                {org.name[0].toUpperCase()}
              </div>
            </Link>
          );
        })}

        {/* Divider */}
        {orgs && orgs.length > 0 && (
          <div className="mx-auto h-px w-8 bg-border-default" />
        )}

        {/* Add org button */}
        <button
          onClick={() => setShowCreate(true)}
          title="New Organization"
          className="flex h-10 w-10 items-center justify-center rounded-xl border-2 border-dashed border-border-default text-text-muted transition-colors hover:border-text-secondary hover:text-text-secondary"
        >
          <Plus size={18} />
        </button>
      </aside>

      <OrgForm
        mode="create"
        open={showCreate}
        onClose={() => setShowCreate(false)}
        onSuccess={(name) => navigate(`/org/${name}`)}
      />
    </>
  );
}
