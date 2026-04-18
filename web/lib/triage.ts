import { CLIENT_API_URL, SERVER_API_URL } from "./api";

export type HeuristicHit = {
  heuristic: string;
  severity: number;
  signature: string;
  details: Record<string, unknown>;
};

export type QueueItem = {
  trajectory_id: string;
  name: string;
  service_name: string;
  started_at: string | null;
  assigned_user_id: string | null;
  score: number;
  hit_count: number;
  hits: HeuristicHit[];
};

export type Cluster = {
  id: string;
  signature: string;
  heuristics: string[];
  size: number;
  trajectory_ids: string[];
};

export async function fetchQueue(
  params: { heuristic?: string[]; assigned_to_me?: boolean } = {},
  cookie?: string,
): Promise<{ items: QueueItem[] }> {
  const qs = new URLSearchParams();
  (params.heuristic ?? []).forEach((h) => qs.append("heuristic", h));
  if (params.assigned_to_me) qs.set("assigned_to_me", "true");
  const base = cookie ? SERVER_API_URL : CLIENT_API_URL;
  const res = await fetch(
    `${base}/api/queue?${qs}`,
    cookie ? { headers: { cookie }, cache: "no-store" } : { credentials: "include", cache: "no-store" },
  );
  return res.json();
}

export async function fetchClusters(cookie?: string): Promise<{ clusters: Cluster[] }> {
  const base = cookie ? SERVER_API_URL : CLIENT_API_URL;
  const res = await fetch(
    `${base}/api/clusters`,
    cookie ? { headers: { cookie }, cache: "no-store" } : { credentials: "include", cache: "no-store" },
  );
  return res.json();
}

export async function fetchTrajectoryHits(trajectoryId: string, cookie?: string): Promise<HeuristicHit[]> {
  const base = cookie ? SERVER_API_URL : CLIENT_API_URL;
  const res = await fetch(
    `${base}/api/queue/${trajectoryId}/hits`,
    cookie ? { headers: { cookie }, cache: "no-store" } : { credentials: "include", cache: "no-store" },
  );
  return res.json();
}
