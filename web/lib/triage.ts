import { apiFetch } from "./fetch-utils";

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
): Promise<{ items: QueueItem[] }> {
  const qs = new URLSearchParams();
  (params.heuristic ?? []).forEach((h) => qs.append("heuristic", h));
  if (params.assigned_to_me) qs.set("assigned_to_me", "true");
  return apiFetch<{ items: QueueItem[] }>(`/api/queue?${qs}`);
}

export async function fetchClusters(): Promise<{ clusters: Cluster[] }> {
  return apiFetch<{ clusters: Cluster[] }>(`/api/clusters`);
}

export async function fetchTrajectoryHits(trajectoryId: string): Promise<HeuristicHit[]> {
  return apiFetch<HeuristicHit[]>(`/api/queue/${trajectoryId}/hits`);
}
