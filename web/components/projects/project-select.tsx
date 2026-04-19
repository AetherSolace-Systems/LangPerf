"use client";

import type { Project } from "@/lib/projects";

export function ProjectSelect({
  projects,
  value,
  onChange,
}: {
  projects: Project[];
  value: string;
  onChange: (slug: string) => void;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="mt-1 w-full rounded border border-[color:var(--border)] bg-carbon px-3 py-2 text-sm text-warm-fog focus:border-aether-teal focus:outline-none"
    >
      {projects.map((p) => (
        <option key={p.slug} value={p.slug}>
          {p.name}
        </option>
      ))}
    </select>
  );
}
