import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { useWebSocket } from "../hooks/useWebSocket";

// ---------------------------------------------------------------------------
// Mock WebSocket — uses class syntax so `new WebSocket(url)` works.
// ---------------------------------------------------------------------------

type WsCallback = (event: unknown) => void;

class MockWebSocketInstance {
  url: string;
  readyState = 0; // CONNECTING
  onopen: WsCallback | null = null;
  onmessage: WsCallback | null = null;
  onclose: WsCallback | null = null;
  onerror: WsCallback | null = null;
  readonly send = vi.fn();
  readonly close = vi.fn(() => {
    this.readyState = 3; // CLOSED
  });

  constructor(url: string) {
    this.url = url;
    instances.push(this);
  }

  simulateOpen() {
    this.readyState = 1;
    this.onopen?.({});
  }
  simulateMessage(data: string) {
    this.onmessage?.({ data });
  }
  simulateClose() {
    this.readyState = 3;
    this.onclose?.({});
  }
  simulateError() {
    this.onerror?.({});
  }

  static OPEN = 1;
}

const instances: MockWebSocketInstance[] = [];

beforeEach(() => {
  instances.length = 0;
  vi.useFakeTimers();
  vi.stubGlobal("WebSocket", MockWebSocketInstance);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useWebSocket", () => {
  it("starts in connecting status", () => {
    const { result } = renderHook(() => useWebSocket("ws://localhost:8765", vi.fn()));
    expect(result.current.status).toBe("connecting");
  });

  it("transitions to connected when WebSocket opens", () => {
    const { result } = renderHook(() => useWebSocket("ws://localhost:8765", vi.fn()));
    act(() => {
      instances[0].simulateOpen();
    });
    expect(result.current.status).toBe("connected");
  });

  it("transitions to disconnected when WebSocket closes", () => {
    const { result } = renderHook(() => useWebSocket("ws://localhost:8765", vi.fn()));
    act(() => {
      instances[0].simulateOpen();
      instances[0].simulateClose();
    });
    expect(result.current.status).toBe("disconnected");
  });

  it("transitions to error on WebSocket error", () => {
    const { result } = renderHook(() => useWebSocket("ws://localhost:8765", vi.fn()));
    act(() => {
      instances[0].simulateError();
    });
    expect(result.current.status).toBe("error");
  });

  it("calls onMessage with parsed server message", () => {
    const onMessage = vi.fn();
    renderHook(() => useWebSocket("ws://localhost:8765", onMessage));
    act(() => {
      instances[0].simulateOpen();
      instances[0].simulateMessage('{"type":"ready"}');
    });
    expect(onMessage).toHaveBeenCalledWith({ type: "ready" });
  });

  it("calls onMessage for every message individually — no batching skips", () => {
    const onMessage = vi.fn();
    renderHook(() => useWebSocket("ws://localhost:8765", onMessage));
    act(() => {
      instances[0].simulateOpen();
      instances[0].simulateMessage('{"type":"status","text":"scanning"}');
      instances[0].simulateMessage('{"type":"ready"}');
    });
    expect(onMessage).toHaveBeenCalledTimes(2);
    expect(onMessage).toHaveBeenNthCalledWith(1, { type: "status", text: "scanning" });
    expect(onMessage).toHaveBeenNthCalledWith(2, { type: "ready" });
  });

  it("ignores invalid JSON messages without throwing", () => {
    const onMessage = vi.fn();
    renderHook(() => useWebSocket("ws://localhost:8765", onMessage));
    act(() => {
      instances[0].simulateOpen();
      instances[0].simulateMessage("not json {{");
    });
    expect(onMessage).not.toHaveBeenCalled();
  });

  it("send() calls WebSocket.send() with serialised JSON", () => {
    const { result } = renderHook(() => useWebSocket("ws://localhost:8765", vi.fn()));
    act(() => {
      instances[0].simulateOpen();
    });
    act(() => {
      result.current.send({ type: "disconnect" });
    });
    expect(instances[0].send).toHaveBeenCalledOnce();
    const sent = JSON.parse(instances[0].send.mock.calls[0][0] as string);
    expect(sent).toEqual({ type: "disconnect" });
  });

  it("send() is a no-op when not connected", () => {
    const { result } = renderHook(() => useWebSocket("ws://localhost:8765", vi.fn()));
    act(() => {
      result.current.send({ type: "disconnect" });
    });
    expect(instances[0].send).not.toHaveBeenCalled();
  });

  it("reconnects after disconnect with backoff", () => {
    renderHook(() => useWebSocket("ws://localhost:8765", vi.fn()));
    act(() => {
      instances[0].simulateOpen();
      instances[0].simulateClose();
    });
    act(() => {
      vi.advanceTimersByTime(1_001);
    });
    expect(instances).toHaveLength(2);
  });

  it("closes WebSocket on unmount", () => {
    const { unmount } = renderHook(() => useWebSocket("ws://localhost:8765", vi.fn()));
    const ws = instances[0];
    unmount();
    expect(ws.close).toHaveBeenCalled();
  });

  it("does not reconnect after unmount", () => {
    const { unmount } = renderHook(() => useWebSocket("ws://localhost:8765", vi.fn()));
    act(() => {
      instances[0].simulateOpen();
    });
    unmount();
    act(() => {
      instances[0].simulateClose();
      vi.advanceTimersByTime(5_000);
    });
    expect(instances).toHaveLength(1);
  });
});
