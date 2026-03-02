import { usePixelEditor } from "./hooks/usePixelEditor";
import { StartupScreen } from "./components/StartupScreen";
import { EditorScreen } from "./components/EditorScreen";
import "./App.css";

function App() {
  const { phase, state, actions, modelRef, viewportRef, error, setError } =
    usePixelEditor();

  if (phase === "startup") {
    return (
      <StartupScreen
        onStartNew={actions.initEmpty}
        onLoadGrot={actions.initGrot}
        onOpenFile={actions.initFromFile}
        error={error}
      />
    );
  }

  return (
    <EditorScreen
      state={state}
      actions={actions}
      modelRef={modelRef}
      viewportRef={viewportRef}
      error={error}
      onDismissError={() => setError(null)}
    />
  );
}

export default App;
