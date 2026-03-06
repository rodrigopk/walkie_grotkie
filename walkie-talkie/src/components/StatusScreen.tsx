interface StatusLine {
  text: string;
  error?: boolean;
}

interface StatusScreenProps {
  gifSrc: string;
  gifAlt: string;
  lines: StatusLine[];
}

export default function StatusScreen({ gifSrc, gifAlt, lines }: StatusScreenProps) {
  return (
    <div className="device-screen">
      <div className="loading-container">
        <img src={gifSrc} alt={gifAlt} className="loading-animation" />
        {lines.map((line, i) => (
          <p
            key={i}
            className={`loading-caption${line.error ? " led-error" : ""}`}
          >
            {line.text}
          </p>
        ))}
      </div>
    </div>
  );
}
