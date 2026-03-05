/**
 * Play back base64-encoded audio (MP3, WAV, OGG, etc.) received from the
 * WebSocket server.
 *
 * Uses the Web Audio API (AudioContext) to decode and schedule playback.
 * Returns a Promise that resolves when audio finishes playing.
 */
export async function playAudioFromBase64(b64: string): Promise<void> {
  const binaryStr = atob(b64);
  const bytes = new Uint8Array(binaryStr.length);
  for (let i = 0; i < binaryStr.length; i++) {
    bytes[i] = binaryStr.charCodeAt(i);
  }

  const ctx = new AudioContext();
  const audioBuffer = await ctx.decodeAudioData(bytes.buffer);

  return new Promise((resolve) => {
    const source = ctx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(ctx.destination);
    source.onended = () => {
      void ctx.close();
      resolve();
    };
    source.start();
  });
}
