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
  exact?: boolean;    // true ⇒ only activate on exact pathname match
  group?: "primary" | "later" | "footer";
};

export const RAIL_ITEMS: RailItem[] = [
  { id: "home",     label: "home",    glyph: "□", href: "/",          group: "primary" },
  { id: "agents",   label: "agents",  glyph: "◇", href: "/agents",    group: "primary" },
  { id: "history",  label: "history", glyph: "≡", href: "/history",   group: "primary" },
  { id: "logs",     label: "logs",    glyph: "⌘", href: "/logs",      group: "primary" },
  { id: "queue",    label: "queue",    glyph: "≔", href: "/queue",      exact: true, group: "later" },
  { id: "clusters", label: "clusters", glyph: "⬡", href: "/queue/clusters", group: "later" },
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
