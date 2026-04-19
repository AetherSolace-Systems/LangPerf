"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

const STORAGE_KEY = "langperf.sidebar";
const MIN = 280;
const MAX = 720;
const DEFAULT_WIDTH = 420;

type Persisted = { width: number; open: boolean; tab: string };

function load(): Persisted {
  if (typeof window === "undefined") {
    return { width: DEFAULT_WIDTH, open: true, tab: "detail" };
  }
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { width: DEFAULT_WIDTH, open: true, tab: "detail" };
    const parsed = JSON.parse(raw) as Partial<Persisted>;
    return {
      width: clamp(parsed.width ?? DEFAULT_WIDTH, MIN, MAX),
      open: parsed.open ?? true,
      tab: parsed.tab ?? "detail",
    };
  } catch {
    return { width: DEFAULT_WIDTH, open: true, tab: "detail" };
  }
}

function save(state: Persisted) {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    /* private-browsing / quota — ignore */
  }
}

function clamp(n: number, lo: number, hi: number) {
  return Math.min(hi, Math.max(lo, n));
}

export function ResizableSidebar({
  children,
  tab,
  onTabChange,
}: {
  children: ReactNode;
  tab: string;
  onTabChange: (t: string) => void;
}) {
  const [hydrated, setHydrated] = useState(false);
  const [width, setWidth] = useState(DEFAULT_WIDTH);
  const [open, setOpen] = useState(true);
  const draggingRef = useRef(false);

  useEffect(() => {
    const s = load();
    setWidth(s.width);
    setOpen(s.open);
    if (s.tab !== tab) onTabChange(s.tab);
    setHydrated(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (hydrated) save({ width, open, tab });
  }, [hydrated, width, open, tab]);

  function onMouseDown(e: React.MouseEvent) {
    e.preventDefault();
    draggingRef.current = true;
    const startX = e.clientX;
    const startW = width;
    const move = (ev: MouseEvent) => {
      if (!draggingRef.current) return;
      const delta = startX - ev.clientX;
      setWidth(clamp(startW + delta, MIN, MAX));
    };
    const up = () => {
      draggingRef.current = false;
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
    };
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
  }

  if (!open) {
    return (
      <div
        data-sidebar-root
        data-open="false"
        className="relative flex-shrink-0 border-l border-[color:var(--border)] bg-[color:var(--surface-2)]"
        style={{ width: 24 }}
      >
        <button
          type="button"
          onClick={() => setOpen(true)}
          title="Expand sidebar"
          aria-label="Expand sidebar"
          className="w-full h-8 flex items-center justify-center text-[color:var(--muted)] hover:text-warm-fog"
        >
          ‹
        </button>
      </div>
    );
  }

  return (
    <div
      data-sidebar-root
      data-open="true"
      className="relative flex-shrink-0 border-l border-[color:var(--border)] overflow-hidden"
      style={{ width }}
    >
      <div
        onMouseDown={onMouseDown}
        title="Drag to resize"
        className="absolute top-0 left-0 h-full w-1.5 cursor-col-resize z-10 hover:bg-aether-teal/30"
      />
      <button
        type="button"
        onClick={() => setOpen(false)}
        title="Collapse sidebar"
        aria-label="Collapse sidebar"
        className="absolute top-2 left-1.5 z-20 w-5 h-5 flex items-center justify-center text-[10px] text-[color:var(--muted)] hover:text-warm-fog bg-[color:var(--surface)] border border-[color:var(--border)] rounded"
      >
        ›
      </button>
      <div className="h-full pl-2">{children}</div>
    </div>
  );
}
