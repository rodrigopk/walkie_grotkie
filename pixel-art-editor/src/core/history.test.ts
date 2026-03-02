import { describe, it, expect } from "vitest";
import { PixelBuffer } from "./PixelBuffer";
import { History } from "./history";

describe("History", () => {
  it("undo restores previous state", () => {
    const h = new History();
    const v1 = PixelBuffer.emptyBlack();
    h.push(v1);

    const v2 = v1.clone();
    v2.setRGBA(0, 0, 255, 0, 0);

    const restored = h.undo(v2)!;
    expect(restored.getRGBA(0, 0)).toEqual([0, 0, 0, 255]);
  });

  it("redo restores undone state", () => {
    const h = new History();
    const v1 = PixelBuffer.emptyBlack();
    h.push(v1);

    const v2 = v1.clone();
    v2.setRGBA(0, 0, 255, 0, 0);
    h.undo(v2);

    const redone = h.redo(v1)!;
    expect(redone.getRGBA(0, 0)).toEqual([255, 0, 0, 255]);
  });

  it("push clears redo stack", () => {
    const h = new History();
    h.push(PixelBuffer.emptyBlack());
    h.undo(PixelBuffer.emptyBlack());
    expect(h.canRedo).toBe(true);

    h.push(PixelBuffer.emptyBlack());
    expect(h.canRedo).toBe(false);
  });

  it("undo returns null when stack is empty", () => {
    const h = new History();
    expect(h.undo(PixelBuffer.emptyBlack())).toBeNull();
  });

  it("redo returns null when stack is empty", () => {
    const h = new History();
    expect(h.redo(PixelBuffer.emptyBlack())).toBeNull();
  });

  it("clear empties both stacks", () => {
    const h = new History();
    h.push(PixelBuffer.emptyBlack());
    h.push(PixelBuffer.emptyBlack());
    h.undo(PixelBuffer.emptyBlack());
    expect(h.canUndo).toBe(true);
    expect(h.canRedo).toBe(true);

    h.clear();
    expect(h.canUndo).toBe(false);
    expect(h.canRedo).toBe(false);
  });

  it("respects max history size", () => {
    const h = new History();
    for (let i = 0; i < 110; i++) {
      const pb = PixelBuffer.emptyBlack();
      pb.setRGBA(0, 0, i % 256, 0, 0);
      h.push(pb);
    }
    // Should only be able to undo 100 times
    let count = 0;
    let current = PixelBuffer.emptyBlack();
    while (h.canUndo) {
      const prev = h.undo(current);
      if (!prev) break;
      current = prev;
      count++;
    }
    expect(count).toBe(100);
  });
});
