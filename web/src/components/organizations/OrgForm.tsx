import { useState, useEffect } from "react";
import { X } from "lucide-react";
import { useCreateOrganization, useUpdateOrganization } from "@/api/mutations";
import { ApiRequestError } from "@/api/client";
import { useToast } from "@/components/shared/Toast";
import { SNAKE_CASE_RE } from "@/lib/format";
import type { OrganizationDetail } from "@/api/types";

interface Props {
  mode: "create" | "edit";
  organization?: OrganizationDetail;
  open: boolean;
  onClose: () => void;
  onSuccess?: (name: string) => void;
}

export default function OrgForm({
  mode,
  organization,
  open,
  onClose,
  onSuccess,
}: Props) {
  const [name, setName] = useState("");
  const [workspacePath, setWorkspacePath] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const { toast } = useToast();

  const createMut = useCreateOrganization();
  const updateMut = useUpdateOrganization(organization?.name ?? "");

  useEffect(() => {
    if (open && organization && mode === "edit") {
      setWorkspacePath(organization.workspace_path);
      setDescription(organization.description ?? "");
    }
    if (open && mode === "create") {
      setName("");
      setWorkspacePath("");
      setDescription("");
    }
    setError("");
  }, [open, organization, mode]);

  if (!open) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (mode === "create" && !SNAKE_CASE_RE.test(name)) {
      setError("Name must be snake_case (lowercase, underscores, starts with letter)");
      return;
    }

    try {
      if (mode === "create") {
        await createMut.mutateAsync({
          name,
          workspace_path: workspacePath,
          description: description || undefined,
        });
        toast("Organization created", "success");
        onSuccess?.(name);
      } else {
        await updateMut.mutateAsync({
          workspace_path: workspacePath || undefined,
          description: description || undefined,
        });
        toast("Organization updated", "success");
      }
      onClose();
    } catch (err) {
      if (err instanceof ApiRequestError) {
        setError(err.detail);
      } else {
        setError("An unexpected error occurred");
      }
    }
  };

  const isLoading = createMut.isPending || updateMut.isPending;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-lg border border-neutral-700 bg-neutral-900 shadow-2xl">
        <div className="flex items-center justify-between border-b border-neutral-800 px-5 py-4">
          <h3 className="text-lg font-semibold">
            {mode === "create" ? "New Organization" : "Edit Organization"}
          </h3>
          <button
            onClick={onClose}
            className="rounded p-1 text-neutral-400 hover:bg-neutral-800 hover:text-neutral-200"
          >
            <X size={18} />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {mode === "create" ? (
            <div>
              <label className="mb-1 block text-sm font-medium text-neutral-300">
                Name
              </label>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="my_project"
                className="w-full rounded-md border border-neutral-700 bg-neutral-800 px-3 py-2 text-sm text-neutral-100 placeholder:text-neutral-600 focus:border-primary-500 focus:outline-none"
                required
              />
            </div>
          ) : (
            <div>
              <label className="mb-1 block text-sm font-medium text-neutral-300">
                Name
              </label>
              <div className="rounded-md bg-neutral-800/50 px-3 py-2 text-sm text-neutral-500 font-mono">
                {organization?.name}
              </div>
            </div>
          )}
          <div>
            <label className="mb-1 block text-sm font-medium text-neutral-300">
              Workspace Path
            </label>
            <input
              value={workspacePath}
              onChange={(e) => setWorkspacePath(e.target.value)}
              placeholder="/home/user/project"
              className="w-full rounded-md border border-neutral-700 bg-neutral-800 px-3 py-2 text-sm font-mono text-neutral-100 placeholder:text-neutral-600 focus:border-primary-500 focus:outline-none"
              required
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-neutral-300">
              Description
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional description..."
              rows={3}
              className="w-full rounded-md border border-neutral-700 bg-neutral-800 px-3 py-2 text-sm text-neutral-100 placeholder:text-neutral-600 focus:border-primary-500 focus:outline-none resize-none"
            />
          </div>
          {error && (
            <p className="text-sm text-red-400">{error}</p>
          )}
          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md px-4 py-2 text-sm font-medium text-neutral-300 hover:bg-neutral-800"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isLoading}
              className="rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-500 disabled:opacity-50"
            >
              {isLoading ? "Saving..." : mode === "create" ? "Create" : "Save"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
