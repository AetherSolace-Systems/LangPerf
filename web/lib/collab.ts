import { apiFetch, apiFetchVoid } from "./fetch-utils";

export type Comment = {
  id: string;
  trajectory_id: string;
  span_id: string | null;
  author_id: string;
  author_display_name: string;
  parent_comment_id: string | null;
  body: string;
  resolved: boolean;
  created_at: string;
  updated_at: string;
};

export type Notification = {
  id: string;
  kind: string;
  payload: Record<string, unknown>;
  read_at: string | null;
  created_at: string;
};

export type FailureMode = {
  id: string;
  slug: string;
  label: string;
  color: string;
};

export async function listComments(trajectoryId: string, spanId: string): Promise<Comment[]> {
  return apiFetch<Comment[]>(
    `/api/trajectories/${trajectoryId}/nodes/${spanId}/comments`,
  );
}

export async function createComment(trajectoryId: string, spanId: string, body: string): Promise<Comment> {
  return apiFetch<Comment>(
    `/api/trajectories/${trajectoryId}/nodes/${spanId}/comments`,
    { method: "POST", body: { body } },
  );
}

export async function resolveComment(commentId: string): Promise<Comment> {
  return apiFetch<Comment>(`/api/comments/${commentId}/resolve`, {
    method: "POST",
  });
}

export async function listNotifications(unreadOnly = false): Promise<Notification[]> {
  const path = `/api/notifications${unreadOnly ? "?unread_only=true" : ""}`;
  return apiFetch<Notification[]>(path);
}

export async function markNotificationRead(id: string): Promise<void> {
  await apiFetchVoid(`/api/notifications/${id}/read`, { method: "POST" });
}

export async function listFailureModes(): Promise<FailureMode[]> {
  return apiFetch<FailureMode[]>(`/api/failure-modes`);
}

export async function tagFailureMode(trajectoryId: string, failureModeId: string): Promise<void> {
  await apiFetchVoid(`/api/trajectories/${trajectoryId}/failure-modes`, {
    method: "POST",
    body: { failure_mode_id: failureModeId },
  });
}

export async function untagFailureMode(trajectoryId: string, failureModeId: string): Promise<void> {
  await apiFetchVoid(
    `/api/trajectories/${trajectoryId}/failure-modes/${failureModeId}`,
    { method: "DELETE" },
  );
}

export async function assignReviewer(trajectoryId: string, userId: string | null): Promise<void> {
  await apiFetchVoid(`/api/trajectories/${trajectoryId}/assign`, {
    method: "POST",
    body: { user_id: userId },
  });
}

export async function createShareLink(trajectoryId: string): Promise<{ token: string }> {
  return apiFetch<{ token: string }>(`/api/trajectories/${trajectoryId}/share`, {
    method: "POST",
    body: {},
  });
}
