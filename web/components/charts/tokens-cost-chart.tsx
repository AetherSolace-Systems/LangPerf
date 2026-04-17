export type TokensCostBucket = {
  label: string;
  input_tokens: number;
  output_tokens: number;
  cost: number;
};

export function TokensCostChart({
  buckets,
  height = 150,
}: {
  buckets: TokensCostBucket[];
  height?: number;
}) {
  const maxTokens = Math.max(1, ...buckets.map((b) => b.input_tokens + b.output_tokens));
  const maxCost = Math.max(0.0001, ...buckets.map((b) => b.cost));
  const vw = 240;
  const vh = 130;
  const barW = buckets.length ? Math.max(2, vw / buckets.length - 2) : 0;
  const gap = 2;

  const costPoints = buckets
    .map((b, i) => {
      const x = i * (vw / buckets.length) + barW / 2;
      const y = vh - (b.cost / maxCost) * (vh - 6);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  return (
    <div className="relative" style={{ height }}>
      <div className="absolute left-0 top-0 bottom-[18px] w-[48px] flex flex-col justify-between font-mono text-[9px] text-aether-teal text-right pr-[6px]">
        <span>{(maxTokens / 1000).toFixed(0)}k</span>
        <span>{((maxTokens * 0.5) / 1000).toFixed(0)}k</span>
        <span>0</span>
      </div>
      <div className="absolute right-0 top-0 bottom-[18px] w-[40px] flex flex-col justify-between font-mono text-[9px] text-peach-neon text-left pl-[6px]">
        <span>${maxCost.toFixed(2)}</span>
        <span>${(maxCost / 2).toFixed(2)}</span>
        <span>$0</span>
      </div>
      <div className="absolute left-[48px] right-[40px] top-0 bottom-[18px] border-l border-r border-b border-[color:var(--border)]">
        <svg viewBox={`0 0 ${vw} ${vh}`} preserveAspectRatio="none" className="w-full h-full">
          {buckets.map((b, i) => {
            const x = i * (vw / buckets.length) + gap;
            const totalH = ((b.input_tokens + b.output_tokens) / maxTokens) * vh;
            const inputH = (b.input_tokens / maxTokens) * vh;
            const outputH = totalH - inputH;
            return (
              <g key={i}>
                <rect
                  x={x}
                  y={vh - totalH}
                  width={barW - gap}
                  height={outputH}
                  fill="#6BBAB1"
                  opacity={0.45}
                />
                <rect
                  x={x}
                  y={vh - inputH}
                  width={barW - gap}
                  height={inputH}
                  fill="#6BBAB1"
                  opacity={0.85}
                />
              </g>
            );
          })}
          {buckets.length > 1 ? (
            <polyline points={costPoints} fill="none" stroke="#E8A87C" strokeWidth={1.5} />
          ) : null}
        </svg>
      </div>
      <div className="absolute left-[48px] right-[40px] bottom-0 flex justify-between font-mono text-[9px] text-patina">
        {buckets.map((b, i) => (
          <span key={`${b.label}-${i}`}>{b.label}</span>
        ))}
      </div>
    </div>
  );
}
