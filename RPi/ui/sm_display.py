"""SmartMirror — Display tab.

Layout: left panel (clock + schedule) | center (greeting + annotated camera) | right panel (weather + status)
Camera uses browser-side streaming webcam with YOLO face recognition.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.request
from collections import Counter, deque
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import gradio as gr
import numpy as np
import PIL.Image as Image

from ui.context import AppContext
from ui.smartmirror_theme import (
    C_BORDER,
    C_CARD,
    C_CYAN,
    C_GREEN,
    C_MUTED,
    C_PURPLE,
    C_RED,
    dot,
    tag,
)

# Currently recognised person — set once per session, read by Operating tab.
_current_user: str = ""

# ── Raspberry Pi Camera (Picamera2, lazy-loaded once) ─────────────────────────

_picam2 = None
_picam2_lock = threading.Lock()


def _get_picam():
    global _picam2
    if _picam2 is not None:
        return _picam2
    with _picam2_lock:
        if _picam2 is None:
            try:
                from picamera2 import Picamera2
                cam = Picamera2()
                cam.configure(cam.create_preview_configuration(
                    main={"format": "RGB888", "size": (640, 480)}
                ))
                cam.start()
                _picam2 = cam
                print("[PiCam] Started successfully")
            except Exception as exc:
                print(f"[PiCam] Failed to start: {exc}")
    return _picam2


def capture_frame() -> Image.Image | None:
    """Capture one frame from the Pi camera. Returns a PIL RGB image or None on failure."""
    cam = _get_picam()
    if cam is None:
        return None
    try:
        frame = cam.capture_array()
        # Picamera2's "RGB888" format is actually BGR-ordered in practice
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        # NOT flipped here — this frame feeds YOLO recognition, and the model
        # was trained on un-mirrored faces. Flip only at display time.
        return Image.fromarray(frame)
    except Exception as exc:
        print(f"[PiCam] Capture error: {exc}")
        return None


# Background frame buffer — updated by a daemon thread for smooth display
_latest_frame: Image.Image | None = None
_frame_lock = threading.Lock()


def _start_capture_thread() -> None:
    def _loop():
        global _latest_frame
        while True:
            img = capture_frame()
            if img is not None:
                with _frame_lock:
                    _latest_frame = img
            time.sleep(0.08)   # ~12 fps capture

    t = threading.Thread(target=_loop, daemon=True)
    t.start()


def get_latest_frame() -> Image.Image | None:
    with _frame_lock:
        return _latest_frame


_start_capture_thread()


# ── YOLO model (lazy-loaded once) ─────────────────────────────────────────────

_yolo_model = None
_yolo_lock = threading.Lock()
_MODEL_PATH = Path(__file__).resolve().parent.parent.parent / "Laptop" / "best.pt"


def _get_model():
    global _yolo_model
    if _yolo_model is not None:
        return _yolo_model
    with _yolo_lock:
        if _yolo_model is None:
            try:
                from ultralytics import YOLO
                print(f"[YOLO] Loading model from {_MODEL_PATH}...")
                _yolo_model = YOLO(str(_MODEL_PATH))
                print(f"[YOLO] Model loaded successfully")
            except Exception as e:
                print(f"[YOLO] ERROR: Could not load model from {_MODEL_PATH}: {e}")
                import traceback
                traceback.print_exc()
    return _yolo_model


# ── Weather cache ─────────────────────────────────────────────────────────────

_weather_cache: dict[str, Any] = {}
_weather_lock = threading.Lock()
_weather_fetched_at: float = 0.0
_WEATHER_TTL = 300.0

WEATHER_LOCATION = "Kortrijk"


def _weather_icon(desc: str) -> str:
    d = desc.lower()
    if "thunder" in d:                              return "⛈️"
    if "snow" in d or "blizzard" in d:              return "🌨️"
    if "rain" in d or "drizzle" in d or "shower" in d: return "🌧️"
    if "fog" in d or "mist" in d or "haze" in d:   return "🌫️"
    if "partly" in d:                               return "⛅"
    if "cloud" in d or "overcast" in d:             return "☁️"
    if "sun" in d or "clear" in d:                  return "☀️"
    return "🌡️"


def fetch_weather(location: str = WEATHER_LOCATION) -> dict[str, Any] | None:
    global _weather_fetched_at
    now = time.monotonic()
    with _weather_lock:
        if now - _weather_fetched_at < _WEATHER_TTL and _weather_cache:
            return dict(_weather_cache)
    try:
        url = f"https://wttr.in/{location}?format=j1"
        req = urllib.request.Request(url, headers={"User-Agent": "SmartMirror/1.3"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        with _weather_lock:
            _weather_cache.clear()
            _weather_cache.update(data)
            _weather_fetched_at = time.monotonic()
        return data
    except Exception:
        with _weather_lock:
            return dict(_weather_cache) if _weather_cache else None


def _parse_weather(data: dict | None) -> dict:
    if not data:
        return {
            "temp_c": "--", "feels_c": "--", "humidity": "--",
            "wind_kmph": "--", "uv": "--", "desc": "Unavailable",
            "icon": "🌡️", "city": WEATHER_LOCATION, "country": "Belgium",
            "forecast": [],
        }
    try:
        cc = data["current_condition"][0]
        area = data["nearest_area"][0]
        city = area["areaName"][0]["value"]
        country = area["country"][0]["value"]
        desc = cc["weatherDesc"][0]["value"]
        forecast = []
        for day in data.get("weather", [])[:3]:
            hourly = day.get("hourly", [])
            day_desc = hourly[4]["weatherDesc"][0]["value"] if len(hourly) > 4 else desc
            forecast.append({
                "date": day["date"],
                "min": day["mintempC"],
                "max": day["maxtempC"],
                "icon": _weather_icon(day_desc),
            })
        return {
            "temp_c": cc["temp_C"], "feels_c": cc["FeelsLikeC"],
            "humidity": cc["humidity"], "wind_kmph": cc["windspeedKmph"],
            "uv": cc.get("uvIndex", "--"), "desc": desc,
            "icon": _weather_icon(desc), "city": city, "country": country,
            "forecast": forecast,
        }
    except (KeyError, IndexError, TypeError):
        return {
            "temp_c": "--", "feels_c": "--", "humidity": "--",
            "wind_kmph": "--", "uv": "--", "desc": "Parse error",
            "icon": "🌡️", "city": WEATHER_LOCATION, "country": "Belgium",
            "forecast": [],
        }


# ── Event helpers ─────────────────────────────────────────────────────────────

SAMPLE_EVENTS: list[dict] = [
    {"time": "09:00", "title": "Design Lecture – Room A204",     "active": False},
    {"time": "11:30", "title": "SmartMirror Project Check-in",   "active": True},
    {"time": "13:00", "title": "Lunch Break",                    "active": False},
    {"time": "14:30", "title": "Makerlab – Hardware Build",      "active": False},
    {"time": "17:00", "title": "Team Stand-up (Google Meet)",    "active": False},
]


def _event_tag(title: str) -> str:
    s = title.lower()
    if any(k in s for k in ("lecture", "school", "class", "stand-up", "meet")):
        return tag("School",   "rgba(123,47,255,0.2)",  C_PURPLE)
    if any(k in s for k in ("project", "check-in", "lab", "makerlab", "build")):
        return tag("Project",  "rgba(108,92,231,0.15)",  C_CYAN)
    return tag("Personal", "rgba(0,255,136,0.15)", C_GREEN)


def _day_abbr(date_str: str) -> str:
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%a")
    except ValueError:
        return date_str[:3]


# ── Panel renderers ───────────────────────────────────────────────────────────

def _render_left(events: list[dict]) -> str:
    events_html = ""
    for ev in events[:6]:
        t      = ev.get("time", "")
        title  = ev.get("title", "")
        active = ev.get("active", False)
        border = f"border-left:3px solid {C_CYAN};" if active else ""
        bg     = "background:rgba(108,92,231,0.05);" if active else ""
        events_html += f"""
        <div style="background:{C_CARD};{bg}border-radius:10px;padding:12px 16px;
                    margin-bottom:8px;{border}display:flex;justify-content:space-between;
                    align-items:center;">
            <div>
                <div style="font-size:12px;color:{C_MUTED};margin-bottom:2px;">{t}</div>
                <div style="font-size:14px;color:#fff;">{title}</div>
            </div>
            {_event_tag(title)}
        </div>"""

    return f"""
