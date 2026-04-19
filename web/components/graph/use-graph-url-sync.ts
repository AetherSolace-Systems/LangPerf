"use client";

import { useEffect } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

/**
 * Keeps a boolean fullscreen-state in sync with `?fs=1` in the URL.
 *
 * On mount, reads `?fs` and flips local state to match (one-way init).
 * When `fsOpen` changes after mount, pushes a `router.replace` that adds or
 * removes `fs=1` while preserving any other query params. A value-compare
 * guards against redundant replaces that would otherwise thrash history.
 */
export function useGraphUrlSync(
  fsOpen: boolean,
  setFsOpen: (v: boolean) => void,
): void {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  // On mount, sync fsOpen FROM URL.
  useEffect(() => {
    const want = params.get("fs") === "1";
    if (want !== fsOpen) setFsOpen(want);
    // intentionally only on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // When fsOpen changes, push URL.
  useEffect(() => {
    const want = fsOpen ? "1" : null;
    const current = params.get("fs");
    if (current !== want) {
      const sp = new URLSearchParams(params.toString());
      if (want) sp.set("fs", want);
      else sp.delete("fs");
      const q = sp.toString();
      router.replace(q ? `${pathname}?${q}` : pathname);
    }
  }, [fsOpen, params, router, pathname]);
}
