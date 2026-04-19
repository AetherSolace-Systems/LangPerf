// Server-side API client for talking to langperf-api across the docker network.
// Client-side code should use `NEXT_PUBLIC_LANGPERF_API_URL` (exposed via env).

export const SERVER_API_URL =
  process.env.LANGPERF_API_URL ?? "http://localhost:4318";

export const CLIENT_API_URL =
  process.env.NEXT_PUBLIC_LANGPERF_API_URL ?? "http://localhost:4318";

// Pick the right base URL by execution context, not by cookie presence.
// Cookie-based selection breaks in single-user mode (no session cookie) — server
// components then hit localhost:4318 from inside the container.
export function apiBase(): string {
  return typeof window === "undefined" ? SERVER_API_URL : CLIENT_API_URL;
}

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
  const base = apiBase();
  const url = `${base}${path}`;
  // On the server, forward the incoming session cookie so authenticated
  // calls don't 401. `next/headers` is dynamic import because this module
  // is also pulled into client bundles where the import doesn't resolve.
  let cookie = "";
  if (typeof window === "undefined") {
    try {
      const { headers } = await import("next/headers");
      cookie = headers().get("cookie") ?? "";
    } catch {
      // Outside a request context (e.g. build-time); no cookie available.
    }
  }
  const init: RequestInit = { cache: "no-store" };
  if (cookie) init.headers = { cookie };
  else if (typeof window !== "undefined") init.credentials = "include";
  const resp = await fetch(url, init);
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

// ── Agents (Phase 2b) ─────────────────────────────────────────────────

export type ProjectRef = {
  id: string;
  slug: string;
  name: string;
  color: string | null;
};

export type AgentMiniMetrics = {
  runs: number;
  error_rate: number;
  p95_latency_ms: number | null;
};

export type AgentSummary = {
  id: string;
  name: string;
  display_name: string | null;
  description: string | null;
  owner: string | null;
  github_url: string | null;
  language: string | null;
  token_prefix: string | null;
  last_token_used_at: string | null;
  created_at: string;
  updated_at: string;
  project: ProjectRef | null;
};

export type AgentSummaryWithMetrics = AgentSummary & {
  metrics: AgentMiniMetrics;
  sparkline: number[];
  version_count: number;
  environments: string[];
};

export type AgentVersionSummary = {
  id: string;
  label: string;
  git_sha: string | null;
  short_sha: string | null;
  package_version: string | null;
  first_seen_at: string;
  last_seen_at: string;
};

export type AgentDetail = AgentSummary & {
  signature: string;
  versions: AgentVersionSummary[];
};

export type AgentMetrics = {
  agent: string;
  window: string;
  runs: number;
  errors: number;
  error_rate: number;
  p50_latency_ms: number | null;
  p95_latency_ms: number | null;
  p99_latency_ms: number | null;
  total_tokens: number;
  latency_series?: LatencyPoint[];
};

export type AgentToolUsage = {
  tool: string;
  calls: number;
  errors: number;
};

export type AgentRunRow = {
  id: string;
  started_at: string;
  ended_at: string | null;
  duration_ms: number | null;
  step_count: number;
  token_count: number;
  input_tokens: number;
  output_tokens: number;
  status_tag: string | null;
  name: string | null;
  environment: string | null;
  version_label: string | null;
  agent_name?: string | null;
};

export type AgentRunsResponse = {
  items: AgentRunRow[];
  total: number;
  limit: number;
  offset: number;
};

// ── Overview (dashboard) ──────────────────────────────────────────────

export type LatencyPoint = {
  bucket_start: string;
  runs: number;
  p50_latency_ms: number | null;
  p95_latency_ms: number | null;
  p99_latency_ms: number | null;
};

export type OverviewKpi = {
  runs: number;
  agents: number;
  error_rate: number;
  p50_latency_ms: number | null;
  p95_latency_ms: number | null;
  p99_latency_ms: number | null;
  flagged: number;
  total_tokens: number;
};

export type VolumeDay = {
  day: string;
  prod: number;
  staging: number;
  dev: number;
  other: number;
};

export type EnvSplit = { environment: string; runs: number };
export type TopTool = { tool: string; calls: number; errors: number };
export type FlaggedRun = {
  id: string;
  started_at: string;
  duration_ms: number | null;
  status_tag: string | null;
  agent_name: string | null;
  summary: string | null;
};
export type HeatmapCell = { agent_name: string; tool: string; calls: number };

