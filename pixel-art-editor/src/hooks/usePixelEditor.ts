import { useRef, useState, useCallback, useEffect } from "react";
import { PixelBuffer } from "../core/PixelBuffer";
import type { RGBA } from "../core/PixelBuffer";
import { History } from "../core/history";
import {
  applyBrush,
  applyEraser,
  applyFill,
  pickColor,
} from "../core/tools";
import type { ToolType } from "../core/tools";
import { renderToModel, renderToViewport, pointerToCell } from "../core/render";
import { exportPng, importPng, loadDefaultAsset } from "../core/io";

export interface CursorInfo {
  x: number;
  y: number;
  color: RGBA;
}

export interface PixelEditorState {
  tool: ToolType;
  color: RGBA;
  showGrid: boolean;
  dirty: boolean;
  cursorInfo: CursorInfo | null;
  canUndo: boolean;
  canRedo: boolean;
}

export interface PixelEditorActions {
  setTool: (tool: ToolType) => void;
  setColor: (color: RGBA) => void;
  toggleGrid: () => void;
  undo: () => void;
  redo: () => void;
  handleExport: () => Promise<void>;
  handleImport: (file: File) => Promise<void>;
  initEmpty: () => void;
  initGrot: () => Promise<void>;
  initFromFile: (file: File) => Promise<void>;
  handlePointerDown: (e: React.PointerEvent) => void;
  handlePointerMove: (e: React.PointerEvent) => void;
  handlePointerUp: () => void;
  goToStartup: () => void;
}

export type EditorPhase = "startup" | "editor";