<div style="font-family:'Inter',sans-serif;background:#0A0A0F;
            height:100%;padding:32px 24px;color:#fff;">
    <div id="sm-time" style="font-size:88px;font-weight:300;color:#fff;
                             letter-spacing:-3px;line-height:1;">--:--</div>
    <div id="sm-date" style="font-size:16px;color:{C_MUTED};margin-top:10px;"></div>
    <div id="sm-ampm" style="display:inline-block;border:1px solid {C_CYAN};color:{C_CYAN};
                font-size:11px;padding:2px 10px;border-radius:4px;
                margin-top:10px;letter-spacing:.06em;"></div>
    <div style="margin-top:32px;">
        <div style="font-size:10px;letter-spacing:.12em;text-transform:uppercase;
                    color:{C_CYAN};margin-bottom:12px;">Today's Schedule</div>
        {events_html or f'<div style="color:{C_MUTED};font-size:14px;">No events today.</div>'}
    </div>
</div>"""


def _render_display_tasks(tasks: list[dict]) -> str:
    if not tasks:
        return ""
    from datetime import date as _date
    today = _date.today().isoformat()
    rows = ""
    for t in tasks:
        if t.get("completed"):
            continue
        title = t.get("title", t.get("text", ""))
        due   = t.get("due", "")
        is_today = due == today
        color = C_CYAN if is_today else C_MUTED
        today_label = f'<div style="font-size:11px;color:{C_CYAN};margin-top:2px;">Today</div>' if is_today else ""
        rows += (
            f'<div style="background:{C_CARD};border-radius:10px;padding:10px 14px;'
            f'margin-bottom:6px;border-left:3px solid {color};">'
            f'<div style="font-size:13px;color:#fff;">{title}</div>'
            f'{today_label}'
            f'</div>'
        )
    if not rows:
        return ""
    return (
        f'<div style="font-family:Bebas Neue,sans-serif;padding:0 24px 24px;">'
        f'<div style="font-size:10px;letter-spacing:.12em;text-transform:uppercase;'
        f'color:{C_CYAN};margin-bottom:10px;">To-Do List</div>'
        f'{rows}</div>'
    )


def _render_right(weather_data: dict | None, status: dict) -> str:
    w = _parse_weather(weather_data)

    forecast_html = ""
    for fc in w["forecast"]:
        forecast_html += f"""
        <div style="text-align:center;flex:1;">
            <div style="font-size:10px;color:{C_MUTED};letter-spacing:.08em;
                        text-transform:uppercase;">{_day_abbr(fc['date'])}</div>
            <div style="font-size:20px;margin:4px 0;">{fc['icon']}</div>
            <div style="font-size:12px;color:#fff;">{fc['min']}°</div>
        </div>"""

    def _scrd(ok_dot: str, label: str, value: str, val_color: str) -> str:
        return (
            f'<div style="background:{C_CARD};border:1px solid {C_BORDER};'
            f'border-radius:10px;padding:14px 16px;">'
            f'<div style="font-size:11px;color:{C_MUTED};margin-bottom:6px;">'
            f'{ok_dot}{label}</div>'
            f'<div style="font-size:14px;font-weight:500;color:{val_color};">{value}</div>'
            f'</div>'
        )

    cam_ok   = bool(status.get("camera"))
    led_str  = status.get("led", "Off")
    led_ok   = led_str.lower() == "green"
    cloud_ok = bool(status.get("cloud"))
    wapi_ok  = bool(status.get("weather_api"))

    return f"""
