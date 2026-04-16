import Link from "next/link";
import { listTrajectories, type TrajectorySummary } from "@/lib/api";

export const dynamic = "force-dynamic";

function fmtDuration(ms: number | null): string {
  if (ms == null) return "—";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

function fmtTime(iso: string): string {
  return new Date(iso).toLocaleString();
}

function tagStyle(tag: string | null): string {
  switch (tag) {
    case "good":
      return "bg-emerald-500/15 text-emerald-300 border-emerald-500/30";
    case "bad":
      return "bg-rose-500/15 text-rose-300 border-rose-500/30";
    case "interesting":
      return "bg-sky-500/15 text-sky-300 border-sky-500/30";
    case "todo":
      return "bg-amber-500/15 text-amber-300 border-amber-500/30";
    default:
      return "bg-[var(--border)]/50 text-[var(--muted)] border-[var(--border)]";
  }
}

function Row({ t }: { t: TrajectorySummary }) {
  return (
    <Link
      href={`/t/${t.id}`}
      className="block border-b border-[var(--border)] px-4 py-3 hover:bg-white/[0.03] transition-colors"
    >
      <div className="flex items-center gap-3">
        <span className="font-mono text-xs text-[var(--muted)] w-28 truncate">
          {t.id.slice(0, 8)}…
        </span>
        <span className="text-sm flex-1 truncate">
          {t.name ?? <em className="text-[var(--muted)]">(unnamed)</em>}
        </span>
        <span
          className={`text-[10px] font-mono uppercase tracking-wider border rounded px-1.5 py-0.5 ${tagStyle(
            t.status_tag,
          )}`}
        >
          {t.status_tag ?? "—"}
        </span>
        <span className="text-xs text-[var(--muted)] w-32 text-right truncate">
          {t.service_name}
          {t.environment ? ` · ${t.environment}` : ""}
        </span>
        <span className="text-xs text-[var(--muted)] w-20 text-right tabular-nums">
          {t.step_count} step{t.step_count === 1 ? "" : "s"}
        </span>
        <span className="text-xs text-[var(--muted)] w-20 text-right tabular-nums">
          {t.token_count.toLocaleString()}t
        </span>
        <span className="text-xs text-[var(--muted)] w-16 text-right tabular-nums">
          {fmtDuration(t.duration_ms)}
        </span>
        <span className="text-xs text-[var(--muted)] w-36 text-right">
          {fmtTime(t.started_at)}
        </span>
      </div>
    </Link>
  );
}

export default async function Home() {
  let data;
  try {
    data = await listTrajectories({ limit: 100 });
  } catch (err) {
    return (
      <main className="min-h-screen p-10">
        <h1 className="text-2xl font-semibold">LangPerf</h1>
        <div className="mt-6 rounded border border-rose-500/40 bg-rose-500/10 p-4 text-sm">
          <p className="font-medium text-rose-300">
            Could not reach langperf-api
          </p>
          <p className="mt-1 text-[var(--muted)] font-mono text-xs">
            {err instanceof Error ? err.message : String(err)}
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen">
      <header className="border-b border-[var(--border)] px-6 py-4 flex items-baseline gap-3">
        <h1 className="text-lg font-semibold tracking-tight">LangPerf</h1>
        <span className="text-xs text-[var(--muted)]">
          {data.total} trajector{data.total === 1 ? "y" : "ies"}
        </span>
      </header>

      {data.items.length === 0 ? (
        <div className="p-10 text-sm text-[var(--muted)]">
          <p>No trajectories yet.</p>
          <p className="mt-2">
            Send OTLP spans to{" "}
            <code className="font-mono text-[var(--accent)]">
              POST http://localhost:4318/v1/traces
            </code>{" "}
            — or run <code className="font-mono">python scripts/smoke.py</code>
            .
          </p>
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
