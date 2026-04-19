"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createAgent } from "@/lib/agents";
import { TokenDisplay } from "./token-display";
import type { Project } from "@/lib/projects";
import { ProjectSelect } from "@/components/projects/project-select";

export function NewAgentModal({
  onClose,
  projects,
  defaultProjectSlug = "default",
}: {
  onClose: () => void;
  projects: Project[];
  defaultProjectSlug?: string;
}) {
  const router = useRouter();
  const [name, setName] = useState("");
  const [language, setLanguage] = useState("python");
  const [description, setDescription] = useState("");
  const [githubUrl, setGithubUrl] = useState("");
  const [projectSlug, setProjectSlug] = useState(defaultProjectSlug);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [issuedToken, setIssuedToken] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setPending(true);
    setError(null);
    try {
      const res = await createAgent({
        name,
        language,
        description: description || undefined,
        github_url: githubUrl || undefined,
        project_slug: projectSlug || undefined,
      });
      setIssuedToken(res.token);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "unknown error");
    } finally {
      setPending(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface)] p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="mb-4 text-lg font-semibold text-aether-teal">
          {issuedToken ? "Agent created" : "Register new agent"}
        </h2>
        {issuedToken ? (
          <div className="space-y-3">
            <TokenDisplay token={issuedToken} />
            <p className="text-xs text-warm-fog/60">
              Set <code>LANGPERF_API_TOKEN</code> in your SDK environment.
            </p>
            <button
              type="button"
              onClick={onClose}
              className="w-full rounded bg-aether-teal px-3 py-2 text-sm font-semibold text-carbon"
            >
              Done
            </button>
          </div>
        ) : (
          <form className="space-y-3" onSubmit={onSubmit}>
            <label className="block text-xs text-warm-fog/70">
              Name (slug)
              <input
                required
                pattern="[a-zA-Z0-9][a-zA-Z0-9_-]*"
                className="mt-1 w-full rounded border border-[color:var(--border)] bg-carbon px-3 py-2 text-sm text-warm-fog focus:border-aether-teal focus:outline-none"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </label>
            {projects.length > 0 && (
              <label className="block text-xs text-warm-fog/70">
                Project
                <ProjectSelect projects={projects} value={projectSlug} onChange={setProjectSlug} />
              </label>
            )}
            <label className="block text-xs text-warm-fog/70">
              Language
              <select
                className="mt-1 w-full rounded border border-[color:var(--border)] bg-carbon px-3 py-2 text-sm text-warm-fog focus:border-aether-teal focus:outline-none"
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
              >
                <option value="python">Python</option>
                <option value="typescript">TypeScript</option>
                <option value="other">Other</option>
              </select>
            </label>
            <label className="block text-xs text-warm-fog/70">
              Description
              <input
                className="mt-1 w-full rounded border border-[color:var(--border)] bg-carbon px-3 py-2 text-sm text-warm-fog focus:border-aether-teal focus:outline-none"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </label>
            <label className="block text-xs text-warm-fog/70">
              GitHub URL (optional)
              <input
                className="mt-1 w-full rounded border border-[color:var(--border)] bg-carbon px-3 py-2 text-sm text-warm-fog focus:border-aether-teal focus:outline-none"
                value={githubUrl}
                onChange={(e) => setGithubUrl(e.target.value)}
              />
            </label>
            {error && <p className="text-xs text-warn">{error}</p>}
            <div className="flex gap-2">
              <button
                type="button"
                onClick={onClose}
                className="flex-1 rounded bg-carbon px-3 py-2 text-sm text-warm-fog/70"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={pending}
                className="flex-1 rounded bg-aether-teal px-3 py-2 text-sm font-semibold text-carbon disabled:opacity-50"
              >
                {pending ? "Creating..." : "Create"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
