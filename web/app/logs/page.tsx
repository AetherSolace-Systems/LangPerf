import { AppShell } from "@/components/shell/app-shell";
import { ContextSidebar, CtxHeader, CtxItem } from "@/components/shell/context-sidebar";
import { Chip } from "@/components/ui/chip";

export default function Logs() {
  const sidebar = (
    <ContextSidebar>
      <CtxHeader>Sources</CtxHeader>
      <CtxItem>● api-server</CtxItem>
      <CtxItem>● ingest</CtxItem>
      <CtxItem>● otel-collector</CtxItem>
      <CtxItem>● web</CtxItem>
      <CtxHeader>Levels</CtxHeader>
      <CtxItem>INFO · WARN · ERROR</CtxItem>
      <CtxHeader>Forwarding</CtxHeader>
      <CtxItem>(configure in Settings)</CtxItem>
    </ContextSidebar>
  );

  return (
    <AppShell
      topBar={{
        breadcrumb: <span className="font-medium text-warm-fog">Logs</span>,
        right: <Chip>env: all</Chip>,
      }}
      contextSidebar={sidebar}
    >
      <div className="border border-[color:var(--border)] border-l-2 border-l-peach-neon rounded-[3px] bg-[color:var(--surface)] p-[14px]">
        <div className="font-mono text-[9px] text-peach-neon uppercase tracking-[0.1em] mb-[4px]">
          phase 5
        </div>
        <div className="text-[13px] text-warm-fog">
          Real-time server log stream (SSE) with source + level filters lands in Phase 5,
          together with Settings → Log forwarding.
        </div>
      </div>
    </AppShell>
  );
}
