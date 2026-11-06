import path from "node:path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    include: ["src/**/*.test.ts", "workers/**/*.test.ts"],
    coverage: {
      provider: "v8",
      reporter: ["text"],
      include: ["src/**/*.ts"],
      exclude: ["src/**/migrations/**", "src/**/*.d.ts"],
      thresholds: {
        lines: 80,
        functions: 80,
        statements: 80,
        branches: 80,
      },
    },
  },
});
