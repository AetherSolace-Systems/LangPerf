"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState, useTransition } from "react";
import type { FacetsResponse } from "@/lib/api";

const TAG_OPTIONS = [
  { value: "", label: "all tags" },
  { value: "good", label: "good" },
  { value: "bad", label: "bad" },
  { value: "interesting", label: "interesting" },
  { value: "todo", label: "todo" },
  { value: "none", label: "untagged" },
];

export function FilterBar({ facets }: { facets: FacetsResponse }) {
  const router = useRouter();
  const params = useSearchParams();
  const [, startTransition] = useTransition();
  const [q, setQ] = useState(params.get("q") ?? "");

  const update = (updates: Record<string, string | null>) => {
    const next = new URLSearchParams(params.toString());
    for (const [k, v] of Object.entries(updates)) {
      if (v === null || v === "") next.delete(k);
      else next.set(k, v);
    }
    startTransition(() => router.push(`/history?${next.toString()}`));
  };

  const selectCls =
    "bg-transparent border border-[var(--border)] text-xs rounded px-2 py-1 font-mono hover:border-[var(--foreground)]/30 focus:outline-none focus:border-[var(--accent)]/60";

  return (
    <div className="px-6 py-2 border-b border-[var(--border)] flex items-center gap-2 flex-wrap">
      <select
        value={params.get("tag") ?? ""}
        onChange={(e) => update({ tag: e.target.value || null })}
        className={selectCls}
      >
        {TAG_OPTIONS.map((o) => (
          <option key={o.value} value={o.value} className="bg-[var(--background)]">
            {o.label}
          </option>
        ))}
      </select>
      <select
        value={params.get("service") ?? ""}
        onChange={(e) => update({ service: e.target.value || null })}
        className={selectCls}
      >
        <option value="" className="bg-[var(--background)]">all services</option>
        {facets.services.map((s) => (
          <option key={s} value={s} className="bg-[var(--background)]">
            {s}
          </option>
        ))}
      </select>
      <select
        value={params.get("environment") ?? ""}
        onChange={(e) => update({ environment: e.target.value || null })}
        className={selectCls}
      >
        <option value="" className="bg-[var(--background)]">all environments</option>
        {facets.environments.map((e) => (
          <option key={e} value={e} className="bg-[var(--background)]">
            {e}
          </option>
        ))}
      </select>
      <form
        className="flex-1 min-w-[200px]"
        onSubmit={(e) => {
          e.preventDefault();
          update({ q: q || null });
        }}
      >
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="search name, notes, span content…"
          className="w-full bg-transparent border border-[var(--border)] text-xs rounded px-2 py-1 font-mono placeholder:text-[var(--muted)] focus:outline-none focus:border-[var(--accent)]/60"
        />
      </form>
      {params.toString() ? (
        <button
          type="button"
          onClick={() => {
            setQ("");
            startTransition(() => router.push("/history"));
          }}
          className="text-xs font-mono text-[var(--muted)] hover:text-[var(--foreground)] px-2"
        >
          clear
        </button>
      ) : null}
    </div>
  );
}