export function usePixelEditor() {
  const bufferRef = useRef<PixelBuffer>(PixelBuffer.emptyBlack());
  const historyRef = useRef(new History());
  const modelRef = useRef<HTMLCanvasElement | null>(null);
  const viewportRef = useRef<HTMLCanvasElement | null>(null);
  const drawingRef = useRef(false);
  const lastCellRef = useRef<{ x: number; y: number } | null>(null);

  const [phase, setPhase] = useState<EditorPhase>("startup");
  const [tool, setTool] = useState<ToolType>("brush");
  const [color, setColor] = useState<RGBA>([255, 255, 255, 255]);
  const [showGrid, setShowGrid] = useState(true);
  const [dirty, setDirty] = useState(false);
  const [cursorInfo, setCursorInfo] = useState<CursorInfo | null>(null);
  const [canUndo, setCanUndo] = useState(false);
  const [canRedo, setCanRedo] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const syncHistoryState = useCallback(() => {
    setCanUndo(historyRef.current.canUndo);
    setCanRedo(historyRef.current.canRedo);
  }, []);

  const repaint = useCallback(() => {
    const model = modelRef.current;
    const viewport = viewportRef.current;
    if (!model || !viewport) return;
    renderToModel(bufferRef.current, model);
    renderToViewport(model, viewport, showGrid);
  }, [showGrid]);

  useEffect(() => {
    repaint();
  }, [repaint, phase]);

  const pushHistory = useCallback(() => {
    historyRef.current.push(bufferRef.current);
    syncHistoryState();
  }, [syncHistoryState]);

  const replaceBuffer = useCallback(
    (pb: PixelBuffer) => {
      bufferRef.current = pb;
      repaint();
    },
    [repaint],
  );

  // --- Initialization ---

  const initEmpty = useCallback(() => {
    bufferRef.current = PixelBuffer.emptyBlack();
    historyRef.current.clear();
    setDirty(false);
    setError(null);
    syncHistoryState();
    setPhase("editor");
    // repaint will happen via useEffect when phase changes
  }, [syncHistoryState]);

  const initGrot = useCallback(async () => {
    const model = modelRef.current;
    if (!model) {
      // Model canvas not mounted yet — defer
      setPhase("editor");
      setTimeout(async () => {
        const m = modelRef.current;
        if (!m) return;
        try {
          bufferRef.current = await loadDefaultAsset("/grot.png", m);
          historyRef.current.clear();
          setDirty(false);
          setError(null);
          syncHistoryState();
          repaint();
        } catch {
          bufferRef.current = PixelBuffer.emptyBlack();
          setError("Failed to load grot asset, starting with empty canvas");
          repaint();
        }
      }, 0);
      return;
    }
    try {
      bufferRef.current = await loadDefaultAsset("/grot.png", model);
      historyRef.current.clear();
      setDirty(false);
      setError(null);
      syncHistoryState();
      setPhase("editor");
    } catch {
      bufferRef.current = PixelBuffer.emptyBlack();
      setError("Failed to load grot asset, starting with empty canvas");
      setPhase("editor");
    }
  }, [syncHistoryState, repaint]);

  const initFromFile = useCallback(
    async (file: File) => {
      const model = modelRef.current ?? document.createElement("canvas");
      try {
        bufferRef.current = await importPng(file, model);
        historyRef.current.clear();
        setDirty(false);
        setError(null);
        syncHistoryState();
        setPhase("editor");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to import file");
      }
    },
    [syncHistoryState],
  );

  // --- Tool application ---

  const applyToolAt = useCallback(
    (x: number, y: number, isStart: boolean) => {
      const pb = bufferRef.current;
      switch (tool) {
        case "brush":
          applyBrush(pb, x, y, color);
          break;
        case "eraser":
          applyEraser(pb, x, y);
          break;
        case "fill":
          if (isStart) applyFill(pb, x, y, color);
          break;
        case "picker":
          if (isStart) {
            const picked = pickColor(pb, x, y);
            setColor(picked);
          }
          return; // picker doesn't dirty the canvas
      }
      setDirty(true);
      repaint();
    },
    [tool, color, repaint],
  );

  // --- Pointer handlers ---

  const handlePointerDown = useCallback(
    (e: React.PointerEvent) => {
      const viewport = viewportRef.current;
      if (!viewport) return;
      const cell = pointerToCell(e.nativeEvent, viewport);
      if (!cell) return;

      pushHistory();
      drawingRef.current = true;
      lastCellRef.current = cell;
      applyToolAt(cell.x, cell.y, true);
      (e.target as HTMLElement).setPointerCapture(e.pointerId);
    },
    [pushHistory, applyToolAt],
  );

  const handlePointerMove = useCallback(
    (e: React.PointerEvent) => {
      const viewport = viewportRef.current;
      if (!viewport) return;
      const cell = pointerToCell(e.nativeEvent, viewport);

      if (cell) {
        setCursorInfo({
          x: cell.x,
          y: cell.y,
          color: bufferRef.current.getRGBA(cell.x, cell.y),
        });
      } else {
        setCursorInfo(null);
      }

      if (!drawingRef.current || !cell) return;
      if (
        lastCellRef.current &&
        lastCellRef.current.x === cell.x &&
        lastCellRef.current.y === cell.y
      ) {
        return;
      }
      lastCellRef.current = cell;
      applyToolAt(cell.x, cell.y, false);
    },
    [applyToolAt],
  );

  const handlePointerUp = useCallback(() => {
    drawingRef.current = false;
    lastCellRef.current = null;
  }, []);

  // --- Undo/Redo ---

  const undo = useCallback(() => {
    const prev = historyRef.current.undo(bufferRef.current);
    if (prev) {
      replaceBuffer(prev);
      setDirty(true);
      syncHistoryState();
    }
  }, [replaceBuffer, syncHistoryState]);

  const redo = useCallback(() => {
    const next = historyRef.current.redo(bufferRef.current);
    if (next) {
      replaceBuffer(next);
      setDirty(true);
      syncHistoryState();
    }
  }, [replaceBuffer, syncHistoryState]);

  // --- Import/Export ---

  const handleExport = useCallback(async () => {
    const model = modelRef.current;
    if (!model) return;
    renderToModel(bufferRef.current, model);
    await exportPng(model);
    setDirty(false);
  }, []);

  const handleImport = useCallback(
    async (file: File) => {
      const model = modelRef.current ?? document.createElement("canvas");
      try {
        pushHistory();
        bufferRef.current = await importPng(file, model);
        setDirty(false);
        setError(null);
        repaint();
        syncHistoryState();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to import file");
      }
    },
    [pushHistory, repaint, syncHistoryState],
  );

  const toggleGrid = useCallback(() => {
    setShowGrid((g) => !g);
  }, []);

  const goToStartup = useCallback(() => {
    setPhase("startup");
    setDirty(false);
    setError(null);
    setCursorInfo(null);
    historyRef.current.clear();
    syncHistoryState();
  }, [syncHistoryState]);

  // --- Keyboard shortcuts ---

  useEffect(() => {
    if (phase !== "editor") return;

    const handler = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey;
      const target = e.target as HTMLElement;
      if (target.tagName === "INPUT" || target.tagName === "TEXTAREA") return;

      if (mod && e.key === "z" && e.shiftKey) {
        e.preventDefault();
        redo();
        return;
      }
      if (mod && e.key === "z") {
        e.preventDefault();
        undo();
        return;
      }
      if (mod && e.key === "s") {
        e.preventDefault();
        handleExport();
        return;
      }
      if (mod && e.key === "o") {
        e.preventDefault();
        const input = document.createElement("input");
        input.type = "file";
        input.accept = ".png,image/png";
        input.onchange = () => {
          const file = input.files?.[0];
          if (file) handleImport(file);
        };
        input.click();
        return;
      }

      if (!mod && !e.shiftKey) {
        switch (e.key.toLowerCase()) {
          case "b": setTool("brush"); break;
          case "e": setTool("eraser"); break;
          case "f": setTool("fill"); break;
          case "i": setTool("picker"); break;
          case "g": toggleGrid(); break;
        }
      }
    };

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [phase, undo, redo, handleExport, handleImport, toggleGrid]);

  const state: PixelEditorState = {
    tool,
    color,
    showGrid,
    dirty,
    cursorInfo,
    canUndo,
    canRedo,
  };

  const actions: PixelEditorActions = {
    setTool,
    setColor,
    toggleGrid,
    undo,
    redo,
    handleExport,
    handleImport,
    initEmpty,
    initGrot,
    initFromFile,
    handlePointerDown,
    handlePointerMove,
    handlePointerUp,
    goToStartup,
  };

  return {
    phase,
    state,
    actions,
    modelRef,
    viewportRef,
    error,
    setError,
  };
}
