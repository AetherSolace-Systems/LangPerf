/**
 * Reads the latest valid session token from the running Postgres and writes
 * storageState so every Playwright test starts authenticated. Local-dogfood
 * only — CI would need a dedicated test user + programmatic signup flow.
 */
import { execFileSync } from "node:child_process";
import { writeFileSync, mkdirSync } from "node:fs";
import { dirname } from "node:path";

const STORAGE_STATE_PATH = "tests/.auth/storage-state.json";

function fetchToken(): string {
  const out = execFileSync(
    "docker",
    [
      "compose",
      "exec",
      "-T",
      "postgres",
      "psql",
      "-U",
      "langperf",
      "-d",
      "langperf",
      "-t",
      "-A",
      "-c",
      "SELECT token FROM sessions WHERE expires_at > now() ORDER BY created_at DESC LIMIT 1;",
    ],
    { encoding: "utf-8" },
  );
  const token = out.trim();
  if (!token) {
    throw new Error(
      "No valid session in DB — log in via the UI once so tests can piggyback.",
    );
  }
  return token;
}

export default async function globalSetup() {
  const token = fetchToken();
  mkdirSync(dirname(STORAGE_STATE_PATH), { recursive: true });
  writeFileSync(
    STORAGE_STATE_PATH,
    JSON.stringify({
      cookies: [
        {
          name: "langperf_session",
          value: token,
          domain: "localhost",
          path: "/",
          httpOnly: true,
          secure: false,
          sameSite: "Lax",
          expires: -1,
        },
      ],
      origins: [],
    }),
  );
}
