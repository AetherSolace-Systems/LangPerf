# Phase 1 — UI Shell Foundations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current two-route web app (trajectory list at `/`, trajectory detail at `/t/[id]`) with a full navigation shell — Aether Dusk palette, top bar + icon rail + context sidebar, and scaffolded routes for every section in the IA (Dashboard, Agents, History, Logs, Settings) with placeholder content. No data-model or backend changes.

**Architecture:** Pure frontend work. Swap palette hex values in Tailwind / CSS / `colors.ts` while keeping the existing utility class names as aliases — so existing components adopt the new palette without edits. Add reusable shell components (`TopBar`, `IconRail`, `ContextSidebar`, `AppShell`) that every route composes. Move the existing trajectory-list behavior to `/history` verbatim so users can still reach their data; stub `/`, `/agents`, `/logs`, `/settings` as placeholder pages consistent with the mocked design.

**Tech Stack:** Next.js 14 (app router), React 18, TypeScript, Tailwind CSS 3.4, `next/font` for Inter + JetBrains Mono. No tests (project has no test infrastructure — verification is `next build` + browser check).

---

## File Structure

**New files:**
- `web/components/ui/chip.tsx` — reusable uppercase-mono chip primitive
- `web/components/shell/top-bar.tsx` — logo + breadcrumb slot + search + right slot
- `web/components/shell/icon-rail.tsx` — labeled vertical nav with active state + v2 disabled items
- `web/components/shell/context-sidebar.tsx` — 220px sidebar with header + children
- `web/components/shell/app-shell.tsx` — composer combining rail + ctx sidebar + main + top bar
- `web/components/shell/nav-config.ts` — single source of truth for rail items and their paths
- `web/app/agents/page.tsx` — agents index placeholder
- `web/app/agents/[name]/page.tsx` — redirects to `/agents/[name]/overview`
- `web/app/agents/[name]/[tab]/page.tsx` — agent-detail tab shell with placeholder content
- `web/app/history/page.tsx` — re-homed trajectory list
- `web/app/logs/page.tsx` — logs placeholder
- `web/app/settings/page.tsx` — redirects to `/settings/log-forwarding`
- `web/app/settings/[section]/page.tsx` — settings section router with placeholder content
- `web/app/r/[run_id]/page.tsx` — `/r/<id>` permalink that redirects to `/t/<id>`

**Modified files:**
- `web/tailwind.config.ts` — swap hex values to Aether Dusk; add new semantic tokens; wire JetBrains Mono + Inter font variables
- `web/app/globals.css` — swap CSS variable hex values to Aether Dusk
- `web/lib/colors.ts` — swap hex values in `DRIFT` to Aether Dusk; add named aliases
- `web/app/layout.tsx` — load Inter + JetBrains Mono via `next/font`; wrap children in `AppShell`
- `web/app/page.tsx` — replace trajectory list with Dashboard placeholder
- `web/components/filter-bar.tsx` — `router.push('/?...')` → `router.push('/history?...')`, same for clear button
- `web/app/t/[id]/page.tsx` — wrap existing content in breadcrumb + identity strip (still canonical URL in Phase 1)

**Unchanged (picks up new palette via CSS variables / tailwind aliases):**
- `web/components/trajectory-view.tsx`, `trajectory-tree.tsx`, `trajectory-graph.tsx`, `trajectory-timeline.tsx`
- `web/components/node-detail-panel.tsx`, `notes-editor.tsx`, `tag-selector.tsx`
- `web/components/views/*`

---

## Aether Dusk Palette Reference (used throughout)

| Token | Hex | Old alias (kept) |
|---|---|---|
| `--background` / `carbon` | `#181D21` | `midnight` |
| `--surface` / `steel-mist` | `#242D32` | `deep-indigo` |
| `--surface-2` | `#1F272B` | (new) |
| `--accent` / `aether-teal` | `#6BBAB1` | `drift-violet` |
| `--accent-warm` / `peach-neon` | `#E8A87C` | `marigold` |
| `--warn` | `#D98A6A` | `coral` |
| `--foreground` / `warm-fog` | `#F2EAE2` | `linen` |
| `--muted` / `patina` | `#7A8B8E` | `twilight` |
| `--border` | `#2E3A40` | (bg change) |
| `--border-strong` | `#3A4950` | (bg change) |

`lagoon`, `plum`, `sage` are merged into `aether-teal` / `peach-neon` since the new palette is intentionally reduced. The old names stay as aliases so existing component code continues to compile.

---

### Task 1: Swap palette hex values (Tailwind + globals.css + colors.ts)

**Files:**
- Modify: `web/tailwind.config.ts` (replace entire file)
- Modify: `web/app/globals.css` (replace `:root` block)
- Modify: `web/lib/colors.ts` (update `DRIFT` constant + add `AETHER` alias)

- [ ] **Step 1: Replace `web/tailwind.config.ts` with new palette + semantic tokens + font variables**

```ts
import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Aether Dusk — canonical names
        carbon: "#181D21",
        "steel-mist": "#242D32",
        "surface-2": "#1F272B",
        "aether-teal": "#6BBAB1",
        "peach-neon": "#E8A87C",
        "warm-fog": "#F2EAE2",
        patina: "#7A8B8E",
        warn: "#D98A6A",

        // Legacy aliases — same hex as the canonical name they used to be,
        // now re-pointed so existing components adopt Aether Dusk without edits.
        midnight: "#181D21",          // was #14141F
        "deep-indigo": "#242D32",     // was #1F2035
        "drift-violet": "#6BBAB1",    // was #8B8CC7
        marigold: "#E8A87C",          // was #E5B754
        linen: "#F2EAE2",             // was #EDE7DD
        twilight: "#7A8B8E",          // was #6E6F88
        lagoon: "#6BBAB1",            // merged into aether-teal
        plum: "#E8A87C",              // merged into peach-neon
        coral: "#D98A6A",             // repointed to warn
        sage: "#6BBAB1",              // merged into aether-teal
      },
      fontFamily: {
        sans: ["var(--font-inter)", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto", "sans-serif"],
        mono: ["var(--font-jetbrains-mono)", "ui-monospace", "SFMono-Regular", "Menlo", "Monaco", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
```

- [ ] **Step 2: Replace the `:root` block in `web/app/globals.css`**

Current file contents (lines 5–15) read:

```css
:root {
  /* Drift Signal palette */
  --background: #14141F;     /* Midnight */
  --surface: #1F2035;         /* Deep Indigo */
  --foreground: #EDE7DD;      /* Linen */
  --muted: #6E6F88;           /* Twilight */
  --accent: #8B8CC7;          /* Drift Violet */
  --accent-warm: #E5B754;     /* Marigold */
  --border: #2B2B45;          /* subtle border derived from indigo */
  --border-strong: #3A3B58;
}
```

Replace with:

```css
:root {
  /* Aether Dusk palette */
  --background: #181D21;      /* Carbon */
  --surface: #242D32;         /* Steel Mist */
  --surface-2: #1F272B;       /* secondary surface — rail, identity strip */
  --foreground: #F2EAE2;      /* Warm Fog */
  --muted: #7A8B8E;           /* Patina */
  --accent: #6BBAB1;          /* Aether Teal */
  --accent-warm: #E8A87C;     /* Peach Neon */
  --warn: #D98A6A;
  --border: #2E3A40;
  --border-strong: #3A4950;
}
```

