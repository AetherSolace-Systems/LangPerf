import Link from "next/link";
import { notFound } from "next/navigation";
import { AppShell } from "@/components/shell/app-shell";
import { ContextSidebar } from "@/components/shell/context-sidebar";
import { SETTINGS_SECTIONS } from "@/components/shell/nav-config";
import { LogForwardingForm } from "@/components/settings/log-forwarding-form";
import { getLogForwarding } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function SettingsSection({
  params,
}: {
  params: Promise<{ section: string }>;
}) {
  const { section } = await params;
  const item = SETTINGS_SECTIONS.find((s) => s.id === section);
  if (!item || item.v2) notFound();

  const groups: Array<{ key: string; label: string }> = [
    { key: "workspace", label: "Workspace" },
    { key: "observability", label: "Observability" },
    { key: "integrations", label: "Integrations" },
    { key: "later", label: "Later" },
  ];

  const sidebar = (
    <ContextSidebar>
      {groups.map((g) => (
        <div key={g.key} className="mb-[6px]">
          <div className="px-[6px] pt-[10px] pb-[4px] font-mono text-[9px] text-patina uppercase tracking-[0.1em]">
            {g.label}
          </div>
          {SETTINGS_SECTIONS.filter((s) => s.group === g.key).map((s) => {
            const active = s.id === section;
            if (s.v2) {
              return (
                <div
                  key={s.id}
                  className="px-[10px] py-[6px] text-[12px] text-patina opacity-55 cursor-not-allowed"
                  title="v2 · coming soon"
                  aria-disabled
                >
                  {s.label}
                </div>
              );
            }
            return (
              <Link
                key={s.id}
                href={s.href}
                className={`block px-[10px] py-[6px] text-[12px] rounded-[2px] ${
                  active
                    ? "bg-[color:rgba(107,186,177,0.07)] text-warm-fog border-l-2 border-l-aether-teal pl-[8px]"
                    : "text-patina hover:text-warm-fog"
                }`}
              >
                {s.label}
              </Link>
            );
          })}
        </div>
      ))}
    </ContextSidebar>
  );

  const breadcrumb = (
    <>
      <span className="font-medium text-warm-fog">Settings</span>
      <span className="mx-[6px] text-[color:var(--border-strong)]">›</span>
      <span>{item.label}</span>
    </>
  );

  const phaseHint: Record<string, string> = {
    "log-forwarding": "Forward in-process logs to external sinks. Local file is fully implemented; Datadog / Loki / OTLP persist config today and will enforce forwarding in a follow-up.",
    "trace-export": "Follow-up — what gets forwarded: server logs, trace events, full payloads, SDK diagnostics.",
    "profile": "Phase 2+ — single-user placeholder in v1.",
    "environments": "Phase 2 — rename and order your dev/staging/prod environments.",
    "agents-review": "Phase 2 — queue of auto-detected agents needing human review.",
    "sdk-keys": "Follow-up — SDK key rotation for authenticated ingest.",
    "webhooks": "Follow-up — outbound webhooks on run events.",
  };

  let logForwardingConfig = null;
  if (section === "log-forwarding") {
    try {
      logForwardingConfig = await getLogForwarding();
    } catch {
      // Surface the error inside the panel below instead of 500'ing the whole page.
    }
  }

  return (
    <AppShell
      topBar={{ breadcrumb }}
      contextSidebar={sidebar}
    >
      <div>
        <h1 className="text-[15px] text-warm-fog font-medium mb-[4px]">{item.label}</h1>
        <div className="font-mono text-[10px] text-patina mb-[16px] max-w-[780px] leading-[1.6]">
          {phaseHint[section] ?? "Placeholder."}
        </div>
        {section === "log-forwarding" ? (
          logForwardingConfig ? (
            <LogForwardingForm initial={logForwardingConfig} />
          ) : (
            <div className="border border-[color:var(--border)] border-l-2 border-l-warn rounded-[3px] bg-[color:var(--surface)] p-[14px] max-w-[760px]">
              <div className="font-mono text-[9px] text-warn uppercase tracking-[0.1em] mb-[4px]">
                could not load config
              </div>
              <div className="text-[13px] text-warm-fog">
                Check that <code className="font-mono text-aether-teal">langperf-api</code>{" "}
                is running and that migration 0008 applied.
              </div>
            </div>
          )
        ) : (
          <div className="border border-[color:var(--border)] border-l-2 border-l-peach-neon rounded-[3px] bg-[color:var(--surface)] p-[14px] max-w-[760px]">
            <div className="font-mono text-[9px] text-peach-neon uppercase tracking-[0.1em] mb-[4px]">
              placeholder
            </div>
            <div className="text-[13px] text-warm-fog">
              The settings section nav is live. Section content lands with the phase noted above.
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
