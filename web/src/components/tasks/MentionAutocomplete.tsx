import { useAgents } from "@/api/queries";
import { useState, useEffect } from "react";

interface Props {
  organization: string;
  query: string;
  onSelect: (name: string) => void;
  visible: boolean;
}

export default function MentionAutocomplete({
  organization,
  query,
  onSelect,
  visible,
}: Props) {
  const { data: agents } = useAgents(organization);
  const [selectedIndex, setSelectedIndex] = useState(0);

  const options = [
    "user",
    ...(agents?.filter((a) => !a.is_removed).map((a) => a.name) ?? []),
  ].filter((name) => name.toLowerCase().includes(query.toLowerCase()));

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  useEffect(() => {
    if (!visible) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((i) => Math.min(i + 1, options.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((i) => Math.max(i - 1, 0));
      } else if (e.key === "Enter" || e.key === "Tab") {
        e.preventDefault();
        if (options[selectedIndex]) onSelect(options[selectedIndex]);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [visible, options, selectedIndex, onSelect]);

  if (!visible || options.length === 0) return null;

  return (
    <div className="absolute bottom-full left-0 mb-1 w-56 rounded-md border border-neutral-700 bg-neutral-800 py-1 shadow-lg">
      {options.slice(0, 10).map((name, i) => (
        <button
          key={name}
          className={`flex w-full items-center px-3 py-1.5 text-sm ${
            i === selectedIndex
              ? "bg-primary-600/20 text-primary-300"
              : "text-neutral-300 hover:bg-neutral-700"
          }`}
          onMouseDown={(e) => {
            e.preventDefault();
            onSelect(name);
          }}
        >
          <span className="text-neutral-500">@</span>
          {name}
        </button>
      ))}
    </div>
  );
}
