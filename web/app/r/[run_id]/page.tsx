import { redirect } from "next/navigation";

/**
 * Stable short-form permalink for a run. In Phase 1, runs still live under
 * /t/<id>; Phase 2 rehomes them under /agents/<name>/runs/<id> and this
 * redirect will change correspondingly. External consumers (Slack links,
 * export CSVs) should always use /r/<id>.
 */
export default async function RunPermalink({
  params,
}: {
  params: Promise<{ run_id: string }>;
}) {
  const { run_id } = await params;
  redirect(`/t/${encodeURIComponent(run_id)}`);
}
