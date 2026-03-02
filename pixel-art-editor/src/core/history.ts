import { PixelBuffer } from "./PixelBuffer";

const MAX_HISTORY = 100;

export class History {
  private undoStack: PixelBuffer[] = [];
  private redoStack: PixelBuffer[] = [];

  push(snapshot: PixelBuffer): void {
    this.undoStack.push(snapshot.clone());
    if (this.undoStack.length > MAX_HISTORY) this.undoStack.shift();
    this.redoStack = [];
  }

  undo(current: PixelBuffer): PixelBuffer | null {
    if (this.undoStack.length === 0) return null;
    this.redoStack.push(current.clone());
    return this.undoStack.pop()!;
  }

  redo(current: PixelBuffer): PixelBuffer | null {
    if (this.redoStack.length === 0) return null;
    this.undoStack.push(current.clone());
    return this.redoStack.pop()!;
  }

  get canUndo(): boolean {
    return this.undoStack.length > 0;
  }

  get canRedo(): boolean {
    return this.redoStack.length > 0;
  }

  clear(): void {
    this.undoStack = [];
    this.redoStack = [];
  }
}
