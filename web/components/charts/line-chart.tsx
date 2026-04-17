export type LineSeries = {
  name: string;
  color: string;
  values: number[];
};

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
            if (s.values.length === 0) return null;
            const step = s.values.length > 1 ? vw / (s.values.length - 1) : 0;
            const points = s.values.map((v, i) => `${i * step},${toY(v).toFixed(2)}`).join(" ");
            return (
              <polyline
                key={s.name}
                points={points}
                fill="none"
                stroke={s.color}
                strokeWidth={1.5}
              />
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
