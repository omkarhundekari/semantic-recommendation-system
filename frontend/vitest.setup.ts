import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

if (typeof Element !== "undefined") {
  Object.defineProperty(Element.prototype, "scrollIntoView", {
    configurable: true,
    value: vi.fn(),
  });
}

afterEach(() => {
  if (typeof document !== "undefined") {
    cleanup();
  }

  if (typeof window !== "undefined") {
    window.localStorage.clear();
  }
});
