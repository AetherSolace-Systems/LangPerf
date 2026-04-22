"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

type SharedCursorValue = {
  hoverX: number | null;
  setX: (x: number | null) => void;
};

const Ctx = createContext<SharedCursorValue | null>(null);

export function SharedCursorProvider({ children }: { children: ReactNode }) {
  const [hoverX, setHoverX] = useState<number | null>(null);
  const setX = useCallback((x: number | null) => setHoverX(x), []);
  const value = useMemo(() => ({ hoverX, setX }), [hoverX, setX]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useSharedCursor(): SharedCursorValue {
  const v = useContext(Ctx);
  if (v == null) {
    throw new Error(
      "useSharedCursor must be used inside a <SharedCursorProvider>",
    );
  }
  return v;
}
