import type { CSSProperties } from "react";

export function Sparkline({
  values,
  stroke = "#6BBAB1",
  strokeWidth = 1.2,
  height = 30,
  className,
}: {
  values: number[];
  stroke?: string;
  strokeWidth?: number;
  height?: number;
  className?: string;
}) {
  if (values.length === 0) {
    return (
      <svg
        viewBox="0 0 100 30"
        preserveAspectRatio="none"
        className={className}
        style={{ width: "100%", height } as CSSProperties}
        aria-hidden="true"
      />
    );
  }
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const range = max - min || 1;
  const step = values.length > 1 ? 100 / (values.length - 1) : 0;
  const points = values
    .map((v, i) => {
      const x = i * step;
      const y = 30 - ((v - min) / range) * 26 - 2;
      return `${x},${y.toFixed(2)}`;
    })
    .join(" ");
  return (
    <svg
      viewBox="0 0 100 30"
      preserveAspectRatio="none"
      className={className}
      style={{ width: "100%", height } as CSSProperties}
      aria-hidden="true"
    >
      <polyline points={points} fill="none" stroke={stroke} strokeWidth={strokeWidth} />
    </svg>
  );
}
