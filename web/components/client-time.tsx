"use client";

import { useEffect, useState } from "react";

/**
 * Render a timestamp that stays hydration-safe.
 *
 * Server and first-client render both emit an ISO-ish value (identical string
 * on both sides → no hydration mismatch). After mount, a useEffect swaps in
 * the user's localized string.
 */
export function ClientTime({ iso }: { iso: string | null | undefined }) {
  const initial = iso ? isoShort(iso) : "—";
  const [text, setText] = useState<string>(initial);
  useEffect(() => {
    if (!iso) return;
    setText(new Date(iso).toLocaleString());
  }, [iso]);
  return <span suppressHydrationWarning>{text}</span>;
}

function isoShort(iso: string): string {
  // "2026-04-16T23:22:15.607Z" -> "2026-04-16 23:22:15Z"
  return iso.replace("T", " ").replace(/\.\d+Z?$/, "").replace(/Z?$/, "Z");
}
