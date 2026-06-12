import os
import glob
import random
import threading
import pygame

# MP3 lives alongside this file in RPi/ui/
MUSIC_DIR = os.path.dirname(os.path.abspath(__file__))
SUPPORTED_EXTENSIONS = ("*.mp3", "*.ogg", "*.wav")

UNDER_VOLUME = 0.08
START_SECONDS = 4.0
DURATION_SECONDS = 10.0

_active = False
_played_once = False
_stop_timer: threading.Timer | None = None


def _find_tracks() -> list[str]:
    tracks = []
    for pattern in SUPPORTED_EXTENSIONS:
        tracks.extend(glob.glob(os.path.join(MUSIC_DIR, pattern)))
    return tracks


def play_under() -> None:
    """Play music once for DURATION_SECONDS, only on the first call of the session."""
    global _active, _played_once, _stop_timer

    if _played_once:
        return

    tracks = _find_tracks()
    if not tracks:
        _played_once = True
        return

    track = random.choice(tracks)
    try:
        pygame.mixer.music.load(track)
        pygame.mixer.music.set_volume(UNDER_VOLUME)
        pygame.mixer.music.play(loops=0, start=START_SECONDS)
        _active = True
        _played_once = True

        _stop_timer = threading.Timer(DURATION_SECONDS, _timed_stop)
        _stop_timer.daemon = True
        _stop_timer.start()
    except pygame.error as exc:
        print(f"[Music error: {exc}]")
        _active = False
        _played_once = True


def _timed_stop() -> None:
    global _active
    if _active:
        try:
            pygame.mixer.music.stop()
        except pygame.error:
            pass
        _active = False


def stop() -> None:
    global _active, _stop_timer
    if _stop_timer is not None:
        _stop_timer.cancel()
        _stop_timer = None
    if _active:
        try:
            pygame.mixer.music.stop()
        except pygame.error:
            pass
        _active = False
