import { Fragment } from "react";

export type LineSeries = {
  name: string;
  color: string;
  /** `null` skips that x-position — the line breaks into a new segment on the next non-null value. */
  values: Array<number | null>;
};

/**
 * Split a series of possibly-null values into contiguous non-null runs,
 * each paired with its x-index so SVG polylines render as broken segments.
 */
function segments(values: Array<number | null>): Array<Array<{ x: number; y: number }>> {
  const out: Array<Array<{ x: number; y: number }>> = [];
  let current: Array<{ x: number; y: number }> = [];
  values.forEach((v, i) => {
    if (v == null) {
      if (current.length) {
        out.push(current);
        current = [];
      }
    } else {
      current.push({ x: i, y: v });
    }
  });
  if (current.length) out.push(current);
  return out;
}

export function LineChart({
  lines,
  xLabels,
  yTicks,
  yFormat,
  height = 150,
}: {
  lines: LineSeries[];
  xLabels: string[];
  yTicks: number[];
  yFormat: (v: number) => string;
  height?: number;
}) {
  const vw = 240;
  const vh = 130;
  const maxY = yTicks[yTicks.length - 1] ?? 1;
  const toY = (v: number) => vh - (v / maxY) * vh;
  // Assume the longest series defines the x-domain. Dotted fallback if empty.
  const length = Math.max(0, ...lines.map((s) => s.values.length));
  const step = length > 1 ? vw / (length - 1) : 0;
  return (
    <div className="relative" style={{ height }}>
      <div className="absolute left-0 top-0 bottom-[18px] w-[40px] flex flex-col justify-between font-mono text-[9px] text-patina">
        {[...yTicks].reverse().map((t) => (
          <span key={t} className="text-right pr-[6px]">
            {yFormat(t)}
          </span>
        ))}
      </div>
      <div className="absolute left-[40px] right-0 top-0 bottom-[18px] border-l border-b border-[color:var(--border)]">
        <svg viewBox={`0 0 ${vw} ${vh}`} preserveAspectRatio="none" className="w-full h-full">
          {yTicks.slice(0, -1).map((t) => (
            <line
              key={t}
              x1={0}
              x2={vw}
              y1={toY(t)}
              y2={toY(t)}
              stroke="#2E3A40"
              strokeDasharray="2,3"
            />
          ))}
          {lines.map((s) => {
            const segs = segments(s.values);
            if (segs.length === 0) return null;
            return (
              <Fragment key={s.name}>
                {segs.map((seg, si) => {
                  if (seg.length === 1) {
                    const pt = seg[0];
                    return (
                      <circle
                        key={si}
                        cx={pt.x * step}
                        cy={toY(pt.y)}
                        r={1.5}
                        fill={s.color}
                      />
                    );
                  }
                  const points = seg
                    .map((p) => `${p.x * step},${toY(p.y).toFixed(2)}`)
                    .join(" ");
                  return (
                    <polyline
                      key={si}
                      points={points}
                      fill="none"
                      stroke={s.color}
                      strokeWidth={1.5}
                    />
                  );
                })}
              </Fragment>
            );
          })}
        </svg>
      </div>
      <div className="absolute left-[40px] right-0 bottom-0 flex justify-between font-mono text-[9px] text-patina">
        {xLabels.map((label, i) => (
          <span key={`${label}-${i}`}>{label}</span>
        ))}
      </div>
    </div>
  );
}
