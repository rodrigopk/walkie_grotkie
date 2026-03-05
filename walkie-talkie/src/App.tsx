import { useCallback, useEffect, useRef, useState } from "react";
import WalkieTalkie from "./components/WalkieTalkie";
import LEDDisplay, { type DisplayLine } from "./components/LEDDisplay";
import PushToTalkButton, { type ButtonState } from "./components/PushToTalkButton";
import { useWebSocket } from "./hooks/useWebSocket";
import { useAudioRecorder } from "./hooks/useAudioRecorder";
import { playAudioFromBase64 } from "./utils/audio";
import type { ServerMessage } from "./types/protocol";

const WS_URL = "ws://localhost:8765";

let _lineId = 0;
function makeId() {
  return String(_lineId++);
}

export default function App() {
  const recorder = useAudioRecorder();

  const [lines, setLines] = useState<DisplayLine[]>([]);
  const [buttonState, setButtonState] = useState<ButtonState>("disabled");
  // Flips to true when the first voice_audio arrives (greeting complete).
  const [appReady, setAppReady] = useState(false);

  // Accumulates streaming tokens for the current Grot response.
  const tokenBufferRef = useRef<string>("");
  // Buffers Grot's text until the matching voice_audio arrives so both appear together.
  const pendingGrotTextRef = useRef<string>("");

  // Keep buttonState accessible inside onMessage without stale closures.
  const buttonStateRef = useRef<ButtonState>("disabled");
  buttonStateRef.current = buttonState;

  function addLine(text: string, variant: DisplayLine["variant"]) {
    setLines((prev) => [...prev, { id: makeId(), text, variant }]);
  }

  // ── Handle incoming server messages ───────────────────────────────────
  // Called directly from useWebSocket (not via state), so every message is
  // handled individually — React batching cannot skip any message.
  const handleMessage = useCallback((msg: ServerMessage) => {
    switch (msg.type) {
      case "ready":
        setButtonState("idle");
        break;

      case "status":
        // Status messages are informational only; log them for debugging.
        console.log("[status]", msg.text);
        break;

      case "transcription":
        addLine(`You: ${msg.text}`, "user");
        break;

      case "chat_token":
        // Accumulate tokens silently; the full response will be shown on voice_audio.
        tokenBufferRef.current += msg.text;
        break;

      case "chat_done": {
        const text = msg.text || tokenBufferRef.current;
        tokenBufferRef.current = "";
        // Buffer the text — it will be shown when voice_audio arrives so both
        // appear simultaneously.
        pendingGrotTextRef.current = text;
        break;
      }

      case "voice_audio": {
        // Show Grot's text in sync with audio playback starting.
        const pending = pendingGrotTextRef.current;
        pendingGrotTextRef.current = "";
        if (pending) addLine(`Grot: ${pending}`, "grot");

        // Transition out of the loading screen on the very first voice_audio.
        setAppReady(true);

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
        // Animation state changes are informational — no UI update needed here.
        break;

      case "error": {
        // Flush any buffered Grot text so it is never silently lost.
        const pending = pendingGrotTextRef.current;
        pendingGrotTextRef.current = "";
        if (pending) addLine(`Grot: ${pending}`, "grot");

        addLine(`Error: ${msg.text}`, "error");
        setButtonState("idle");
        break;
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const ws = useWebSocket(WS_URL, handleMessage);

  // ── Map WebSocket connection status to button state ───────────────────
  useEffect(() => {
    if (ws.status === "connecting") {
      setButtonState("disabled");
    } else if (ws.status === "disconnected") {
      setButtonState("disabled");
    } else if (ws.status === "error") {
      setButtonState("disabled");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ws.status]);

  // ── Push-to-Talk handlers ─────────────────────────────────────────────
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
    // Button stays in "processing" until voice_audio (TTS) is received.
  }, [buttonState, recorder, ws]);

  // ── Microphone not available ──────────────────────────────────────────
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
      </WalkieTalkie>
    );
  }

  return (
    <WalkieTalkie>
      {appReady ? (
        <LEDDisplay lines={lines} />
      ) : (
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
      )}
      <div className="device-button-area">
        <PushToTalkButton
          state={buttonState}
          onPressStart={() => void handlePressStart()}
          onPressEnd={() => void handlePressEnd()}
        />
      </div>
    </WalkieTalkie>
  );
}
