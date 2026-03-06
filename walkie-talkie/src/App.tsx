import { useCallback, useEffect, useRef, useState } from "react";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { load, type Store } from "@tauri-apps/plugin-store";
import WalkieTalkie from "./components/WalkieTalkie";
import LEDDisplay, { type DisplayLine } from "./components/LEDDisplay";
import SettingsView from "./components/SettingsView";
import PushToTalkButton, { type ButtonState } from "./components/PushToTalkButton";
import SmallButtons from "./components/SmallButtons";
import { useWebSocket } from "./hooks/useWebSocket";
import { useAudioRecorder } from "./hooks/useAudioRecorder";
import { playAudioFromBase64 } from "./utils/audio";
import type { ServerMessage } from "./types/protocol";

const WS_URL = "ws://localhost:8765";

let _lineId = 0;
function makeId() {
  return String(_lineId++);
}

async function handleQuit() {
  await getCurrentWindow().close();
}

/** Validate an OpenAI API key by hitting the models list endpoint. */
async function validateOpenAIKey(key: string): Promise<boolean> {
  try {
    const res = await fetch("https://api.openai.com/v1/models", {
      headers: { Authorization: `Bearer ${key}` },
    });
    return res.status === 200;
  } catch {
    return false;
  }
}

type AppPhase =
  | "checking"   // reading the Tauri store on mount
  | "needs_key"  // no key found → sleeping grot
  | "settings"   // user is entering / updating key
  | "validating" // key available, validating with OpenAI
  | "loading"    // key valid, waiting for first voice_audio greeting
  | "ready"      // chat active
  | "auth_error"; // key rejected by OpenAI

