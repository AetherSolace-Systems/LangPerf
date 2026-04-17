// Server-side API client for talking to langperf-api across the docker network.
// Client-side code should use `NEXT_PUBLIC_LANGPERF_API_URL` (exposed via env).

const SERVER_API_URL =
  process.env.LANGPERF_API_URL ?? "http://localhost:4318";

export const CLIENT_API_URL =
  process.env.NEXT_PUBLIC_LANGPERF_API_URL ?? "http://localhost:4318";

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

export type FacetsResponse = {
  services: string[];
  environments: string[];
  tags: string[];
};

export type ListFilters = {
  limit?: number;
  offset?: number;
  tag?: string;
  service?: string;
  environment?: string;
  q?: string;
};

function buildQuery(filters: ListFilters): string {
  const p = new URLSearchParams();
  if (filters.limit != null) p.set("limit", String(filters.limit));
  if (filters.offset != null) p.set("offset", String(filters.offset));
  if (filters.tag) p.set("tag", filters.tag);
  if (filters.service) p.set("service", filters.service);
  if (filters.environment) p.set("environment", filters.environment);
  if (filters.q) p.set("q", filters.q);
  const s = p.toString();
  return s ? `?${s}` : "";
}

async function apiFetch<T>(path: string): Promise<T> {
  const url = `${SERVER_API_URL}${path}`;
  const resp = await fetch(url, { cache: "no-store" });
  if (!resp.ok) throw new Error(`langperf-api ${resp.status} at ${url}`);
  return resp.json();
}

export async function listTrajectories(
  filters: ListFilters = {},
): Promise<TrajectoryListResponse> {
  const base = {
    limit: filters.limit ?? 100,
    offset: filters.offset ?? 0,
    ...filters,
  };
  return apiFetch<TrajectoryListResponse>(
    `/api/trajectories${buildQuery(base)}`,
  );
}

export async function getTrajectory(id: string): Promise<TrajectoryDetail> {
  return apiFetch<TrajectoryDetail>(`/api/trajectories/${id}`);
}

export async function getFacets(): Promise<FacetsResponse> {
  return apiFetch<FacetsResponse>(`/api/trajectories/facets`);
}
