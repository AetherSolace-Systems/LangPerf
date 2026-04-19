"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { deleteAgent, issueAgentToken, rotateAgentToken } from "@/lib/agents";
import { TokenDisplay } from "./token-display";

export function RowActions({
  name,
  hasToken,
}: {
  name: string;
  hasToken: boolean;
}) {
  const router = useRouter();
  const [issued, setIssued] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onIssue() {
    setPending(true);
    try {
      const r = await issueAgentToken(name);
      setIssued(r.token);
      router.refresh();
    } finally {
      setPending(false);
    }
  }
  async function onRotate() {
    if (
      !confirm(
        `Rotate token for ${name}? The old token stops working immediately.`,
      )
    )
      return;
    setPending(true);
    try {
      const r = await rotateAgentToken(name);
      setIssued(r.token);
      router.refresh();
    } finally {
      setPending(false);
    }
  }
  async function onDelete() {
    if (
      !confirm(
        `Delete ${name}? This removes the agent and all its trajectories.`,
      )
    )
      return;
    setPending(true);
    try {
      await deleteAgent(name);
      router.refresh();
    } finally {
      setPending(false);
    }
  }

  return (
    <>
      <div className="flex items-center justify-end gap-2">
        {!hasToken ? (
          <button
            type="button"
            onClick={onIssue}
            disabled={pending}
            className="rounded bg-peach-neon/20 px-2 py-1 text-[11px] text-peach-neon"
          >
            Issue token
          </button>
        ) : (
          <button
            type="button"
            onClick={onRotate}
            disabled={pending}
            className="rounded bg-carbon px-2 py-1 text-[11px] text-warm-fog/70 hover:text-warm-fog"
          >
            Rotate
          </button>
        )}
        <button
          type="button"
          onClick={onDelete}
          disabled={pending}
          className="rounded px-2 py-1 text-[11px] text-warn hover:bg-warn/10"
        >
          Delete
        </button>
      </div>
      {issued && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onClick={() => setIssued(null)}
        >
          <div
            className="w-full max-w-md rounded-2xl bg-warm-fog/5 p-6 ring-1 ring-aether-teal/20"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="mb-4 text-lg font-semibold text-aether-teal">
              New token
            </h3>
            <TokenDisplay token={issued} />
            <button
              type="button"
              onClick={() => setIssued(null)}
              className="mt-3 w-full rounded bg-aether-teal px-3 py-2 text-sm font-semibold text-carbon"
            >
              Done
            </button>
          </div>
        </div>
      )}
    </>
  );
}
