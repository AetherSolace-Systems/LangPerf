import { type ProjectRef } from "./api";
import { apiFetch, apiFetchVoid } from "./fetch-utils";

// Re-export the minimal embedded shape used by AgentSummary, so callers that
// only need {id, slug, name, color} can consume it without importing api.ts.
export type { ProjectRef };

// Full project record returned by /api/projects — extends the minimal ref
// with description + counts + timestamp.
export type Project = {
  id: string;
  slug: string;
  name: string;
  description: string | null;
  color: string | null;
  agent_count?: number;
  created_at?: string;
};

export async function listProjects(): Promise<Project[]> {
  return apiFetch<Project[]>(`/api/projects`);
}

export async function createProject(payload: {
  name: string;
  slug?: string;
  description?: string;
  color?: string;
}): Promise<Project> {
  return apiFetch<Project>(`/api/projects`, { method: "POST", body: payload });
}

export async function updateProject(
  slug: string,
  payload: { name?: string; description?: string; color?: string; rename_to_slug?: string },
): Promise<Project> {
  return apiFetch<Project>(`/api/projects/${encodeURIComponent(slug)}`, {
    method: "PATCH",
    body: payload,
  });
}

export async function deleteProject(slug: string): Promise<void> {
  await apiFetchVoid(`/api/projects/${encodeURIComponent(slug)}`, {
    method: "DELETE",
  });
}
