import { headers } from "next/headers";

import { FilterBar } from "@/components/queue/filter-bar";
import { QueueRow } from "@/components/queue/queue-row";
import { fetchQueue } from "@/lib/triage";

export const dynamic = "force-dynamic";

export default async function QueuePage({
  searchParams,
}: {
  searchParams: { heuristic?: string | string[] };
}) {
  const cookie = headers().get("cookie") ?? "";
  const heuristic = searchParams.heuristic
    ? Array.isArray(searchParams.heuristic)
      ? searchParams.heuristic
      : [searchParams.heuristic]
    : [];
  const { items } = await fetchQueue({ heuristic }, cookie);

  return (
    <main className="space-y-6 p-6">
      <header className="space-y-1">
        <h1 className="text-lg font-semibold text-aether-teal">Triage queue</h1>
        <p className="text-xs text-warm-fog/60">
          Sorted by heuristic severity. Work the top of the list first.
        </p>
      </header>
      <FilterBar />
      <ul className="space-y-2">
        {items.length === 0 ? (
          <li className="rounded-lg border border-dashed border-warm-fog/20 p-6 text-center text-sm text-warm-fog/50">
            Queue is empty — nothing needs review.
          </li>
        ) : (
          items.map((item) => (
            <li key={item.trajectory_id}>
              <QueueRow item={item} />
            </li>
          ))
        )}
      </ul>
    </main>
  );
}
