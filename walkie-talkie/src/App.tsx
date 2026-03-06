import { useCallback, useEffect, useRef, useState } from "react";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { load, type Store } from "@tauri-apps/plugin-store";
import WalkieTalkie from "./components/WalkieTalkie";
import LEDDisplay, { type DisplayLine } from "./components/LEDDisplay";
import SettingsView from "./components/SettingsView";
import StatusScreen from "./components/StatusScreen";
import PushToTalkButton, { type ButtonState } from "./components/PushToTalkButton";
import SmallButtons from "./components/SmallButtons";
import { useWebSocket } from "./hooks/useWebSocket";
import { useAudioRecorder } from "./hooks/useAudioRecorder";
import { playAudioFromBase64 } from "./utils/audio";
import type { ServerMessage } from "./types/protocol";

const WS_URL = "ws://localhost:8765";

const CYCLE_ANIMATIONS = ["thinking", "talking", "excited", "dancing"] as const;

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
  | "auth_error" // key rejected by OpenAI
  | "ble_error"; // BLE device connection failed

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

  // Tracks which animation is next in the cycle (avoids re-creating the callback on each advance).
  const animCycleRef = useRef(0);

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

      case "ble_error":
        setAppPhase("ble_error");
        break;
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const ws = useWebSocket(WS_URL, handleMessage);

  // Wire up the send function for the validation effect.
  wsSendRef.current = ws.send;

  // ── Map WebSocket connection status to button state ───────────
  // Also re-send the API key when the WebSocket reconnects after the initial
  // setup, since the new server connection doesn't have the key yet.
  // We track "has ever connected" instead of prev-status because React may
  // render intermediate "connecting" state between "disconnected" and
  // "connected", making prev-status unreliable for reconnect detection.
  const hasConnectedRef = useRef(false);
  useEffect(() => {
    if (
      ws.status === "connecting" ||
      ws.status === "disconnected" ||
      ws.status === "error"
    ) {
      setButtonState("disabled");
    }

    if (ws.status === "connected") {
      if (hasConnectedRef.current && apiKeyRef.current) {
        ws.send({ type: "set_api_key", key: apiKeyRef.current });
      }
      hasConnectedRef.current = true;
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

  // Shared "go home" action: used by the Home button and the Settings cancel link.
  const handleGoHome = useCallback(() => {
    setAppPhase(apiKeyRef.current ? "ready" : "needs_key");
  }, []);

  // ── Animation cycle handler ───────────────────────────────────
  const handleCycleAnimation = useCallback(() => {
    const name = CYCLE_ANIMATIONS[animCycleRef.current];
    animCycleRef.current = (animCycleRef.current + 1) % CYCLE_ANIMATIONS.length;
    ws.send({ type: "command", text: `/animation ${name}` });
    addLine(`[animation: ${name}]`, "system");
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ws]);

  // ── Visor routing ─────────────────────────────────────────────
  function renderScreen() {
    switch (appPhase) {
      case "checking":
      case "loading":
        return (
          <StatusScreen
            gifSrc="/grot-spin.gif"
            gifAlt="Grot waking up"
            lines={[{ text: "Grot is waking up..." }]}
          />
        );

      case "validating":
        return (
          <StatusScreen
            gifSrc="/grot-spin.gif"
            gifAlt="Validating"
            lines={[{ text: "Validating API key..." }]}
          />
        );

      case "needs_key":
        return (
          <StatusScreen
            gifSrc="/grot-sleep.gif"
            gifAlt="Grot sleeping"
            lines={[
              { text: "No OpenAI key detected" },
              { text: "Please add one in Settings" },
            ]}
          />
        );

      case "auth_error":
        return (
          <StatusScreen
            gifSrc="/grot-sleep.gif"
            gifAlt="Grot sleeping"
            lines={[
              { text: "Invalid API key", error: true },
              { text: "Please update in Settings" },
            ]}
          />
        );

      case "ble_error":
        return (
          <StatusScreen
            gifSrc="/grot-antenna.gif"
            gifAlt="Grot with antenna"
            lines={[
              { text: "Error connecting to the", error: true },
              { text: "iDotMatrix device", error: true },
            ]}
          />
        );

      case "settings":
        return (
          <SettingsView
            onSave={(key) => void handleSaveKey(key)}
            onCancel={handleGoHome}
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
          onHome={handleGoHome}
          onCycleAnimation={handleCycleAnimation}
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
        onHome={handleGoHome}
        onCycleAnimation={handleCycleAnimation}
        onSettings={handleOpenSettings}
      />
    </WalkieTalkie>
  );
}