Also update the selection rule at lines 28–31 to use the new accent-warm value. Current:

```css
::selection {
  background: rgba(229, 183, 84, 0.3);
  color: var(--foreground);
}
```

Replace with:

```css
::selection {
  background: rgba(232, 168, 124, 0.3);
  color: var(--foreground);
}
```

- [ ] **Step 3: Update `web/lib/colors.ts` — swap `DRIFT` hex values and add `AETHER` alias**

Replace the `DRIFT` constant block (lines 18–32) with:

```ts
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
```

Leave the `rgba`, `Swatch`, `mk`, `KIND`, `ROLE`, `TAG`, `KIND_GLYPH`, `KIND_LABEL`, and `GRADIENT` exports (lines 34–end) as-is — they reference `DRIFT.*` and will pick up the new hexes automatically. Update the `GRADIENT` constant to use the new hexes:

Current:
```ts
export const GRADIENT =
  "linear-gradient(135deg, #14141F 0%, #1F2035 30%, #8B8CC7 60%, #E5B754 100%)";
```

Replace with:
```ts
export const GRADIENT =
  "linear-gradient(135deg, #181D21 0%, #242D32 25%, #6BBAB1 60%, #E8A87C 100%)";
```

- [ ] **Step 4: Type-check**

Run: `cd web && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 5: Visual smoke test**

Run: `cd /Users/andrewlavoie/code/langperf && docker compose up -d postgres langperf-api langperf-web`
(wait for `web` to print `ready`)
Open: `http://localhost:3000`
Expected: existing trajectory list renders but with Aether Dusk colors — dark carbon background, teal accents where purple was, peach where marigold was.

- [ ] **Step 6: Commit**

```bash
cd /Users/andrewlavoie/code/langperf
git add web/tailwind.config.ts web/app/globals.css web/lib/colors.ts
git commit -m "web: swap palette to Aether Dusk (teal/peach on carbon)"
```

---

### Task 2: Add Inter + JetBrains Mono via next/font

**Files:**
- Modify: `web/package.json` (no change — Next 14 bundles `next/font` with Google Fonts out of the box, no external dep needed)
- Modify: `web/app/layout.tsx`

- [ ] **Step 1: Replace `web/app/layout.tsx`**

```tsx
import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-jetbrains-mono",
});

export const metadata: Metadata = {
  title: "LangPerf",
  description: "The agent improvement loop",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${inter.variable} ${jetbrainsMono.variable}`}>
      <body className="font-sans">{children}</body>
    </html>
  );
}
```

Note: `AppShell` wrapping happens in Task 8 — this step just establishes fonts.

- [ ] **Step 2: Verify build**

Run: `cd web && npx next build`
Expected: build succeeds; console mentions `Inter` and `JetBrains Mono` being downloaded/cached.

- [ ] **Step 3: Commit**

```bash
git add web/app/layout.tsx
git commit -m "web: load Inter + JetBrains Mono via next/font"
```

---

### Task 3: Create `Chip` primitive

**Files:**
- Create: `web/components/ui/chip.tsx`

- [ ] **Step 1: Create `web/components/ui/chip.tsx`**

```tsx
import type { ReactNode } from "react";

export type ChipVariant = "default" | "primary" | "accent" | "warn" | "on";

