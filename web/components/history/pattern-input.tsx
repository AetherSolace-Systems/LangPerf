"use client";

import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { useState, useTransition, useEffect } from "react";

export function PatternInput({ current }: { current: string }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [, startTransition] = useTransition();
  const [value, setValue] = useState(current);

  useEffect(() => {
    setValue(current);
  }, [current]);

  const apply = (next: string) => {
    const p = new URLSearchParams(params.toString());
    if (next) p.set("pattern", next);
    else p.delete("pattern");
    startTransition(() => router.push(`${pathname}?${p.toString()}`));
  };

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        apply(value.trim());
      }}
      className="flex-1 min-w-[340px]"
    >
      <input
        type="text"
        value={value}
        placeholder="agent.env.version · e.g. support-*.prod.* or *.test.v1.4.*"
        onChange={(e) => setValue(e.target.value)}
        className="w-full bg-[color:var(--background)] border border-[color:var(--border-strong)] rounded-[3px] px-[12px] py-[8px] text-[12px] font-mono text-warm-fog placeholder:text-patina focus:outline-none focus:border-aether-teal"
      />
    </form>
  );
}
