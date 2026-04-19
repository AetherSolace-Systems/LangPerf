"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { NewAgentModal } from "./new-agent-modal";
import { RowActions } from "./row-actions";
import type { AgentSummary } from "@/lib/api";

type Col = "name" | "language" | "token" | "last_used" | "created";

export function AgentsTable({ agents }: { agents: AgentSummary[] }) {
  const [filter, setFilter] = useState("");
  const [sort, setSort] = useState<{ col: Col; dir: "asc" | "desc" }>({
    col: "name",
    dir: "asc",
  });
  const [showModal, setShowModal] = useState(false);

  const visible = useMemo(() => {
    const q = filter.trim().toLowerCase();
    const arr = agents.filter(
      (a) =>
        !q ||
        a.name.toLowerCase().includes(q) ||
        (a.description ?? "").toLowerCase().includes(q) ||
        (a.language ?? "").toLowerCase().includes(q),
    );
    const cmp = (x: AgentSummary, y: AgentSummary): number => {
      switch (sort.col) {
        case "name":
          return x.name.localeCompare(y.name);
        case "language":
          return (x.language ?? "").localeCompare(y.language ?? "");
        case "token":
          return (
            Number(Boolean(x.token_prefix)) - Number(Boolean(y.token_prefix))
          );
        case "last_used":
          return (
            new Date(x.last_token_used_at ?? 0).getTime() -
            new Date(y.last_token_used_at ?? 0).getTime()
          );
        case "created":
          return (
            new Date(x.created_at).getTime() -
            new Date(y.created_at).getTime()
          );
      }
    };
    arr.sort((a, b) => (sort.dir === "asc" ? cmp(a, b) : -cmp(a, b)));
    return arr;
  }, [agents, filter, sort]);

  function toggleSort(col: Col) {
    setSort((s) =>
      s.col === col
        ? { col, dir: s.dir === "asc" ? "desc" : "asc" }
        : { col, dir: "asc" },
    );
  }

  return (
    <>
      <div className="mb-3 flex items-center gap-2">
        <input
          placeholder="Filter agents..."
          className="flex-1 rounded bg-carbon px-3 py-2 text-sm text-warm-fog"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        <button
          type="button"
          onClick={() => setShowModal(true)}
          className="rounded bg-aether-teal px-3 py-2 text-sm font-semibold text-carbon"
        >
          + Add agent
        </button>
      </div>

      <div className="overflow-hidden rounded border border-[color:var(--border)] bg-[color:var(--surface)]">
        <table className="w-full text-left text-xs">
          <thead className="bg-carbon text-[10px] uppercase text-warm-fog/60">
            <tr>
              <Th
                label="Name"
                onClick={() => toggleSort("name")}
                active={sort.col === "name"}
                dir={sort.dir}
              />
              <Th
                label="Lang"
                onClick={() => toggleSort("language")}
                active={sort.col === "language"}
                dir={sort.dir}
              />
              <Th
                label="Token"
                onClick={() => toggleSort("token")}
                active={sort.col === "token"}
                dir={sort.dir}
              />
              <Th
                label="Last used"
                onClick={() => toggleSort("last_used")}
                active={sort.col === "last_used"}
                dir={sort.dir}
              />
              <Th
                label="Created"
                onClick={() => toggleSort("created")}
                active={sort.col === "created"}
                dir={sort.dir}
              />
              <th className="px-3 py-2 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {visible.length === 0 ? (
              <tr>
                <td
                  colSpan={6}
                  className="p-6 text-center text-warm-fog/50"
                >
                  No agents yet. Click &quot;+ Add agent&quot; to register one.
                </td>
              </tr>
            ) : (
              visible.map((a) => (
                <tr
                  key={a.id}
                  className="border-t border-[color:var(--border)]"
                >
                  <td className="px-3 py-2">
                    <Link
                      href={`/agents/${a.name}/overview`}
                      className="text-aether-teal hover:underline"
                    >
                      {a.name}
                    </Link>
                    {a.description && (
                      <div className="text-[10px] text-warm-fog/50">
                        {a.description}
                      </div>
                    )}
                  </td>
                  <td className="px-3 py-2 text-warm-fog/70">
                    {a.language ?? "—"}
                  </td>
                  <td className="px-3 py-2">
                    {a.token_prefix ? (
                      <code className="rounded bg-carbon px-1.5 py-0.5 font-mono text-[10px] text-warm-fog/80">
                        {a.token_prefix}…
                      </code>
                    ) : (
                      <span className="rounded bg-peach-neon/20 px-1.5 py-0.5 text-[10px] text-peach-neon">
                        unregistered
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-warm-fog/70">
                    {a.last_token_used_at
                      ? new Date(a.last_token_used_at).toLocaleString()
                      : "—"}
                  </td>
                  <td className="px-3 py-2 text-warm-fog/70">
                    {new Date(a.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-3 py-2 text-right">
                    <RowActions
                      name={a.name}
                      hasToken={Boolean(a.token_prefix)}
                    />
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {showModal && <NewAgentModal onClose={() => setShowModal(false)} />}
    </>
  );
}

function Th({
  label,
  onClick,
  active,
  dir,
}: {
  label: string;
  onClick: () => void;
  active: boolean;
  dir: "asc" | "desc";
}) {
  return (
    <th
      onClick={onClick}
      className="cursor-pointer select-none px-3 py-2 hover:text-warm-fog"
    >
      {label}
      {active && (dir === "asc" ? " ▲" : " ▼")}
    </th>
  );
}
