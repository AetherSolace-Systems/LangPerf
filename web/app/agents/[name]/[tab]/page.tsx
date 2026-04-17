import Link from "next/link";
import { notFound } from "next/navigation";
import { AppShell } from "@/components/shell/app-shell";
import { ContextSidebar, CtxHeader, CtxItem } from "@/components/shell/context-sidebar";
import { Chip } from "@/components/ui/chip";

const TABS = ["overview", "runs", "prompt", "tools", "versions", "config"] as const;
type Tab = (typeof TABS)[number];

export default async function AgentTab({
  params,
}: {
  params: Promise<{ name: string; tab: string }>;
}) {
  const { name, tab } = await params;
  if (!TABS.includes(tab as Tab)) notFound();

  const breadcrumb = (
    <>
      <Link href="/agents" className="hover:text-warm-fog">Agents</Link>
      <span className="mx-[6px] text-[color:var(--border-strong)]">›</span>
      <span className="font-medium text-warm-fog">{name}</span>
    </>
  );

  const sidebar = (
    <ContextSidebar>
      <CtxHeader>Versions</CtxHeader>
      <CtxItem>(Phase 2)</CtxItem>
      <CtxHeader>Environments</CtxHeader>
      <CtxItem>(Phase 2)</CtxItem>
      <CtxHeader>Saved filters</CtxHeader>
      <CtxItem>(Phase 2)</CtxItem>
    </ContextSidebar>
  );

  return (
    <AppShell
      topBar={{
        breadcrumb,
        right: <Chip>env: all</Chip>,
      }}
      contextSidebar={sidebar}
    >
      {/* Identity strip — Phase 2 populates real version/env/live KPIs */}
      <div className="flex items-center gap-2 px-[14px] py-[9px] -mx-[14px] -mt-[14px] mb-[14px] border-b border-[color:var(--border)] bg-gradient-to-b from-[color:var(--surface-2)] to-[color:var(--background)]">
        <span className="font-mono text-[9px] text-patina uppercase tracking-[0.1em] mr-[2px]">Agent</span>
        <Chip>{name}</Chip>
        <span className="font-mono text-[9px] text-patina uppercase tracking-[0.1em] mx-[2px] ml-[6px]">Ver</span>
        <Chip>—</Chip>
        <span className="font-mono text-[9px] text-patina uppercase tracking-[0.1em] mx-[2px] ml-[6px]">Env</span>
        <Chip>—</Chip>
        <div className="flex-1" />
        <span className="font-mono text-[10px] text-patina">live KPIs arrive in Phase 2</span>
      </div>

      {/* Tab nav */}
      <div className="flex gap-[20px] border-b border-[color:var(--border)] -mx-[14px] px-[14px] mb-[14px]">
        {TABS.map((t) => {
          const active = t === tab;
          return (
            <Link
              key={t}
              href={`/agents/${encodeURIComponent(name)}/${t}`}
              className={`py-[10px] text-[12px] -mb-px border-b-2 ${
                active
                  ? "text-warm-fog border-b-aether-teal"
                  : "text-patina border-b-transparent hover:text-warm-fog"
              }`}
            >
              <span className="capitalize">{t}</span>
            </Link>
          );
        })}
      </div>

      <div className="border border-[color:var(--border)] border-l-2 border-l-peach-neon rounded-[3px] bg-[color:var(--surface)] p-[14px]">
        <div className="font-mono text-[9px] text-peach-neon uppercase tracking-[0.1em] mb-[4px]">
          phase 2 · {tab}
        </div>
        <div className="text-[13px] text-warm-fog">
          This tab's content lands once first-class Agents ship in Phase 2.
          Overview gets KPIs + charts + recent runs. Runs becomes an agent-scoped
          run table. Prompt / Tools / Versions / Config land in follow-up specs.
        </div>
      </div>
    </AppShell>
  );
}
