"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { CLIENT_API_URL, type AgentDetail } from "@/lib/api";

type Status = { kind: "idle" } | { kind: "error"; message: string } | { kind: "saved" };

export function ConfigForm({ agent }: { agent: AgentDetail }) {
  const router = useRouter();
  const [, startTransition] = useTransition();
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  const [saving, setSaving] = useState(false);
  const [name, setName] = useState(agent.name);
  const [displayName, setDisplayName] = useState(agent.display_name ?? "");
  const [description, setDescription] = useState(agent.description ?? "");
  const [owner, setOwner] = useState(agent.owner ?? "");
  const [githubUrl, setGithubUrl] = useState(agent.github_url ?? "");

  const dirty =
    name !== agent.name ||
    displayName !== (agent.display_name ?? "") ||
    description !== (agent.description ?? "") ||
    owner !== (agent.owner ?? "") ||
    githubUrl !== (agent.github_url ?? "");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!dirty || saving) return;
    setSaving(true);
    setStatus({ kind: "idle" });
    const patch: Record<string, string> = {};
    if (name !== agent.name) patch.rename_to = name;
    if (displayName !== (agent.display_name ?? "")) patch.display_name = displayName;
    if (description !== (agent.description ?? "")) patch.description = description;
    if (owner !== (agent.owner ?? "")) patch.owner = owner;
    if (githubUrl !== (agent.github_url ?? "")) patch.github_url = githubUrl;

    try {
      const resp = await fetch(
        `${CLIENT_API_URL}/api/agents/${encodeURIComponent(agent.name)}`,
        {
          method: "PATCH",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(patch),
        },
      );
      if (!resp.ok) {
        const detail = await resp.text();
        throw new Error(`${resp.status} — ${detail.slice(0, 200)}`);
      }
      setStatus({ kind: "saved" });
      // If the agent was renamed, navigate to the new URL; otherwise just refresh the RSC.
      if (patch.rename_to && patch.rename_to !== agent.name) {
        startTransition(() => {
          router.push(`/agents/${encodeURIComponent(patch.rename_to)}/config`);
          router.refresh();
        });
      } else {
        startTransition(() => router.refresh());
      }
    } catch (err) {
      setStatus({
        kind: "error",
        message: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={submit} className="max-w-[720px]">
      <Row label="Name (slug)" hint="lowercase letters/digits/hyphens · URL visible">
        <Input value={name} onChange={setName} mono />
      </Row>
      <Row label="Display name" hint="human-readable, overrides the slug in chrome">
        <Input value={displayName} onChange={setDisplayName} placeholder={agent.name} />
      </Row>
      <Row label="Description" hint="one-liner, appears on the agent card">
        <Textarea value={description} onChange={setDescription} />
      </Row>
      <Row label="Owner" hint="person or team responsible">
        <Input value={owner} onChange={setOwner} placeholder="e.g. @andrew or platform-team" />
      </Row>
      <Row label="GitHub URL" hint="auto-inferred from git origin when available">
        <Input value={githubUrl} onChange={setGithubUrl} placeholder="https://github.com/…" mono />
      </Row>

      <Row label="Signature" hint="stable fingerprint — not editable">
        <div className="font-mono text-[11px] text-patina break-all">
          {agent.signature}
        </div>
      </Row>

      <div className="flex items-center gap-[10px] mt-[14px] pt-[14px] border-t border-[color:var(--border)]">
        <button
          type="submit"
          disabled={!dirty || saving}
          className={`px-[12px] py-[6px] rounded-[3px] text-[12px] font-mono uppercase tracking-[0.08em] border ${
            dirty && !saving
              ? "bg-[color:rgba(107,186,177,0.1)] text-aether-teal border-[color:rgba(107,186,177,0.45)] hover:bg-[color:rgba(107,186,177,0.2)]"
              : "text-patina border-[color:var(--border-strong)] cursor-not-allowed"
          }`}
        >
          {saving ? "saving…" : dirty ? "save" : "no changes"}
        </button>
        {status.kind === "saved" ? (
          <span className="font-mono text-[11px] text-aether-teal">✓ saved</span>
        ) : null}
        {status.kind === "error" ? (
          <span className="font-mono text-[11px] text-warn">{status.message}</span>
        ) : null}
      </div>
    </form>
  );
}

function Row({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="grid grid-cols-[220px_1fr] gap-[14px] py-[14px] border-b border-[color:var(--border)]">
      <div>
        <div className="text-[12px] text-warm-fog font-medium">{label}</div>
        {hint ? (
          <div className="text-[11px] text-patina mt-[4px] leading-[1.5]">{hint}</div>
        ) : null}
      </div>
      <div>{children}</div>
    </div>
  );
}

function Input({
  value,
  onChange,
  placeholder = "",
  mono = false,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  mono?: boolean;
}) {
  return (
    <input
      type="text"
      value={value}
      placeholder={placeholder}
      onChange={(e) => onChange(e.target.value)}
      className={`w-full bg-[color:var(--background)] border border-[color:var(--border-strong)] rounded-[3px] px-[10px] py-[6px] text-[12px] text-warm-fog placeholder:text-patina focus:outline-none focus:border-aether-teal ${
        mono ? "font-mono text-[11px]" : ""
      }`}
    />
  );
}

function Textarea({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <textarea
      value={value}
      onChange={(e) => onChange(e.target.value)}
      rows={3}
      className="w-full bg-[color:var(--background)] border border-[color:var(--border-strong)] rounded-[3px] px-[10px] py-[6px] text-[12px] text-warm-fog placeholder:text-patina focus:outline-none focus:border-aether-teal resize-y"
    />
  );
}
