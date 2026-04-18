import type { Page } from "@playwright/test";

const API_BASE = "http://localhost:4318";

/**
 * Fetch an existing agent name from the backend so tests don't hard-code one.
 * Returns the first non-legacy agent when possible, else the first agent at all.
 */
export async function firstAgentName(page: Page): Promise<string> {
  const resp = await page.request.get(`${API_BASE}/api/agents`);
  const agents = (await resp.json()) as { name: string; signature?: string }[];
  if (agents.length === 0) {
    throw new Error("no agents on the server — seed data is missing");
  }
  const real = agents.find((a) => a.signature && !a.signature.startsWith("legacy:"));
  return (real ?? agents[0]).name;
}

/**
 * Fetch an existing trajectory id for the /t/[id] tests.
 */
export async function firstRunId(page: Page): Promise<string> {
  const resp = await page.request.get(`${API_BASE}/api/runs?limit=1`);
  const body = (await resp.json()) as { items: { id: string }[] };
  if (body.items.length === 0) {
    throw new Error("no runs on the server — seed data is missing");
  }
  return body.items[0].id;
}
