import Link from "next/link";
import {
  getFacets,
  listTrajectories,
  type TrajectorySummary,
} from "@/lib/api";
import { ClientTime } from "@/components/client-time";
import { FilterBar } from "@/components/filter-bar";
import { tagSwatch } from "@/lib/colors";
import { fmtDuration } from "@/lib/format";
import { AppShell } from "@/components/shell/app-shell";
import { ContextSidebar, CtxHeader, CtxItem } from "@/components/shell/context-sidebar";
import { Chip } from "@/components/ui/chip";

export const dynamic = "force-dynamic";

function Row({ t }: { t: TrajectorySummary }) {
  const swatch = tagSwatch(t.status_tag);
  return (
    <Link
      href={`/t/${t.id}`}
      className="block border-b border-[color:var(--border)] px-4 py-3 hover:bg-linen/[0.03] transition-colors"
    >
      <div className="flex items-center gap-3">
        <span className="font-mono text-xs text-twilight w-28 truncate">
          {t.id.slice(0, 8)}…
        </span>
        <span className="text-sm flex-1 truncate">
          {t.name ?? <em className="text-twilight">(unnamed)</em>}
        </span>
        <span
          className="text-[10px] font-mono uppercase tracking-wider border rounded px-1.5 py-0.5"
          style={{
            color: t.status_tag ? swatch.fg : "var(--muted)",
            background: t.status_tag ? swatch.bg : "transparent",
            borderColor: t.status_tag ? swatch.border : "var(--border)",
          }}
        >
          {t.status_tag ?? "—"}
        </span>
        <span className="text-xs text-twilight w-32 text-right truncate">
          {t.service_name}
          {t.environment ? ` · ${t.environment}` : ""}
        </span>
        <span className="text-xs text-twilight w-20 text-right tabular-nums">
          {t.step_count} step{t.step_count === 1 ? "" : "s"}
        </span>
        <span className="text-xs text-twilight w-20 text-right tabular-nums">
          {t.token_count.toLocaleString()}t
        </span>
        <span className="text-xs text-twilight w-16 text-right tabular-nums">
          {fmtDuration(t.duration_ms)}
        </span>
        <span className="text-xs text-twilight w-36 text-right">
          <ClientTime iso={t.started_at} />
        </span>
      </div>
    </Link>
  );
}

export default async function History({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const params = await searchParams;

  let data;
  let facets;
  try {
    [data, facets] = await Promise.all([
      listTrajectories({
        limit: 100,
        tag: params.tag,
        service: params.service,
        environment: params.environment,
        q: params.q,
      }),
      getFacets(),
    ]);
  } catch (err) {
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

  const hasFilters = Object.values(params).some(Boolean);

  const sidebar = (
    <ContextSidebar>
      <CtxHeader>Saved patterns</CtxHeader>
      <CtxItem>(none yet — lands in Phase 4)</CtxItem>
      <CtxHeader>Quick filters</CtxHeader>
      <CtxItem>• flagged · 24h</CtxItem>
      <CtxItem>• errors only</CtxItem>
      <CtxItem>• new agents</CtxItem>
    </ContextSidebar>
  );

  return (
    <AppShell
      topBar={{
        breadcrumb: <span className="font-medium text-warm-fog">History</span>,
        right: (
          <>
            <Chip>
              {data.total} run{data.total === 1 ? "" : "s"}
              {hasFilters ? " (filtered)" : ""}
            </Chip>
            <Chip variant="primary">ingest ok</Chip>
          </>
        ),
      }}
      contextSidebar={sidebar}
    >
      <FilterBar facets={facets} />
      {data.items.length === 0 ? (
        <div className="p-10 text-sm text-patina">
          {hasFilters ? (
            <p>No runs match these filters.</p>
          ) : (
            <>
              <p>No runs yet.</p>
              <p className="mt-2">
                Send OTLP spans to{" "}
                <code className="font-mono text-aether-teal">
                  POST http://localhost:4318/v1/traces
                </code>{" "}
                — or run{" "}
                <code className="font-mono">
                  python scripts/seed_demo_data.py
                </code>
                .
              </p>
            </>
          )}
        </div>
      ) : (
        <div>
          {data.items.map((t) => (
            <Row key={t.id} t={t} />
          ))}
        </div>
      )}
    </AppShell>
  );
}
