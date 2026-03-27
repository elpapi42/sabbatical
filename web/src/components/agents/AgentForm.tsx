import { useState, useEffect } from "react";
import { X } from "lucide-react";
import { useAgents } from "@/api/queries";
import { useCreateAgent, useUpdateAgent } from "@/api/mutations";
import { ApiRequestError } from "@/api/client";
import { useToast } from "@/components/shared/Toast";
import { SNAKE_CASE_RE } from "@/lib/format";
import type { AgentDetail } from "@/api/types";

interface Props {
  mode: "create" | "edit";
  organization: string;
  agent?: AgentDetail;
  open: boolean;
  onClose: () => void;
}

export default function AgentForm({
  mode,
  organization,
  agent,
  open,
  onClose,
}: Props) {
  const [name, setName] = useState("");
  const [boss, setBoss] = useState("");
  const [instructionsPath, setInstructionsPath] = useState("");
  const [maxIterations, setMaxIterations] = useState("");
  const [model, setModel] = useState("");
  const [error, setError] = useState("");
  const { toast } = useToast();

  const { data: agents } = useAgents(organization);
  const createMut = useCreateAgent(organization);
  const updateMut = useUpdateAgent(organization, agent?.name ?? "");

  useEffect(() => {
    if (!open) return;
    if (mode === "edit" && agent) {
      setBoss(agent.boss ?? "");
      setInstructionsPath(agent.instructions_path);
      setMaxIterations(agent.max_iterations?.toString() ?? "");
      setModel(agent.model ?? "");
    } else {
      setName("");
      setBoss("");
      setInstructionsPath("");
      setMaxIterations("");
      setModel("");
    }
    setError("");
  }, [open, mode, agent]);

  if (!open) return null;

  const availableBosses =
    agents?.filter(
      (a) => !a.is_removed && (mode === "create" || a.name !== agent?.name),
    ) ?? [];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (mode === "create" && !SNAKE_CASE_RE.test(name)) {
      setError(
        "Name must be snake_case (lowercase, underscores, starts with letter)",
      );
      return;
    }

    try {
      if (mode === "create") {
        await createMut.mutateAsync({
          name,
          boss: boss || undefined,
          instructions_path: instructionsPath,
          max_iterations: maxIterations ? parseInt(maxIterations) : undefined,
          model: model || undefined,
        });
        toast("Agent added", "success");
      } else {
        await updateMut.mutateAsync({
          boss: boss === "" ? null : boss || undefined,
          instructions_path: instructionsPath || undefined,
          max_iterations: maxIterations ? parseInt(maxIterations) : undefined,
          model: model === "default" ? undefined : model || undefined,
        });
        toast("Agent updated", "success");
      }
      onClose();
    } catch (err) {
      if (err instanceof ApiRequestError) setError(err.detail);
      else setError("An unexpected error occurred");
    }
  };

  const isLoading = createMut.isPending || updateMut.isPending;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-lg border border-neutral-700 bg-neutral-900 shadow-2xl">
        <div className="flex items-center justify-between border-b border-neutral-800 px-5 py-4">
          <h3 className="text-lg font-semibold">
            {mode === "create" ? "Add Agent" : "Edit Agent"}
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
                placeholder="frontend_dev"
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
                {agent?.name}
              </div>
            </div>
          )}

          <div>
            <label className="mb-1 block text-sm font-medium text-neutral-300">
              Boss
            </label>
            <select
              value={boss}
              onChange={(e) => setBoss(e.target.value)}
              className="w-full rounded-md border border-neutral-700 bg-neutral-800 px-3 py-2 text-sm text-neutral-100 focus:border-primary-500 focus:outline-none"
            >
              <option value="">(None — Root Agent)</option>
              {availableBosses.map((a) => (
                <option key={a.name} value={a.name}>
                  {a.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-neutral-300">
              Instructions Path
            </label>
            <input
              value={instructionsPath}
              onChange={(e) => setInstructionsPath(e.target.value)}
              placeholder="/path/to/instructions.md"
              className="w-full rounded-md border border-neutral-700 bg-neutral-800 px-3 py-2 text-sm font-mono text-neutral-100 placeholder:text-neutral-600 focus:border-primary-500 focus:outline-none"
              required={mode === "create"}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-sm font-medium text-neutral-300">
                Max Iterations
              </label>
              <input
                type="number"
                value={maxIterations}
                onChange={(e) => setMaxIterations(e.target.value)}
                placeholder="50"
                className="w-full rounded-md border border-neutral-700 bg-neutral-800 px-3 py-2 text-sm text-neutral-100 placeholder:text-neutral-600 focus:border-primary-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-neutral-300">
                Model
              </label>
              <input
                value={model}
                onChange={(e) => setModel(e.target.value)}
                placeholder="System default"
                className="w-full rounded-md border border-neutral-700 bg-neutral-800 px-3 py-2 text-sm text-neutral-100 placeholder:text-neutral-600 focus:border-primary-500 focus:outline-none"
              />
            </div>
          </div>

          {error && <p className="text-sm text-red-400">{error}</p>}

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
              {isLoading ? "Saving..." : mode === "create" ? "Add Agent" : "Save"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