export default function App() {
  const recorder = useAudioRecorder();

  const [lines, setLines] = useState<DisplayLine[]>([]);
  const [buttonState, setButtonState] = useState<ButtonState>("disabled");
  const [appPhase, setAppPhase] = useState<AppPhase>("checking");
  const [apiKey, setApiKey] = useState<string>("");

  const storeRef = useRef<Store | null>(null);

  // Accumulates streaming tokens for the current Grot response.
  const tokenBufferRef = useRef<string>("");
  // Buffers Grot's text until the matching voice_audio arrives so both appear together.
  const pendingGrotTextRef = useRef<string>("");

  // Keep buttonState accessible inside onMessage without stale closures.
  const buttonStateRef = useRef<ButtonState>("disabled");
  buttonStateRef.current = buttonState;

  // Keep apiKey accessible inside the validation effect without stale closure.
  const apiKeyRef = useRef<string>("");
  apiKeyRef.current = apiKey;

  function addLine(text: string, variant: DisplayLine["variant"]) {
    setLines((prev) => [...prev, { id: makeId(), text, variant }]);
  }

  // ── Read stored key on mount ───────────────────────────────────
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const store = await load("settings.json", { autoSave: true });
      storeRef.current = store;
      const stored = await store.get<string>("openai_api_key");
      if (cancelled) return;

      if (stored) {
        setApiKey(stored);
        setAppPhase("validating");
      } else {
        setAppPhase("needs_key");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // ── Validate key whenever appPhase enters "validating" ────────
  // Declared before useWebSocket so ws is available, but we use a ref
  // (wsRef) to avoid a stale closure — the actual ws.send is called
  // after the effect via a callback stored in wsSendRef.
  const wsSendRef = useRef<((msg: Parameters<ReturnType<typeof useWebSocket>["send"]>[0]) => void) | null>(null);

  useEffect(() => {
    if (appPhase !== "validating") return;
    const key = apiKeyRef.current;
    if (!key) {
      setAppPhase("needs_key");
      return;
    }

    // Reset chat state before re-validating (handles re-keying mid-session).
    setLines([]);
    setButtonState("disabled");
    tokenBufferRef.current = "";
    pendingGrotTextRef.current = "";

    let cancelled = false;
    (async () => {
      const valid = await validateOpenAIKey(key);
      if (cancelled) return;
      if (valid) {
        setAppPhase("loading");
        wsSendRef.current?.({ type: "set_api_key", key });
      } else {
        setAppPhase("auth_error");
      }
    })();
    return () => {
      cancelled = true;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [appPhase]);

  // ── Handle incoming server messages ───────────────────────────
  const handleMessage = useCallback((msg: ServerMessage) => {
    switch (msg.type) {
      case "ready":
        setButtonState("idle");
        break;

      case "status":
        console.log("[status]", msg.text);
        break;

      case "transcription":
        addLine(`You: ${msg.text}`, "user");
        break;

      case "chat_token":
        tokenBufferRef.current += msg.text;
        break;

      case "chat_done": {
        const text = msg.text || tokenBufferRef.current;
        tokenBufferRef.current = "";
        pendingGrotTextRef.current = text;
        break;
      }

      case "voice_audio": {
        const pending = pendingGrotTextRef.current;
        pendingGrotTextRef.current = "";
        if (pending) addLine(`Grot: ${pending}`, "grot");

        // Transition out of loading on the very first voice_audio (greeting).
        setAppPhase("ready");

        void playAudioFromBase64(msg.data)
          .catch((err) => {
            console.error("[App] Audio playback failed", err);
          })
          .finally(() => {
            ws.send({ type: "audio_done" });
            setButtonState("idle");
          });
        break;
      }

      case "animation":
        break;

      case "error": {
        const pending = pendingGrotTextRef.current;
        pendingGrotTextRef.current = "";
        if (pending) addLine(`Grot: ${pending}`, "grot");

        addLine(`Error: ${msg.text}`, "error");
        setButtonState("idle");
        break;
      }

      case "auth_error":
        setAppPhase("auth_error");
        break;
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const ws = useWebSocket(WS_URL, handleMessage);

  // Wire up the send function for the validation effect.
  wsSendRef.current = ws.send;

  // ── Map WebSocket connection status to button state ───────────
  useEffect(() => {
    if (
      ws.status === "connecting" ||
      ws.status === "disconnected" ||
      ws.status === "error"
    ) {
      setButtonState("disabled");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ws.status]);

  // ── Push-to-Talk handlers ─────────────────────────────────────
  const handlePressStart = useCallback(async () => {
    if (buttonState !== "idle") return;
    setButtonState("recording");
    await recorder.startRecording();
  }, [buttonState, recorder]);

  const handlePressEnd = useCallback(async () => {
    if (buttonState !== "recording") return;
    setButtonState("processing");

    const audioB64 = await recorder.stopRecording();
    if (!audioB64) {
      setButtonState("idle");
      return;
    }

    ws.send({ type: "voice_audio", data: audioB64 });
  }, [buttonState, recorder, ws]);

  // ── Settings handlers ─────────────────────────────────────────
  const handleOpenSettings = useCallback(() => {
    setAppPhase("settings");
  }, []);

  const handleSaveKey = useCallback(async (key: string) => {
    setApiKey(key);
    if (storeRef.current) {
      await storeRef.current.set("openai_api_key", key);
    }
    setAppPhase("validating");
  }, []);

  const handleCancelSettings = useCallback(() => {
    setAppPhase(apiKeyRef.current ? "ready" : "needs_key");
  }, []);

  // ── Visor routing ─────────────────────────────────────────────
  function renderScreen() {
    switch (appPhase) {
      case "checking":
      case "loading":
        return (
          <div className="device-screen">
            <div className="loading-container">
              <img
                src="/grot-spin.gif"
                alt="Grot waking up"
                className="loading-animation"
              />
              <p className="loading-caption">Grot is waking up...</p>
            </div>
          </div>
        );

      case "validating":
        return (
          <div className="device-screen">
            <div className="loading-container">
              <img
                src="/grot-spin.gif"
                alt="Validating"
                className="loading-animation"
              />
              <p className="loading-caption">Validating API key...</p>
            </div>
          </div>
        );

      case "needs_key":
        return (
          <div className="device-screen">
            <div className="loading-container">
              <img
                src="/grot-sleep.gif"
                alt="Grot sleeping"
                className="loading-animation"
              />
              <p className="loading-caption">No OpenAI key detected</p>
              <p className="loading-caption">Please add one in Settings</p>
            </div>
          </div>
        );

      case "auth_error":
        return (
          <div className="device-screen">
            <div className="loading-container">
              <img
                src="/grot-sleep.gif"
                alt="Grot sleeping"
                className="loading-animation"
              />
              <p className="loading-caption led-error">Invalid API key</p>
              <p className="loading-caption">Please update in Settings</p>
            </div>
          </div>
        );

      case "settings":
        return (
          <SettingsView
            onSave={(key) => void handleSaveKey(key)}
            onCancel={handleCancelSettings}
            initialKey={apiKey}
          />
        );

      case "ready":
        return <LEDDisplay lines={lines} />;
    }
  }

  // ── Microphone not available ──────────────────────────────────
  if (!recorder.isSupported) {
    return (
      <WalkieTalkie>
        <LEDDisplay
          lines={[
            {
              id: "err",
              text: "Microphone not available. Check browser permissions.",
              variant: "error",
            },
          ]}
        />
        <div className="device-button-area">
          <PushToTalkButton
            state="disabled"
            onPressStart={() => void 0}
            onPressEnd={() => void 0}
          />
        </div>
        <SmallButtons
          onQuit={() => void handleQuit()}
          onSettings={handleOpenSettings}
        />
      </WalkieTalkie>
    );
  }

  return (
    <WalkieTalkie>
      {renderScreen()}
      <div className="device-button-area">
        <PushToTalkButton
          state={buttonState}
          onPressStart={() => void handlePressStart()}
          onPressEnd={() => void handlePressEnd()}
        />
      </div>
      <SmallButtons
        onQuit={() => void handleQuit()}
        onSettings={handleOpenSettings}
      />
    </WalkieTalkie>
  );
}
