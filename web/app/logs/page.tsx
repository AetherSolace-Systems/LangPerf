import Link from "next/link";
import { AppShell } from "@/components/shell/app-shell";
import {
  ContextSidebar,
  CtxHeader,
  CtxItem,
} from "@/components/shell/context-sidebar";
import { Chip } from "@/components/ui/chip";
import { LiveConsole } from "@/components/logs/live-console";

export const dynamic = "force-dynamic";

const SOURCE_DESCRIPTIONS: Array<{ id: string; label: string; note: string }> = [
  { id: "langperf", label: "langperf", note: "app-level events" },
  { id: "uvicorn", label: "uvicorn", note: "request access + lifecycle" },
  { id: "fastapi", label: "fastapi", note: "app framework" },
  { id: "sqlalchemy", label: "sqlalchemy", note: "queries (off by default)" },
  { id: "alembic", label: "alembic", note: "migrations" },
];

export default function Logs() {
  const sidebar = (
    <ContextSidebar>
      <CtxHeader>Sources</CtxHeader>
      {SOURCE_DESCRIPTIONS.map((s) => (
        <div
          key={s.id}
          className="px-[6px] py-[4px] rounded-[2px] my-[1px]"
        >
          <div className="font-mono text-[12px] text-warm-fog">{s.label}</div>
          <div className="font-mono text-[10px] text-patina">{s.note}</div>
        </div>
      ))}
      <CtxHeader>Forwarding</CtxHeader>
      <CtxItem>
        <Link href="/settings/log-forwarding" className="text-aether-teal hover:underline">
          configure →
        </Link>
      </CtxItem>
    </ContextSidebar>
  );

  return (
    <AppShell
      topBar={{
        breadcrumb: <span className="font-medium text-warm-fog">Logs</span>,
        right: <Chip variant="primary">live</Chip>,
      }}
      contextSidebar={sidebar}
    >
      <LiveConsole />
    </AppShell>
  );
}
