import { useRef } from "react";
import "./StartupScreen.css";

interface StartupScreenProps {
  onStartNew: () => void;
  onLoadGrot: () => Promise<void>;
  onOpenFile: (file: File) => Promise<void>;
  error: string | null;
}

export function StartupScreen({
  onStartNew,
  onLoadGrot,
  onOpenFile,
  error,
}: StartupScreenProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      await onOpenFile(file);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  return (
    <div className="startup-screen">
      <div className="startup-card">
        <h1 className="startup-title">Pixel Art Editor</h1>
        <p className="startup-subtitle">64 × 64 pixel canvas</p>

        <div className="startup-buttons">
          <button className="startup-btn" onClick={onStartNew}>
            Start New
          </button>
          <button className="startup-btn" onClick={onLoadGrot}>
            Load Grot
          </button>
          <button
            className="startup-btn"
            onClick={() => fileInputRef.current?.click()}
          >
            Open File...
          </button>
        </div>

        <input
          ref={fileInputRef}
          type="file"
          accept=".png,image/png"
          className="startup-file-input"
          onChange={handleFileChange}
        />

        {error && <p className="startup-error">{error}</p>}
      </div>
    </div>
  );
}
