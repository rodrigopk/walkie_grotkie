import { useCallback, useRef, useState } from "react";

export interface UseAudioRecorderReturn {
  isRecording: boolean;
  isSupported: boolean;
  /** True when getUserMedia was denied by the OS or user (NotAllowedError). */
  permissionDenied: boolean;
  startRecording: () => Promise<void>;
  /** Stops recording and resolves with a base64-encoded WAV string. */
  stopRecording: () => Promise<string>;
}

const SAMPLE_RATE = 16_000; // Must match the Python backend (Whisper expects 16kHz)
const NUM_CHANNELS = 1; // Mono

/**
 * Web Audio API-based push-to-talk recorder.
 *
 * Records from the default microphone; on stop, converts the raw PCM data to
 * a 16kHz mono WAV and returns it as a base64-encoded string suitable for
 * sending over WebSocket to the Python voice pipeline.
 *
 * Audio format notes:
 *   - Whisper (via OpenAI) works best with 16kHz mono PCM WAV.
 *   - We use AudioContext to resample browser audio to 16kHz regardless of
 *     the device's native sample rate.
 *   - MediaRecorder records raw chunks; we decode them via AudioContext and
 *     re-encode as WAV to guarantee the format.
 */
export function useAudioRecorder(): UseAudioRecorderReturn {
  const [isRecording, setIsRecording] = useState(false);
  const [isSupported, setIsSupported] = useState(
    typeof navigator !== "undefined" &&
      typeof navigator.mediaDevices !== "undefined" &&
      typeof window.AudioContext !== "undefined"
  );
  const [permissionDenied, setPermissionDenied] = useState(false);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  // Promise resolver stored so stopRecording() can await the data.
  const resolveRef = useRef<((b64: string) => void) | null>(null);

  const startRecording = useCallback(async () => {
    if (isRecording) return;

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { sampleRate: SAMPLE_RATE, channelCount: NUM_CHANNELS },
        video: false,
      });
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === "NotAllowedError") {
        setPermissionDenied(true);
      } else {
        setIsSupported(false);
      }
      return;
    }

    streamRef.current = stream;
    chunksRef.current = [];

    const recorder = new MediaRecorder(stream);
    mediaRecorderRef.current = recorder;

    recorder.ondataavailable = (e: BlobEvent) => {
      if (e.data.size > 0) {
        chunksRef.current.push(e.data);
      }
    };

    recorder.onstop = async () => {
      // Decode the recorded audio and re-encode as 16kHz mono WAV.
      const blob = new Blob(chunksRef.current, { type: recorder.mimeType });
      const arrayBuffer = await blob.arrayBuffer();

      try {
        const ctx = new AudioContext();
        const decoded = await ctx.decodeAudioData(arrayBuffer);
        await ctx.close();

        const wavBuffer = encodeWav(decoded, SAMPLE_RATE);
        const b64 = arrayBufferToBase64(wavBuffer);

        if (resolveRef.current) {
          resolveRef.current(b64);
          resolveRef.current = null;
        }
      } catch (err) {
        console.error("[useAudioRecorder] WAV encoding failed", err);
        if (resolveRef.current) {
          resolveRef.current("");
          resolveRef.current = null;
        }
      }

      // Release the microphone.
      streamRef.current?.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    };

    recorder.start();
    setIsRecording(true);
  }, [isRecording]);

  const stopRecording = useCallback((): Promise<string> => {
    return new Promise((resolve) => {
      if (!mediaRecorderRef.current || !isRecording) {
        resolve("");
        return;
      }
      resolveRef.current = resolve;
      setIsRecording(false);
      mediaRecorderRef.current.stop();
      mediaRecorderRef.current = null;
    });
  }, [isRecording]);

  return { isRecording, isSupported, permissionDenied, startRecording, stopRecording };
}

// ---------------------------------------------------------------------------
// WAV encoding utilities
// ---------------------------------------------------------------------------

/**
 * Re-sample and mix an AudioBuffer down to the target sample rate / mono,
 * then pack into a WAV ArrayBuffer.
 */
function encodeWav(audio: AudioBuffer, targetSampleRate: number): ArrayBuffer {
  // Mix down to mono by averaging channels.
  const numChannels = audio.numberOfChannels;
  const inputLength = audio.length;
  const mono = new Float32Array(inputLength);
  for (let ch = 0; ch < numChannels; ch++) {
    const channel = audio.getChannelData(ch);
    for (let i = 0; i < inputLength; i++) {
      mono[i] += channel[i] / numChannels;
    }
  }

  // Resample if needed (linear interpolation — adequate for speech).
  const sourceSR = audio.sampleRate;
  let pcm: Float32Array;
  if (sourceSR !== targetSampleRate) {
    const ratio = sourceSR / targetSampleRate;
    const outLength = Math.floor(inputLength / ratio);
    pcm = new Float32Array(outLength);
    for (let i = 0; i < outLength; i++) {
      const srcIdx = i * ratio;
      const lo = Math.floor(srcIdx);
      const hi = Math.min(lo + 1, inputLength - 1);
      const frac = srcIdx - lo;
      pcm[i] = mono[lo] * (1 - frac) + mono[hi] * frac;
    }
  } else {
    pcm = mono;
  }

  // Convert float32 PCM [-1,1] to int16.
  const int16 = new Int16Array(pcm.length);
  for (let i = 0; i < pcm.length; i++) {
    const s = Math.max(-1, Math.min(1, pcm[i]));
    int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }

  return writeWavHeader(int16, targetSampleRate);
}

function writeWavHeader(samples: Int16Array, sampleRate: number): ArrayBuffer {
  const byteRate = sampleRate * 2; // 1 channel * 2 bytes per sample
  const dataLen = samples.byteLength;
  const buf = new ArrayBuffer(44 + dataLen);
  const view = new DataView(buf);

  writeString(view, 0, "RIFF");
  view.setUint32(4, 36 + dataLen, true);
  writeString(view, 8, "WAVE");
  writeString(view, 12, "fmt ");
  view.setUint32(16, 16, true); // PCM chunk size
  view.setUint16(20, 1, true);  // PCM format
  view.setUint16(22, 1, true);  // Mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, byteRate, true);
  view.setUint16(32, 2, true);  // Block align (1 ch * 2 bytes)
  view.setUint16(34, 16, true); // Bits per sample
  writeString(view, 36, "data");
  view.setUint32(40, dataLen, true);

  new Int16Array(buf, 44).set(samples);
  return buf;
}

function writeString(view: DataView, offset: number, str: string): void {
  for (let i = 0; i < str.length; i++) {
    view.setUint8(offset + i, str.charCodeAt(i));
  }
}

function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}
