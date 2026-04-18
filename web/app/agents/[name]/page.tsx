import { redirect } from "next/navigation";

export default async function AgentRoot({
  params,
}: {
  params: Promise<{ name: string }>;
}) {
  const { name } = await params;
  redirect(`/agents/${encodeURIComponent(name)}/overview`);
}
