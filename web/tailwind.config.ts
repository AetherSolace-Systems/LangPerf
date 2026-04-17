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
