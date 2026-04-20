import { CLIENT_API_URL, SERVER_API_URL } from "./api";
import { ApiError, apiFetch } from "./fetch-utils";

export type AuthMode = "single_user" | "multi_user";

export type CurrentUser = {
  id: string;
  org_id: string;
  email: string;
  display_name: string;
  is_admin: boolean;
};

export async function fetchMode(): Promise<AuthMode> {
  const res = await fetch(`${SERVER_API_URL}/api/auth/mode`, { cache: "no-store" });
  const body = await res.json();
  return body.mode as AuthMode;
}

export async function fetchMe(): Promise<CurrentUser | null> {
  try {
    // allowUnauthorized so apiFetch doesn't redirect to /login on 401 —
    // the login page itself calls this and expects null for "not signed in".
    const body = await apiFetch<{ user: CurrentUser | null }>(`/api/auth/me`, {
      allowUnauthorized: true,
    });
    return body.user;
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return null;
    throw err;
  }
}

export async function loginRequest(email: string, password: string): Promise<CurrentUser> {
  const res = await fetch(`${CLIENT_API_URL}/api/auth/login`, {
    method: "POST",
    credentials: "include",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "login failed" }));
    throw new Error(body.detail ?? "login failed");
  }
  const body = await res.json();
  return body.user;
}

export async function signupRequest(email: string, password: string, display_name: string): Promise<CurrentUser> {
  const res = await fetch(`${CLIENT_API_URL}/api/auth/signup`, {
    method: "POST",
    credentials: "include",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email, password, display_name }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "signup failed" }));
    throw new Error(body.detail ?? "signup failed");
  }
  const body = await res.json();
  return body.user;
}

export async function logoutRequest(): Promise<void> {
  await fetch(`${CLIENT_API_URL}/api/auth/logout`, {
    method: "POST",
    credentials: "include",
  });
}

export async function listMembers(): Promise<{ id: string; display_name: string }[]> {
  return apiFetch<{ id: string; display_name: string }[]>(`/api/auth/org/members`);
}
