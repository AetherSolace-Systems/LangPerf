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

export default async function Home({
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
      <main className="min-h-screen p-10">
        <h1 className="text-2xl font-semibold">LangPerf</h1>
        <div
          className="mt-6 rounded border p-4 text-sm"
          style={{
            borderColor: "rgba(229,139,84,0.45)",
            background: "rgba(229,139,84,0.1)",
          }}
        >
          <p className="font-medium text-coral">Could not reach langperf-api</p>
          <p className="mt-1 text-twilight font-mono text-xs">
            {err instanceof Error ? err.message : String(err)}
          </p>
        </div>
      </main>
    );
  }

  const hasFilters = Object.values(params).some(Boolean);

  return (
    <main className="min-h-screen">
      <header className="border-b border-[color:var(--border)] px-6 py-4 flex items-baseline gap-3">
        <h1 className="text-lg font-semibold tracking-tight">
          <span className="text-drift-violet">Lang</span>
          <span className="text-marigold">Perf</span>
        </h1>
        <span className="text-xs text-twilight">
          {data.total} trajector{data.total === 1 ? "y" : "ies"}
          {hasFilters ? " (filtered)" : ""}
        </span>
      </header>

      <FilterBar facets={facets} />

      {data.items.length === 0 ? (
        <div className="p-10 text-sm text-twilight">
          {hasFilters ? (
            <p>No trajectories match these filters.</p>
          ) : (
            <>
              <p>No trajectories yet.</p>
              <p className="mt-2">
                Send OTLP spans to{" "}
                <code className="font-mono text-drift-violet">
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
    </main>
  );
}
