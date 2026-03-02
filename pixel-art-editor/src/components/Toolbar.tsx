import { useRef } from "react";
import type { ToolType } from "../core/tools";
import "./Toolbar.css";

interface ToolbarProps {
  tool: ToolType;
  showGrid: boolean;
  canUndo: boolean;
  canRedo: boolean;
  dirty: boolean;
  onSetTool: (tool: ToolType) => void;
  onToggleGrid: () => void;
  onUndo: () => void;
  onRedo: () => void;
  onExport: () => Promise<void>;
  onImport: (file: File) => Promise<void>;
  onNew: () => void;
}

const TOOLS: { type: ToolType; label: string; shortcut: string }[] = [
  { type: "brush", label: "Brush", shortcut: "B" },
  { type: "eraser", label: "Eraser", shortcut: "E" },
  { type: "fill", label: "Fill", shortcut: "F" },
  { type: "picker", label: "Picker", shortcut: "I" },
];

export function Toolbar({
  tool,
  showGrid,
  canUndo,
  canRedo,
  dirty,
  onSetTool,
  onToggleGrid,
  onUndo,
  onRedo,
  onExport,
  onImport,
  onNew,
}: ToolbarProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      await onImport(file);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  return (
    <div className="toolbar">
      <div className="toolbar-group">
        {TOOLS.map((t) => (
          <button
            key={t.type}
            className={`toolbar-btn ${tool === t.type ? "active" : ""}`}
            onClick={() => onSetTool(t.type)}
            title={`${t.label} (${t.shortcut})`}
            aria-label={`${t.label} tool`}
            aria-pressed={tool === t.type}
            data-testid={`tool-${t.type}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="toolbar-separator" />

      <div className="toolbar-group">
        <button
          className="toolbar-btn"
          onClick={onUndo}
          disabled={!canUndo}
          title="Undo (Ctrl+Z)"
          aria-label="Undo"
          data-testid="toolbar-undo"
        >
          Undo
        </button>
        <button
          className="toolbar-btn"
          onClick={onRedo}
          disabled={!canRedo}
          title="Redo (Ctrl+Shift+Z)"
          aria-label="Redo"
          data-testid="toolbar-redo"
        >
          Redo
        </button>
      </div>

      <div className="toolbar-separator" />

      <div className="toolbar-group">
        <button
          className={`toolbar-btn ${showGrid ? "active" : ""}`}
          onClick={onToggleGrid}
          title="Toggle Grid (G)"
          aria-label="Toggle grid"
          aria-pressed={showGrid}
          data-testid="toolbar-grid-toggle"
        >
          Grid
        </button>
      </div>

      <div className="toolbar-separator" />

      <div className="toolbar-group">
        <button
          className="toolbar-btn toolbar-btn-action"
          onClick={onExport}
          title="Export PNG (Ctrl+S)"
          aria-label="Export PNG"
          data-testid="toolbar-export"
        >
          Export{dirty ? " *" : ""}
        </button>
        <button
          className="toolbar-btn toolbar-btn-action"
          onClick={() => fileInputRef.current?.click()}
          title="Import PNG (Ctrl+O)"
          aria-label="Import PNG"
          data-testid="toolbar-import"
        >
          Import
        </button>
        <button
          className="toolbar-btn toolbar-btn-action"
          onClick={onNew}
          aria-label="Create new canvas"
          data-testid="toolbar-new"
        >
          New
        </button>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept=".png,image/png"
        className="toolbar-file-input"
        aria-label="Editor import file input"
        data-testid="toolbar-import-input"
        onChange={handleFileChange}
      />
    </div>
  );
}