export function Chip({
  children,
  variant = "default",
  className = "",
}: {
  children: ReactNode;
  variant?: ChipVariant;
  className?: string;
}) {
  const variantCls: Record<ChipVariant, string> = {
    default:
      "text-patina border-[color:var(--border-strong)]",
    primary:
      "text-aether-teal border-[color:rgba(107,186,177,0.45)]",
    accent:
      "text-peach-neon border-[color:rgba(232,168,124,0.45)]",
    warn:
      "text-warn border-[color:rgba(217,138,106,0.4)]",
    on:
      "bg-[color:rgba(107,186,177,0.1)] text-aether-teal border-[color:rgba(107,186,177,0.45)]",
  };
  return (
    <span
      className={`inline-flex items-center px-[7px] py-[2px] rounded-[2px] text-[10px] uppercase tracking-[0.08em] font-mono whitespace-nowrap border ${variantCls[variant]} ${className}`}
    >
      {children}
    </span>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd web && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add web/components/ui/chip.tsx
git commit -m "web: add Chip primitive for Aether Dusk chip styling"
```

---

### Task 4: Create `nav-config.ts` (rail + settings nav source of truth)

**Files:**
- Create: `web/components/shell/nav-config.ts`

- [ ] **Step 1: Create the file**

```ts
/**
 * Single source of truth for rail items and settings section nav. The rail
 * and active-state logic read from here, so route additions happen in one
 * place. v2-flagged items render disabled until those sections ship.
 */

export type RailItem = {
  id: string;
  label: string;      // UPPERCASE short label under the glyph
  glyph: string;      // single-char mono glyph
  href: string;       // href used when enabled
  v2?: boolean;       // true ⇒ render disabled with a "v2 · coming" tooltip
  group?: "primary" | "later" | "footer";
};

export const RAIL_ITEMS: RailItem[] = [
  { id: "home",     label: "home",    glyph: "□", href: "/",          group: "primary" },
  { id: "agents",   label: "agents",  glyph: "◇", href: "/agents",    group: "primary" },
  { id: "history",  label: "history", glyph: "≡", href: "/history",   group: "primary" },
  { id: "logs",     label: "logs",    glyph: "⌘", href: "/logs",      group: "primary" },
  { id: "triage",   label: "triage",  glyph: "!", href: "#",          v2: true, group: "later" },
  { id: "evals",    label: "evals",   glyph: "✓", href: "#",          v2: true, group: "later" },
  { id: "data",     label: "data",    glyph: "↓", href: "#",          v2: true, group: "later" },
  { id: "config",   label: "config",  glyph: "⚙", href: "/settings",  group: "footer" },
];

export type SettingsSection = {
  id: string;
  label: string;
  href: string;
  group: "workspace" | "observability" | "integrations" | "later";
  v2?: boolean;
};

export const SETTINGS_SECTIONS: SettingsSection[] = [
  { id: "profile",        label: "Profile",             href: "/settings/profile",         group: "workspace" },
  { id: "environments",   label: "Environments",        href: "/settings/environments",    group: "workspace" },
  { id: "agents-review",  label: "Agents · auto-detected", href: "/settings/agents-review", group: "workspace" },
  { id: "log-forwarding", label: "Log forwarding",      href: "/settings/log-forwarding",  group: "observability" },
  { id: "trace-export",   label: "Agent trace export",  href: "/settings/trace-export",    group: "observability" },
  { id: "sdk-keys",       label: "SDK keys",            href: "/settings/sdk-keys",        group: "integrations" },
  { id: "webhooks",       label: "Webhooks",            href: "/settings/webhooks",        group: "integrations" },
  { id: "users-org",      label: "Users & org",         href: "#",                          group: "later", v2: true },
  { id: "billing",        label: "Billing",             href: "#",                          group: "later", v2: true },
  { id: "sso",            label: "SSO / SAML",          href: "#",                          group: "later", v2: true },
];
```

- [ ] **Step 2: Type-check + commit**

```bash
cd web && npx tsc --noEmit
cd /Users/andrewlavoie/code/langperf
git add web/components/shell/nav-config.ts
git commit -m "web: add nav-config.ts (source of truth for rail + settings nav)"
```

---

### Task 5: Create `TopBar` component

**Files:**
- Create: `web/components/shell/top-bar.tsx`

- [ ] **Step 1: Create the file**

```tsx
import type { ReactNode } from "react";
import Link from "next/link";
import { Chip } from "@/components/ui/chip";

export type TopBarProps = {
  /** Breadcrumb content rendered next to the logo. Can be a single label or a chain of <Link>s. */
  breadcrumb?: ReactNode;
  /** Right-side slot — env chip, ingest status, etc. */
  right?: ReactNode;
  /** When true, hide the search input (e.g. on narrow layouts). */
  hideSearch?: boolean;
};

export function TopBar({ breadcrumb, right, hideSearch = false }: TopBarProps) {
  return (
    <header className="flex items-center gap-3 px-4 py-[9px] border-b border-[color:var(--border)] bg-[color:var(--surface)]">
      <Link href="/" className="font-semibold text-[13px] tracking-[-0.01em] select-none">
        <span className="text-aether-teal">lang</span>
        <span className="text-peach-neon">perf</span>
      </Link>
      {breadcrumb ? (
        <div className="text-[12px] text-patina flex items-center gap-2">{breadcrumb}</div>
      ) : null}
      <div className="flex-1" />
      {!hideSearch ? (
        <div className="max-w-[260px] flex-1">
          <input
            type="text"
            placeholder="⌘k · fuzzy · my_agent.*.*"
            className="w-full bg-[color:var(--background)] border border-[color:var(--border)] rounded-[3px] px-[10px] py-[5px] text-[11px] font-mono text-warm-fog placeholder:text-patina focus:outline-none focus:border-[color:var(--border-strong)]"
            disabled
            aria-disabled="true"
            title="Global search lands in a follow-up plan"
          />
        </div>
      ) : null}
      {right ?? <Chip>env: all</Chip>}
    </header>
  );
}
```

- [ ] **Step 2: Type-check + commit**

```bash
cd web && npx tsc --noEmit
cd /Users/andrewlavoie/code/langperf
git add web/components/shell/top-bar.tsx
git commit -m "web: add TopBar shell component"
```

---

### Task 6: Create `IconRail` component

**Files:**
- Create: `web/components/shell/icon-rail.tsx`

- [ ] **Step 1: Create the file**

```tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { RAIL_ITEMS, type RailItem } from "@/components/shell/nav-config";

function isActive(pathname: string, item: RailItem): boolean {
  if (item.v2) return false;
  if (item.href === "/") return pathname === "/";
  return pathname === item.href || pathname.startsWith(`${item.href}/`);
}

function RailCell({ item, active }: { item: RailItem; active: boolean }) {
  const base =
    "flex flex-col items-center gap-[2px] px-[2px] py-[8px] text-[9px] uppercase tracking-[0.08em] border-l-2 border-transparent";
  const state = item.v2
    ? "text-patina opacity-55 cursor-not-allowed"
    : active
      ? "text-aether-teal border-l-aether-teal bg-[color:rgba(107,186,177,0.04)]"
      : "text-patina hover:text-warm-fog";
  const body = (
    <>
      <span className="font-mono text-[12px]">{item.glyph}</span>
      <span>{item.label}</span>
    </>
  );
  if (item.v2) {
    return (
      <div className={`${base} ${state}`} title="v2 · coming soon" aria-disabled="true">
        {body}
      </div>
    );
  }
  return (
    <Link href={item.href} className={`${base} ${state}`}>
      {body}
    </Link>
  );
}

export function IconRail() {
  const pathname = usePathname() ?? "/";
  const primary = RAIL_ITEMS.filter((i) => i.group === "primary");
  const later = RAIL_ITEMS.filter((i) => i.group === "later");
  const footer = RAIL_ITEMS.filter((i) => i.group === "footer");

  return (
    <nav className="w-[56px] border-r border-[color:var(--border)] bg-[color:var(--surface-2)] flex flex-col py-[8px] gap-[2px]">
      {primary.map((i) => (
        <RailCell key={i.id} item={i} active={isActive(pathname, i)} />
      ))}
      <div className="h-px bg-[color:var(--border)] mx-[8px] my-[6px]" />
      {later.map((i) => (
        <RailCell key={i.id} item={i} active={false} />
      ))}
      <div className="flex-1" />
      <div className="h-px bg-[color:var(--border)] mx-[8px] my-[6px]" />
      {footer.map((i) => (
        <RailCell key={i.id} item={i} active={isActive(pathname, i)} />
      ))}
    </nav>
  );
}
```

- [ ] **Step 2: Type-check + commit**

```bash
cd web && npx tsc --noEmit
cd /Users/andrewlavoie/code/langperf
git add web/components/shell/icon-rail.tsx
git commit -m "web: add IconRail — labeled vertical nav with active-state + v2 disabled"
```

---

### Task 7: Create `ContextSidebar` component

**Files:**
- Create: `web/components/shell/context-sidebar.tsx`

- [ ] **Step 1: Create the file**

```tsx
import type { ReactNode } from "react";

export type ContextSidebarProps = {
  children: ReactNode;
  className?: string;
};

/**
 * 220px fixed-width sidebar that lives between the icon rail and the main
 * content. Pages own their sidebar content — this component just provides
 * the consistent frame (width, border, padding, scrollbar).
 */
export function ContextSidebar({ children, className = "" }: ContextSidebarProps) {
  return (
    <aside
      className={`w-[220px] border-r border-[color:var(--border)] bg-[color:var(--background)] px-[10px] py-[12px] overflow-y-auto ${className}`}
    >
      {children}
    </aside>
  );
}

/**
 * Helper components so pages don't re-invent the header/item styling.
 */
export function CtxHeader({
  children,
  action,
}: {
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex items-center justify-between px-[4px] pt-[6px] pb-[4px] font-mono text-[9px] text-patina uppercase tracking-[0.1em]">
      <span>{children}</span>
      {action ? <span className="text-aether-teal">{action}</span> : null}
    </div>
  );
}

export function CtxItem({
  children,
  active = false,
  sub,
}: {
  children: ReactNode;
  active?: boolean;
  sub?: ReactNode;
}) {
  return (
    <div
      className={`flex items-center gap-2 px-[6px] py-[5px] rounded-[2px] text-[12px] my-[1px] ${
        active ? "bg-[color:rgba(107,186,177,0.07)] text-warm-fog" : "text-warm-fog"
      }`}
    >
      <span className="flex-1 truncate">{children}</span>
      {sub ? <span className="font-mono text-[10px] text-patina">{sub}</span> : null}
    </div>
  );
}
```

- [ ] **Step 2: Type-check + commit**

```bash
cd web && npx tsc --noEmit
cd /Users/andrewlavoie/code/langperf
git add web/components/shell/context-sidebar.tsx
git commit -m "web: add ContextSidebar + CtxHeader/CtxItem helpers"
```

---

### Task 8: Create `AppShell` composer + apply in root layout

**Files:**
- Create: `web/components/shell/app-shell.tsx`
- Modify: `web/app/layout.tsx`

- [ ] **Step 1: Create `web/components/shell/app-shell.tsx`**

```tsx
import type { ReactNode } from "react";
import { IconRail } from "@/components/shell/icon-rail";
import { TopBar, type TopBarProps } from "@/components/shell/top-bar";

export type AppShellProps = {
  /** Top-bar props forwarded verbatim. */
  topBar?: TopBarProps;
  /** Optional context sidebar. Pass a <ContextSidebar>…</ContextSidebar> node, or omit for a two-zone layout. */
  contextSidebar?: ReactNode;
  /** Main content. */
  children: ReactNode;
};

export function AppShell({ topBar, contextSidebar, children }: AppShellProps) {
  return (
    <div className="min-h-screen flex flex-col bg-[color:var(--background)] text-[color:var(--foreground)]">
      <TopBar {...(topBar ?? {})} />
      <div className="flex flex-1 min-h-0">
        <IconRail />
        {contextSidebar}
        <main className="flex-1 min-w-0 overflow-auto p-[14px]">{children}</main>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Decide on layout wrapping strategy**

The root layout does NOT wrap every page in `AppShell` directly — individual pages call `<AppShell>` so each page can pass its own `topBar` and `contextSidebar`. The root layout stays minimal (just `<html><body>{children}` with fonts) so legacy routes that haven't been migrated yet (e.g. the raw `/t/[id]` page in Task 15) still render.

`web/app/layout.tsx` was updated in Task 2. No further change needed here. Confirm it still reads:

```tsx
import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-jetbrains-mono",
});

export const metadata: Metadata = {
  title: "LangPerf",
  description: "The agent improvement loop",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${inter.variable} ${jetbrainsMono.variable}`}>
      <body className="font-sans">{children}</body>
    </html>
  );
}
```

- [ ] **Step 3: Type-check + commit**

```bash
cd web && npx tsc --noEmit
cd /Users/andrewlavoie/code/langperf
git add web/components/shell/app-shell.tsx
git commit -m "web: add AppShell composer (pages call it per-route)"
```

---

### Task 9: Move trajectory list to `/history`

**Files:**
- Create: `web/app/history/page.tsx`
- Modify: `web/components/filter-bar.tsx` (update router pushes from `/` to `/history`)

- [ ] **Step 1: Create `web/app/history/page.tsx`**

This is the current contents of `web/app/page.tsx`, rewritten to render inside `AppShell` and without its own header (the AppShell provides it). The `Row` helper + trajectory-fetch code is preserved verbatim; only the wrapping changes.

```tsx
import Link from "next/link";
import {
  getFacets,
  listTrajectories,
  type TrajectorySummary,
} from "@/lib/api";
import { ClientTime } from "@/components/client-time";
import { FilterBar } from "@/components/filter-bar";
import { tagSwatch } from "@/lib/colors";
import { fmtDuration } from "@/lib/format";
import { AppShell } from "@/components/shell/app-shell";
import { ContextSidebar, CtxHeader, CtxItem } from "@/components/shell/context-sidebar";
import { Chip } from "@/components/ui/chip";

export const dynamic = "force-dynamic";

function Row({ t }: { t: TrajectorySummary }) {
  const swatch = tagSwatch(t.status_tag);
  return (
    <Link
      href={`/t/${t.id}`}
      className="block border-b border-[color:var(--border)] px-4 py-3 hover:bg-linen/[0.03] transition-colors"
    >
      <div className="flex items-center gap-3">
        <span className="font-mono text-xs text-twilight w-28 truncate">
          {t.id.slice(0, 8)}…
        </span>
        <span className="text-sm flex-1 truncate">
          {t.name ?? <em className="text-twilight">(unnamed)</em>}
        </span>
        <span
          className="text-[10px] font-mono uppercase tracking-wider border rounded px-1.5 py-0.5"
          style={{
            color: t.status_tag ? swatch.fg : "var(--muted)",
            background: t.status_tag ? swatch.bg : "transparent",
            borderColor: t.status_tag ? swatch.border : "var(--border)",
          }}
        >
          {t.status_tag ?? "—"}
        </span>
        <span className="text-xs text-twilight w-32 text-right truncate">
          {t.service_name}
          {t.environment ? ` · ${t.environment}` : ""}
        </span>
        <span className="text-xs text-twilight w-20 text-right tabular-nums">
          {t.step_count} step{t.step_count === 1 ? "" : "s"}
        </span>
        <span className="text-xs text-twilight w-20 text-right tabular-nums">
          {t.token_count.toLocaleString()}t
        </span>
        <span className="text-xs text-twilight w-16 text-right tabular-nums">
          {fmtDuration(t.duration_ms)}
        </span>
        <span className="text-xs text-twilight w-36 text-right">
          <ClientTime iso={t.started_at} />
        </span>
      </div>
    </Link>
  );
}

export default async function History({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const params = await searchParams;

  let data;
  let facets;
  try {
    [data, facets] = await Promise.all([
      listTrajectories({
        limit: 100,
        tag: params.tag,
        service: params.service,
        environment: params.environment,
        q: params.q,
      }),
      getFacets(),
    ]);
  } catch (err) {
    return (
      <AppShell
        topBar={{
          breadcrumb: <span className="font-medium text-warm-fog">History</span>,
        }}
      >
        <div
          className="rounded border p-4 text-sm"
          style={{
            borderColor: "rgba(217,138,106,0.45)",
            background: "rgba(217,138,106,0.1)",
          }}
        >
          <p className="font-medium text-warn">Could not reach langperf-api</p>
          <p className="mt-1 text-patina font-mono text-xs">
            {err instanceof Error ? err.message : String(err)}
          </p>
        </div>
      </AppShell>
    );
  }

  const hasFilters = Object.values(params).some(Boolean);

  const sidebar = (
    <ContextSidebar>
      <CtxHeader>Saved patterns</CtxHeader>
      <CtxItem>(none yet — lands in Phase 4)</CtxItem>
      <CtxHeader>Quick filters</CtxHeader>
      <CtxItem>• flagged · 24h</CtxItem>
      <CtxItem>• errors only</CtxItem>
      <CtxItem>• new agents</CtxItem>
    </ContextSidebar>
  );

  return (
    <AppShell
      topBar={{
        breadcrumb: <span className="font-medium text-warm-fog">History</span>,
        right: (
          <>
            <Chip>
              {data.total} run{data.total === 1 ? "" : "s"}
              {hasFilters ? " (filtered)" : ""}
            </Chip>
            <Chip variant="primary">ingest ok</Chip>
          </>
        ),
      }}
      contextSidebar={sidebar}
    >
      <FilterBar facets={facets} />
      {data.items.length === 0 ? (
        <div className="p-10 text-sm text-patina">
          {hasFilters ? (
            <p>No runs match these filters.</p>
          ) : (
            <>
              <p>No runs yet.</p>
              <p className="mt-2">
                Send OTLP spans to{" "}
                <code className="font-mono text-aether-teal">
                  POST http://localhost:4318/v1/traces
                </code>{" "}
                — or run{" "}
                <code className="font-mono">
                  python scripts/seed_demo_data.py
                </code>
                .
              </p>
            </>
          )}
        </div>
      ) : (
        <div>
          {data.items.map((t) => (
            <Row key={t.id} t={t} />
          ))}
        </div>
      )}
    </AppShell>
  );
}
```

- [ ] **Step 2: Update `web/components/filter-bar.tsx` to push to `/history` instead of `/`**

In the `update` function (line 28), change:

```ts
startTransition(() => router.push(`/?${next.toString()}`));
```

to:

```ts
startTransition(() => router.push(`/history?${next.toString()}`));
```

And in the clear button (line 90):

```ts
startTransition(() => router.push("/"));
```

to:

```ts
startTransition(() => router.push("/history"));
```

- [ ] **Step 3: Type-check + browser verify**

```bash
cd web && npx tsc --noEmit
```

Then `docker compose restart langperf-web && open http://localhost:3000/history`
Expected: trajectory list renders, filters work, clicking a row opens `/t/[id]`.

- [ ] **Step 4: Commit**

```bash
cd /Users/andrewlavoie/code/langperf
git add web/app/history/page.tsx web/components/filter-bar.tsx
git commit -m "web: relocate trajectory list to /history under AppShell"
```

---

### Task 10: Replace `/` with Dashboard placeholder

**Files:**
- Modify: `web/app/page.tsx` (full replacement)

- [ ] **Step 1: Replace the entire file**

```tsx
import Link from "next/link";
import { AppShell } from "@/components/shell/app-shell";
import { ContextSidebar, CtxHeader, CtxItem } from "@/components/shell/context-sidebar";
import { Chip } from "@/components/ui/chip";

export const dynamic = "force-dynamic";

function KpiTile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="border border-[color:var(--border)] rounded-[3px] bg-[color:var(--surface)] p-[10px]">
      <div className="font-mono text-[9px] text-patina uppercase tracking-[0.1em] mb-[6px]">
        {label}
      </div>
      <div className="font-mono text-[20px] text-warm-fog tracking-[-0.02em]">{value}</div>
      {sub ? (
        <div className="font-mono text-[10px] text-patina mt-[3px]">{sub}</div>
      ) : null}
    </div>
  );
}

export default function Dashboard() {
  const sidebar = (
    <ContextSidebar>
      <CtxHeader>Pinned agents</CtxHeader>
      <CtxItem>(lands in Phase 2)</CtxItem>
      <CtxHeader>Saved views</CtxHeader>
      <CtxItem>(lands in Phase 2)</CtxItem>
    </ContextSidebar>
  );

  return (
    <AppShell
      topBar={{
        breadcrumb: <span className="font-medium text-warm-fog">Dashboard</span>,
        right: <Chip variant="primary">ingest ok</Chip>,
      }}
      contextSidebar={sidebar}
    >
      <div className="grid grid-cols-5 gap-[8px] mb-[10px]">
        <KpiTile label="runs · 7d" value="—" sub="wait for Phase 2" />
        <KpiTile label="agents" value="—" sub="wait for Phase 2" />
        <KpiTile label="error rate" value="—" />
        <KpiTile label="p95 latency" value="—" />
        <KpiTile label="flagged" value="—" />
      </div>

      <div className="border border-[color:var(--border)] border-l-2 border-l-peach-neon rounded-[3px] bg-[color:var(--surface)] p-[14px]">
        <div className="font-mono text-[9px] text-peach-neon uppercase tracking-[0.1em] mb-[4px]">
          phase 1 · the shell is ready
        </div>
        <div className="text-[13px] text-warm-fog mb-[4px]">
          Charts, agent grid, top tools, heatmap, and flagged runs arrive in Phase 2
          (first-class Agent data model).
        </div>
        <div className="text-[11px] text-patina leading-[1.5]">
          Meanwhile the existing trajectory list is available at{" "}
          <Link href="/history" className="text-aether-teal hover:underline">
            /history
          </Link>
          . OTLP ingestion at{" "}
          <code className="font-mono text-aether-teal">POST /v1/traces</code> is unchanged.
        </div>
      </div>
    </AppShell>
  );
}
```

- [ ] **Step 2: Type-check + browser verify**

```bash
cd web && npx tsc --noEmit
```

Open `http://localhost:3000/` — expected: dashboard placeholder with 5 dashed KPI tiles and a peach-accented phase-1 notice card linking to `/history`.

- [ ] **Step 3: Commit**

```bash
cd /Users/andrewlavoie/code/langperf
git add web/app/page.tsx
git commit -m "web: replace / with Dashboard placeholder (Phase 2 will fill it)"
```

---

### Task 11: `/agents` index placeholder

**Files:**
- Create: `web/app/agents/page.tsx`

- [ ] **Step 1: Create the file**

```tsx
import { AppShell } from "@/components/shell/app-shell";
import { ContextSidebar, CtxHeader, CtxItem } from "@/components/shell/context-sidebar";
import { Chip } from "@/components/ui/chip";

export default function AgentsIndex() {
  const sidebar = (
    <ContextSidebar>
      <CtxHeader action="+ new">Agents</CtxHeader>
      <CtxItem>(lands in Phase 2)</CtxItem>
    </ContextSidebar>
  );

  return (
    <AppShell
      topBar={{
        breadcrumb: <span className="font-medium text-warm-fog">Agents</span>,
        right: <Chip>env: all</Chip>,
      }}
      contextSidebar={sidebar}
    >
      <div className="border border-[color:var(--border)] border-l-2 border-l-peach-neon rounded-[3px] bg-[color:var(--surface)] p-[14px]">
        <div className="font-mono text-[9px] text-peach-neon uppercase tracking-[0.1em] mb-[4px]">
          phase 2
        </div>
        <div className="text-[13px] text-warm-fog mb-[4px]">
          Agents become a first-class entity in Phase 2. The SDK will auto-detect each
          agent from its source signature (git origin + init call site), and this page
          will list every agent with live metrics.
        </div>
        <div className="text-[11px] text-patina leading-[1.5]">
          Until then, agent metadata is effectively <code className="font-mono text-aether-teal">service_name</code> on
          each run — visible on the History table.
        </div>
      </div>
    </AppShell>
  );
}
```

- [ ] **Step 2: Type-check + commit**

```bash
cd web && npx tsc --noEmit
cd /Users/andrewlavoie/code/langperf
git add web/app/agents/page.tsx
git commit -m "web: /agents index placeholder (Phase 2 fills it)"
```

---

### Task 12: `/agents/[name]` redirect + `/agents/[name]/[tab]` shell

**Files:**
- Create: `web/app/agents/[name]/page.tsx`
- Create: `web/app/agents/[name]/[tab]/page.tsx`

- [ ] **Step 1: Create `web/app/agents/[name]/page.tsx` (redirects to /overview tab)**

```tsx
import { redirect } from "next/navigation";

export default async function AgentRoot({
  params,
}: {
  params: Promise<{ name: string }>;
}) {
  const { name } = await params;
  redirect(`/agents/${encodeURIComponent(name)}/overview`);
}
```

- [ ] **Step 2: Create `web/app/agents/[name]/[tab]/page.tsx` (tab shell + identity strip placeholder)**

```tsx
import Link from "next/link";
import { notFound } from "next/navigation";
import { AppShell } from "@/components/shell/app-shell";
import { ContextSidebar, CtxHeader, CtxItem } from "@/components/shell/context-sidebar";
import { Chip } from "@/components/ui/chip";

const TABS = ["overview", "runs", "prompt", "tools", "versions", "config"] as const;
type Tab = (typeof TABS)[number];

export default async function AgentTab({
  params,
}: {
  params: Promise<{ name: string; tab: string }>;
}) {
  const { name, tab } = await params;
  if (!TABS.includes(tab as Tab)) notFound();

  const breadcrumb = (
    <>
      <Link href="/agents" className="hover:text-warm-fog">Agents</Link>
      <span className="mx-[6px] text-[color:var(--border-strong)]">›</span>
      <span className="font-medium text-warm-fog">{name}</span>
    </>
  );

  const sidebar = (
    <ContextSidebar>
      <CtxHeader>Versions</CtxHeader>
      <CtxItem>(Phase 2)</CtxItem>
      <CtxHeader>Environments</CtxHeader>
      <CtxItem>(Phase 2)</CtxItem>
      <CtxHeader>Saved filters</CtxHeader>
      <CtxItem>(Phase 2)</CtxItem>
    </ContextSidebar>
  );

  return (
    <AppShell
      topBar={{
        breadcrumb,
        right: <Chip>env: all</Chip>,
      }}
      contextSidebar={sidebar}
    >
      {/* Identity strip — Phase 2 populates real version/env/live KPIs */}
      <div className="flex items-center gap-2 px-[14px] py-[9px] -mx-[14px] -mt-[14px] mb-[14px] border-b border-[color:var(--border)] bg-gradient-to-b from-[color:var(--surface-2)] to-[color:var(--background)]">
        <span className="font-mono text-[9px] text-patina uppercase tracking-[0.1em] mr-[2px]">Agent</span>
        <Chip>{name}</Chip>
        <span className="font-mono text-[9px] text-patina uppercase tracking-[0.1em] mx-[2px] ml-[6px]">Ver</span>
        <Chip>—</Chip>
        <span className="font-mono text-[9px] text-patina uppercase tracking-[0.1em] mx-[2px] ml-[6px]">Env</span>
        <Chip>—</Chip>
        <div className="flex-1" />
        <span className="font-mono text-[10px] text-patina">live KPIs arrive in Phase 2</span>
      </div>

      {/* Tab nav */}
      <div className="flex gap-[20px] border-b border-[color:var(--border)] -mx-[14px] px-[14px] mb-[14px]">
        {TABS.map((t) => {
          const active = t === tab;
          return (
            <Link
              key={t}
              href={`/agents/${encodeURIComponent(name)}/${t}`}
              className={`py-[10px] text-[12px] -mb-px border-b-2 ${
                active
                  ? "text-warm-fog border-b-aether-teal"
                  : "text-patina border-b-transparent hover:text-warm-fog"
              }`}
            >
              <span className="capitalize">{t}</span>
            </Link>
          );
        })}
      </div>

      <div className="border border-[color:var(--border)] border-l-2 border-l-peach-neon rounded-[3px] bg-[color:var(--surface)] p-[14px]">
        <div className="font-mono text-[9px] text-peach-neon uppercase tracking-[0.1em] mb-[4px]">
          phase 2 · {tab}
        </div>
        <div className="text-[13px] text-warm-fog">
          This tab's content lands once first-class Agents ship in Phase 2.
          Overview gets KPIs + charts + recent runs. Runs becomes an agent-scoped
          run table. Prompt / Tools / Versions / Config land in follow-up specs.
        </div>
      </div>
    </AppShell>
  );
}
```

- [ ] **Step 3: Type-check + browser verify**

```bash
cd web && npx tsc --noEmit
```

Open `http://localhost:3000/agents/support-refund-bot` — expected: redirects to `/agents/support-refund-bot/overview`, shows breadcrumb, identity strip with placeholder version/env, tab nav with Overview highlighted.

Open `http://localhost:3000/agents/support-refund-bot/prompt` — expected: same shell, Prompt tab highlighted.

Open `http://localhost:3000/agents/support-refund-bot/bogus` — expected: Next.js 404.

- [ ] **Step 4: Commit**

```bash
cd /Users/andrewlavoie/code/langperf
git add web/app/agents/[name]/page.tsx web/app/agents/[name]/[tab]/page.tsx
git commit -m "web: agent detail shell with tab nav + identity strip (placeholder)"
```

---

### Task 13: `/logs` placeholder

**Files:**
- Create: `web/app/logs/page.tsx`

- [ ] **Step 1: Create the file**

```tsx
import { AppShell } from "@/components/shell/app-shell";
import { ContextSidebar, CtxHeader, CtxItem } from "@/components/shell/context-sidebar";
import { Chip } from "@/components/ui/chip";

export default function Logs() {
  const sidebar = (
    <ContextSidebar>
      <CtxHeader>Sources</CtxHeader>
      <CtxItem>● api-server</CtxItem>
      <CtxItem>● ingest</CtxItem>
      <CtxItem>● otel-collector</CtxItem>
      <CtxItem>● web</CtxItem>
      <CtxHeader>Levels</CtxHeader>
      <CtxItem>INFO · WARN · ERROR</CtxItem>
      <CtxHeader>Forwarding</CtxHeader>
      <CtxItem>(configure in Settings)</CtxItem>
    </ContextSidebar>
  );

  return (
    <AppShell
      topBar={{
        breadcrumb: <span className="font-medium text-warm-fog">Logs</span>,
        right: <Chip>env: all</Chip>,
      }}
      contextSidebar={sidebar}
    >
      <div className="border border-[color:var(--border)] border-l-2 border-l-peach-neon rounded-[3px] bg-[color:var(--surface)] p-[14px]">
        <div className="font-mono text-[9px] text-peach-neon uppercase tracking-[0.1em] mb-[4px]">
          phase 5
        </div>
        <div className="text-[13px] text-warm-fog">
          Real-time server log stream (SSE) with source + level filters lands in Phase 5,
          together with Settings → Log forwarding.
        </div>
      </div>
    </AppShell>
  );
}
```

- [ ] **Step 2: Type-check + commit**

```bash
cd web && npx tsc --noEmit
cd /Users/andrewlavoie/code/langperf
git add web/app/logs/page.tsx
git commit -m "web: /logs placeholder (Phase 5)"
```

---

### Task 14: `/settings` redirect + `/settings/[section]` shell

**Files:**
- Create: `web/app/settings/page.tsx`
- Create: `web/app/settings/[section]/page.tsx`

- [ ] **Step 1: Create `web/app/settings/page.tsx` (redirects to log-forwarding)**

```tsx
import { redirect } from "next/navigation";

export default function SettingsRoot() {
  redirect("/settings/log-forwarding");
}
```

- [ ] **Step 2: Create `web/app/settings/[section]/page.tsx` (section nav + placeholder)**

```tsx
import Link from "next/link";
import { notFound } from "next/navigation";
import { AppShell } from "@/components/shell/app-shell";
import { ContextSidebar } from "@/components/shell/context-sidebar";
import { SETTINGS_SECTIONS } from "@/components/shell/nav-config";

export default async function SettingsSection({
  params,
}: {
  params: Promise<{ section: string }>;
}) {
  const { section } = await params;
  const item = SETTINGS_SECTIONS.find((s) => s.id === section);
  if (!item || item.v2) notFound();

  const groups: Array<{ key: string; label: string }> = [
    { key: "workspace", label: "Workspace" },
    { key: "observability", label: "Observability" },
    { key: "integrations", label: "Integrations" },
    { key: "later", label: "Later" },
  ];

  const sidebar = (
    <ContextSidebar>
      {groups.map((g) => (
        <div key={g.key} className="mb-[6px]">
          <div className="px-[6px] pt-[10px] pb-[4px] font-mono text-[9px] text-patina uppercase tracking-[0.1em]">
            {g.label}
          </div>
          {SETTINGS_SECTIONS.filter((s) => s.group === g.key).map((s) => {
            const active = s.id === section;
            if (s.v2) {
              return (
                <div
                  key={s.id}
                  className="px-[10px] py-[6px] text-[12px] text-patina opacity-55 cursor-not-allowed"
                  title="v2 · coming soon"
                  aria-disabled
                >
                  {s.label}
                </div>
              );
            }
            return (
              <Link
                key={s.id}
                href={s.href}
                className={`block px-[10px] py-[6px] text-[12px] rounded-[2px] ${
                  active
                    ? "bg-[color:rgba(107,186,177,0.07)] text-warm-fog border-l-2 border-l-aether-teal pl-[8px]"
                    : "text-patina hover:text-warm-fog"
                }`}
              >
                {s.label}
              </Link>
            );
          })}
        </div>
      ))}
    </ContextSidebar>
  );

  const breadcrumb = (
    <>
      <span className="font-medium text-warm-fog">Settings</span>
      <span className="mx-[6px] text-[color:var(--border-strong)]">›</span>
      <span>{item.label}</span>
    </>
  );

  const phaseHint: Record<string, string> = {
    "log-forwarding": "Phase 5 — Datadog / Grafana Loki / Generic OTLP / Local file targets.",
    "trace-export": "Phase 5 — what gets forwarded: server logs, trace events, full payloads, SDK diagnostics.",
    "profile": "Phase 2+ — single-user placeholder in v1.",
    "environments": "Phase 2 — rename and order your dev/staging/prod environments.",
    "agents-review": "Phase 2 — queue of auto-detected agents needing human review.",
    "sdk-keys": "Follow-up — SDK key rotation for authenticated ingest.",
    "webhooks": "Follow-up — outbound webhooks on run events.",
  };

  return (
    <AppShell
      topBar={{ breadcrumb }}
      contextSidebar={sidebar}
    >
      <div className="max-w-[760px]">
        <h1 className="text-[15px] text-warm-fog font-medium mb-[4px]">{item.label}</h1>
        <div className="font-mono text-[10px] text-patina mb-[16px]">
          {phaseHint[section] ?? "Placeholder."}
        </div>
        <div className="border border-[color:var(--border)] border-l-2 border-l-peach-neon rounded-[3px] bg-[color:var(--surface)] p-[14px]">
          <div className="font-mono text-[9px] text-peach-neon uppercase tracking-[0.1em] mb-[4px]">
            placeholder
          </div>
          <div className="text-[13px] text-warm-fog">
            The settings section nav is live. Section content lands with the phase noted above.
          </div>
        </div>
      </div>
    </AppShell>
  );
}
```

- [ ] **Step 3: Type-check + browser verify**

```bash
cd web && npx tsc --noEmit
```

Open `http://localhost:3000/settings` — expected: redirects to `/settings/log-forwarding`.
Open `http://localhost:3000/settings/billing` — expected: 404 (it's v2).
Click each non-v2 section in the sidebar — expected: URL updates, active state moves.

- [ ] **Step 4: Commit**

```bash
cd /Users/andrewlavoie/code/langperf
git add web/app/settings/page.tsx web/app/settings/[section]/page.tsx
git commit -m "web: /settings shell with section nav + placeholder content"
```

---

### Task 15: `/r/[run_id]` redirect to canonical trajectory URL

**Files:**
- Create: `web/app/r/[run_id]/page.tsx`

- [ ] **Step 1: Create the file**

```tsx
import { redirect } from "next/navigation";

/**
 * Stable short-form permalink for a run. In Phase 1, runs still live under
 * /t/<id>; Phase 2 rehomes them under /agents/<name>/runs/<id> and this
 * redirect will change correspondingly. External consumers (Slack links,
 * export CSVs) should always use /r/<id>.
 */
export default async function RunPermalink({
  params,
}: {
  params: Promise<{ run_id: string }>;
}) {
  const { run_id } = await params;
  redirect(`/t/${encodeURIComponent(run_id)}`);
}
```

- [ ] **Step 2: Type-check + browser verify**

```bash
cd web && npx tsc --noEmit
```

Open `http://localhost:3000/r/<any-existing-trajectory-id>` — expected: redirects to `/t/<id>`, renders the trajectory detail.

- [ ] **Step 3: Commit**

```bash
cd /Users/andrewlavoie/code/langperf
git add web/app/r/[run_id]/page.tsx
git commit -m "web: /r/<id> permalink → /t/<id> redirect (canonical in Phase 1)"
```

---

### Task 16: Wrap `/t/[id]` in `AppShell` with breadcrumb + identity strip

**Files:**
- Read: `web/app/t/[id]/page.tsx` (current contents — preserved in full below)
- Modify: `web/app/t/[id]/page.tsx`

- [ ] **Step 1: Read the current file to know what you're preserving**

```bash
cat /Users/andrewlavoie/code/langperf/web/app/t/[id]/page.tsx
```

Capture the full contents. The body typically fetches the trajectory, renders `<TrajectoryView>`, and handles errors.

- [ ] **Step 2: Rewrite the file wrapping its current contents with `AppShell`**

Replace the file with the template below. Any existing fetch / TrajectoryView logic goes inside the marked region (keep it verbatim — do not simplify).

```tsx
import Link from "next/link";
import { notFound } from "next/navigation";
import { getTrajectory } from "@/lib/api";
import { TrajectoryView } from "@/components/trajectory-view";
import { AppShell } from "@/components/shell/app-shell";
import { Chip } from "@/components/ui/chip";

export const dynamic = "force-dynamic";

export default async function TrajectoryPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let trajectory;
  try {
    trajectory = await getTrajectory(id);
  } catch {
    notFound();
  }

  const serviceLabel = trajectory.service_name;
  const envLabel = trajectory.environment ?? "—";

  const breadcrumb = (
    <>
      <Link href="/history" className="hover:text-warm-fog">History</Link>
      <span className="mx-[6px] text-[color:var(--border-strong)]">›</span>
      <span className="font-mono text-[11px] text-warm-fog">{id.slice(0, 8)}</span>
    </>
  );

  return (
    <AppShell
      topBar={{
        breadcrumb,
        right: <Chip>env: {envLabel}</Chip>,
      }}
    >
      {/* Identity strip — Phase 1 fills it from service_name/environment since
          Agents aren't first-class yet. Phase 2 swaps to real agent+version. */}
      <div className="flex items-center gap-2 px-[14px] py-[9px] -mx-[14px] -mt-[14px] mb-[14px] border-b border-[color:var(--border)] bg-gradient-to-b from-[color:var(--surface-2)] to-[color:var(--background)]">
        <span className="font-mono text-[9px] text-patina uppercase tracking-[0.1em] mr-[2px]">Service</span>
        <Chip>{serviceLabel}</Chip>
        <span className="font-mono text-[9px] text-patina uppercase tracking-[0.1em] mx-[2px] ml-[6px]">Env</span>
        <Chip>{envLabel}</Chip>
        <span className="font-mono text-[9px] text-patina uppercase tracking-[0.1em] mx-[2px] ml-[6px]">Run</span>
        <Chip>{id.slice(0, 8)}</Chip>
        <div className="flex-1" />
        <span className="font-mono text-[10px] text-patina">
          {trajectory.step_count} steps · {trajectory.token_count.toLocaleString()}t
        </span>
      </div>

      {/* ============================================================ */}
      {/* Preserved from the previous /t/[id] page — do not simplify.  */}
      {/* TrajectoryView is the existing graph/tree/right-panel layout.*/}
      {/* ============================================================ */}
      <TrajectoryView trajectory={trajectory} />
    </AppShell>
  );
}
```

**Important:** The `<TrajectoryView>` component is imported from `@/components/trajectory-view`. If the current `/t/[id]/page.tsx` does something different (inlines the view, uses different props, fetches more data), preserve that — wrap the existing JSX inside the `<AppShell>…</AppShell>` instead of swapping it out. The goal is ONLY to add the shell + identity strip; the detail view internals stay unchanged.

- [ ] **Step 3: Type-check + browser verify**

```bash
cd web && npx tsc --noEmit
```

Open `http://localhost:3000/history`, click any run → `/t/<id>` loads, shell chrome (rail + top bar) visible, identity strip with service + env + short run id shows, and the trajectory graph/tree/detail panel renders normally underneath.

- [ ] **Step 4: Commit**

```bash
cd /Users/andrewlavoie/code/langperf
git add web/app/t/[id]/page.tsx
git commit -m "web: wrap trajectory detail in AppShell with breadcrumb + identity strip"
```

---

### Task 17: Final sweep — delete dead code, full build, screenshot pass

**Files:**
- Verify: all pages render without console errors
- Verify: existing trajectory detail still functions (graph loads, tree collapses, tags / notes save)

- [ ] **Step 1: Full build**

```bash
cd /Users/andrewlavoie/code/langperf/web
npx next build
```

Expected: build succeeds with no errors. Warnings about unused imports are fine to ignore but if any appear in code you just wrote, clean them up.

- [ ] **Step 2: Full route walk**

With `docker compose up` running, open each of these and confirm the shell chrome (rail + top bar) is present, the active rail item is correct, and the page renders its placeholder card or real content:

- `/` — Dashboard placeholder, HOME rail active
- `/agents` — Agents index placeholder, AGENTS rail active
- `/agents/foo` → redirects to `/agents/foo/overview`, tab shell renders
- `/agents/foo/runs` — same shell, Runs tab active
- `/agents/foo/bogus` — 404
- `/history` — trajectory list with FilterBar, HISTORY rail active
- `/history?tag=bad` — filter works, URL updates via FilterBar
- `/logs` — placeholder, LOGS rail active
- `/settings` — redirects to `/settings/log-forwarding`
- `/settings/log-forwarding` — placeholder, CONFIG rail active
- `/settings/billing` — 404 (v2 section)
- `/r/<existing-run-id>` — redirects to `/t/<id>`
- `/t/<existing-run-id>` — shell + identity strip + trajectory view, clicking breadcrumb goes to `/history`

- [ ] **Step 3: Verify v2 rail items are non-clickable**

Hover the Triage / Evals / Data rail items: cursor stays default, tooltip shows "v2 · coming soon", clicking does nothing.

- [ ] **Step 4: Confirm palette is uniform**

No stray purple, no stray dark indigo (`#1F2035`), no stray marigold (`#E5B754`) anywhere. Spot-check the trajectory graph view — it should now render in teal/peach instead of violet/marigold (the DRIFT alias repointing handles this automatically).

- [ ] **Step 5: Clean up any leftover drift-signal notes in globals.css**

Check `web/app/globals.css` for any stale comments referencing "Drift Signal":

```bash
grep -n "Drift Signal\|Midnight\|Deep Indigo\|Drift Violet" /Users/andrewlavoie/code/langperf/web/app/globals.css
```

Expected: only the new "Aether Dusk" header comment appears. If the old names persist anywhere, update.

- [ ] **Step 6: Commit final verification notes, if any**

If any cleanup happened in step 5:

```bash
cd /Users/andrewlavoie/code/langperf
git add web/app/globals.css
git commit -m "web: clean up leftover Drift Signal references in globals.css"
```

If no cleanup was needed, skip this step.

- [ ] **Step 7: Push branch and open PR (if following the normal workflow)**

Not required by this plan — leave to the usual branch strategy. Phase 1 is complete when all preceding tasks are committed.

---

## Self-Review (checklist for the plan author, not the engineer)

**Spec coverage** — mapping against `docs/superpowers/specs/2026-04-17-ui-shell-and-agent-first-class-design.md`:

| Spec section | Covered by |
|---|---|
| §3 Aether Dusk palette | Task 1 |
| §5 Nav shell — top bar / icon rail / context sidebar | Tasks 5, 6, 7, 8 |
| §5 V2 rail items disabled | Task 6 (via `nav-config.ts` + IconRail rendering) |
| §5 Identity strip on agent + run pages | Tasks 12 (agent detail) & 16 (run detail) |
| §6.1 Dashboard placeholder | Task 10 |
| §6.2 Agents index placeholder | Task 11 |
| §6.3 Agent detail with tab nav | Task 12 |
| §6.4 Run detail rehomed under shell | Task 16 |
| §6.5 History | Task 9 |
| §6.6 Logs placeholder | Task 13 |
| §6.7 Settings with section nav | Task 14 |
| §7 V2 placeholder treatment | Tasks 10, 11, 12, 13, 14 (peach left-border cards) |
| §11 Phase 1 scope | Entire plan |

**Explicitly deferred to later plans (Phase 2+):**
- First-class Agent data model (tables, SDK signature capture, ingest upsert, backfill)
- Dashboard / agent-detail real content
- History fuzzy pattern parser
- Logs SSE stream + Settings log-forwarding targets
- Run detail URL move from `/t/<id>` → `/agents/<name>/runs/<run_id>` (Phase 1 keeps `/t/<id>` canonical with `/r/<id>` redirect)

**Type consistency** — property and method names used across tasks:
- `RailItem`, `SettingsSection`, `RAIL_ITEMS`, `SETTINGS_SECTIONS` from `nav-config.ts` — referenced identically in Tasks 6 and 14.
- `AppShellProps { topBar, contextSidebar, children }` — consumed identically in Tasks 9, 10, 11, 12, 13, 14, 16.
- `ContextSidebar` + `CtxHeader` + `CtxItem` — consumed identically in all page tasks.
- `Chip { variant? }` with variants `default | primary | accent | warn | on` — consumed identically.

**Placeholder scan** — no "TBD", "TODO", or "similar to Task N" in any task's code blocks. Every code block is complete and self-contained. Placeholder PAGES exist (that's the point of Phase 1), but each placeholder is fully written out with its marker explaining which phase fills it.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-17-phase-1-ui-shell-foundations.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — I execute the tasks in this session using `executing-plans`, with a checkpoint after each major group (palette → shell → routes → verify).

Which approach?
