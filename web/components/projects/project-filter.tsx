"use client";

import { useRouter, useSearchParams, usePathname } from "next/navigation";
import type { Project } from "@/lib/projects";

export function ProjectFilter({ projects }: { projects: Project[] }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const active = params.get("project");

  function setProject(slug: string | null) {
    const sp = new URLSearchParams(params.toString());
    if (slug) sp.set("project", slug);
    else sp.delete("project");
    const q = sp.toString();
    router.push(q ? `${pathname}?${q}` : pathname);
  }

  return (
    <div className="flex items-center gap-1.5 flex-wrap mb-3">
      <Chip label="All projects" active={active == null} onClick={() => setProject(null)} />
      {projects.map((p) => (
        <Chip
          key={p.slug}
          label={p.name}
          active={active === p.slug}
          onClick={() => setProject(p.slug)}
          count={p.agent_count}
        />
      ))}
    </div>
  );
}

function Chip({
  label,
  active,
  onClick,
  count,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
  count?: number;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex items-center gap-1.5 rounded border px-2 py-1 text-[11px] font-mono transition-colors ${
        active
          ? "border-aether-teal text-aether-teal bg-aether-teal/10"
          : "border-[color:var(--border)] text-warm-fog/70 hover:text-warm-fog"
      }`}
    >
      <span style={{ background: active ? "var(--accent)" : "var(--muted)", width: 6, height: 6, borderRadius: 999 }} />
      {label}
      {count != null ? <span className="text-warm-fog/50">· {count}</span> : null}
    </button>
  );
}
