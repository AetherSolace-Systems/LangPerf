"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { CLIENT_API_URL } from "@/lib/api";

type LogEvent = {
  ts: number;
  level: string;
  source: string;
  logger: string;
  message: string;
  seq: number;
};

const LEVEL_COLORS: Record<string, string> = {
  DEBUG: "text-patina",
  INFO: "text-aether-teal",
  WARN: "text-peach-neon",
  WARNING: "text-peach-neon",
  ERROR: "text-warn",
  CRITICAL: "text-warn",
};

const SOURCES = ["langperf", "uvicorn", "fastapi", "sqlalchemy", "alembic"];

export function LiveConsole({
  initialSource,
  initialLevel,
}: {
  initialSource?: string;
  initialLevel?: string;
}) {
  const [events, setEvents] = useState<LogEvent[]>([]);
  const [follow, setFollow] = useState(true);
  const [paused, setPaused] = useState(false);
  const [wrap, setWrap] = useState(false);
  const [levelFilter, setLevelFilter] = useState(initialLevel ?? "INFO");
  const [activeSources, setActiveSources] = useState<Set<string>>(
    () => new Set(initialSource ? initialSource.split(",") : SOURCES),
  );
  const [query, setQuery] = useState("");
  const [connected, setConnected] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const pausedRef = useRef(paused);
  pausedRef.current = paused;

  // Initial history fetch
  useEffect(() => {
    let cancelled = false;
    fetch(`${CLIENT_API_URL}/api/logs/recent?limit=300`)
      .then((r) => r.json())
      .then((rows: LogEvent[]) => {
        if (!cancelled) setEvents(rows);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  // Live stream
  useEffect(() => {
    const es = new EventSource(`${CLIENT_API_URL}/api/logs/stream`);
    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(false);
    es.onmessage = (e) => {
      if (pausedRef.current) return;
      try {
        const event = JSON.parse(e.data) as LogEvent;
        setEvents((prev) => {
          if (prev.length && prev[prev.length - 1].seq === event.seq) return prev;
          const next = [...prev, event];
          if (next.length > 3000) next.splice(0, next.length - 3000);
          return next;
        });
      } catch {}
    };
    return () => es.close();
  }, []);

  // Auto-scroll to bottom when following
  useEffect(() => {
    if (!follow || !scrollRef.current) return;
    scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [events, follow]);

  const rank = (l: string) =>
    ({ DEBUG: 10, INFO: 20, WARN: 30, WARNING: 30, ERROR: 40, CRITICAL: 50 }[
      l.toUpperCase()
    ] ?? 20);
  const minRank = rank(levelFilter);
  const qLower = query.toLowerCase();

  const visible = useMemo(() => {
    return events.filter((e) => {
      if (!activeSources.has(e.source)) return false;
      if (rank(e.level) < minRank) return false;
      if (qLower && !e.message.toLowerCase().includes(qLower)) return false;
      return true;
    });
  }, [events, activeSources, minRank, qLower]);

  const toggleSource = (s: string) => {
    setActiveSources((prev) => {
      const next = new Set(prev);
      if (next.has(s)) next.delete(s);
      else next.add(s);
      return next;
    });
  };

  return (
    <div className="flex flex-col gap-[10px]">
      <div className="flex gap-[8px] items-center flex-wrap">
        <input
          type="text"
          placeholder="search substring"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="flex-1 min-w-[260px] bg-[color:var(--background)] border border-[color:var(--border-strong)] rounded-[3px] px-[10px] py-[6px] text-[12px] font-mono text-warm-fog placeholder:text-patina focus:outline-none focus:border-aether-teal"
        />
        <Segmented
          value={levelFilter}
          onChange={setLevelFilter}
          options={["DEBUG", "INFO", "WARN", "ERROR"]}
        />
        <button
          type="button"
          onClick={() => setFollow((v) => !v)}
          className={pillCls(follow)}
        >
          follow
        </button>
        <button
          type="button"
          onClick={() => setPaused((v) => !v)}
          className={pillCls(paused, "accent")}
        >
          {paused ? "resume" : "pause"}
        </button>
        <button
          type="button"
          onClick={() => setEvents([])}
          className={pillCls(false)}
        >
          clear
        </button>
        <button
          type="button"
          onClick={() => setWrap((v) => !v)}
          className={pillCls(wrap)}
        >
          wrap
        </button>
        <span
          className={`font-mono text-[10px] uppercase tracking-[0.08em] ${
            connected ? "text-aether-teal" : "text-warn"
          }`}
        >
          ● {connected ? "streaming" : "disconnected"}
        </span>
      </div>

      <div className="flex gap-[6px] items-center flex-wrap">
        <span className="font-mono text-[9px] text-patina uppercase tracking-[0.1em]">
          sources
        </span>
        {SOURCES.map((s) => {
          const on = activeSources.has(s);
          return (
            <button
              key={s}
              type="button"
              onClick={() => toggleSource(s)}
              className={`px-[8px] py-[2px] text-[10px] font-mono rounded-[2px] border ${
                on
                  ? "bg-[color:rgba(107,186,177,0.08)] text-aether-teal border-[color:rgba(107,186,177,0.45)]"
                  : "text-patina border-[color:var(--border-strong)] opacity-60"
              }`}
            >
              {s}
            </button>
          );
        })}
        <span className="font-mono text-[10px] text-patina ml-auto">
          {visible.length} of {events.length} · showing last 3k buffered
        </span>
      </div>

      <div
        ref={scrollRef}
        className="font-mono text-[11px] bg-[color:var(--background)] border border-[color:var(--border)] rounded-[3px] overflow-auto"
        style={{ height: "calc(100vh - 280px)", minHeight: 360 }}
      >
        {visible.length === 0 ? (
          <div className="text-patina p-[16px]">No matching log events.</div>
        ) : (
          visible.map((e) => (
            <div
              key={e.seq}
              className={`flex gap-[10px] px-[12px] py-[1px] hover:bg-[color:rgba(107,186,177,0.03)] ${
                wrap ? "" : "whitespace-nowrap"
              }`}
            >
              <span className="text-patina shrink-0 w-[100px] tabular-nums">
                {fmtTs(e.ts)}
              </span>
              <span
                className={`shrink-0 w-[54px] uppercase tracking-[0.08em] text-[10px] pt-[1px] ${
                  LEVEL_COLORS[e.level.toUpperCase()] ?? "text-patina"
                }`}
              >
                {e.level}
              </span>
              <span className="text-patina shrink-0 w-[76px] truncate">
                {e.source}
              </span>
              <span
                className={`text-warm-fog ${wrap ? "" : "truncate"} flex-1 min-w-0`}
              >
                {e.message}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function pillCls(active: boolean, variant: "primary" | "accent" = "primary") {
  if (!active) {
    return "px-[10px] py-[4px] text-[10px] font-mono uppercase tracking-[0.08em] rounded-[3px] border border-[color:var(--border-strong)] text-patina hover:text-warm-fog";
  }
  const color =
    variant === "accent"
      ? "bg-[color:rgba(232,168,124,0.1)] text-peach-neon border-[color:rgba(232,168,124,0.45)]"
      : "bg-[color:rgba(107,186,177,0.1)] text-aether-teal border-[color:rgba(107,186,177,0.45)]";
  return `px-[10px] py-[4px] text-[10px] font-mono uppercase tracking-[0.08em] rounded-[3px] border ${color}`;
}

function Segmented({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: string[];
}) {
  return (
    <span className="inline-flex border border-[color:var(--border-strong)] rounded-[3px] overflow-hidden">
      {options.map((o) => {
        const on = o === value;
        return (
          <button
            key={o}
            type="button"
            onClick={() => onChange(o)}
            className={`px-[10px] py-[4px] text-[10px] font-mono uppercase tracking-[0.08em] border-r last:border-r-0 border-[color:var(--border)] ${
              on
                ? "bg-[color:rgba(107,186,177,0.08)] text-aether-teal"
                : "text-patina hover:text-warm-fog"
            }`}
          >
            {o}
          </button>
        );
      })}
    </span>
  );
}

function fmtTs(ts: number): string {
  const d = new Date(ts * 1000);
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  const ss = String(d.getSeconds()).padStart(2, "0");
  const ms = String(d.getMilliseconds()).padStart(3, "0");
  return `${hh}:${mm}:${ss}.${ms}`;
}
