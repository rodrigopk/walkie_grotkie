import { describe, it, expect } from "vitest";
import { PixelBuffer, W, H } from "./PixelBuffer";

describe("importPng validation", () => {
  it("rejects non-PNG MIME type", async () => {
    const file = new File(["not-png"], "test.jpg", { type: "image/jpeg" });
    const canvas = document.createElement("canvas");
    const { importPng } = await import("./io");
    await expect(importPng(file, canvas)).rejects.toThrow("Expected image/png");
  });
});

describe("PixelBuffer round-trip via canvas", () => {
  it("putImageData -> getImageData produces identical buffer", () => {
    const canvas = document.createElement("canvas");
    canvas.width = W;
    canvas.height = H;
    const ctx = canvas.getContext("2d");

    // jsdom doesn't support canvas 2d context without the native canvas package
    if (!ctx) return;

    const pb = PixelBuffer.emptyBlack();
    pb.setRGBA(10, 10, 255, 128, 64, 255);
    pb.setRGBA(63, 63, 0, 255, 0, 255);

    ctx.putImageData(new ImageData(new Uint8ClampedArray(pb.data), W, H), 0, 0);

    const readback = new PixelBuffer(ctx.getImageData(0, 0, W, H).data);
    expect(readback.equals(pb)).toBe(true);
  });
});
