"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  type Project,
  createProject,
  updateProject,
  deleteProject,
} from "@/lib/projects";

type Mode = { kind: "idle" } | { kind: "creating" } | { kind: "editing"; slug: string };

export function ProjectsManager({ initial }: { initial: Project[] }) {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>(initial);
  const [mode, setMode] = useState<Mode>({ kind: "idle" });
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    // Soft refresh via server component
    router.refresh();
  }

  async function handleCreate(payload: {
    name: string;
    slug?: string;
    description?: string;
    color?: string;
  }) {
    setError(null);
    try {
      const p = await createProject(payload);
      setProjects((prev) => [...prev, p].sort((a, b) => a.slug.localeCompare(b.slug)));
      setMode({ kind: "idle" });
      refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "create failed");
    }
  }

  async function handleUpdate(
    slug: string,
    payload: {
      name?: string;
      description?: string;
      color?: string;
      rename_to_slug?: string;
    },
  ) {
    setError(null);
    try {
      const updated = await updateProject(slug, payload);
      setProjects((prev) =>
        prev.map((p) => (p.slug === slug ? { ...p, ...updated } : p)).sort((a, b) => a.slug.localeCompare(b.slug)),
      );
      setMode({ kind: "idle" });
      refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "update failed");
    }
  }

  async function handleDelete(slug: string) {
    if (!confirm(`Delete project "${slug}"? (will fail if agents are assigned)`)) return;
    setError(null);
    try {
      await deleteProject(slug);
      setProjects((prev) => prev.filter((p) => p.slug !== slug));
      refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "delete failed");
    }
  }

  return (
    <div className="space-y-4 max-w-[860px]">
      <div className="flex items-center justify-between">
        <div className="text-xs text-warm-fog/70">
          {projects.length} project{projects.length === 1 ? "" : "s"} · one per deployment workspace.
        </div>
        <button
          type="button"
          onClick={() => setMode({ kind: "creating" })}
          className="rounded bg-aether-teal px-3 py-1.5 text-xs font-semibold text-carbon"
        >
          + New project
        </button>
      </div>

      {error ? (
        <div className="border border-warn/40 bg-warn/10 rounded px-3 py-2 text-xs text-warn">
          {error}
        </div>
      ) : null}

      {mode.kind === "creating" ? (
        <ProjectForm
          initial={null}
          onCancel={() => setMode({ kind: "idle" })}
          onSubmit={handleCreate}
        />
      ) : null}

      <div className="overflow-hidden rounded border border-[color:var(--border)] bg-[color:var(--surface)]">
        <table className="w-full text-left text-xs">
          <thead className="bg-carbon text-[10px] uppercase text-warm-fog/60">
            <tr>
              <th className="px-3 py-2">Name</th>
              <th className="px-3 py-2">Slug</th>
              <th className="px-3 py-2">Description</th>
              <th className="px-3 py-2">Agents</th>
              <th className="px-3 py-2 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {projects.length === 0 ? (
              <tr>
                <td colSpan={5} className="p-6 text-center text-warm-fog/50">
                  No projects yet.
                </td>
              </tr>
            ) : (
              projects.map((p) =>
                mode.kind === "editing" && mode.slug === p.slug ? (
                  <tr key={p.slug} className="border-t border-[color:var(--border)]">
                    <td colSpan={5} className="px-3 py-3 bg-carbon">
                      <ProjectForm
                        initial={p}
                        onCancel={() => setMode({ kind: "idle" })}
                        onSubmit={(payload) =>
                          handleUpdate(p.slug, {
                            name: payload.name,
                            description: payload.description,
                            color: payload.color,
                            rename_to_slug:
                              payload.slug && payload.slug !== p.slug ? payload.slug : undefined,
                          })
                        }
                      />
                    </td>
                  </tr>
                ) : (
                  <tr key={p.slug} className="border-t border-[color:var(--border)]">
                    <td className="px-3 py-2">
                      <span className="inline-flex items-center gap-1.5">
                        <span
                          style={{
                            background: "var(--accent)",
                            width: 6,
                            height: 6,
                            borderRadius: 999,
                          }}
                        />
                        <span className="text-warm-fog">{p.name}</span>
                      </span>
                    </td>
                    <td className="px-3 py-2 font-mono text-[11px] text-warm-fog/70">
                      {p.slug}
                    </td>
                    <td className="px-3 py-2 text-warm-fog/70">
                      {p.description ?? "—"}
                    </td>
                    <td className="px-3 py-2 text-warm-fog/70 tabular-nums">
                      {p.agent_count ?? 0}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <div className="inline-flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => setMode({ kind: "editing", slug: p.slug })}
                          className="rounded bg-carbon px-2 py-1 text-[11px] text-warm-fog/70 hover:text-warm-fog"
                        >
                          Edit
                        </button>
                        {p.slug !== "default" ? (
                          <button
                            type="button"
                            onClick={() => handleDelete(p.slug)}
                            className="rounded px-2 py-1 text-[11px] text-warn hover:bg-warn/10"
                          >
                            Delete
                          </button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ),
              )
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ProjectForm({
  initial,
  onCancel,
  onSubmit,
}: {
  initial: Project | null;
  onCancel: () => void;
  onSubmit: (payload: {
    name: string;
    slug?: string;
    description?: string;
    color?: string;
  }) => Promise<void>;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [slug, setSlug] = useState(initial?.slug ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [color, setColor] = useState(initial?.color ?? "");
  const [pending, setPending] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setPending(true);
    try {
      await onSubmit({
        name,
        slug: slug || undefined,
        description: description || undefined,
        color: color || undefined,
      });
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-2 max-w-[560px]">
      <div className="grid grid-cols-2 gap-2">
        <label className="block text-xs text-warm-fog/70">
          Name
          <input
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="mt-1 w-full rounded border border-[color:var(--border)] bg-carbon px-2 py-1.5 text-xs text-warm-fog focus:border-aether-teal focus:outline-none"
          />
        </label>
        <label className="block text-xs text-warm-fog/70">
          Slug (optional)
          <input
            pattern="[a-z0-9][a-z0-9-]*"
            value={slug}
            onChange={(e) => setSlug(e.target.value)}
            placeholder="auto-generated from name"
            className="mt-1 w-full rounded border border-[color:var(--border)] bg-carbon px-2 py-1.5 text-xs font-mono text-warm-fog focus:border-aether-teal focus:outline-none"
          />
        </label>
      </div>
      <label className="block text-xs text-warm-fog/70">
        Description
        <input
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          className="mt-1 w-full rounded border border-[color:var(--border)] bg-carbon px-2 py-1.5 text-xs text-warm-fog focus:border-aether-teal focus:outline-none"
        />
      </label>
      <label className="block text-xs text-warm-fog/70">
        Color (token name — e.g. aether-teal, peach-neon)
        <input
          value={color}
          onChange={(e) => setColor(e.target.value)}
          className="mt-1 w-full rounded border border-[color:var(--border)] bg-carbon px-2 py-1.5 text-xs font-mono text-warm-fog focus:border-aether-teal focus:outline-none"
        />
      </label>
      <div className="flex gap-2 pt-1">
        <button
          type="button"
          onClick={onCancel}
          className="rounded bg-carbon px-3 py-1.5 text-xs text-warm-fog/70"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={pending}
          className="rounded bg-aether-teal px-3 py-1.5 text-xs font-semibold text-carbon disabled:opacity-50"
        >
          {pending ? "Saving..." : initial ? "Save" : "Create"}
        </button>
      </div>
    </form>
  );
}
