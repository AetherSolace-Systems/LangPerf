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
        // Reserved for model reasoning / "thinking" — a purpley cyber
        // accent that reads distinct from the teal/peach pair without
        // fighting the warm palette.
        "aether-violet": "#A78BFA",
        "peach-neon": "#E8A87C",
        "warm-fog": "#F2EAE2",
        patina: "#7A8B8E",
        warn: "#D98A6A",
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
