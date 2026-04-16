// Server-side API client for talking to langperf-api across the docker network.
// Client-side code should use `NEXT_PUBLIC_LANGPERF_API_URL` (exposed via env).

const SERVER_API_URL =
  process.env.LANGPERF_API_URL ?? "http://localhost:4318";

export type TrajectorySummary = {
  id: string;
  trace_id: string | null;
  service_name: string;
  environment: string | null;
  name: string | null;
  started_at: string;
  ended_at: string | null;
  status_tag: string | null;
  notes: string | null;
  step_count: number;
  token_count: number;
  duration_ms: number | null;
};

export type Span = {
  span_id: string;
  trace_id: string;
  trajectory_id: string;
  parent_span_id: string | null;
  name: string;
  kind: string | null;
  started_at: string;
  ended_at: string | null;
  duration_ms: number | null;
  attributes: Record<string, unknown>;
  events: unknown[] | null;
  status_code: string | null;
  notes: string | null;
};

export type TrajectoryDetail = TrajectorySummary & {
  spans: Span[];
};

export type TrajectoryListResponse = {
  items: TrajectorySummary[];
  total: number;
  limit: number;
  offset: number;
};

async function apiFetch<T>(path: string): Promise<T> {
  const url = `${SERVER_API_URL}${path}`;
  const resp = await fetch(url, { cache: "no-store" });
  if (!resp.ok) {
    throw new Error(`langperf-api ${resp.status} at ${url}`);
  }
  return resp.json();
}

export async function listTrajectories(
  { limit = 50, offset = 0 }: { limit?: number; offset?: number } = {},
): Promise<TrajectoryListResponse> {
  return apiFetch<TrajectoryListResponse>(
    `/api/trajectories?limit=${limit}&offset=${offset}`,
  );
}

export async function getTrajectory(id: string): Promise<TrajectoryDetail> {
  return apiFetch<TrajectoryDetail>(`/api/trajectories/${id}`);
}
