import { useEffect, useRef } from "react";

export type DisplayVariant = "status" | "user" | "grot" | "error";

export interface DisplayLine {
  id: string;
  text: string;
  variant: DisplayVariant;
}

interface LEDDisplayProps {
  lines: DisplayLine[];
}

const VARIANT_CLASS: Record<DisplayVariant, string> = {
  status: "led-status",
  user: "led-user",
  grot: "led-grot",
  error: "led-error",
};

export default function LEDDisplay({ lines }: LEDDisplayProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to the bottom whenever lines change.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [lines]);

  return (
    <div className="device-screen" data-testid="led-screen">
      <div className="led-display" data-testid="led-display">
        {lines.length === 0 ? (
          <p className="led-line led-status" data-testid="led-empty">
            &nbsp;
          </p>
        ) : (
          lines.map((line) => (
            <p
              key={line.id}
              className={`led-line ${VARIANT_CLASS[line.variant]}`}
              data-testid={`led-line-${line.variant}`}
            >
              {line.text}
            </p>
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
