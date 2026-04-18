import { headers } from "next/headers";
import { notFound, redirect } from "next/navigation";

import { SERVER_API_URL } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function SharedPage({ params }: { params: { token: string } }) {
  const cookie = headers().get("cookie") ?? "";
  const res = await fetch(`${SERVER_API_URL}/api/shared/${params.token}`, {
    headers: { cookie },
    cache: "no-store",
  });
  if (res.status === 404) notFound();
  if (res.status === 401) redirect(`/login?next=/shared/${params.token}`);
  const body = await res.json();
  redirect(`/t/${body.trajectory_id}`);
}
