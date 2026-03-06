import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import StatusScreen from "../components/StatusScreen";

describe("StatusScreen", () => {
  it("renders the gif with correct src and alt", () => {
    render(
      <StatusScreen
        gifSrc="/grot-spin.gif"
        gifAlt="Grot waking up"
        lines={[{ text: "Loading..." }]}
      />
    );
    const img = screen.getByAltText("Grot waking up");
    expect(img).toHaveAttribute("src", "/grot-spin.gif");
  });

  it("renders a single caption line", () => {
    render(
      <StatusScreen
        gifSrc="/grot-spin.gif"
        gifAlt="Validating"
        lines={[{ text: "Validating API key..." }]}
      />
    );
    expect(screen.getByText("Validating API key...")).toBeInTheDocument();
  });

  it("renders multiple caption lines", () => {
    render(
      <StatusScreen
        gifSrc="/grot-sleep.gif"
        gifAlt="Grot sleeping"
        lines={[
          { text: "No OpenAI key detected" },
          { text: "Please add one in Settings" },
        ]}
      />
    );
    expect(screen.getByText("No OpenAI key detected")).toBeInTheDocument();
    expect(screen.getByText("Please add one in Settings")).toBeInTheDocument();
  });

  it("applies led-error class to error lines only", () => {
    render(
      <StatusScreen
        gifSrc="/grot-sleep.gif"
        gifAlt="Grot sleeping"
        lines={[
          { text: "Invalid API key", error: true },
          { text: "Please update in Settings" },
        ]}
      />
    );
    const errorLine = screen.getByText("Invalid API key");
    expect(errorLine).toHaveClass("led-error");

    const normalLine = screen.getByText("Please update in Settings");
    expect(normalLine).not.toHaveClass("led-error");
  });

  it("applies led-error class to all error lines in ble_error screen", () => {
    render(
      <StatusScreen
        gifSrc="/grot-antenna.gif"
        gifAlt="Grot with antenna"
        lines={[
          { text: "Error connecting to the", error: true },
          { text: "iDotMatrix device", error: true },
        ]}
      />
    );
    const line1 = screen.getByText("Error connecting to the");
    const line2 = screen.getByText("iDotMatrix device");
    expect(line1).toHaveClass("led-error");
    expect(line2).toHaveClass("led-error");
  });

  it("renders without error class when error is false or omitted", () => {
    render(
      <StatusScreen
        gifSrc="/grot-spin.gif"
        gifAlt="Grot waking up"
        lines={[
          { text: "Grot is waking up...", error: false },
          { text: "Another line" },
        ]}
      />
    );
    expect(screen.getByText("Grot is waking up...")).not.toHaveClass("led-error");
    expect(screen.getByText("Another line")).not.toHaveClass("led-error");
  });
});
