"use client";

import { useState } from "react";
import {
  BaseEdge,
  EdgeLabelRenderer,
  getSmoothStepPath,
  type EdgeProps,
} from "@xyflow/react";
import type { LabelledEdgeData } from "@/lib/graph-edges";

export function LabelledEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
}: EdgeProps & { data?: LabelledEdgeData }) {
  const [expanded, setExpanded] = useState(false);
  const [edgePath, labelX, labelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
    borderRadius: 8,
  });

  return (
    <>
      <BaseEdge id={id} path={edgePath} style={{ stroke: "var(--muted)", strokeWidth: 1.5, strokeOpacity: 0.75 }} />
      <EdgeLabelRenderer>
        <div
          data-edge-label=""
          data-expanded={expanded ? "true" : "false"}
          onClick={(e) => {
            e.stopPropagation();
            if (data?.payload) setExpanded((v) => !v);
          }}
          style={{
            position: "absolute",
            transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
            pointerEvents: "all",
            fontFamily: 'ui-monospace, "SF Mono", Menlo, monospace',
            fontSize: 9,
            textTransform: "uppercase",
            letterSpacing: "0.06em",
            color: "var(--muted)",
            background: "var(--surface)",
            border: "1px solid var(--border)",
            borderRadius: 3,
            padding: expanded ? "4px 8px" : "1px 6px",
            cursor: data?.payload ? "pointer" : "default",
            maxWidth: expanded ? 240 : undefined,
            whiteSpace: expanded ? "normal" : "nowrap",
            // Lift above React Flow's internal pane / edges / node wrappers
            // so the click actually reaches our onClick rather than the pane's
            // drag handler. Any value > the default flow layers (5) works.
            zIndex: 20,
          }}
        >
          <div>{data?.label ?? "→"}</div>
          {expanded && data?.payload ? (
            <div
              style={{
                marginTop: 4,
                color: "var(--foreground)",
                whiteSpace: "pre-wrap",
                wordBreak: "break-all",
                fontSize: 10,
              }}
            >
              {data.payload}
            </div>
          ) : null}
        </div>
      </EdgeLabelRenderer>
    </>
  );
}
