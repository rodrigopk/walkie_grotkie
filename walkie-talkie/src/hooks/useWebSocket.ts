import { useCallback, useEffect, useRef, useState } from "react";
import {
  type ClientMessage,
  type ServerMessage,
  parseServerMessage,
  serialiseMessage,
} from "../types/protocol";

export type ConnectionStatus =
  | "connecting"
  | "connected"
  | "disconnected"
  | "error";

export interface UseWebSocketReturn {
  status: ConnectionStatus;
  send: (msg: ClientMessage) => void;
}

const INITIAL_BACKOFF_MS = 1_000;
const MAX_BACKOFF_MS = 30_000;
const BACKOFF_FACTOR = 2;

/**
 * Connects to the Grot WebSocket server and provides a typed message channel.
 *
 * - Reconnects automatically with exponential backoff on disconnect.
 * - Parses incoming JSON into ServerMessage objects via parseServerMessage().
 * - Sends ClientMessage objects serialised to JSON.
 * - Calls onMessage for every received message directly (no React state batching),
 *   so rapid successive messages like voice_audio + animation are never merged.
 */
export function useWebSocket(
  url: string,
  onMessage: (msg: ServerMessage) => void,
): UseWebSocketReturn {
  const [status, setStatus] = useState<ConnectionStatus>("connecting");

  const wsRef = useRef<WebSocket | null>(null);
  const backoffRef = useRef<number>(INITIAL_BACKOFF_MS);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const unmountedRef = useRef(false);
  // Keep a stable ref to the latest onMessage callback so the WebSocket
  // handler never captures a stale closure.
  const onMessageRef = useRef(onMessage);
  useEffect(() => { onMessageRef.current = onMessage; });

  const connect = useCallback(() => {
    if (unmountedRef.current) return;

    setStatus("connecting");
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      if (unmountedRef.current) {
        ws.close();
        return;
      }
      backoffRef.current = INITIAL_BACKOFF_MS;
      setStatus("connected");
    };

    ws.onmessage = (event: MessageEvent<string>) => {
      const parsed = parseServerMessage(event.data);
      if (parsed) {
        onMessageRef.current(parsed);
      }
    };

    ws.onclose = () => {
      if (unmountedRef.current) return;
      wsRef.current = null;
      setStatus("disconnected");

      // Schedule reconnect with exponential backoff.
      const delay = backoffRef.current;
      backoffRef.current = Math.min(delay * BACKOFF_FACTOR, MAX_BACKOFF_MS);
      reconnectTimerRef.current = setTimeout(connect, delay);
    };

    ws.onerror = () => {
      if (unmountedRef.current) return;
      setStatus("error");
      // onclose fires after onerror, which will trigger reconnect.
    };
  }, [url]);

  useEffect(() => {
    unmountedRef.current = false;
    connect();

    return () => {
      unmountedRef.current = true;
      if (reconnectTimerRef.current !== null) {
        clearTimeout(reconnectTimerRef.current);
      }
      wsRef.current?.close();
    };
  }, [connect]);

  const send = useCallback((msg: ClientMessage) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(serialiseMessage(msg));
    }
  }, []);

  return { status, send };
}
