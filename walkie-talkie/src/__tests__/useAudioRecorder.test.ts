import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { useAudioRecorder } from "../hooks/useAudioRecorder";

// ---------------------------------------------------------------------------
// Mock state shared between test instances
// ---------------------------------------------------------------------------

const mockStart = vi.fn();
const mockStop = vi.fn();
let _onStop: (() => void) | null = null;
let _onData: ((e: BlobEvent) => void) | null = null;

// MediaRecorder mock — must be a class so `new MediaRecorder(...)` works.
class MockMediaRecorder {
  mimeType = "audio/webm";
  start = mockStart;
  stop = mockStop.mockImplementation(() => {
    _onStop?.();
  });

  get ondataavailable() { return _onData; }
  set ondataavailable(fn: ((e: BlobEvent) => void) | null) { _onData = fn; }
  get onstop() { return _onStop; }
  set onstop(fn: (() => void) | null) { _onStop = fn; }
}

// AudioContext mock — class so `new AudioContext()` works.
class MockAudioContext {
  sampleRate = 16_000;
  decodeAudioData = vi.fn().mockResolvedValue({
    numberOfChannels: 1,
    length: 160,
    sampleRate: 16_000,
    getChannelData: () => new Float32Array(160),
  });
  close = vi.fn().mockResolvedValue(undefined);
}

const mockGetUserMedia = vi.fn().mockResolvedValue({
  getTracks: () => [{ stop: vi.fn() }],
});

beforeEach(() => {
  _onStop = null;
  _onData = null;
  vi.stubGlobal("MediaRecorder", MockMediaRecorder);
  vi.stubGlobal("AudioContext", MockAudioContext);
  vi.stubGlobal("navigator", {
    mediaDevices: { getUserMedia: mockGetUserMedia },
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useAudioRecorder", () => {
  it("isRecording starts as false", () => {
    const { result } = renderHook(() => useAudioRecorder());
    expect(result.current.isRecording).toBe(false);
  });

  it("calls getUserMedia on startRecording", async () => {
    const { result } = renderHook(() => useAudioRecorder());
    await act(async () => {
      await result.current.startRecording();
    });
    expect(mockGetUserMedia).toHaveBeenCalledOnce();
    expect(mockGetUserMedia).toHaveBeenCalledWith(
      expect.objectContaining({ audio: expect.any(Object) })
    );
  });

  it("sets isRecording to true while recording", async () => {
    const { result } = renderHook(() => useAudioRecorder());
    await act(async () => {
      await result.current.startRecording();
    });
    expect(result.current.isRecording).toBe(true);
  });

  it("sets isRecording to false after stopRecording", async () => {
    const { result } = renderHook(() => useAudioRecorder());
    await act(async () => {
      await result.current.startRecording();
    });
    await act(async () => {
      await result.current.stopRecording();
    });
    expect(result.current.isRecording).toBe(false);
  });

  it("returns a non-empty base64 string from stopRecording", async () => {
    const { result } = renderHook(() => useAudioRecorder());
    await act(async () => {
      await result.current.startRecording();
    });
    let b64 = "";
    await act(async () => {
      b64 = await result.current.stopRecording();
    });
    expect(typeof b64).toBe("string");
    expect(b64.length).toBeGreaterThan(0);
  });

  it("sets isSupported to false when getUserMedia is denied", async () => {
    mockGetUserMedia.mockRejectedValueOnce(new Error("Permission denied"));
    const { result } = renderHook(() => useAudioRecorder());
    await act(async () => {
      await result.current.startRecording();
    });
    expect(result.current.isSupported).toBe(false);
  });

  it("returns empty string from stopRecording when not recording", async () => {
    const { result } = renderHook(() => useAudioRecorder());
    let b64 = "not-empty";
    await act(async () => {
      b64 = await result.current.stopRecording();
    });
    expect(b64).toBe("");
  });

  it("does not call getUserMedia twice if already recording", async () => {
    const { result } = renderHook(() => useAudioRecorder());
    await act(async () => {
      await result.current.startRecording();
    });
    const callsBefore = mockGetUserMedia.mock.calls.length;
    await act(async () => {
      await result.current.startRecording();
    });
    expect(mockGetUserMedia.mock.calls.length).toBe(callsBefore);
  });
});
