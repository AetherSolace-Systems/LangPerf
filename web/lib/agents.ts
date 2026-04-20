import { apiFetch, apiFetchVoid } from "./fetch-utils";

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
  return apiFetch<{ agent: any; token: string }>(`/api/agents`, {
    method: "POST",
    body: payload,
  });
}

export async function rotateAgentToken(
  name: string,
): Promise<{ token: string; token_prefix: string }> {
  return apiFetch<{ token: string; token_prefix: string }>(
    `/api/agents/${encodeURIComponent(name)}/rotate-token`,
    { method: "POST" },
  );
}

export async function issueAgentToken(
  name: string,
): Promise<{ token: string; token_prefix: string }> {
  return apiFetch<{ token: string; token_prefix: string }>(
    `/api/agents/${encodeURIComponent(name)}/issue-token`,
    { method: "POST" },
  );
}

export async function deleteAgent(name: string): Promise<void> {
  await apiFetchVoid(`/api/agents/${encodeURIComponent(name)}`, {
    method: "DELETE",
  });
}
