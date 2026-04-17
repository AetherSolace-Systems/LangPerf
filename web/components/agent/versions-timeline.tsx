import type { AgentVersionSummary } from "@/lib/api";
import { ClientTime } from "@/components/client-time";

export function VersionsTimeline({
  versions,
}: {
  versions: AgentVersionSummary[];
}) {
  if (versions.length === 0) {
    return (
      <div className="text-patina text-[12px] p-[16px]">
        No versions yet. Versions are captured from the SDK via git SHA +
        package version on each run.
      </div>
    );
  }
  return (
    <table className="w-full border-collapse text-[12px]">
      <thead>
        <tr>
          <Th>Version</Th>
          <Th>SHA</Th>
          <Th>Package</Th>
          <Th>First seen</Th>
          <Th>Last seen</Th>
        </tr>
      </thead>
      <tbody>
        {versions.map((v, i) => {
          const current = i === 0;
          return (
            <tr
              key={v.id}
              className="border-b border-[color:var(--border)] last:border-b-0 hover:bg-[color:rgba(107,186,177,0.03)]"
            >
              <Td>
                <span
                  className={`font-mono text-[12px] ${
                    current ? "text-aether-teal font-medium" : "text-warm-fog"
                  }`}
                >
                  {v.label}
                  {current ? (
                    <span className="ml-[8px] font-mono text-[9px] uppercase tracking-[0.08em] text-patina">
                      current
                    </span>
                  ) : null}
                </span>
              </Td>
              <Td mono>{v.short_sha ?? "—"}</Td>
              <Td mono>{v.package_version ?? "—"}</Td>
              <Td mono>
                <ClientTime iso={v.first_seen_at} />
              </Td>
              <Td mono>
                <ClientTime iso={v.last_seen_at} />
              </Td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return (
    <th className="text-left font-mono text-[9px] text-patina uppercase tracking-[0.1em] px-[10px] py-[8px] border-b border-[color:var(--border)] font-medium">
      {children}
    </th>
  );
}

function Td({
  children,
  mono = false,
}: {
  children: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <td
      className={`px-[10px] py-[7px] text-warm-fog ${
        mono ? "font-mono text-[11px] text-patina" : ""
      }`}
    >
      {children}
    </td>
  );
}
