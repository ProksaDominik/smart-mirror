import os
import asyncio
import tempfile
import threading
import queue

import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write as write_wav
import pygame
import edge_tts
import requests

from ui import music

SAMPLE_RATE = 16000
CHANNELS = 1

EDGE_VOICE = "en-GB-ThomasNeural"
EDGE_PITCH = "+0Hz"
EDGE_RATE = "-3%"

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "").strip()
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "").strip()
ELEVENLABS_MODEL = "eleven_multilingual_v2"

VOICE_CHANNEL_ID = 0

# Whisper is lazy-loaded — only when transcribe() is first called.
_whisper = None


def _get_whisper():
    global _whisper
    if _whisper is None:
        print("[Loading Whisper model... this happens once, then cached]")
        from faster_whisper import WhisperModel
        _whisper = WhisperModel("base", device="cpu", compute_type="int8")
        print("[Whisper ready]")
    return _whisper


pygame.mixer.init()


class Recorder:
    """Push-button microphone recorder. Call start() then stop() to get a WAV path."""

    def __init__(self) -> None:
        self._chunks: list[np.ndarray] = []
        self._queue: "queue.Queue[np.ndarray]" = queue.Queue()
        self._stream: sd.InputStream | None = None

    def _callback(self, indata, frames, time_info, status) -> None:
        if status:
            print(f"[audio status: {status}]")
        self._queue.put(indata.copy())

    def start(self) -> None:
        self._chunks = []
        self._queue = queue.Queue()
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            callback=self._callback,
        )
        self._stream.start()

    def stop(self) -> str:
        if self._stream is None:
            return ""
        self._stream.stop()
        self._stream.close()
        self._stream = None

        while not self._queue.empty():
            self._chunks.append(self._queue.get())

        if not self._chunks:
            return ""

        audio = np.concatenate(self._chunks, axis=0)
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        write_wav(tmp.name, SAMPLE_RATE, audio)
        tmp.close()
        return tmp.name


def record_until_enter() -> str:
    """Record audio from the microphone until the user presses Enter."""
    print("[Recording... press Enter to stop]")

    audio_queue: "queue.Queue[np.ndarray]" = queue.Queue()
    stop_event = threading.Event()

    def callback(indata, frames, time_info, status):
        if status:
            print(f"[audio status: {status}]")
        audio_queue.put(indata.copy())

    def wait_for_enter():
        input()
        stop_event.set()

    threading.Thread(target=wait_for_enter, daemon=True).start()

    chunks = []
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="int16", callback=callback):
        while not stop_event.is_set():
            try:
                chunks.append(audio_queue.get(timeout=0.1))
            except queue.Empty:
                continue

    while not audio_queue.empty():
        chunks.append(audio_queue.get())

    if not chunks:
        return ""

    audio = np.concatenate(chunks, axis=0)
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    write_wav(tmp.name, SAMPLE_RATE, audio)
    tmp.close()
    return tmp.name


def record_until_silence(
    silence_rms: float = 350.0,
    silence_duration_s: float = 1.2,
    max_duration_s: float = 15.0,
    min_duration_s: float = 0.5,
) -> str:
    """Record from the mic until the user stops talking (RMS-based silence detection)."""
    block_size = 1024
    blocks_per_sec = SAMPLE_RATE / block_size
    silence_blocks_limit = int(blocks_per_sec * silence_duration_s)
    max_blocks = int(blocks_per_sec * max_duration_s)
    min_blocks = int(blocks_per_sec * min_duration_s)

    q: "queue.Queue[np.ndarray]" = queue.Queue()

    def callback(indata, frames, time_info, status):
        if status:
            print(f"[audio status: {status}]")
        q.put(indata.copy())

    chunks: list[np.ndarray] = []
    silence_run = 0
    block_count = 0

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="int16",
        blocksize=block_size,
        callback=callback,
    ):
        while block_count < max_blocks:
            try:
                chunk = q.get(timeout=0.5)
            except queue.Empty:
                continue
            chunks.append(chunk)
            block_count += 1

            rms = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))
            if rms < silence_rms:
                silence_run += 1
                if silence_run >= silence_blocks_limit and block_count > min_blocks:
                    break
            else:
                silence_run = 0

    if not chunks:
        return ""

    audio = np.concatenate(chunks, axis=0)
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    write_wav(tmp.name, SAMPLE_RATE, audio)
    tmp.close()
    return tmp.name


def transcribe(wav_path: str) -> str:
    """Transcribe audio locally with faster-whisper."""
    segments, _info = _get_whisper().transcribe(wav_path, language="en")
    text = " ".join(seg.text for seg in segments).strip()
    return text


def _play_voice_file(path: str) -> None:
    """Play a TTS audio file on its own channel so music can play in parallel."""
    voice_sound = pygame.mixer.Sound(path)
    voice_channel = pygame.mixer.Channel(VOICE_CHANNEL_ID)
    voice_channel.set_volume(1.0)
    voice_channel.play(voice_sound)
    while voice_channel.get_busy():
        pygame.time.Clock().tick(10)
    try:
        os.remove(path)
    except OSError:
        pass


async def _edge_synthesize(text: str, out_path: str) -> None:
    communicator = edge_tts.Communicate(text, EDGE_VOICE, pitch=EDGE_PITCH, rate=EDGE_RATE)
    await communicator.save(out_path)


def _speak_edge(text: str) -> None:
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp.close()
    asyncio.run(_edge_synthesize(text, tmp.name))
    _play_voice_file(tmp.name)


def _speak_elevenlabs(text: str) -> bool:
    if not ELEVENLABS_API_KEY or not ELEVENLABS_VOICE_ID:
        return False
    if ELEVENLABS_API_KEY.startswith("your_") or ELEVENLABS_VOICE_ID.startswith("your_"):
        return False

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": text,
        "model_id": ELEVENLABS_MODEL,
        "voice_settings": {
            "stability": 0.45,
            "similarity_boost": 0.85,
            "style": 0.30,
            "use_speaker_boost": True,
        },
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
    except requests.RequestException as exc:
        print(f"[ElevenLabs network error → falling back to Edge TTS: {exc}]")
        return False

    if response.status_code != 200:
        print(f"[ElevenLabs error {response.status_code} → falling back to Edge TTS]")
        return False

    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp.write(response.content)
    tmp.close()
    _play_voice_file(tmp.name)
    return True


def speak(text: str) -> None:
    """Speak text aloud. Background music starts on first call and plays for a few seconds."""
    music.play_under()
    if not _speak_elevenlabs(text):
        _speak_edge(text)