<div style="font-family:'Inter',sans-serif;background:#0A0A0F;
            height:100%;padding:32px 24px;color:#fff;">
    <div style="background:{C_CARD};border:1px solid {C_BORDER};
                border-radius:12px;padding:20px;margin-bottom:16px;">
        <div style="display:flex;align-items:center;gap:16px;margin-bottom:16px;">
            <span style="font-size:44px;line-height:1;">{w['icon']}</span>
            <div>
                <div style="font-size:36px;font-weight:300;line-height:1;">{w['temp_c']}°C</div>
                <div style="font-size:14px;color:{C_MUTED};margin-top:4px;">{w['desc']}</div>
                <div style="font-size:12px;color:{C_MUTED};">{w['city']}, {w['country']}</div>
            </div>
        </div>
        <div style="border-top:1px solid {C_BORDER};padding-top:12px;">
            <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:4px;text-align:center;">
                <div>
                    <div style="font-size:9px;color:{C_MUTED};letter-spacing:.05em;
                                text-transform:uppercase;">Feels</div>
                    <div style="font-size:13px;margin-top:4px;">{w['feels_c']}°C</div>
                </div>
                <div>
                    <div style="font-size:9px;color:{C_MUTED};letter-spacing:.05em;
                                text-transform:uppercase;">Humidity</div>
                    <div style="font-size:13px;margin-top:4px;">{w['humidity']}%</div>
                </div>
                <div>
                    <div style="font-size:9px;color:{C_MUTED};letter-spacing:.05em;
                                text-transform:uppercase;">Wind</div>
                    <div style="font-size:13px;margin-top:4px;">{w['wind_kmph']} km/h</div>
                </div>
                <div>
                    <div style="font-size:9px;color:{C_MUTED};letter-spacing:.05em;
                                text-transform:uppercase;">UV</div>
                    <div style="font-size:13px;margin-top:4px;">{w['uv']}</div>
                </div>
            </div>
        </div>
        {f'<div style="border-top:1px solid {C_BORDER};padding-top:12px;display:flex;">' + forecast_html + '</div>' if forecast_html else ''}
    </div>

    <div>
        <div style="font-size:10px;letter-spacing:.12em;text-transform:uppercase;
                    color:{C_CYAN};margin-bottom:12px;">System Status</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
            {_scrd(dot(C_GREEN if cam_ok  else C_RED), "Camera",
                   "Online"   if cam_ok  else "Offline", C_GREEN if cam_ok  else C_RED)}
            {_scrd(dot(C_GREEN if led_ok  else C_RED), "LED",
                   led_str,                              C_GREEN if led_ok  else C_RED)}
            {_scrd(dot(C_GREEN if cloud_ok else C_MUTED), "Cloud Sync",
                   "In Sync"  if cloud_ok else "Offline", C_GREEN if cloud_ok else C_MUTED)}
            {_scrd(dot(C_GREEN if wapi_ok  else C_MUTED), "Weather API",
                   "Live"     if wapi_ok  else "Offline", C_GREEN if wapi_ok  else C_MUTED)}
        </div>
    </div>
