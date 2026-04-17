import { AppShell } from "@/components/shell/app-shell";
import { ContextSidebar, CtxHeader, CtxItem } from "@/components/shell/context-sidebar";
import { Chip } from "@/components/ui/chip";

export default function AgentsIndex() {
  const sidebar = (
    <ContextSidebar>
      <CtxHeader action="+ new">Agents</CtxHeader>
      <CtxItem>(lands in Phase 2)</CtxItem>
    </ContextSidebar>
  );

  return (
    <AppShell
      topBar={{
        breadcrumb: <span className="font-medium text-warm-fog">Agents</span>,
        right: <Chip>env: all</Chip>,
      }}
      contextSidebar={sidebar}
    >
      <div className="border border-[color:var(--border)] border-l-2 border-l-peach-neon rounded-[3px] bg-[color:var(--surface)] p-[14px]">
        <div className="font-mono text-[9px] text-peach-neon uppercase tracking-[0.1em] mb-[4px]">
          phase 2
        </div>
        <div className="text-[13px] text-warm-fog mb-[4px]">
          Agents become a first-class entity in Phase 2. The SDK will auto-detect each
          agent from its source signature (git origin + init call site), and this page
          will list every agent with live metrics.
        </div>
        <div className="text-[11px] text-patina leading-[1.5]">
          Until then, agent metadata is effectively <code className="font-mono text-aether-teal">service_name</code> on
          each run — visible on the History table.
        </div>
      </div>
    </AppShell>
  );
}
