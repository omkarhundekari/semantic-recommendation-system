// @vitest-environment jsdom

import {
  render,
  screen,
} from "@testing-library/react";
import {
  describe,
  expect,
  it,
} from "vitest";

import ExperienceLab from "./page";


describe("Solvyn experience lab", () => {
  it("keeps the first experience focused and progressively disclosed", () => {
    render(<ExperienceLab />);

    expect(
      screen.getByRole("heading", {
        name: "Build with conviction.",
      }),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("link", {
        name: /start building/i,
      }),
    ).toHaveAttribute(
      "href",
      "/ui-lab/login",
    );

    expect(
      screen.queryByText("ACTIVE MISSION"),
    ).not.toBeInTheDocument();

    expect(
      screen.queryByText("SIGNAL ARRAY"),
    ).not.toBeInTheDocument();

    expect(
      screen.queryByText("CURRENT DECISION"),
    ).not.toBeInTheDocument();
  });
});
