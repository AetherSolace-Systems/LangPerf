export default function Home() {
  return (
    <main className="min-h-screen p-10">
      <h1 className="text-2xl font-semibold tracking-tight">LangPerf</h1>
      <p className="text-[var(--muted)] mt-1 text-sm">
        v0.1 · M1 skeleton · trajectories coming in M2
      </p>
      <div className="mt-8 border border-[var(--border)] rounded-md p-5 max-w-xl">
        <h2 className="text-sm font-medium text-[var(--muted)] uppercase tracking-wider">
          Service check
        </h2>
        <p className="mt-2 text-sm">
          API expected at{" "}
          <code className="font-mono text-[var(--accent)]">
            http://localhost:4318
          </code>
        </p>
        <p className="mt-1 text-sm">
          Send OTLP spans to{" "}
          <code className="font-mono text-[var(--accent)]">
            POST /v1/traces
          </code>{" "}
          to see them in the server logs.
        </p>
      </div>
    </main>
  );
}
