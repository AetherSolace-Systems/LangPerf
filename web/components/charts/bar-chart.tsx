export type BarSegment = { color: string; value: number };
export type BarColumn = { label: string; segments: BarSegment[] };

export function StackedBarChart({
  bars,
  height = 120,
}: {
  bars: BarColumn[];
  height?: number;
}) {
  const max = Math.max(
    1,
    ...bars.map((b) => b.segments.reduce((s, seg) => s + seg.value, 0)),
  );
  return (
    <div className="flex flex-col gap-[6px]" style={{ height }}>
      <div className="flex items-end h-full gap-[4px]">
        {bars.map((b) => (
          <div key={b.label} className="flex-1 flex flex-col-reverse gap-[1px] h-full">
            {b.segments.map((seg, i) => {
              const hPct = (seg.value / max) * 100;
              return (
                <div
                  key={i}
                  style={{ background: seg.color, height: `${hPct}%` }}
                  aria-label={`${b.label}: ${seg.value}`}
                />
              );
            })}
          </div>
        ))}
      </div>
      <div className="flex justify-between font-mono text-[9px] text-patina tracking-[0.05em]">
        {bars.map((b) => (
          <span key={b.label} className="flex-1 text-center uppercase">
            {b.label}
          </span>
        ))}
      </div>
    </div>
  );
}
