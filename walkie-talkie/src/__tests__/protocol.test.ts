import { describe, it, expect } from "vitest";
import {
  isServerMessage,
  parseServerMessage,
  serialiseMessage,
  type ClientMessage,
  type ServerMessage,
} from "../types/protocol";

describe("isServerMessage", () => {
  it("returns true for valid server messages", () => {
    expect(isServerMessage({ type: "ready" })).toBe(true);
    expect(isServerMessage({ type: "status", text: "hello" })).toBe(true);
    expect(isServerMessage({ type: "animation", state: "talking" })).toBe(true);
    expect(isServerMessage({ type: "auth_error", text: "Invalid key" })).toBe(true);
  });

  it("returns false for null", () => {
    expect(isServerMessage(null)).toBe(false);
  });

  it("returns false for non-objects", () => {
    expect(isServerMessage("string")).toBe(false);
    expect(isServerMessage(42)).toBe(false);
    expect(isServerMessage(undefined)).toBe(false);
  });

  it("returns false for objects without a type field", () => {
    expect(isServerMessage({ text: "no type" })).toBe(false);
  });
});

describe("parseServerMessage", () => {
  it("parses a valid ready message", () => {
    const msg = parseServerMessage('{"type":"ready"}');
    expect(msg).toEqual({ type: "ready" });
  });

  it("parses a status message", () => {
    const msg = parseServerMessage('{"type":"status","text":"scanning..."}');
    expect(msg).toEqual({ type: "status", text: "scanning..." });
  });

  it("parses a chat_token message", () => {
    const msg = parseServerMessage('{"type":"chat_token","text":"Hello"}');
    expect(msg).toEqual({ type: "chat_token", text: "Hello" });
  });

  it("parses an animation message", () => {
    const msg = parseServerMessage('{"type":"animation","state":"talking"}');
    expect(msg).toEqual({ type: "animation", state: "talking" });
  });

  it("returns null for invalid JSON", () => {
    expect(parseServerMessage("not json {")).toBeNull();
  });

  it("returns null for JSON without type field", () => {
    expect(parseServerMessage('{"text":"no type"}')).toBeNull();
  });

  it("handles empty string gracefully", () => {
    expect(parseServerMessage("")).toBeNull();
  });

  it("parses an auth_error message", () => {
    const msg = parseServerMessage('{"type":"auth_error","text":"Invalid key"}');
    expect(msg).toEqual({ type: "auth_error", text: "Invalid key" } satisfies ServerMessage);
  });
});

describe("serialiseMessage", () => {
  it("serialises a voice_audio message", () => {
    const msg: ClientMessage = { type: "voice_audio", data: "abc123" };
    const raw = serialiseMessage(msg);
    expect(JSON.parse(raw)).toEqual(msg);
  });

  it("serialises a command message", () => {
    const msg: ClientMessage = { type: "command", text: "/help" };
    const raw = serialiseMessage(msg);
    expect(JSON.parse(raw)).toEqual(msg);
  });

  it("serialises a disconnect message", () => {
    const msg: ClientMessage = { type: "disconnect" };
    const raw = serialiseMessage(msg);
    expect(JSON.parse(raw)).toEqual({ type: "disconnect" });
  });

  it("serialises a set_api_key message", () => {
    const msg: ClientMessage = { type: "set_api_key", key: "sk-test123" };
    const raw = serialiseMessage(msg);
    expect(JSON.parse(raw)).toEqual(msg);
  });

  it("serialises a connect_device message with optional address", () => {
    const msg: ClientMessage = {
      type: "connect_device",
      address: "AA:BB:CC:DD:EE:FF",
    };
    const raw = serialiseMessage(msg);
    expect(JSON.parse(raw)).toEqual(msg);
  });

  it("produces valid JSON for all ClientMessage types", () => {
    const messages: ClientMessage[] = [
      { type: "voice_audio", data: "data" },
      { type: "command", text: "/animation dancing" },
      { type: "connect_device" },
      { type: "disconnect" },
      { type: "set_api_key", key: "sk-test" },
    ];
    for (const msg of messages) {
      expect(() => JSON.parse(serialiseMessage(msg))).not.toThrow();
    }
  });
});
