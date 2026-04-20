import { AppShell } from "@/components/shell/app-shell";
import { AgentsTable } from "@/components/agents/agents-table";
import { Chip } from "@/components/ui/chip";
import { listAgents, type AgentSummary } from "@/lib/api";
import { isRedirectError } from "@/lib/fetch-utils";
import { listProjects, type Project } from "@/lib/projects";
import { ProjectFilter } from "@/components/projects/project-filter";

export const dynamic = "force-dynamic";

export default async function AgentsPage({
  searchParams,
}: {
  searchParams: Promise<{ project?: string }>;
}) {
  const params = await searchParams;
  const selectedProject = params.project ?? null;

  let agents: AgentSummary[];
  let projects: Project[];
  try {
    [agents, projects] = await Promise.all([
      listAgents().then((a) => a as AgentSummary[]),
      listProjects(),
    ]);
  } catch (err) {
    if (isRedirectError(err)) throw err;
    return (
      <AppShell
        topBar={{
          breadcrumb: <span className="font-medium text-warm-fog">Agents</span>,
        }}
      >
        <div
          className="rounded border p-4 text-sm"
          style={{
            borderColor: "rgba(217,138,106,0.45)",
            background: "rgba(217,138,106,0.1)",
          }}
        >
          <p className="font-medium text-warn">Could not reach langperf-api</p>
          <p className="mt-1 text-patina font-mono text-xs">
            {err instanceof Error ? err.message : String(err)}
          </p>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell
      topBar={{
        breadcrumb: <span className="font-medium text-warm-fog">Agents</span>,
        right: (
          <Chip>
            {agents.length} agent{agents.length === 1 ? "" : "s"}
          </Chip>
        ),
      }}
    >
      <ProjectFilter projects={projects} />
      <AgentsTable agents={agents} projects={projects} selectedProject={selectedProject} />
    </AppShell>
  );
}
