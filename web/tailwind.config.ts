import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        midnight: "#14141F",
        "deep-indigo": "#1F2035",
        "drift-violet": "#8B8CC7",
        marigold: "#E5B754",
        linen: "#EDE7DD",
        twilight: "#6E6F88",
        lagoon: "#5BB6C7",
        plum: "#C78BAD",
        coral: "#E58B54",
        sage: "#7BC89D",
      },
      fontFamily: {
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Monaco", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
