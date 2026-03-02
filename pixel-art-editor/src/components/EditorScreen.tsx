import { CanvasViewport } from "./CanvasViewport";
import { Toolbar } from "./Toolbar";
import { ColorPalette } from "./ColorPalette";
import { StatusBar } from "./StatusBar";
import type { PixelEditorState, PixelEditorActions } from "../hooks/usePixelEditor";
import "./EditorScreen.css";

interface EditorScreenProps {
  state: PixelEditorState;
  actions: PixelEditorActions;
  modelRef: React.RefObject<HTMLCanvasElement | null>;
  viewportRef: React.RefObject<HTMLCanvasElement | null>;
  error: string | null;
  onDismissError: () => void;
}

const VIEWPORT_SIZE = 576;

export function EditorScreen({
  state,
  actions,
  modelRef,
  viewportRef,
  error,
  onDismissError,
}: EditorScreenProps) {
  return (
    <div className="editor-screen">
      <Toolbar
        tool={state.tool}
        showGrid={state.showGrid}
        canUndo={state.canUndo}
        canRedo={state.canRedo}
        dirty={state.dirty}
        onSetTool={actions.setTool}
        onToggleGrid={actions.toggleGrid}
        onUndo={actions.undo}
        onRedo={actions.redo}
        onExport={actions.handleExport}
        onImport={actions.handleImport}
        onNew={actions.goToStartup}
      />

      {error && (
        <div className="editor-error">
          <span>{error}</span>
          <button className="editor-error-dismiss" onClick={onDismissError}>
            ×
          </button>
        </div>
      )}

      <div className="editor-body">
        <ColorPalette color={state.color} onSetColor={actions.setColor} />
        <CanvasViewport
          viewportRef={viewportRef}
          onPointerDown={actions.handlePointerDown}
          onPointerMove={actions.handlePointerMove}
          onPointerUp={actions.handlePointerUp}
          size={VIEWPORT_SIZE}
        />
      </div>

      <StatusBar
        cursorInfo={state.cursorInfo}
        tool={state.tool}
        dirty={state.dirty}
      />

      <canvas ref={modelRef} className="model-canvas" />
    </div>
  );
}
