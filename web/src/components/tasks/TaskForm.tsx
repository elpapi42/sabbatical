import { useState, useEffect } from "react";
import { X } from "lucide-react";
import { useOrganizations } from "@/api/queries";
import { useCreateTask } from "@/api/mutations";
import { ApiRequestError } from "@/api/client";
import { useToast } from "@/components/shared/Toast";

interface Props {
  open: boolean;
  onClose: () => void;
  onSuccess?: (id: string) => void;
  defaultOrg?: string;
  orgLocked?: boolean;
}

export default function TaskForm({
  open,
  onClose,
  onSuccess,
  defaultOrg,
  orgLocked,
}: Props) {
  const [title, setTitle] = useState("");
  const [organization, setOrganization] = useState(defaultOrg ?? "");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const { toast } = useToast();

  const { data: orgs } = useOrganizations();
  const createMut = useCreateTask();

  useEffect(() => {
    if (open) {
      setTitle("");
      setOrganization(defaultOrg ?? "");
      setDescription("");
      setError("");
    }
  }, [open, defaultOrg]);

  if (!open) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    try {
      const result = await createMut.mutateAsync({
        title,
        organization,
        description: description || undefined,
      });
      toast("Task created", "success");
      onSuccess?.(result.id);
      onClose();
    } catch (err) {
      if (err instanceof ApiRequestError) setError(err.detail);
      else setError("An unexpected error occurred");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-lg rounded-lg border border-border-default bg-surface-raised shadow-2xl animate-enter">
        <div className="flex items-center justify-between border-b border-border-default px-5 py-4">
          <h3 className="text-lg font-semibold text-text-primary">New Task</h3>
          <button
            onClick={onClose}
            className="rounded p-1 text-text-muted hover:bg-surface-overlay hover:text-text-secondary"
          >
            <X size={18} />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-text-secondary">
              Title
            </label>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Implement feature X"
              className="w-full rounded-md border border-border-default bg-surface px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-primary-500 focus:outline-none"
              required
            />
          </div>

          {orgLocked ? (
            <div>
              <label className="mb-1 block text-sm font-medium text-text-secondary">
                Organization
              </label>
              <div className="flex items-center h-[38px] rounded-md border border-border-default bg-surface px-3 text-sm text-text-secondary">
                {organization}
              </div>
            </div>
          ) : (
            <div>
              <label className="mb-1 block text-sm font-medium text-text-secondary">
                Organization
              </label>
              <select
                value={organization}
                onChange={(e) => setOrganization(e.target.value)}
                className="w-full rounded-md border border-border-default bg-surface px-3 py-2 text-sm text-text-primary focus:border-primary-500 focus:outline-none"
                required
              >
                <option value="">Select...</option>
                {orgs?.map((o) => (
                  <option key={o.name} value={o.name}>
                    {o.name}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div>
            <label className="mb-1 block text-sm font-medium text-text-secondary">
              Description
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Detailed task specification (Markdown supported)..."
              rows={6}
              className="w-full rounded-md border border-border-default bg-surface px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-primary-500 focus:outline-none resize-none"
            />
          </div>

          {error && <p className="text-sm text-red-400">{error}</p>}

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md px-4 py-2 text-sm font-medium text-text-secondary hover:bg-surface-overlay"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={createMut.isPending}
              className="rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-500 disabled:opacity-50"
            >
              {createMut.isPending ? "Creating..." : "Create Task"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
