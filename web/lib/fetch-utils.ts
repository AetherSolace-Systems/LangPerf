// Shared fetch helper for talking to langperf-api from both server and client
// components. Centralises three concerns that otherwise get duplicated in
// every domain module:
//
//   1. Base URL selection (SERVER vs CLIENT) via apiBase().
//   2. Auth forwarding:
//        - server: dynamically import next/headers and forward the incoming
//          request's cookie header so the API sees the caller's session.
//        - client: set credentials: "include" so the browser ships cookies.
//   3. Error handling: extract { detail } from the response body when
//      present, fall back to a url+status message otherwise.
//
// Keep the next/headers import dynamic — this module is pulled into client
// bundles too, where the import doesn't resolve.

import { apiBase } from "./api";

export type FetchOpts = {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown; // JSON-stringified if present
  headers?: Record<string, string>; // merged with auth + content-type
  signal?: AbortSignal;
  cache?: RequestCache; // default "no-store"
};

async function buildInit(opts: FetchOpts): Promise<RequestInit> {
  const init: RequestInit = {
    method: opts.method ?? "GET",
    cache: opts.cache ?? "no-store",
  };
  if (opts.signal) init.signal = opts.signal;

  const headers: Record<string, string> = { ...(opts.headers ?? {}) };

  // Server-side: forward the incoming request cookie so authenticated calls
  // don't 401. Dynamic import because this module also ships to client
  // bundles where next/headers doesn't resolve. Silently ignore failures
  // from outside-request-context (e.g. build time).
  let cookie = "";
  if (typeof window === "undefined") {
    try {
      const { headers: nextHeaders } = await import("next/headers");
      cookie = nextHeaders().get("cookie") ?? "";
    } catch {
      // Outside a request context; no cookie available.
    }
  }

  if (cookie && !headers.cookie) {
    headers.cookie = cookie;
  } else if (typeof window !== "undefined") {
    init.credentials = "include";
  }

  if (opts.body !== undefined) {
    if (!headers["content-type"]) headers["content-type"] = "application/json";
    init.body = JSON.stringify(opts.body);
  }

  if (Object.keys(headers).length > 0) init.headers = headers;
  return init;
}

export class ApiError extends Error {
  readonly status: number;
  readonly url: string;
  constructor(status: number, url: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.url = url;
  }
}

async function throwFromResponse(resp: Response, url: string): Promise<never> {
  let detail: string | undefined;
  try {
    const body = (await resp.json()) as { detail?: unknown };
    if (body && typeof body.detail === "string") detail = body.detail;
  } catch {
    // body wasn't JSON (or was empty) — fall through to generic message.
  }
  const msg = detail ?? `langperf-api ${resp.status} at ${url}`;
  throw new ApiError(resp.status, url, msg);
}

export async function apiFetch<T>(path: string, opts: FetchOpts = {}): Promise<T> {
  const url = `${apiBase()}${path}`;
  const init = await buildInit(opts);
  const resp = await fetch(url, init);
  if (!resp.ok) await throwFromResponse(resp, url);
  return (await resp.json()) as T;
}

// Variant for endpoints that return 204 / no body.
export async function apiFetchVoid(path: string, opts: FetchOpts = {}): Promise<void> {
  const url = `${apiBase()}${path}`;
  const init = await buildInit(opts);
  const resp = await fetch(url, init);
  if (!resp.ok) await throwFromResponse(resp, url);
}
