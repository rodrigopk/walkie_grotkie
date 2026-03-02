import "./CanvasViewport.css";

interface CanvasViewportProps {
  viewportRef: React.RefObject<HTMLCanvasElement | null>;
  onPointerDown: (e: React.PointerEvent) => void;
  onPointerMove: (e: React.PointerEvent) => void;
  onPointerUp: () => void;
  size: number;
}

export function CanvasViewport({
  viewportRef,
  onPointerDown,
  onPointerMove,
  onPointerUp,
  size,
}: CanvasViewportProps) {
  return (
    <div 
      className="canvas-viewport-wrapper"
      role="button"
      aria-label="Pixel art canvas"
      data-testid="canvas-viewport-wrapper"
      tabIndex={0}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerLeave={onPointerUp}
    >
      <canvas
        ref={viewportRef}
        width={size}
        height={size}
        className="canvas-viewport"
        style={{ width: size, height: size }}
        aria-label="Pixel art viewport"
        data-testid="canvas-viewport"
      />
    </div>
  );
}
