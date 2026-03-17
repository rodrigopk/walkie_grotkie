import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import HelpView from "../components/HelpView";

describe("HelpView", () => {
  it("renders the help-view container", () => {
    render(<HelpView />);
    expect(screen.getByTestId("help-view")).toBeInTheDocument();
  });

  it("renders the screen title header", () => {
    render(<HelpView />);
    expect(screen.getByTestId("screen-title")).toBeInTheDocument();
  });

  it("screen title reads 'Help'", () => {
    render(<HelpView />);
    expect(screen.getByTestId("screen-title")).toHaveTextContent("Help");
  });

  it("renders all 7 help entries", () => {
    render(<HelpView />);
    expect(screen.getAllByTestId("help-row")).toHaveLength(7);
  });

  it("contains an entry for turning off the app", () => {
    render(<HelpView />);
    expect(screen.getByText("Turn off the app")).toBeInTheDocument();
  });

  it("contains an entry for the home screen", () => {
    render(<HelpView />);
    expect(screen.getByText("Home / chat screen")).toBeInTheDocument();
  });

  it("contains an entry for picking animations", () => {
    render(<HelpView />);
    expect(screen.getByText("Pick Grot animation")).toBeInTheDocument();
  });

  it("contains an entry for settings", () => {
    render(<HelpView />);
    expect(screen.getByText("Settings (API key)")).toBeInTheDocument();
  });

  it("contains an entry for restarting the session", () => {
    render(<HelpView />);
    expect(screen.getByText("Restart session")).toBeInTheDocument();
  });

  it("contains an entry for the help screen itself", () => {
    render(<HelpView />);
    expect(screen.getByText("This help screen")).toBeInTheDocument();
  });

  it("contains an entry for changing the voice", () => {
    render(<HelpView />);
    expect(screen.getByText("Change Grot's voice")).toBeInTheDocument();
  });

  it("each row has a help-icon span", () => {
    render(<HelpView />);
    const rows = screen.getAllByTestId("help-row");
    for (const row of rows) {
      expect(row.querySelector(".help-icon")).not.toBeNull();
    }
  });
});
