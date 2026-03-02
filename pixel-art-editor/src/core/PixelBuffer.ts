export const W = 64;
export const H = 64;
export const BYTES = W * H * 4;

export type RGBA = [number, number, number, number];

export class PixelBuffer {
  readonly data: Uint8ClampedArray;

  constructor(source?: Uint8ClampedArray) {
    this.data = source
      ? new Uint8ClampedArray(source)
      : new Uint8ClampedArray(BYTES);
  }

  static emptyBlack(): PixelBuffer {
    const pb = new PixelBuffer();
    for (let i = 3; i < BYTES; i += 4) pb.data[i] = 255;
    return pb;
  }

  clone(): PixelBuffer {
    return new PixelBuffer(this.data);
  }

  idx(x: number, y: number): number {
    return (y * W + x) * 4;
  }

  getRGBA(x: number, y: number): RGBA {
    const i = this.idx(x, y);
    return [this.data[i], this.data[i + 1], this.data[i + 2], this.data[i + 3]];
  }

  setRGBA(x: number, y: number, r: number, g: number, b: number, a = 255): void {
    const i = this.idx(x, y);
    this.data[i] = r;
    this.data[i + 1] = g;
    this.data[i + 2] = b;
    this.data[i + 3] = a;
  }

  equals(other: PixelBuffer): boolean {
    if (this.data.length !== other.data.length) return false;
    for (let i = 0; i < this.data.length; i++) {
      if (this.data[i] !== other.data[i]) return false;
    }
    return true;
  }
}
