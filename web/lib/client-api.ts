"use client";

// Client-side API helpers for PATCH actions. Uses NEXT_PUBLIC_LANGPERF_API_URL
// because these run in the browser, not the Next.js server.

const BASE =
  process.env.NEXT_PUBLIC_LANGPERF_API_URL ?? "http://localhost:4318";

export async function patchTrajectory(
  id: string,
  patch: {
    status_tag?: string | null;
    notes?: string | null;
    clear_tag?: boolean;
    clear_notes?: boolean;
  },
) {
  const body = {
    status_tag: patch.status_tag ?? null,
    notes: patch.notes ?? null,
    clear_tag: !!patch.clear_tag,
    clear_notes: !!patch.clear_notes,
  };
  const resp = await fetch(`${BASE}/api/trajectories/${id}`, {
    method: "PATCH",
    credentials: "include",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) throw new Error(`patch trajectory ${resp.status}`);
  return resp.json();
}

export async function patchNode(
  spanId: string,
  patch: { notes?: string | null; clear_notes?: boolean },
) {
  const body = {
    notes: patch.notes ?? null,
    clear_notes: !!patch.clear_notes,
  };
  const resp = await fetch(`${BASE}/api/nodes/${spanId}`, {
    method: "PATCH",
    credentials: "include",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) throw new Error(`patch node ${resp.status}`);
  return resp.json();
}
