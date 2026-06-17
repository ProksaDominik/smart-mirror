"""Controls the physical HDMI display's power state via wlr-randr (labwc/Wayland).

Used so the screen is genuinely off (no backlight, no signal) when idle —
not just a blank page — and turns back on the instant a face is recognised.
"""

from __future__ import annotations

import os
import subprocess

_OUTPUT = "HDMI-A-1"


def _env() -> dict:
    env = os.environ.copy()
    env.setdefault("XDG_RUNTIME_DIR", "/run/user/1000")
    env.setdefault("WAYLAND_DISPLAY", "wayland-0")
    return env


def screen_on(output: str = _OUTPUT) -> None:
    try:
        subprocess.run(
            ["wlr-randr", "--output", output, "--on"],
            env=_env(), timeout=5, capture_output=True,
        )
    except Exception as exc:
        print(f"[Display] Could not turn screen on: {exc}")


def screen_off(output: str = _OUTPUT) -> None:
    try:
        subprocess.run(
            ["wlr-randr", "--output", output, "--off"],
            env=_env(), timeout=5, capture_output=True,
        )
    except Exception as exc:
        print(f"[Display] Could not turn screen off: {exc}")
