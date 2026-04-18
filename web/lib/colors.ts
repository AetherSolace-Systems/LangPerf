/**
 * Drift Signal — centralized color system.
 *
 * All kind/role/tag coloring lives here so tree, graph, timeline, and
 * right-panel agree. Change a color here and it propagates across views.
 *
 * Convention (read before adding colors):
 *   - Kind-aware colors (LLM/tool/agent/reasoning/trajectory node borders,
 *     tag chips, role-coded message cards) MUST come from kindSwatch() /
 *     roleSwatch() / tagSwatch() or the DRIFT palette below. Don't hardcode
 *     hexes or one-off Tailwind color classes — it breaks cross-view sync.
 *   - Structural colors (page backgrounds, panel borders, muted helper
 *     text, scrollbars) stay on CSS variables (`var(--border)`,
 *     `var(--muted)`, `var(--foreground)`) so a single theme swap can move
 *     the whole app in lockstep with tailwind.config.ts and globals.css.
 */

/**
 * Aether Dusk palette. `DRIFT` export retained as an alias so existing
 * imports continue to work; prefer `AETHER` in new code.
 */
export const AETHER = {
  carbon: "#181D21",           // Page background (was DRIFT.midnight)
  steelMist: "#242D32",        // Cards / surfaces (was DRIFT.deepIndigo)
  surface2: "#1F272B",         // Secondary surface (rail, identity strip)
  aetherTeal: "#6BBAB1",       // Primary accent (was DRIFT.driftViolet)
  peachNeon: "#E8A87C",        // Secondary accent (was DRIFT.marigold)
  warmFog: "#F2EAE2",          // Text (was DRIFT.linen)
  patina: "#7A8B8E",           // Muted text (was DRIFT.twilight)
  warn: "#D98A6A",             // Errors / bad tags
} as const;

export const DRIFT = {
  // Legacy alias — values repointed to Aether Dusk so existing imports adopt
  // the new palette without rewiring. Prefer AETHER in new code.
  midnight: AETHER.carbon,
  deepIndigo: AETHER.steelMist,
  driftViolet: AETHER.aetherTeal,
  marigold: AETHER.peachNeon,
  linen: AETHER.warmFog,
  twilight: AETHER.patina,

  // Extended hues collapsed into the reduced Aether Dusk palette.
  lagoon: AETHER.aetherTeal,
  plum: AETHER.peachNeon,
  coral: AETHER.warn,
  sage: AETHER.aetherTeal,
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
  "linear-gradient(135deg, #181D21 0%, #242D32 25%, #6BBAB1 60%, #E8A87C 100%)";

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
