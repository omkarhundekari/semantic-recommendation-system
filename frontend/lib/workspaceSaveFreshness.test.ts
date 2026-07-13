import {
  describe,
  expect,
  it,
} from "vitest";

import {
  formatWorkspaceSaveFreshness,
} from "./workspaceSaveFreshness";

describe("formatWorkspaceSaveFreshness", () => {
  const now = new Date("2026-07-13T00:15:00.000Z");

  it("returns no status without a valid save time", () => {
    expect(
      formatWorkspaceSaveFreshness(null, now),
    ).toBeNull();

    expect(
      formatWorkspaceSaveFreshness("not-a-date", now),
    ).toBeNull();
  });

  it("describes saves from the last minute as just now", () => {
    expect(
      formatWorkspaceSaveFreshness(
        "2026-07-13T00:14:30.000Z",
        now,
      )?.label,
    ).toBe("Saved just now");
  });

  it("reports recent saves in whole minutes", () => {
    expect(
      formatWorkspaceSaveFreshness(
        "2026-07-13T00:12:00.000Z",
        now,
      )?.label,
    ).toBe("Saved 3 min ago");
  });

  it("uses the exact clock time for older saves", () => {
    const savedAt = "2026-07-12T18:00:00.000Z";
    const expectedTime = new Intl.DateTimeFormat(undefined, {
      hour: "numeric",
      minute: "2-digit",
    }).format(new Date(savedAt));

    expect(
      formatWorkspaceSaveFreshness(savedAt, now)?.label,
    ).toBe(`Saved at ${expectedTime}`);
  });

  it("includes an exact timestamp for the tooltip", () => {
    const result = formatWorkspaceSaveFreshness(
      "2026-07-13T00:12:00.000Z",
      now,
    );

    expect(result?.exactTimestamp).toBeTruthy();
  });
});
