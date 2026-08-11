import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";
import "@testing-library/jest-dom/vitest";

// Testing Library's auto-cleanup-after-each-test only self-registers under
// a globals-style runner (Jest, or Vitest with `test.globals: true`) — this
// project keeps explicit `import { describe, it } from "vitest"` instead of
// globals, so without this, each render() leaks into the next test's DOM.
afterEach(() => {
  cleanup();
});
