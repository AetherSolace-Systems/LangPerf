/**
 * Drift Signal — centralized color system.
 *
 * All kind/role/tag coloring lives here so tree, graph, timeline, and
 * right-panel agree. Change a color here and it propagates across views.
 */

export const DRIFT = {
  midnight: "#14141F",       // Page background
  deepIndigo: "#1F2035",      // Cards / surfaces
  driftViolet: "#8B8CC7",     // Primary accent
  marigold: "#E5B754",        // Secondary accent
  linen: "#EDE7DD",           // Text
  twilight: "#6E6F88",        // Muted text

  // Extended hues — derived for node-kind differentiation while staying
  // tonally coherent with the primary palette.
  lagoon: "#5BB6C7",          // cool teal (agents)
  plum: "#C78BAD",            // warm mauve (reasoning / retriever)
  coral: "#E58B54",           // warm red-orange (errors / bad)
  sage: "#7BC89D",            // soft green (good / embedding)
} as const;

function rgba(hex: string, alpha: number): string {
  const h = hex.replace("#", "");
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

export type Swatch = {
  fg: string;
  bg: string;
  border: string;
  solid: string; // for bars on the timeline
};

const mk = (hex: string): Swatch => ({
  fg: hex,
  bg: rgba(hex, 0.09),
  border: rgba(hex, 0.45),
  solid: hex,
});

export const KIND: Record<string, Swatch> = {
  llm: mk(DRIFT.driftViolet),
  tool: mk(DRIFT.marigold),
  tool_call: mk(DRIFT.marigold),
  agent: mk(DRIFT.lagoon),
  chain: mk(DRIFT.marigold),
  retriever: mk(DRIFT.plum),
  embedding: mk(DRIFT.sage),
  reasoning: mk(DRIFT.plum),
  trajectory: mk(DRIFT.linen),
};

export const DEFAULT_KIND = mk(DRIFT.twilight);

export function kindSwatch(kind: string | null | undefined): Swatch {
  if (!kind) return DEFAULT_KIND;
  return KIND[kind.toLowerCase()] ?? DEFAULT_KIND;
}

export const ROLE: Record<string, Swatch> = {
  system: mk(DRIFT.marigold),
  user: mk(DRIFT.lagoon),
  assistant: mk(DRIFT.driftViolet),
  tool: mk(DRIFT.plum),
  developer: mk(DRIFT.coral),
};

export function roleSwatch(role: string): Swatch {
  return ROLE[role.toLowerCase()] ?? DEFAULT_KIND;
}

export const TAG: Record<string, Swatch> = {
  good: mk(DRIFT.sage),
  bad: mk(DRIFT.coral),
  interesting: mk(DRIFT.driftViolet),
  todo: mk(DRIFT.marigold),
};

export function tagSwatch(tag: string | null): Swatch {
  if (!tag) return DEFAULT_KIND;
  return TAG[tag.toLowerCase()] ?? DEFAULT_KIND;
}

export const GRADIENT =
  "linear-gradient(135deg, #14141F 0%, #1F2035 30%, #8B8CC7 60%, #E5B754 100%)";

/**
 * Glyph + label per kind, co-located with the color swatches above. When
 * a view needs to render a kind (tree row, graph node, timeline label),
 * reach for KIND_GLYPH / KIND_LABEL together with kindSwatch() so color,
 * icon, and label stay in sync across views.
 */
export const KIND_GLYPH: Record<string, string> = {
  llm: "✦",
  tool: "▸",
  tool_call: "▸",
  reasoning: "≈",
  agent: "◇",
  trajectory: "◆",
  chain: "▸",
  retriever: "▸",
  embedding: "▸",
};

export const KIND_LABEL: Record<string, string> = {
  llm: "llm",
  tool: "tool",
  tool_call: "tool",
  reasoning: "reasoning",
  agent: "agent",
  trajectory: "trajectory",
  chain: "chain",
  retriever: "retriever",
  embedding: "embedding",
};
