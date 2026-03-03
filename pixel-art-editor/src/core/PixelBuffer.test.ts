import { describe, it, expect } from "vitest";
import { PixelBuffer, W, H } from "./PixelBuffer";

describe("PixelBuffer", () => {
  it("creates an empty buffer of correct size", () => {
    const pb = new PixelBuffer();
    expect(pb.data.length).toBe(W * H * 4);
  });

  it("emptyBlack fills with opaque black", () => {
    const pb = PixelBuffer.emptyBlack();
    for (let y = 0; y < H; y++) {
      for (let x = 0; x < W; x++) {
        expect(pb.getRGBA(x, y)).toEqual([0, 0, 0, 255]);
      }
    }
  });

  it("setRGBA / getRGBA round-trips", () => {
    const pb = new PixelBuffer();
    pb.setRGBA(10, 20, 255, 128, 64, 200);
    expect(pb.getRGBA(10, 20)).toEqual([255, 128, 64, 200]);
  });

  it("clone produces an independent copy", () => {
    const pb = PixelBuffer.emptyBlack();
    const copy = pb.clone();
    copy.setRGBA(0, 0, 255, 0, 0);
    expect(pb.getRGBA(0, 0)).toEqual([0, 0, 0, 255]);
    expect(copy.getRGBA(0, 0)).toEqual([255, 0, 0, 255]);
  });

  it("equals returns true for identical buffers", () => {
    const a = PixelBuffer.emptyBlack();
    const b = PixelBuffer.emptyBlack();
    expect(a.equals(b)).toBe(true);
    b.setRGBA(0, 0, 1, 2, 3);
    expect(a.equals(b)).toBe(false);
  });

  it("default alpha is 255 when omitted", () => {
    const pb = new PixelBuffer();
    pb.setRGBA(0, 0, 100, 200, 50);
    expect(pb.getRGBA(0, 0)).toEqual([100, 200, 50, 255]);
  });

  it("constructor from Uint8ClampedArray copies data correctly", () => {
    const src = new Uint8ClampedArray(W * H * 4);
    src[0] = 42; src[1] = 100; src[2] = 200; src[3] = 255;
    const pb = new PixelBuffer(src);
    expect(pb.getRGBA(0, 0)).toEqual([42, 100, 200, 255]);
    src[0] = 0;
    expect(pb.getRGBA(0, 0)[0]).toBe(42);
  });
});
