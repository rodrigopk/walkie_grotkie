import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import LEDDisplay, { type DisplayLine } from "../components/LEDDisplay";

function makeLine(
  text: string,
  variant: DisplayLine["variant"] = "status",
  id = Math.random().toString()
): DisplayLine {
  return { id, text, variant };
}

describe("LEDDisplay", () => {
  it("renders all provided lines", () => {
    const lines: DisplayLine[] = [
      makeLine("Connected", "status"),
      makeLine("You: hello", "user"),
      makeLine("Grot: hi!", "grot"),
    ];
    render(<LEDDisplay lines={lines} />);
    expect(screen.getByText("Connected")).toBeInTheDocument();
    expect(screen.getByText("You: hello")).toBeInTheDocument();
    expect(screen.getByText("Grot: hi!")).toBeInTheDocument();
  });

  it("renders empty state placeholder when no lines", () => {
    render(<LEDDisplay lines={[]} />);
    expect(screen.getByTestId("led-empty")).toBeInTheDocument();
    // No regular lines should be rendered
    expect(screen.queryAllByTestId(/^led-line-/)).toHaveLength(0);
  });

  it("applies the correct CSS class for status variant", () => {
    render(<LEDDisplay lines={[makeLine("scanning...", "status", "1")]} />);
    const el = screen.getByTestId("led-line-status");
    expect(el).toHaveClass("led-status");
  });

  it("applies the correct CSS class for user variant", () => {
    render(<LEDDisplay lines={[makeLine("You: test", "user", "1")]} />);
    const el = screen.getByTestId("led-line-user");
    expect(el).toHaveClass("led-user");
  });

  it("applies the correct CSS class for grot variant", () => {
    render(<LEDDisplay lines={[makeLine("Grot: hello", "grot", "1")]} />);
    const el = screen.getByTestId("led-line-grot");
    expect(el).toHaveClass("led-grot");
  });

  it("applies the correct CSS class for error variant", () => {
    render(<LEDDisplay lines={[makeLine("ERROR!", "error", "1")]} />);
    const el = screen.getByTestId("led-line-error");
    expect(el).toHaveClass("led-error");
  });

  it("renders multiple lines in order", () => {
    const lines: DisplayLine[] = [
      makeLine("first", "status", "a"),
      makeLine("second", "status", "b"),
      makeLine("third", "status", "c"),
    ];
    render(<LEDDisplay lines={lines} />);
    const allLines = screen.getAllByTestId("led-line-status");
    expect(allLines).toHaveLength(3);
    expect(allLines[0]).toHaveTextContent("first");
    expect(allLines[1]).toHaveTextContent("second");
    expect(allLines[2]).toHaveTextContent("third");
  });

  it("removes empty placeholder once lines are added", () => {
    const { rerender } = render(<LEDDisplay lines={[]} />);
    expect(screen.getByTestId("led-empty")).toBeInTheDocument();

    rerender(<LEDDisplay lines={[makeLine("hello", "status", "1")]} />);
    expect(screen.queryByTestId("led-empty")).not.toBeInTheDocument();
    expect(screen.getByText("hello")).toBeInTheDocument();
  });
});
