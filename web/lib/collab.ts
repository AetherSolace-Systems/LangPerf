import { apiBase, CLIENT_API_URL } from "./api";

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

export async function listComments(trajectoryId: string, spanId: string, cookie?: string): Promise<Comment[]> {
  const base = apiBase();
  const res = await fetch(
    `${base}/api/trajectories/${trajectoryId}/nodes/${spanId}/comments`,
    cookie
      ? { headers: { cookie }, cache: "no-store" }
      : { credentials: "include", cache: "no-store" },
  );
  if (!res.ok) throw new Error(`listComments ${res.status}`);
  return res.json();
}

export async function createComment(trajectoryId: string, spanId: string, body: string): Promise<Comment> {
  const res = await fetch(
    `${CLIENT_API_URL}/api/trajectories/${trajectoryId}/nodes/${spanId}/comments`,
    {
      method: "POST",
      credentials: "include",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ body }),
    },
  );
  if (!res.ok) throw new Error(`createComment ${res.status}`);
  return res.json();
}

export async function resolveComment(commentId: string): Promise<Comment> {
  const res = await fetch(`${CLIENT_API_URL}/api/comments/${commentId}/resolve`, {
    method: "POST",
    credentials: "include",
  });
  return res.json();
}

export async function listNotifications(unreadOnly = false, cookie?: string): Promise<Notification[]> {
  const base = apiBase();
  const url = `${base}/api/notifications${unreadOnly ? "?unread_only=true" : ""}`;
  const res = await fetch(
    url,
    cookie
      ? { headers: { cookie }, cache: "no-store" }
      : { credentials: "include", cache: "no-store" },
  );
  return res.json();
}

export async function markNotificationRead(id: string): Promise<void> {
  await fetch(`${CLIENT_API_URL}/api/notifications/${id}/read`, {
    method: "POST",
    credentials: "include",
  });
}

export async function listFailureModes(cookie?: string): Promise<FailureMode[]> {
  const base = apiBase();
  const res = await fetch(`${base}/api/failure-modes`,
    cookie
      ? { headers: { cookie }, cache: "no-store" }
      : { credentials: "include", cache: "no-store" },
  );
  return res.json();
}

export async function tagFailureMode(trajectoryId: string, failureModeId: string): Promise<void> {
  await fetch(`${CLIENT_API_URL}/api/trajectories/${trajectoryId}/failure-modes`, {
    method: "POST",
    credentials: "include",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ failure_mode_id: failureModeId }),
  });
}

export async function untagFailureMode(trajectoryId: string, failureModeId: string): Promise<void> {
  await fetch(`${CLIENT_API_URL}/api/trajectories/${trajectoryId}/failure-modes/${failureModeId}`, {
    method: "DELETE",
    credentials: "include",
  });
}

export async function assignReviewer(trajectoryId: string, userId: string | null): Promise<void> {
  await fetch(`${CLIENT_API_URL}/api/trajectories/${trajectoryId}/assign`, {
    method: "POST",
    credentials: "include",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ user_id: userId }),
  });
}

export async function createShareLink(trajectoryId: string): Promise<{ token: string }> {
  const res = await fetch(`${CLIENT_API_URL}/api/trajectories/${trajectoryId}/share`, {
    method: "POST",
    credentials: "include",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({}),
  });
  return res.json();
}