export type MostRanAgent = {
  name: string;
  runs: number;
  error_rate: number;
};

export type OverviewResponse = {
  window: string;
  kpi: OverviewKpi;
  volume_by_day: VolumeDay[];
  env_split: EnvSplit[];
  top_tools: TopTool[];
  recent_flagged: FlaggedRun[];
  heatmap: HeatmapCell[];
  most_ran_agents: MostRanAgent[];
  latency_series?: LatencyPoint[];
};

export type TimeWindow = "24h" | "7d" | "30d";

// ── Fetch functions ───────────────────────────────────────────────────

export async function getOverview(window: TimeWindow = "7d"): Promise<OverviewResponse> {
  return apiFetch<OverviewResponse>(`/api/overview?window=${window}`);
}

export async function listAgents(
  opts: { with_metrics?: boolean; window?: TimeWindow } = {},
): Promise<AgentSummary[] | AgentSummaryWithMetrics[]> {
  const p = new URLSearchParams();
  if (opts.with_metrics) p.set("with_metrics", "true");
  if (opts.window) p.set("window", opts.window);
  const q = p.toString();
  return apiFetch<AgentSummary[] | AgentSummaryWithMetrics[]>(
    `/api/agents${q ? `?${q}` : ""}`,
  );
}

export async function getAgent(name: string): Promise<AgentDetail> {
  return apiFetch<AgentDetail>(`/api/agents/${encodeURIComponent(name)}`);
}

export async function getAgentMetrics(
  name: string,
  window: TimeWindow = "7d",
): Promise<AgentMetrics> {
  return apiFetch<AgentMetrics>(
    `/api/agents/${encodeURIComponent(name)}/metrics?window=${window}`,
  );
}

export async function getAgentTools(
  name: string,
  window: TimeWindow = "7d",
): Promise<AgentToolUsage[]> {
  return apiFetch<AgentToolUsage[]>(
    `/api/agents/${encodeURIComponent(name)}/tools?window=${window}`,
  );
}

export type LogForwardingConfig = {
  file: {
    enabled: boolean;
    path: string;
    rotate_daily: boolean;
    keep_days: number;
  };
  datadog: {
    enabled: boolean;
    site: string;
    api_key_env: string;
  };
  loki: {
    enabled: boolean;
    endpoint: string;
    labels: Record<string, string>;
  };
  otlp: {
    enabled: boolean;
    endpoint: string;
    headers: Record<string, string>;
  };
  kinds: {
    server_logs: boolean;
    trace_events: boolean;
    full_payloads: boolean;
    sdk_diagnostics: boolean;
  };
};

export async function getLogForwarding(): Promise<LogForwardingConfig> {
  return apiFetch<LogForwardingConfig>(`/api/settings/log-forwarding`);
}

export type AgentPromptRow = {
  text: string;
  runs: number;
  first_seen_at: string;
  last_seen_at: string;
};

export type RunsResponse = AgentRunsResponse;

export async function listRuns(opts: {
  pattern?: string;
  tag?: string;
  q?: string;
  limit?: number;
  offset?: number;
}): Promise<RunsResponse> {
  const p = new URLSearchParams();
  if (opts.pattern) p.set("pattern", opts.pattern);
  if (opts.tag) p.set("tag", opts.tag);
  if (opts.q) p.set("q", opts.q);
  if (opts.limit != null) p.set("limit", String(opts.limit));
  if (opts.offset != null) p.set("offset", String(opts.offset));
  const q = p.toString();
  return apiFetch<RunsResponse>(`/api/runs${q ? `?${q}` : ""}`);
}

export async function getAgentPrompts(
  name: string,
  limit = 20,
): Promise<AgentPromptRow[]> {
  return apiFetch<AgentPromptRow[]>(
    `/api/agents/${encodeURIComponent(name)}/prompts?limit=${limit}`,
  );
}

export async function getAgentRuns(
  name: string,
  opts: { limit?: number; offset?: number; environment?: string; version?: string } = {},
): Promise<AgentRunsResponse> {
  const p = new URLSearchParams();
  if (opts.limit != null) p.set("limit", String(opts.limit));
  if (opts.offset != null) p.set("offset", String(opts.offset));
  if (opts.environment) p.set("environment", opts.environment);
  if (opts.version) p.set("version", opts.version);
  const q = p.toString();
  return apiFetch<AgentRunsResponse>(
    `/api/agents/${encodeURIComponent(name)}/runs${q ? `?${q}` : ""}`,
  );
}
