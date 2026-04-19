"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { CLIENT_API_URL, type LogForwardingConfig } from "@/lib/api";

type Status =
  | { kind: "idle" }
  | { kind: "error"; message: string }
  | { kind: "saved" };

export function LogForwardingForm({ initial }: { initial: LogForwardingConfig }) {
  const router = useRouter();
  const [, startTransition] = useTransition();
  const [cfg, setCfg] = useState<LogForwardingConfig>(initial);
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  const [saving, setSaving] = useState(false);

  const dirty = JSON.stringify(cfg) !== JSON.stringify(initial);

  const save = async () => {
    setSaving(true);
    setStatus({ kind: "idle" });
    try {
      const resp = await fetch(`${CLIENT_API_URL}/api/settings/log-forwarding`, {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(cfg),
      });
      if (!resp.ok) {
        const detail = await resp.text();
        throw new Error(`${resp.status} — ${detail.slice(0, 200)}`);
      }
      setStatus({ kind: "saved" });
      startTransition(() => router.refresh());
    } catch (err) {
      setStatus({
        kind: "error",
        message: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-[860px]">
      <TargetCard
        title="Local file"
        subtitle="Append structured JSON to a file. Good for dev / air-gapped hosts. Runs in-process and is fully implemented."
        enabledLabel="enforcing"
        enabled={cfg.file.enabled}
        onToggle={(enabled) =>
          setCfg({ ...cfg, file: { ...cfg.file, enabled } })
        }
      >
        <Field label="Path" mono>
          <Input
            value={cfg.file.path}
            onChange={(v) => setCfg({ ...cfg, file: { ...cfg.file, path: v } })}
            mono
          />
        </Field>
        <div className="grid grid-cols-2 gap-[14px]">
          <Field label="Rotate daily">
            <Toggle
              on={cfg.file.rotate_daily}
              onChange={(v) =>
                setCfg({ ...cfg, file: { ...cfg.file, rotate_daily: v } })
              }
            />
          </Field>
          <Field label="Keep (days)">
            <Input
              value={String(cfg.file.keep_days)}
              onChange={(v) =>
                setCfg({
                  ...cfg,
                  file: {
                    ...cfg.file,
                    keep_days: parseInt(v, 10) || 0,
                  },
                })
              }
              mono
            />
          </Field>
        </div>
      </TargetCard>

      <TargetCard
        title="Datadog"
        subtitle="Stub — stores config, actual forwarding lands in a follow-up."
        stub
        enabled={cfg.datadog.enabled}
        onToggle={(enabled) =>
          setCfg({ ...cfg, datadog: { ...cfg.datadog, enabled } })
        }
      >
        <Field label="Site">
          <Input
            value={cfg.datadog.site}
            onChange={(v) =>
              setCfg({ ...cfg, datadog: { ...cfg.datadog, site: v } })
            }
            mono
          />
        </Field>
        <Field label="API key env var" hint="credential never leaves the process env">
          <Input
            value={cfg.datadog.api_key_env}
            onChange={(v) =>
              setCfg({ ...cfg, datadog: { ...cfg.datadog, api_key_env: v } })
            }
            mono
          />
        </Field>
      </TargetCard>

      <TargetCard
        title="Grafana Loki"
        subtitle="Stub — stores endpoint + labels, forwarding lands in a follow-up."
        stub
        enabled={cfg.loki.enabled}
        onToggle={(enabled) =>
          setCfg({ ...cfg, loki: { ...cfg.loki, enabled } })
        }
      >
        <Field label="Endpoint">
          <Input
            value={cfg.loki.endpoint}
            onChange={(v) =>
              setCfg({ ...cfg, loki: { ...cfg.loki, endpoint: v } })
            }
            mono
            placeholder="https://loki.example/loki/api/v1/push"
          />
        </Field>
        <Field label="Labels (JSON)" hint='e.g. {"env":"prod","region":"us-east-1"}'>
          <Input
            value={JSON.stringify(cfg.loki.labels)}
            onChange={(v) => {
              try {
                setCfg({
                  ...cfg,
                  loki: { ...cfg.loki, labels: JSON.parse(v) },
                });
              } catch {
                // keep previous value; user is mid-typing
              }
            }}
            mono
          />
        </Field>
      </TargetCard>

      <TargetCard
        title="Generic OTLP"
        subtitle="Stub — any OTLP-compatible sink (Honeycomb, Tempo, SigNoz). Lands in a follow-up."
        stub
        enabled={cfg.otlp.enabled}
        onToggle={(enabled) =>
          setCfg({ ...cfg, otlp: { ...cfg.otlp, enabled } })
        }
      >
        <Field label="Endpoint">
          <Input
            value={cfg.otlp.endpoint}
            onChange={(v) =>
              setCfg({ ...cfg, otlp: { ...cfg.otlp, endpoint: v } })
            }
            mono
            placeholder="https://collector.example:4318"
          />
        </Field>
        <Field label="Headers (JSON)">
          <Input
            value={JSON.stringify(cfg.otlp.headers)}
            onChange={(v) => {
              try {
                setCfg({
                  ...cfg,
                  otlp: { ...cfg.otlp, headers: JSON.parse(v) },
                });
              } catch {}
            }}
            mono
          />
        </Field>
      </TargetCard>

      <section className="border border-[color:var(--border)] rounded-[3px] bg-[color:var(--surface)] p-[14px] mt-[14px]">
        <div className="font-mono text-[9px] text-patina uppercase tracking-[0.1em] mb-[10px]">
          What gets forwarded
        </div>
        <div className="grid grid-cols-2 gap-[10px]">
          <KindToggle
            label="Server logs"
            on={cfg.kinds.server_logs}
            onChange={(v) =>
              setCfg({ ...cfg, kinds: { ...cfg.kinds, server_logs: v } })
            }
          />
          <KindToggle
            label="Trace events (new run, flagged, error)"
            on={cfg.kinds.trace_events}
            onChange={(v) =>
              setCfg({ ...cfg, kinds: { ...cfg.kinds, trace_events: v } })
            }
          />
          <KindToggle
            label="Full trajectory payloads (noisy)"
            on={cfg.kinds.full_payloads}
            onChange={(v) =>
              setCfg({ ...cfg, kinds: { ...cfg.kinds, full_payloads: v } })
            }
          />
          <KindToggle
            label="SDK-client diagnostic logs"
            on={cfg.kinds.sdk_diagnostics}
            onChange={(v) =>
              setCfg({ ...cfg, kinds: { ...cfg.kinds, sdk_diagnostics: v } })
            }
          />
        </div>
      </section>

      <div className="flex items-center gap-[10px] mt-[18px] pt-[14px] border-t border-[color:var(--border)]">
        <button
          type="button"
          onClick={save}
          disabled={!dirty || saving}
          className={`px-[12px] py-[6px] rounded-[3px] text-[12px] font-mono uppercase tracking-[0.08em] border ${
            dirty && !saving
              ? "bg-[color:rgba(107,186,177,0.1)] text-aether-teal border-[color:rgba(107,186,177,0.45)] hover:bg-[color:rgba(107,186,177,0.2)]"
              : "text-patina border-[color:var(--border-strong)] cursor-not-allowed"
          }`}
        >
          {saving ? "saving…" : dirty ? "save" : "no changes"}
        </button>
        {status.kind === "saved" ? (
          <span className="font-mono text-[11px] text-aether-teal">✓ saved</span>
        ) : null}
        {status.kind === "error" ? (
          <span className="font-mono text-[11px] text-warn">{status.message}</span>
        ) : null}
      </div>
    </div>
  );
}

function TargetCard({
  title,
  subtitle,
  enabled,
  onToggle,
  children,
  stub = false,
  enabledLabel = "enabled",
}: {
  title: string;
  subtitle: string;
  enabled: boolean;
  onToggle: (v: boolean) => void;
  children: React.ReactNode;
  stub?: boolean;
  enabledLabel?: string;
}) {
  return (
    <section
      className={`border border-[color:var(--border)] rounded-[3px] bg-[color:var(--surface)] p-[14px] mb-[10px] ${
        stub ? "border-l-2 border-l-peach-neon" : ""
      }`}
    >
      <div className="flex items-start gap-[14px] mb-[12px]">
        <div className="flex-1">
          <div className="text-[13px] text-warm-fog font-medium">{title}</div>
          <div className="text-[11px] text-patina mt-[2px] leading-[1.5]">
            {subtitle}
          </div>
        </div>
        <div className="flex items-center gap-[8px]">
          {stub ? (
            <span className="font-mono text-[9px] text-peach-neon uppercase tracking-[0.1em]">
              stub
            </span>
          ) : null}
          <Toggle on={enabled} onChange={onToggle} label={enabledLabel} />
        </div>
      </div>
      <div className="flex flex-col gap-[10px]">{children}</div>
    </section>
  );
}

function Field({
  label,
  hint,
  children,
  mono = false,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <div>
      <div
        className={`font-mono text-[9px] text-patina uppercase tracking-[0.1em] mb-[4px] ${
          mono ? "" : ""
        }`}
      >
        {label}
      </div>
      {children}
      {hint ? (
        <div className="font-mono text-[10px] text-patina mt-[3px]">{hint}</div>
      ) : null}
    </div>
  );
}

function Input({
  value,
  onChange,
  placeholder = "",
  mono = false,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  mono?: boolean;
}) {
  return (
    <input
      type="text"
      value={value}
      placeholder={placeholder}
      onChange={(e) => onChange(e.target.value)}
      className={`w-full bg-[color:var(--background)] border border-[color:var(--border-strong)] rounded-[3px] px-[10px] py-[6px] text-[12px] text-warm-fog placeholder:text-patina focus:outline-none focus:border-aether-teal ${
        mono ? "font-mono text-[11px]" : ""
      }`}
    />
  );
}

function Toggle({
  on,
  onChange,
  label,
}: {
  on: boolean;
  onChange: (v: boolean) => void;
  label?: string;
}) {
  return (
    <button
      type="button"
      onClick={() => onChange(!on)}
      className="inline-flex items-center gap-[8px] focus:outline-none"
    >
      <span
        className={`relative inline-flex w-[28px] h-[16px] rounded-full ${
          on ? "bg-aether-teal" : "bg-[color:var(--border-strong)]"
        }`}
      >
        <span
          className={`absolute top-[2px] w-[12px] h-[12px] rounded-full bg-warm-fog transition-all ${
            on ? "left-[14px]" : "left-[2px]"
          }`}
        />
      </span>
      {label ? (
        <span
          className={`font-mono text-[10px] uppercase tracking-[0.08em] ${
            on ? "text-aether-teal" : "text-patina"
          }`}
        >
          {on ? label : "off"}
        </span>
      ) : null}
    </button>
  );
}

function KindToggle({
  label,
  on,
  onChange,
}: {
  label: string;
  on: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onChange(!on)}
      className="flex items-center gap-[10px] text-left py-[4px]"
    >
      <span
        className={`relative inline-flex w-[28px] h-[16px] rounded-full shrink-0 ${
          on ? "bg-aether-teal" : "bg-[color:var(--border-strong)]"
        }`}
      >
        <span
          className={`absolute top-[2px] w-[12px] h-[12px] rounded-full bg-warm-fog transition-all ${
            on ? "left-[14px]" : "left-[2px]"
          }`}
        />
      </span>
      <span
        className={`text-[12px] ${on ? "text-warm-fog" : "text-patina"}`}
      >
        {label}
      </span>
    </button>
  );
}
