import Link from "next/link";
import { notFound } from "next/navigation";
import { getTrajectory } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function TrajectoryPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let traj;
  try {
    traj = await getTrajectory(id);
  } catch (err) {
    if (err instanceof Error && err.message.includes("404")) notFound();
    throw err;
  }

  return (
    <main className="min-h-screen">
      <header className="border-b border-[var(--border)] px-6 py-4">
        <Link
          href="/"
          className="text-xs text-[var(--muted)] hover:text-[var(--foreground)]"
        >
          ← all trajectories
        </Link>
        <h1 className="text-lg font-semibold tracking-tight mt-1">
          {traj.name ?? (
            <em className="text-[var(--muted)] font-normal">(unnamed)</em>
          )}
        </h1>
        <div className="mt-1 text-xs text-[var(--muted)] font-mono flex gap-4">
          <span>{traj.id}</span>
          <span>·</span>
          <span>{traj.service_name}</span>
          {traj.environment ? (
            <>
              <span>·</span>
              <span>{traj.environment}</span>
            </>
          ) : null}
          <span>·</span>
          <span>
            {traj.step_count} step{traj.step_count === 1 ? "" : "s"}
          </span>
          <span>·</span>
          <span>{traj.token_count.toLocaleString()} tokens</span>
        </div>
      </header>

      <section className="p-6">
        <h2 className="text-xs font-medium uppercase tracking-wider text-[var(--muted)]">
          Raw trajectory (M2 dump — tree view in M3)
        </h2>
        <pre className="mt-3 text-xs font-mono leading-relaxed bg-black/30 border border-[var(--border)] rounded p-4 overflow-x-auto">
          {JSON.stringify(traj, null, 2)}
        </pre>
      </section>
    </main>
  );
}
