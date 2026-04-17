"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { Span } from "@/lib/api";

/**
 * Cross-view span selection. The trajectory detail page has four places
 * that all need to agree on which span is "selected" — the tree, the graph,
 * the timeline, and the right-hand detail panel. Instead of prop-drilling
 * `selectedId` + `onSelect` through each pane, they pull from this context.
 *
 * Usage:
 *
 *   <SelectionProvider spans={spans} initialId={spans[0]?.span_id}>
 *     <Tree />    // uses useSelection() → reads selectedId, calls select(span)
 *     <Graph />
 *     <Timeline />
 *     <DetailPanel />
 *   </SelectionProvider>
 */

type SelectionValue = {
  selectedId: string | null;
  selectedSpan: Span | null;
  select: (span: Span | { span_id: string }) => void;
  clear: () => void;
};

const SelectionContext = createContext<SelectionValue | null>(null);

export function SelectionProvider({
  spans,
  initialId = null,
  children,
}: {
  spans: Span[];
  initialId?: string | null;
  children: ReactNode;
}) {
  const [selectedId, setSelectedId] = useState<string | null>(initialId);

  const select = useCallback((span: Span | { span_id: string }) => {
    setSelectedId(span.span_id);
  }, []);

  const clear = useCallback(() => setSelectedId(null), []);

  const selectedSpan = useMemo(
    () =>
      selectedId ? spans.find((s) => s.span_id === selectedId) ?? null : null,
    [selectedId, spans],
  );

  const value = useMemo<SelectionValue>(
    () => ({ selectedId, selectedSpan, select, clear }),
    [selectedId, selectedSpan, select, clear],
  );

  return (
    <SelectionContext.Provider value={value}>
      {children}
    </SelectionContext.Provider>
  );
}

export function useSelection(): SelectionValue {
  const ctx = useContext(SelectionContext);
  if (!ctx) {
    throw new Error("useSelection must be used inside <SelectionProvider>");
  }
  return ctx;
}
