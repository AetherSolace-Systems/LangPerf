"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { loginRequest, signupRequest } from "@/lib/auth";

export function LoginForm({ bootstrap }: { bootstrap: boolean }) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setPending(true);
    setError(null);
    try {
      if (bootstrap) {
        await signupRequest(email, password, displayName || email.split("@")[0]);
      } else {
        await loginRequest(email, password);
      }
      router.push("/");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "unknown error");
    } finally {
      setPending(false);
    }
  }

  return (
    <form className="space-y-3" onSubmit={onSubmit}>
      {bootstrap && (
        <input
          className="w-full rounded bg-carbon px-3 py-2 text-sm text-warm-fog"
          placeholder="Display name"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
        />
      )}
      <input
        type="email"
        autoComplete="email"
        className="w-full rounded bg-carbon px-3 py-2 text-sm text-warm-fog"
        placeholder="Email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        required
      />
      <input
        type="password"
        autoComplete={bootstrap ? "new-password" : "current-password"}
        className="w-full rounded bg-carbon px-3 py-2 text-sm text-warm-fog"
        placeholder="Password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        required
        minLength={8}
      />
      {error && <p className="text-xs text-warn">{error}</p>}
      <button
        type="submit"
        disabled={pending}
        className="w-full rounded bg-aether-teal px-3 py-2 text-sm font-semibold text-carbon disabled:opacity-50"
      >
        {pending ? "Working..." : bootstrap ? "Create admin account" : "Sign in"}
      </button>
    </form>
  );
}
