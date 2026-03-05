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
  // Accumulates streaming tokens for the current Grot response.
  const tokenBufferRef = useRef<string>("");

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
        addLine("Ready. Hold the button to talk.", "status");
        break;

      case "status":
        addLine(msg.text, "status");
        break;

      case "transcription":
        addLine(`You: ${msg.text}`, "user");
        break;

      case "chat_token":
        // Accumulate tokens silently; show the full response on chat_done.
        tokenBufferRef.current += msg.text;
        break;

      case "chat_done": {
        const text = msg.text || tokenBufferRef.current;
        tokenBufferRef.current = "";
        if (text) addLine(`Grot: ${text}`, "grot");
        break;
      }

      case "voice_audio":
        // Play Grot's spoken response; re-enable button after audio finishes.
        void playAudioFromBase64(msg.data).catch((err) => {
          console.error("[App] Audio playback failed", err);
        }).finally(() => {
          setButtonState("idle");
        });
        break;

      case "animation":
        // Animation state changes are informational — no UI update needed here.
        break;

      case "error":
        addLine(`Error: ${msg.text}`, "error");
        setButtonState("idle");
        break;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const ws = useWebSocket(WS_URL, handleMessage);

  // ── Map WebSocket status to LED + button state ────────────────────────
  useEffect(() => {
    if (ws.status === "connecting") {
      setButtonState("disabled");
      addLine("Connecting to Grot server...", "status");
    } else if (ws.status === "connected") {
      // Button enabled when server sends "ready" (see message handler below)
    } else if (ws.status === "disconnected") {
      setButtonState("disabled");
      addLine("Disconnected. Reconnecting...", "error");
    } else if (ws.status === "error") {
      setButtonState("disabled");
      addLine("Connection error. Retrying...", "error");
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
      addLine("No audio captured. Please try again.", "status");
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
      <LEDDisplay lines={lines} />
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
