import { describe, it, expect } from "vitest";
import { PixelBuffer, W, H } from "./PixelBuffer";
import { applyBrush, applyEraser, applyFill, pickColor } from "./tools";

describe("brush", () => {
  it("sets the pixel to the given color", () => {
    const pb = PixelBuffer.emptyBlack();
    applyBrush(pb, 5, 5, [255, 0, 0, 255]);
    expect(pb.getRGBA(5, 5)).toEqual([255, 0, 0, 255]);
  });

  it("does not affect neighboring pixels", () => {
    const pb = PixelBuffer.emptyBlack();
    applyBrush(pb, 5, 5, [255, 0, 0, 255]);
    expect(pb.getRGBA(4, 5)).toEqual([0, 0, 0, 255]);
    expect(pb.getRGBA(6, 5)).toEqual([0, 0, 0, 255]);
    expect(pb.getRGBA(5, 4)).toEqual([0, 0, 0, 255]);
    expect(pb.getRGBA(5, 6)).toEqual([0, 0, 0, 255]);
  });
});

describe("eraser", () => {
  it("resets pixel to opaque black", () => {
    const pb = PixelBuffer.emptyBlack();
    pb.setRGBA(5, 5, 255, 0, 0, 255);
    applyEraser(pb, 5, 5);
    expect(pb.getRGBA(5, 5)).toEqual([0, 0, 0, 255]);
  });
});

describe("fill", () => {
  it("fills contiguous same-colored region", () => {
    const pb = PixelBuffer.emptyBlack();
    pb.setRGBA(1, 0, 255, 0, 0, 255);
    applyFill(pb, 0, 0, [0, 255, 0, 255]);
    expect(pb.getRGBA(0, 0)).toEqual([0, 255, 0, 255]);
    expect(pb.getRGBA(1, 0)).toEqual([255, 0, 0, 255]);
  });

  it("no-ops when fill color matches target", () => {
    const pb = PixelBuffer.emptyBlack();
    applyFill(pb, 0, 0, [0, 0, 0, 255]);
    expect(pb.getRGBA(0, 0)).toEqual([0, 0, 0, 255]);
  });

  it("fills entire canvas when all same color", () => {
    const pb = PixelBuffer.emptyBlack();
    applyFill(pb, 0, 0, [255, 255, 255, 255]);
    for (let y = 0; y < H; y++) {
      for (let x = 0; x < W; x++) {
        expect(pb.getRGBA(x, y)).toEqual([255, 255, 255, 255]);
      }
    }
  });

  it("fills isolated region bounded by different color", () => {
    const pb = PixelBuffer.emptyBlack();
    // Create a 3x3 red box in the corner
    for (let y = 0; y < 3; y++) {
      for (let x = 0; x < 3; x++) {
        pb.setRGBA(x, y, 255, 0, 0, 255);
      }
    }
    applyFill(pb, 0, 0, [0, 0, 255, 255]);
    expect(pb.getRGBA(0, 0)).toEqual([0, 0, 255, 255]);
    expect(pb.getRGBA(2, 2)).toEqual([0, 0, 255, 255]);
    // Outside the red box should still be black
    expect(pb.getRGBA(3, 0)).toEqual([0, 0, 0, 255]);
  });
});

describe("picker", () => {
  it("returns the RGBA of the pixel", () => {
    const pb = PixelBuffer.emptyBlack();
    pb.setRGBA(3, 3, 128, 64, 32, 200);
    expect(pickColor(pb, 3, 3)).toEqual([128, 64, 32, 200]);
  });
});
