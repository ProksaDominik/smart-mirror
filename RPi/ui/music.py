import os
import glob
import random

os.environ.setdefault("SDL_AUDIODRIVER", "pulse")
import pygame

# MP3 lives alongside this file in RPi/ui/
MUSIC_DIR = os.path.dirname(os.path.abspath(__file__))
SUPPORTED_EXTENSIONS = ("*.mp3", "*.ogg", "*.wav")

UNDER_VOLUME = 0.08
START_SECONDS = 4.0

# Per-person background track — falls back to the default for anyone else.
_TRACK_DEFAULT = "Jazz at Mladost Club - Blue bossa.mp3"
_PERSON_TRACKS = {
    "Liviu": "Jazz at Mladost Club - C-mol blues.mp3",
    "Radu":  "Jazz at Mladost Club - No More Blues.mp3",
}

_active = False
_played_once = False


def _find_tracks() -> list[str]:
    tracks = []
    for pattern in SUPPORTED_EXTENSIONS:
        tracks.extend(glob.glob(os.path.join(MUSIC_DIR, pattern)))
    return tracks


def track_for_person(name: str) -> str:
    """Full path to this person's background track (default: Blue Bossa)."""
    filename = _PERSON_TRACKS.get(name, _TRACK_DEFAULT)
    return os.path.join(MUSIC_DIR, filename)


def play_under(track_path: str | None = None) -> None:
    """Loop a track indefinitely until stop() is called (button press or
    auto-reset — see reset_scan_state() in sm_display.py). Guarded by
    _played_once so a burst of speak() calls within one greeting doesn't
    restart the track — stop() resets the flag for the next greeting."""
    global _active, _played_once

    if _played_once:
        return

    track = track_path if track_path and os.path.exists(track_path) else None
    if track is None:
        tracks = _find_tracks()
        if not tracks:
            _played_once = True
            return
        track = random.choice(tracks)

    try:
        pygame.mixer.music.load(track)
        pygame.mixer.music.set_volume(UNDER_VOLUME)
        pygame.mixer.music.play(loops=-1, start=START_SECONDS)
        _active = True
        _played_once = True
    except pygame.error as exc:
        print(f"[Music error: {exc}]")
        _active = False
        _played_once = True


def stop() -> None:
    global _active, _played_once
    if _active:
        try:
            pygame.mixer.music.stop()
        except pygame.error:
            pass
        _active = False
    _played_once = False




#done