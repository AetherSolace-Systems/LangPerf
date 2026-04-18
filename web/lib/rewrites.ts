import { CLIENT_API_URL, SERVER_API_URL } from "./api";

export type ProposedStep =
  | { kind: "tool_call"; tool_name: string; arguments: Record<string, unknown>; reasoning?: string }
  | { kind: "final_answer"; text: string };

export type Rewrite = {
  id: string;
  trajectory_id: string;
  branch_span_id: string;
  author_id: string;
  author_display_name: string;
  rationale: string;
  proposed_steps: ProposedStep[];
  status: "draft" | "submitted";
  created_at: string;
  updated_at: string;
};

export async function listRewrites(trajectoryId: string, cookie?: string): Promise<Rewrite[]> {
  const base = cookie ? SERVER_API_URL : CLIENT_API_URL;
  const res = await fetch(
    `${base}/api/trajectories/${trajectoryId}/rewrites`,
    cookie ? { headers: { cookie }, cache: "no-store" } : { credentials: "include", cache: "no-store" },
  );
  return res.json();
}

export async function createRewrite(
  trajectoryId: string,
  payload: {
    branch_span_id: string;
    rationale: string;
    proposed_steps: ProposedStep[];
    status: "draft" | "submitted";
  },
): Promise<Rewrite> {
  const res = await fetch(`${CLIENT_API_URL}/api/trajectories/${trajectoryId}/rewrites`, {
    method: "POST",
    credentials: "include",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`createRewrite ${res.status}`);
  return res.json();
}

export async function updateRewrite(
  id: string,
  payload: Partial<{
    rationale: string;
    proposed_steps: ProposedStep[];
    status: "draft" | "submitted";
  }>,
): Promise<Rewrite> {
  const res = await fetch(`${CLIENT_API_URL}/api/rewrites/${id}`, {
    method: "PATCH",
    credentials: "include",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  return res.json();
}

export async function deleteRewrite(id: string): Promise<void> {
  await fetch(`${CLIENT_API_URL}/api/rewrites/${id}`, {
    method: "DELETE",
    credentials: "include",
  });
}
