import { apiBase } from "./api";

export type Project = {
  id: string;
  slug: string;
  name: string;
  description: string | null;
  color: string | null;
  agent_count?: number;
  created_at?: string;
};

async function sendJson(method: string, path: string, body?: unknown) {
  const init: RequestInit = {
    method,
    credentials: "include",
    headers: body ? { "content-type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  };
  const res = await fetch(`${apiBase()}${path}`, init);
  if (!res.ok) {
    const b = await res.json().catch(() => ({ detail: `${method} ${path} failed` }));
    throw new Error(b.detail ?? `${method} ${path} ${res.status}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

export async function listProjects(): Promise<Project[]> {
  const base = apiBase();
  const url = `${base}/api/projects`;

  // Mirror the apiFetch cookie-forwarding pattern from lib/api.ts so server
  // components get auth forwarded and client components use credentials.
  let cookie = "";
  if (typeof window === "undefined") {
    try {
      const { headers } = await import("next/headers");
      cookie = headers().get("cookie") ?? "";
    } catch {
      // Outside a request context (build time); no cookie available.
    }
  }
  const init: RequestInit = { cache: "no-store" };
  if (cookie) init.headers = { cookie };
  else if (typeof window !== "undefined") init.credentials = "include";

  const res = await fetch(url, init);
  if (!res.ok) throw new Error(`listProjects ${res.status}`);
  return res.json();
}

export async function createProject(payload: {
  name: string;
  slug?: string;
  description?: string;
  color?: string;
}): Promise<Project> {
  return sendJson("POST", "/api/projects", payload);
}

export async function updateProject(
  slug: string,
  payload: { name?: string; description?: string; color?: string; rename_to_slug?: string },
): Promise<Project> {
  return sendJson("PATCH", `/api/projects/${encodeURIComponent(slug)}`, payload);
}

export async function deleteProject(slug: string): Promise<void> {
  await sendJson("DELETE", `/api/projects/${encodeURIComponent(slug)}`);
}
