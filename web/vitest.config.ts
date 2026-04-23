import { defineConfig } from "vitest/config";
import path from "node:path";

export default defineConfig({
  test: {
    include: ["tests/unit/**/*.{test,spec}.{ts,tsx}"],
    environment: "jsdom",
    // Playwright specs live in tests/*.spec.ts at the tests/ root — don't double-run them.
    exclude: ["tests/*.spec.ts", "node_modules/**", ".next/**"],
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
});
