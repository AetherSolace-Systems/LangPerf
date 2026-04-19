"use client";

import { useFullscreen } from "@/components/graph/fullscreen-context";

export function GraphToolbar() {
  const { fsOpen, toggleFs, expandAll, toggleExpandAll, collapseAll } =
    useFullscreen();

  return (
    <div className="absolute top-2 right-2 z-10 flex items-center gap-1 bg-[color:var(--surface)] border border-[color:var(--border)] rounded-md p-1">
      <ToolbarButton
        label="expand all"
        active={expandAll}
        onClick={toggleExpandAll}
        title="Expand every node (E)"
      />
      <ToolbarButton
        label="compact all"
        onClick={collapseAll}
        title="Collapse every node (C)"
      />
      <div className="w-px h-4 bg-[color:var(--border)] mx-1" />
      <ToolbarButton
        label={fsOpen ? "exit full-screen" : "full-screen"}
        active={fsOpen}
        onClick={toggleFs}
        title="Toggle full-screen (F)"
      />
    </div>
  );
}

function ToolbarButton({
  label,
  onClick,
  active = false,
  title,
}: {
  label: string;
  onClick: () => void;
  active?: boolean;
  title?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      aria-label={label}
      className={`px-2 py-1 text-[10px] uppercase tracking-wider font-mono rounded transition-colors ${
        active
          ? "bg-aether-teal/15 text-aether-teal"
          : "text-warm-fog/70 hover:text-warm-fog hover:bg-warm-fog/5"
      }`}
    >
      {label}
    </button>
  );
}
