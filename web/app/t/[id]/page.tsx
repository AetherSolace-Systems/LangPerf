import { notFound } from "next/navigation";
import { getTrajectory } from "@/lib/api";
import { TrajectoryView } from "@/components/trajectory-view";

export const dynamic = "force-dynamic";

export default async function TrajectoryPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let traj;
  try {
    traj = await getTrajectory(id);
  } catch (err) {
    if (err instanceof Error && err.message.includes("404")) notFound();
    throw err;
  }

  return <TrajectoryView trajectory={traj} />;
}