</div>"""


# ── YOLO face recognition ─────────────────────────────────────────────────────

# ── Recognition tuning ───────────────────────────────────────────────────────
_DRAW_CONF      = 0.30   # min conf to draw a box at all
_GREET_CONF     = 0.30   # min conf for a frame to count as any vote (known or unknown)
_ID_CONF        = 0.70   # min conf to vote FOR A SPECIFIC NAME; below this → "__unknown__"
_PER_NAME_CONF  = {"Radu": 0.55, "Liviu": 0.55}  # lower bar for names the model is less confident on
_MIN_FACE_FRAC  = 0.05   # face narrower than 5 % of frame → "come closer"
_ZOOM_FACE_FRAC = 0.20   # face narrower than 20 % of frame → re-run on zoomed crop
_VOTE_WINDOW    = 10     # how many recent frames we remember
_VOTE_MIN       = 5      # same name must win this many votes to be greeted
_NAME_HOLD_SEC  = 10.0   # keep the greeting up this long after confirmation
_AUTO_RESET_SEC = 300.0  # auto-reset 5 min after a confirmation, ready for the next face
_RECOG_INTERVAL = 1.5    # seconds between recognition attempts in the background loop

_votes: deque = deque(maxlen=_VOTE_WINDOW)
_confirmed_name: str | None = None
_confirmed_at: float = 0.0

# Module-level scan state — reset by demo.load() on every page refresh
_scan_state: dict = {"done": False, "initialized": False}


def reset_scan_state() -> None:
    """Called on every page load (and on button press / auto-reset) to wipe
    recognition state (but keep model in memory for speed)."""
    global _current_user, _confirmed_name, _confirmed_at

    # Only clear voting and confirmation state — do NOT unload the model
    # Keeping the model in memory prevents slow reload on page refresh
    _votes.clear()
    _confirmed_name = None
    _confirmed_at = 0.0
    _current_user = ""

    from ui import music as _music
    _music.stop()
    _scan_state["done"] = False
    _scan_state["initialized"] = False
    print("[YOLO] Recognition state reset (model kept in memory for speed)")


def _largest_box(result):
    """Return (x1, y1, x2, y2, name, conf) of the widest box, or None."""
    if result.boxes is None or len(result.boxes) == 0:
        return None
    best = max(result.boxes, key=lambda b: float(b.xyxy[0][2] - b.xyxy[0][0]))
    x1, y1, x2, y2 = map(int, best.xyxy[0].tolist())
    return x1, y1, x2, y2, result.names[int(best.cls)], float(best.conf)


def _predict_frame(
    img: Image.Image | None,
    iou_threshold: float = 0.45,
) -> tuple[Image.Image | None, str]:
    global _confirmed_name, _confirmed_at

    if img is None:
        return None, "No one detected"

    model = _get_model()
    if model is None:
        return img, "Model loading..."

    img_np  = np.array(img.convert("RGB"))
    img_bgr = np.ascontiguousarray(img_np[..., ::-1])
    H, W    = img_bgr.shape[:2]

    try:
        result = model.predict(
            source=img_bgr, conf=_DRAW_CONF, iou=iou_threshold,
            imgsz=640, verbose=False,
        )[0]
    except Exception as e:
        print(f"[YOLO] Prediction error: {e}")
        # Reset model on error and try again next frame
        import traceback
        traceback.print_exc()
        global _yolo_model
        _yolo_model = None
        return img, "Model error - reinitializing..."
    
    box = _largest_box(result)
    print(f"[YOLO] boxes={len(result.boxes) if result.boxes else 0} best={f'{box[4]} {box[5]:.2f}' if box else 'none'}")

    name: str | None = None
    conf = 0.0
    too_far = False

    if box:
        x1, y1, x2, y2, name, conf = box
        face_w = x2 - x1

        if face_w < _MIN_FACE_FRAC * W:
            too_far, name = True, None
        elif face_w < _ZOOM_FACE_FRAC * W:
            # Face is smallish: crop a square around it and re-run so the
            # model classifies a close-up face instead of a tiny blur.
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            side   = int(max(face_w, y2 - y1) * 2.2)
            cx1, cy1 = max(0, cx - side // 2), max(0, cy - side // 2)
            cx2, cy2 = min(W, cx1 + side), min(H, cy1 + side)
            crop = np.ascontiguousarray(img_bgr[cy1:cy2, cx1:cx2])
            zres = model.predict(
                source=crop, conf=_DRAW_CONF, iou=iou_threshold,
                imgsz=640, verbose=False,
            )[0]
            zbox = _largest_box(zres)
            if zbox:
                name, conf = zbox[4], zbox[5]

    # Vote: above threshold → specific name; face detected but below → "__unknown__".
    if name and conf >= _PER_NAME_CONF.get(name, _ID_CONF):
        vote = name
    elif box is not None and not too_far:
        vote = "__unknown__"   # Face seen but not confident enough to name
    else:
        vote = None
    _votes.append(vote)
    tally = Counter(v for v in _votes if v)
    if tally:
        winner, n = tally.most_common(1)[0]
        if n >= _VOTE_MIN:
            _confirmed_name, _confirmed_at = winner, time.monotonic()

    if _confirmed_name and time.monotonic() - _confirmed_at < _NAME_HOLD_SEC:
        if _confirmed_name == "__unknown__":
            summary = "Unregistered face recognized"
        else:
            summary = f"{_time_period()}, {_confirmed_name}"
    elif too_far:
        summary = "Come closer to the camera"
    elif box:
        summary = "Scanning..."
    else:
        summary = "No one detected"

    return img, summary


_last_recognized_at: float = 0.0
_PERIODS = ("Good Morning, ", "Good Afternoon, ", "Good Evening, ")

# Updated every loop tick regardless of confirmation state — "is anyone
# (known or unknown) actually visible right now?" Unlike _current_user
# (which intentionally stays set for _AUTO_RESET_SEC so greeting/tasks don't
# flicker away), this is for things that should react immediately to real
# presence, like turning the screen on/off.
_face_present: bool = False


def _recognition_loop() -> None:
    """Runs continuously in the background — independent of any browser tab being
    open. Drives _current_user so the kiosk works standalone, with no dashboard
    session needed to 'keep recognition alive'."""
    global _current_user, _last_recognized_at, _face_present

    while True:
        time.sleep(_RECOG_INTERVAL)
        try:
            # Auto-reset N seconds after a confirmation so the next new face
            # gets recognised fresh, with its own correctly synced to-do list.
            if _current_user and time.monotonic() - _last_recognized_at > _AUTO_RESET_SEC:
                print(f"[YOLO] Auto-reset after {_AUTO_RESET_SEC:.0f}s — ready for a new face")
                reset_scan_state()
                continue

            img = get_latest_frame()
            if img is None:
                _face_present = False
                continue

            _, summary = _predict_frame(img)
            _face_present = summary not in ("No one detected", "Come closer to the camera")

            if _current_user:
                continue  # already confirmed and within the hold window — skip re-greeting

            print(f"[RECOG] summary={summary!r}")

            if summary == "Unregistered face recognized":
                _current_user = "__unknown__"
                _last_recognized_at = time.monotonic()
                threading.Thread(target=_unknown_audio, daemon=True).start()
                continue

            for prefix in _PERIODS:
                if summary.startswith(prefix):
                    name = summary[len(prefix):]
                    _current_user = name
                    _last_recognized_at = time.monotonic()
                    threading.Thread(target=_welcome_audio, args=(name,), daemon=True).start()
                    break
        except Exception as exc:
            print(f"[RECOG] background loop error: {exc}")


def _start_recognition_thread() -> None:
    t = threading.Thread(target=_recognition_loop, daemon=True)
    t.start()


_BUTTON_DEVICE_PATH = "/dev/input/by-path/platform-pwr_button-event"  # Pi 5's dedicated power button
_BUTTON_LONG_PRESS_SEC = 1.5  # presses held longer than this are shutdown territory


def _button_listener_loop() -> None:
    """Short press of the physical button resets recognition, ready for a new
    face. Long press shuts the Pi down.

    Cannot use an exclusive grab (EVIOCGRAB) here — labwc itself holds this
    device open at all times (Wayland compositors must own raw input
    devices to function), so a second exclusive grab always fails with
    EBUSY. We just read non-exclusively alongside it instead."""
    try:
        import evdev
    except ImportError:
        print("[Button] evdev not installed — physical button disabled")
        return

    try:
        dev = evdev.InputDevice(_BUTTON_DEVICE_PATH)
    except Exception as exc:
        print(f"[Button] Could not open {_BUTTON_DEVICE_PATH}: {exc}")
        return

    pressed_at: float | None = None
    for event in dev.read_loop():
        if event.type != evdev.ecodes.EV_KEY or event.code != evdev.ecodes.KEY_POWER:
            continue
        if event.value == 1:  # key down
            pressed_at = time.monotonic()
        elif event.value == 0 and pressed_at is not None:  # key up
            held = time.monotonic() - pressed_at
            pressed_at = None
            if held < _BUTTON_LONG_PRESS_SEC:
                print(f"[Button] Short press ({held:.2f}s) — resetting, ready for a new face")
                reset_scan_state()
            else:
                print(f"[Button] Long press ({held:.2f}s) — shutting down")
                import subprocess
                subprocess.Popen(
                    ["sudo", "poweroff"],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )


def _start_button_listener_thread() -> None:
    t = threading.Thread(target=_button_listener_loop, daemon=True)
    t.start()


def _start_screen_power_thread() -> None:
    """Disabled by choice: real HDMI signal cutoff (via hardware/display_power.py,
    wlr-randr --off/--on) works correctly on this hardware, but the monitor
    shows its own built-in "No Signal" message while off — that's the
    monitor's firmware, not something software can suppress. Decided to
    keep the signal always on and rely purely on the black content page in
    render_mirror() (when no face is present) instead, so nothing but black
    is ever shown — at the cost of not actually saving power."""
    pass


def _time_period() -> str:
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return "Good Morning"
    if 12 <= hour < 18:
        return "Good Afternoon"
    return "Good Evening"


def _greeting_html(summary: str) -> str:
    """Idle / scanning state (no recognition yet)."""
    return (
        f'<div style="background:{C_CARD};border:1px solid {C_BORDER};border-radius:12px;'
        f'padding:16px 24px;text-align:center;font-family:Bebas Neue,sans-serif;margin-bottom:8px;">'
        f'<div style="font-size:13px;color:{C_MUTED};letter-spacing:.08em;">{summary}</div>'
        f'</div>'
    )


def _recognised_html(name: str) -> str:
    """Permanent greeting shown once a known face is confirmed."""
    period = _time_period()
    return (
        f'<div style="background:#0A1F1F;border:2px solid {C_CYAN};border-radius:12px;'
        f'padding:16px 24px;text-align:center;font-family:Bebas Neue,sans-serif;margin-bottom:8px;">'
        f'<div style="font-size:10px;color:{C_CYAN};letter-spacing:.12em;'
        f'text-transform:uppercase;margin-bottom:6px;">Recognised</div>'
        f'<div style="font-size:22px;font-weight:600;color:#fff;">{period}, {name}</div>'
        f'<div style="height:3px;background:linear-gradient(90deg,{C_CYAN},{C_GREEN});'
        f'border-radius:2px;margin-top:10px;"></div>'
        f'</div>'
    )


def _unregistered_html() -> str:
    """Card shown when a face is detected but not in the registered dataset."""
    return (
        f'<div style="background:#1F0A0A;border:2px solid {C_RED};border-radius:12px;'
        f'padding:16px 24px;text-align:center;font-family:Bebas Neue,sans-serif;margin-bottom:8px;">'
        f'<div style="font-size:10px;color:{C_RED};letter-spacing:.12em;'
        f'text-transform:uppercase;margin-bottom:6px;">Unknown</div>'
        f'<div style="font-size:18px;font-weight:600;color:#fff;">Unregistered face recognized</div>'
        f'<div style="height:3px;background:linear-gradient(90deg,{C_RED},#FF8C33);'
        f'border-radius:2px;margin-top:10px;"></div>'
        f'</div>'
    )


# ── Gradio tab builder ────────────────────────────────────────────────────────

def build_display_tab(ctx: AppContext, initial_weather=None) -> dict:
    initial_status = {
        "camera": True, "led": "Green",
        "cloud": False, "weather_api": initial_weather is not None,
    }

    with gr.TabItem("Operating", id="display"):
        with gr.Row():

            # LEFT: clock + schedule + to-do list (populated after face scan)
            with gr.Column(scale=1):
                left_html    = gr.HTML(_render_left([]), sanitize_html=False)
                tasks_html   = gr.HTML(_render_display_tasks([]), sanitize_html=False)

            # CENTER: Pi camera feed + automatic face recognition
            with gr.Column(scale=2):
                greeting_html = gr.HTML(
                    _greeting_html("Looking for a face…"),
                    sanitize_html=False,
                )
                cam_image = gr.Image(
                    label="Camera",
                    show_label=False,
                    container=False,
                    interactive=False,
                )
                cam_timer      = gr.Timer(value=0.1,  active=True)   # display ~10 fps
                recog_timer    = gr.Timer(value=1.5,  active=True)   # YOLO recognition

            # RIGHT: weather + system status
            with gr.Column(scale=1):
                right_html = gr.HTML(
                    _render_right(initial_weather, initial_status),
                    sanitize_html=False,
                )

        weather_state      = gr.State(initial_weather)
        events_state       = gr.State([])
        status_state       = gr.State(initial_status)
        current_user_state = gr.State("")   # Set when a face is confirmed
        synced_user_state  = gr.State("")   # Tracks who was last synced
        weather_timer      = gr.Timer(value=300.0, active=True)
        sync_timer         = gr.Timer(value=2.0, active=True)

    return {
        "left_html":          left_html,
        "tasks_html":         tasks_html,
        "right_html":         right_html,
        "greeting_html":      greeting_html,
        "cam_image":          cam_image,
        "cam_timer":          cam_timer,
        "recog_timer":        recog_timer,
        "weather_state":      weather_state,
        "events_state":       events_state,
        "status_state":       status_state,
        "current_user_state": current_user_state,
        "synced_user_state":  synced_user_state,
        "weather_timer":      weather_timer,
        "sync_timer":         sync_timer,
    }


def _welcome_audio(name: str) -> None:
    """Speak a personalised greeting then read today's tasks. Runs in a daemon thread."""
    try:
        from ui import voice as _voice
        from ui import music as _music
        import time

        # Person-specific background track, looped until button press / auto-reset
        # (see reset_scan_state()) — not stopped when the speech finishes.
        _music.play_under(_music.track_for_person(name))

        # Greeting — plays while the calendar sync runs in parallel
        _voice.speak(f"{_time_period()} sir!")

        # Read today's tasks
        try:
            import db, random
            from datetime import date as _date

            # Sync the calendar directly here instead of waiting on the
            # separate 2s-polling sync timer (a fixed sleep was racing
            # against that timer's actual network call and often lost,
            # leaving the voice reading a stale/empty task list).
            try:
                from pathlib import Path as _Path
                from ui.sm_operating import try_google_calendar_sync, events_to_cal_tasks
                base_dir = _Path(__file__).resolve().parent.parent
                events, _msg = try_google_calendar_sync(base_dir, name)
                db.replace_calendar_tasks(events_to_cal_tasks(events))
            except Exception as sync_exc:
                print(f"[Welcome audio sync] {sync_exc}")

            today = _date.today().isoformat()
            tasks = [
                t for t in db.load_tasks()
                if t.get("due") == today and not t.get("completed")
            ]

            import re as _re

            _ACTION_VERBS = {
                "go", "buy", "pick", "call", "visit", "meet", "send", "check",
                "pay", "get", "attend", "finish", "complete", "submit", "take",
                "bring", "book", "do", "make", "fix", "clean", "prepare",
                "review", "update", "write", "read", "email", "text", "order",
                "plan", "confirm", "cancel", "reply", "respond", "print", "sign",
                "return", "collect", "drop", "deliver", "watch", "study",
                "practice", "grab", "join", "schedule", "organise", "organize",
            }
            _VERB_STARTERS = [
                "you need to", "don't forget to", "you've got to",
                "make sure to", "remember to", "you should",
            ]
            _NOUN_STARTERS = [
                "you've got", "you have", "don't forget you have",
                "remember you have", "there's",
            ]

            def _naturalize(title: str) -> str:
                t = title.strip()
                first_word = t.split()[0].lower() if t else ""
                if first_word in _ACTION_VERBS:
                    return f"{random.choice(_VERB_STARTERS)} {t.lower()}"
                return f"{random.choice(_NOUN_STARTERS)} {t.lower()}"

            def _task_phrase(task: dict) -> str:
                """Build a natural spoken phrase for a task, placing any time at the end."""
                raw = (task.get("title") or task.get("text") or "").strip()
                # Calendar tasks come as "16:00 – Buy flowers" — split time from title
                m = _re.match(r'^(\d{1,2}:\d{2})\s*[–\-]\s*(.+)$', raw)
                if m:
                    time_str = m.group(1)
                    title    = m.group(2).strip()
                    return f"{_naturalize(title)} at {time_str}"
                return _naturalize(raw)

            connectors = ["after that", "then", "also", "and later"]

            if not tasks:
                _voice.speak("Your to do list is clear today, sir. Take it easy and enjoy the day!")
            elif len(tasks) == 1:
                _voice.speak(
                    f"Just one thing on your plate today, sir. {_task_phrase(tasks[0])}. "
                    f"Make it count. Have a great day!"
                )
            elif len(tasks) == 2:
                t0 = _task_phrase(tasks[0])
                t1 = _task_phrase(tasks[1])
                _voice.speak(
                    f"You have two things lined up today, sir. First, {t0}. "
                    f"And {t1}. Stay on top of it. Have a wonderful day!"
                )
            else:
                items = tasks[:4]
                parts = []
                for i, t in enumerate(items):
                    if i == 0:
                        parts.append(f"first, {_task_phrase(t)}")
                    elif i == len(items) - 1:
                        parts.append(f"and finally, {_task_phrase(t)}")
                    else:
                        parts.append(f"{random.choice(connectors)}, {_task_phrase(t)}")
                extra = f" You also have {len(tasks) - 4} more after that." if len(tasks) > 4 else ""
                _voice.speak(
                    f"You've got {len(tasks)} things on your to do list today, sir. "
                    + ". ".join(parts) + f".{extra} Stay sharp and have a brilliant day!"
                )
        except Exception as exc:
            print(f"[Welcome audio tasks] {exc}")

        # Music keeps looping after speech ends — stopped only by a button
        # press or auto-reset (reset_scan_state()), not here.
    except Exception as exc:
        print(f"[Welcome audio] {exc}")


