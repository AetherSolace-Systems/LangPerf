"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type FullscreenValue = {
  fsOpen: boolean;
  toggleFs: () => void;
  setFs: (open: boolean) => void;
  expandAll: boolean;
  toggleExpandAll: () => void;
  expandedIds: Set<string>;
  toggleExpand: (spanId: string) => void;
  collapseAll: () => void;
};

const Ctx = createContext<FullscreenValue | null>(null);

export function FullscreenProvider({
  initialFs = false,
  children,
}: {
  initialFs?: boolean;
  children: ReactNode;
}) {
  const [fsOpen, setFs] = useState(initialFs);
  const [expandAll, setExpandAll] = useState(false);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  const toggleFs = useCallback(() => setFs((v) => !v), []);
  const toggleExpandAll = useCallback(() => {
    setExpandAll((v) => !v);
    setExpandedIds(new Set());
  }, []);
  const toggleExpand = useCallback((spanId: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(spanId)) next.delete(spanId);
      else next.add(spanId);
      return next;
    });
  }, []);
  const collapseAll = useCallback(() => {
    setExpandAll(false);
    setExpandedIds(new Set());
  }, []);

  const value = useMemo<FullscreenValue>(
    () => ({
      fsOpen,
      toggleFs,
      setFs,
      expandAll,
      toggleExpandAll,
      expandedIds,
      toggleExpand,
      collapseAll,
    }),
    [fsOpen, toggleFs, expandAll, toggleExpandAll, expandedIds, toggleExpand, collapseAll],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useFullscreen(): FullscreenValue {
  const v = useContext(Ctx);
  if (!v) throw new Error("useFullscreen must be used inside <FullscreenProvider>");
  return v;
}
