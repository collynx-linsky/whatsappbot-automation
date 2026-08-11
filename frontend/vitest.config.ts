import react from "@vitejs/plugin-react";
import path from "node:path";
import { defineConfig } from "vitest/config";

// Component/unit tests only — fast, no real browser or backend, mocked
// API calls where a page needs one. Real end-to-end coverage (a real
// browser against the real running app + backend) lives in playwright.config.ts
// instead; see docs/testing.md for which layer covers what.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    include: ["**/*.test.{ts,tsx}"],
    exclude: ["node_modules", ".next", "e2e"],
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
});
