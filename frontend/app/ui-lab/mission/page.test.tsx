// @vitest-environment jsdom

import {
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import {
  describe,
  expect,
  it,
} from "vitest";

import MissionStartPage from "./page";


describe("Solvyn mission start", () => {
  it("starts from intent instead of exposing the full workspace", () => {
    render(<MissionStartPage />);

    expect(
      screen.getByRole("heading", {
        name: /what do you want to build/i,
      }),
    ).toBeInTheDocument();

    expect(
      screen.queryByText("Evidence"),
    ).not.toBeInTheDocument();

    expect(
      screen.queryByText("Build Passport"),
    ).not.toBeInTheDocument();
  });

  it("lets an example become the current mission intent", () => {
    render(<MissionStartPage />);

    fireEvent.click(
      screen.getByRole("button", {
        name: /build an ai project for an ml engineer role/i,
      }),
    );

    expect(
      screen.getByRole("textbox"),
    ).toHaveValue(
      "Build an AI project for an ML engineer role",
    );
  });
});
