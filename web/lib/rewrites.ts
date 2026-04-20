import { apiFetch, apiFetchVoid } from "./fetch-utils";

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

export async function listRewrites(trajectoryId: string): Promise<Rewrite[]> {
  return apiFetch<Rewrite[]>(`/api/trajectories/${trajectoryId}/rewrites`);
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
  return apiFetch<Rewrite>(`/api/trajectories/${trajectoryId}/rewrites`, {
    method: "POST",
    body: payload,
  });
}

export async function updateRewrite(
  id: string,
  payload: Partial<{
    rationale: string;
    proposed_steps: ProposedStep[];
    status: "draft" | "submitted";
  }>,
): Promise<Rewrite> {
  return apiFetch<Rewrite>(`/api/rewrites/${id}`, {
    method: "PATCH",
    body: payload,
  });
}

export async function deleteRewrite(id: string): Promise<void> {
  await apiFetchVoid(`/api/rewrites/${id}`, { method: "DELETE" });
}