def _unknown_audio() -> None:
    """Speak a short message when an unregistered face is detected. Runs in a daemon thread."""
    from ui import music as _music
    try:
        from ui import voice as _voice
        _music.play_under(_music.track_for_person("__unknown__"))
        _voice.speak("I don't recognise you. Please register your face to use the mirror.")
        # Music keeps looping after speech ends — stopped only by a button
        # press or auto-reset (reset_scan_state()), not here.
    except Exception as exc:
        print(f"[Unknown audio] {exc}")


def wire_display_callbacks(comps: dict, ctx: AppContext, op_comps: dict | None = None) -> None:
    def _display_tick():
        """Fast tick — pushes the latest camera frame to the UI, mirrored for display only."""
        img = get_latest_frame()
        if img is not None:
            img = Image.fromarray(np.fliplr(np.array(img)))
        return gr.update(value=img)

    comps["cam_timer"].tick(
        fn=_display_tick,
        outputs=[comps["cam_image"]],
        show_progress="hidden",
    )

    def _recog_tick(_session_user):
        """UI-only tick — reflects whatever the background recognition loop
        (_recognition_loop, runs independent of any browser session) found."""
        name = _current_user

        if name == "__unknown__":
            return _unregistered_html(), "__unknown__"

        if name:
            return _recognised_html(name), name

        if get_latest_frame() is None:
            return _greeting_html("Camera not available…"), ""

        return _greeting_html("Looking for a face…"), ""

    comps["recog_timer"].tick(
        fn=_recog_tick,
        inputs=[comps["current_user_state"]],
        outputs=[comps["greeting_html"], comps["current_user_state"]],
        show_progress="hidden",
    )

    def _weather_tick(w, st):
        new_w  = fetch_weather()
        new_st = {**st, "weather_api": new_w is not None}
        return _render_right(new_w, new_st), new_w, new_st

    comps["weather_timer"].tick(
        fn=_weather_tick,
        inputs=[comps["weather_state"], comps["status_state"]],
        outputs=[comps["right_html"], comps["weather_state"], comps["status_state"]],
        show_progress="hidden",
    )

    def _sync_tick(synced_user):
        """Fires every 2 s. If _current_user changed, sync calendar and update panels."""
        name = _current_user
        if not name or name == synced_user:
            return gr.update(), gr.update(), synced_user
        try:
            from ui.sm_operating import try_google_calendar_sync, events_to_cal_tasks
            import db
            events, msg = try_google_calendar_sync(ctx.base_dir, name)
            print(f"[SYNC] {name}: {len(events)} events — {msg}")
            cal_tasks = events_to_cal_tasks(events)
            try:
                db.replace_calendar_tasks(cal_tasks)
            except Exception as exc:
                print(f"[SYNC] DB error: {exc}")
            return _render_left(events), _render_display_tasks(cal_tasks), name
        except Exception as exc:
            print(f"[SYNC] failed: {exc}")
            return gr.update(), gr.update(), synced_user

    comps["sync_timer"].tick(
        fn=_sync_tick,
        inputs=[comps["synced_user_state"]],
        outputs=[comps["left_html"], comps["tasks_html"], comps["synced_user_state"]],
        show_progress="hidden",
    )


# Recognition runs in the background from the moment the app starts — no
# dashboard tab or "start" button needed. The kiosk alone is fully sufficient.
_start_recognition_thread()
_start_screen_power_thread()
_start_button_listener_thread()



#done

#done