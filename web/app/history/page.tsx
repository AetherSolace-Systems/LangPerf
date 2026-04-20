import Link from "next/link";
import { AppShell } from "@/components/shell/app-shell";
import {
  ContextSidebar,
  CtxHeader,
  CtxItem,
} from "@/components/shell/context-sidebar";
import { Chip } from "@/components/ui/chip";
import { listRuns, type AgentRunsResponse } from "@/lib/api";
import { isRedirectError } from "@/lib/fetch-utils";
import { RunsTable } from "@/components/agent/runs-table";
import { PatternInput } from "@/components/history/pattern-input";

export const dynamic = "force-dynamic";

const SAVED_PATTERNS = [
  "*.*.*",
  "*.prod.*",
  "*.staging.*",
  "*.dev.*",
  "weather-*.*.*",
  "code-*.*.*",
];

const QUICK_FILTERS: Array<{ label: string; params: Record<string, string> }> = [
  { label: "flagged only", params: { tag: "bad" } },
  { label: "good only", params: { tag: "good" } },
  { label: "interesting", params: { tag: "interesting" } },
];

export default async function History({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const params = await searchParams;
  const pattern = params.pattern ?? "";
  const tag = params.tag ?? undefined;
  const q = params.q ?? undefined;

  let runs: AgentRunsResponse;
  try {
    runs = await listRuns({ pattern, tag, q, limit: 100 });
  } catch (err) {
    if (isRedirectError(err)) throw err;
    return (
      <AppShell
        topBar={{
          breadcrumb: <span className="font-medium text-warm-fog">History</span>,
        }}
      >
        <div
          className="rounded border p-4 text-sm"
          style={{
            borderColor: "rgba(217,138,106,0.45)",
            background: "rgba(217,138,106,0.1)",
          }}
        >
          <p className="font-medium text-warn">Could not reach langperf-api</p>
          <p className="mt-1 text-patina font-mono text-xs">
            {err instanceof Error ? err.message : String(err)}
          </p>
        </div>
      </AppShell>
    );
  }

  const hasFilters = Boolean(pattern || tag || q);

  const sidebar = (
    <ContextSidebar>
      <CtxHeader>Saved patterns</CtxHeader>
      {SAVED_PATTERNS.map((p) => {
        const active = p === pattern;
        return (
          <Link
            key={p}
            href={`/history?pattern=${encodeURIComponent(p)}`}
            className={`block px-[6px] py-[5px] rounded-[2px] text-[12px] my-[1px] font-mono ${
              active
                ? "bg-[color:rgba(107,186,177,0.07)] text-aether-teal"
                : "text-warm-fog hover:text-aether-teal"
            }`}
          >
            {p}
          </Link>
        );
      })}
      <CtxHeader>Quick filters</CtxHeader>
      {QUICK_FILTERS.map((f) => {
        const qp = new URLSearchParams(f.params).toString();
        const active = Object.entries(f.params).every(
          ([k, v]) => params[k] === v,
        );
        return (
          <Link
            key={f.label}
            href={`/history?${qp}`}
            className={`block px-[6px] py-[5px] rounded-[2px] text-[12px] my-[1px] ${
              active
                ? "bg-[color:rgba(107,186,177,0.07)] text-aether-teal"
                : "text-warm-fog hover:text-aether-teal"
            }`}
          >
            {f.label}
          </Link>
        );
      })}
      {hasFilters ? (
        <Link
          href="/history"
          className="block mt-[10px] px-[6px] py-[5px] text-[10px] font-mono text-patina hover:text-warm-fog uppercase tracking-[0.08em]"
        >
          clear all →
        </Link>
      ) : null}
    </ContextSidebar>
  );

  return (
    <AppShell
      topBar={{
        breadcrumb: <span className="font-medium text-warm-fog">History</span>,
        right: (
          <>
            <Chip>
              {runs.total.toLocaleString()} run{runs.total === 1 ? "" : "s"}
              {hasFilters ? " · filtered" : ""}
            </Chip>
            <Chip variant="primary">ingest ok</Chip>
          </>
        ),
      }}
      contextSidebar={sidebar}
    >
      <div className="flex items-start gap-[8px] mb-[10px]">
        <PatternInput current={pattern} />
      </div>
      <div className="font-mono text-[10px] text-patina mb-[10px] px-[2px]">
        <span className="text-aether-teal">pattern</span> — dot-delimited{" "}
        <code>agent.env.version</code> · <code>*</code> wildcards · missing
        trailing segments default to <code>*</code>
      </div>

      <div className="border border-[color:var(--border)] rounded-[3px] bg-[color:var(--surface)] overflow-hidden">
        <RunsTable rows={runs.items} showAgent />
      </div>

      {runs.total > runs.items.length ? (
        <div className="text-center text-patina font-mono text-[10px] py-[10px]">
          showing {runs.items.length.toLocaleString()} of{" "}
          {runs.total.toLocaleString()}
        </div>
      ) : null}
    </AppShell>
  );
}
