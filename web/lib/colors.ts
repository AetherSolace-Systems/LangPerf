/**
 * Drift Signal — centralized color system.
 *
 * All kind/role/tag coloring lives here so tree, graph, timeline, and
 * right-panel agree. Change a color here and it propagates across views.
 *
 * Convention (read before adding colors):
 *   - Kind-aware colors (LLM/tool/agent/reasoning/trajectory node borders,
 *     tag chips, role-coded message cards) MUST come from kindSwatch() /
 *     roleSwatch() / tagSwatch() or the AETHER palette below. Don't hardcode
 *     hexes or one-off Tailwind color classes — it breaks cross-view sync.
 *   - Structural colors (page backgrounds, panel borders, muted helper
 *     text, scrollbars) stay on CSS variables (`var(--border)`,
 *     `var(--muted)`, `var(--foreground)`) so a single theme swap can move
 *     the whole app in lockstep with tailwind.config.ts and globals.css.
 */

/**
 * Aether Dusk palette. All kind/role/tag swatches derive from these hexes
 * so a single edit here recolors the entire app in lockstep with
 * tailwind.config.ts.
 */
export const AETHER = {
  carbon: "#181D21",           // Page background
  steelMist: "#242D32",        // Cards / surfaces
  surface2: "#1F272B",         // Secondary surface (rail, identity strip)
  aetherTeal: "#6BBAB1",       // Primary accent
  peachNeon: "#E8A87C",        // Secondary accent
  warmFog: "#F2EAE2",          // Text
  patina: "#7A8B8E",           // Muted text
  warn: "#D98A6A",             // Errors / bad tags
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
  llm: mk(AETHER.aetherTeal),
  tool: mk(AETHER.peachNeon),
  tool_call: mk(AETHER.peachNeon),
  agent: mk(AETHER.aetherTeal),
  chain: mk(AETHER.peachNeon),
  retriever: mk(AETHER.peachNeon),
  embedding: mk(AETHER.aetherTeal),
  reasoning: mk(AETHER.peachNeon),
  trajectory: mk(AETHER.warmFog),
};

export const DEFAULT_KIND = mk(AETHER.patina);

export function kindSwatch(kind: string | null | undefined): Swatch {
  if (!kind) return DEFAULT_KIND;
  return KIND[kind.toLowerCase()] ?? DEFAULT_KIND;
}

export const ROLE: Record<string, Swatch> = {
  system: mk(AETHER.peachNeon),
  user: mk(AETHER.aetherTeal),
  assistant: mk(AETHER.aetherTeal),
  tool: mk(AETHER.peachNeon),
  developer: mk(AETHER.warn),
};

export function roleSwatch(role: string): Swatch {
  return ROLE[role.toLowerCase()] ?? DEFAULT_KIND;
}

export const TAG: Record<string, Swatch> = {
  good: mk(AETHER.aetherTeal),
  bad: mk(AETHER.warn),
  interesting: mk(AETHER.aetherTeal),
  todo: mk(AETHER.peachNeon),
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
