/**
 * WebSocket protocol types for the Grot walkie-talkie.
 *
 * All messages are JSON objects with a `type` discriminant.
 * The Python WebSocket server (ws_server.py) implements the server side.
 */

// ---------------------------------------------------------------------------
// Client → Server
// ---------------------------------------------------------------------------

/** Send a base64-encoded WAV recording for voice processing. */
export type VoiceAudioMessage = {
  type: "voice_audio";
  /** Base64-encoded WAV audio bytes. */
  data: string;
};

/** Send a slash command (e.g. "/animation dancing", "/help", "/exit"). */
export type CommandMessage = {
  type: "command";
  text: string;
};

/** Request device connection (optional — server connects at startup). */
export type ConnectDeviceMessage = {
  type: "connect_device";
  /** BLE device address. If omitted, the server scans automatically. */
  address?: string;
};

/** Request graceful server shutdown / session end. */
export type DisconnectMessage = {
  type: "disconnect";
};

/** Signal that audio playback has finished so the server can advance animation state. */
export type AudioDoneMessage = {
  type: "audio_done";
};

/** Send the user's OpenAI API key to the server for session initialisation. */
export type SetApiKeyMessage = {
  type: "set_api_key";
  key: string;
};

export type ClientMessage =
  | VoiceAudioMessage
  | CommandMessage
  | ConnectDeviceMessage
  | DisconnectMessage
  | AudioDoneMessage
  | SetApiKeyMessage;

// ---------------------------------------------------------------------------
// Server → Client
// ---------------------------------------------------------------------------

/** Server is ready and the BLE device is connected. */
export type ReadyMessage = {
  type: "ready";
};

/** A status/informational line to display on the LED display. */
export type StatusMessage = {
  type: "status";
  text: string;
};

/** The user's transcribed speech. */
export type TranscriptionMessage = {
  type: "transcription";
  text: string;
};

/** A streaming LLM token from Grot's response. */
export type ChatTokenMessage = {
  type: "chat_token";
  text: string;
};

/** Grot's full response (after streaming completes, mood tag stripped). */
export type ChatDoneMessage = {
  type: "chat_done";
  text: string;
};

/** Grot's spoken TTS audio as a base64-encoded WAV. */
export type VoiceAudioServerMessage = {
  type: "voice_audio";
  /** Base64-encoded WAV audio bytes. */
  data: string;
};

/** The iDotMatrix animation state changed. */
export type AnimationMessage = {
  type: "animation";
  state: AnimationState;
};

/** An error occurred on the server side. */
export type ErrorMessage = {
  type: "error";
  text: string;
};

/** The provided API key was rejected by OpenAI. */
export type AuthErrorMessage = {
  type: "auth_error";
  text: string;
};

/** The BLE device connection failed. */
export type BleErrorMessage = {
  type: "ble_error";
  text: string;
};

export type ServerMessage =
  | ReadyMessage
  | StatusMessage
  | TranscriptionMessage
  | ChatTokenMessage
  | ChatDoneMessage
  | VoiceAudioServerMessage
  | AnimationMessage
  | ErrorMessage
  | AuthErrorMessage
  | BleErrorMessage;

// ---------------------------------------------------------------------------
// Auxiliary types
// ---------------------------------------------------------------------------

export type AnimationState =
  | "idle"
  | "idle_alt"
  | "thinking"
  | "talking"
  | "talking_alt"
  | "excited"
  | "dancing"
  | "dancing_alt"
  | "dancing_flip"
  | "sleeping";

/** Discriminated union type guard for ServerMessage. */
export function isServerMessage(value: unknown): value is ServerMessage {
  if (typeof value !== "object" || value === null) return false;
  const msg = value as Record<string, unknown>;
  return typeof msg["type"] === "string";
}

/** Serialise a ClientMessage to a JSON string ready for WebSocket.send(). */
export function serialiseMessage(msg: ClientMessage): string {
  return JSON.stringify(msg);
}

/** Parse a raw WebSocket message string into a ServerMessage.
 *  Returns null if parsing fails or the type is not recognised.
 */
export function parseServerMessage(raw: string): ServerMessage | null {
  try {
    const parsed: unknown = JSON.parse(raw);
    if (isServerMessage(parsed)) return parsed;
    return null;
  } catch {
    return null;
  }
}
