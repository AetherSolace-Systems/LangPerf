"use client";

// Client-side API helpers for PATCH actions. Uses the shared apiFetch, which
// resolves to CLIENT_API_URL + credentials: "include" when running in the
// browser.

import { apiFetch } from "./fetch-utils";

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
  return apiFetch<unknown>(`/api/trajectories/${id}`, {
    method: "PATCH",
    body,
  });
}

export async function patchNode(
  spanId: string,
  patch: { notes?: string | null; clear_notes?: boolean },
) {
  const body = {
    notes: patch.notes ?? null,
    clear_notes: !!patch.clear_notes,
  };
  return apiFetch<unknown>(`/api/nodes/${spanId}`, {
    method: "PATCH",
    body,
  });
}
