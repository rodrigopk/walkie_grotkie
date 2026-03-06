import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import SettingsView from "../components/SettingsView";

describe("SettingsView", () => {
  it("renders the API key input", () => {
    render(<SettingsView onSave={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.getByTestId("api-key-input")).toBeInTheDocument();
  });

  it("renders the Save button", () => {
    render(<SettingsView onSave={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.getByTestId("save-api-key-button")).toBeInTheDocument();
  });

  it("Save button is disabled when input is empty", () => {
    render(<SettingsView onSave={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.getByTestId("save-api-key-button")).toBeDisabled();
  });

  it("Save button is disabled when input is only whitespace", () => {
    render(<SettingsView onSave={vi.fn()} onCancel={vi.fn()} initialKey="   " />);
    expect(screen.getByTestId("save-api-key-button")).toBeDisabled();
  });

  it("Save button is enabled when input has a non-empty value", () => {
    render(<SettingsView onSave={vi.fn()} onCancel={vi.fn()} initialKey="sk-test" />);
    expect(screen.getByTestId("save-api-key-button")).not.toBeDisabled();
  });

  it("Save button becomes enabled after typing in the input", () => {
    render(<SettingsView onSave={vi.fn()} onCancel={vi.fn()} />);
    const input = screen.getByTestId("api-key-input");
    fireEvent.change(input, { target: { value: "sk-my-key" } });
    expect(screen.getByTestId("save-api-key-button")).not.toBeDisabled();
  });

  it("calls onSave with the trimmed input value when Save is clicked", () => {
    const onSave = vi.fn();
    render(<SettingsView onSave={onSave} onCancel={vi.fn()} />);
    const input = screen.getByTestId("api-key-input");
    fireEvent.change(input, { target: { value: "sk-my-key" } });
    fireEvent.click(screen.getByTestId("save-api-key-button"));
    expect(onSave).toHaveBeenCalledWith("sk-my-key");
  });

  it("calls onSave with trimmed value (strips surrounding spaces)", () => {
    const onSave = vi.fn();
    render(<SettingsView onSave={onSave} onCancel={vi.fn()} initialKey="  sk-trimmed  " />);
    fireEvent.click(screen.getByTestId("save-api-key-button"));
    expect(onSave).toHaveBeenCalledWith("sk-trimmed");
  });

  it("pre-fills the input with initialKey", () => {
    render(<SettingsView onSave={vi.fn()} onCancel={vi.fn()} initialKey="sk-existing" />);
    expect(screen.getByTestId("api-key-input")).toHaveValue("sk-existing");
  });

  it("uses password type for the input (key is masked)", () => {
    render(<SettingsView onSave={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.getByTestId("api-key-input")).toHaveAttribute("type", "password");
  });

  it("shows the settings-view container", () => {
    render(<SettingsView onSave={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.getByTestId("settings-view")).toBeInTheDocument();
  });

  it("renders the screen title header", () => {
    render(<SettingsView onSave={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.getByTestId("screen-title")).toBeInTheDocument();
  });

  it("screen title reads 'Settings'", () => {
    render(<SettingsView onSave={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.getByTestId("screen-title")).toHaveTextContent("Settings");
  });

  it("renders an OpenAI API Key label", () => {
    render(<SettingsView onSave={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.getByText(/OpenAI API Key/i)).toBeInTheDocument();
  });

  it("calls onSave when Enter is pressed in the input", () => {
    const onSave = vi.fn();
    render(<SettingsView onSave={onSave} onCancel={vi.fn()} initialKey="sk-enter" />);
    fireEvent.keyDown(screen.getByTestId("api-key-input"), { key: "Enter" });
    expect(onSave).toHaveBeenCalledWith("sk-enter");
  });

  it("does not call onSave for non-Enter keys", () => {
    const onSave = vi.fn();
    render(<SettingsView onSave={onSave} onCancel={vi.fn()} initialKey="sk-other" />);
    fireEvent.keyDown(screen.getByTestId("api-key-input"), { key: "Escape" });
    expect(onSave).not.toHaveBeenCalled();
  });
});
