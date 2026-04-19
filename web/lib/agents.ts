import { apiBase } from "./api";

export type CreateAgentPayload = {
  name: string;
  display_name?: string;
  description?: string;
  language?: string;
  github_url?: string;
  project_slug?: string;
};

export async function createAgent(
  payload: CreateAgentPayload,
): Promise<{ agent: any; token: string }> {
  const res = await fetch(`${apiBase()}/api/agents`, {
    method: "POST",
    credentials: "include",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "create failed" }));
    throw new Error(body.detail ?? `createAgent ${res.status}`);
  }
  return res.json();
}

export async function rotateAgentToken(
  name: string,
): Promise<{ token: string; token_prefix: string }> {
  const res = await fetch(
    `${apiBase()}/api/agents/${encodeURIComponent(name)}/rotate-token`,
    {
      method: "POST",
      credentials: "include",
    },
  );
  if (!res.ok) throw new Error(`rotateAgentToken ${res.status}`);
  return res.json();
}

export async function issueAgentToken(
  name: string,
): Promise<{ token: string; token_prefix: string }> {
  const res = await fetch(
    `${apiBase()}/api/agents/${encodeURIComponent(name)}/issue-token`,
    {
      method: "POST",
      credentials: "include",
    },
  );
  if (!res.ok) throw new Error(`issueAgentToken ${res.status}`);
  return res.json();
}

export async function deleteAgent(name: string): Promise<void> {
  const res = await fetch(
    `${apiBase()}/api/agents/${encodeURIComponent(name)}`,
    {
      method: "DELETE",
      credentials: "include",
    },
  );
  if (!res.ok) throw new Error(`deleteAgent ${res.status}`);
}
