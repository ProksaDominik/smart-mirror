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
                _yolo_model = YOLO(str(_MODEL_PATH))
            except Exception as e:
                print(f"[YOLO] Could not load model from {_MODEL_PATH}: {e}")
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
        return tag("Project",  "rgba(0,245,255,0.15)",  C_CYAN)
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
        bg     = "background:rgba(0,245,255,0.05);" if active else ""
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
_DRAW_CONF      = 0.35   # min conf to draw a box at all
_GREET_CONF     = 0.70   # min conf for a frame to count as any vote (known or unknown)
_ID_CONF        = 0.60   # min conf to vote FOR A SPECIFIC NAME; below this → "__unknown__"
_MIN_FACE_FRAC  = 0.08   # face narrower than 8 % of frame → "come closer"
_ZOOM_FACE_FRAC = 0.30   # face narrower than 30 % of frame → re-run on zoomed crop
_VOTE_WINDOW    = 10     # how many recent frames we remember
_VOTE_MIN       = 6      # same name must win this many votes to be greeted
_NAME_HOLD_SEC  = 10.0   # keep the greeting up this long after confirmation

_votes: deque = deque(maxlen=_VOTE_WINDOW)
_confirmed_name: str | None = None
_confirmed_at: float = 0.0


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
        return img, "Model not loaded"

    img_np  = np.array(img.convert("RGB"))
    img_bgr = np.ascontiguousarray(img_np[..., ::-1])
    H, W    = img_bgr.shape[:2]

    result = model.predict(
        source=img_bgr, conf=_DRAW_CONF, iou=iou_threshold,
        imgsz=640, verbose=False,
    )[0]
    box = _largest_box(result)

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

    # Vote: above _ID_CONF → specific name; face detected but below → "__unknown__".
    if name and conf >= _ID_CONF:
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

    # Annotate the frame.
    annotated = img_bgr.copy()
    if box:
        x1, y1, x2, y2 = box[0], box[1], box[2], box[3]
        label = f"{name} {conf:.2f}" if name else "..."
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 245, 255), 2)
        cv2.putText(
            annotated, label, (x1, max(0, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 245, 255), 2,
        )

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

    return Image.fromarray(annotated[..., ::-1]), summary


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
        f'padding:16px 24px;text-align:center;font-family:Inter,sans-serif;margin-bottom:8px;">'
        f'<div style="font-size:13px;color:{C_MUTED};letter-spacing:.08em;">{summary}</div>'
        f'</div>'
    )


def _recognised_html(name: str) -> str:
    """Permanent greeting shown once a known face is confirmed."""
    period = _time_period()
    return (
        f'<div style="background:#0A1F1F;border:2px solid {C_CYAN};border-radius:12px;'
        f'padding:16px 24px;text-align:center;font-family:Inter,sans-serif;margin-bottom:8px;">'
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
        f'padding:16px 24px;text-align:center;font-family:Inter,sans-serif;margin-bottom:8px;">'
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

    with gr.TabItem("Display", id="display", render_children=False):
        with gr.Row():

            # LEFT: clock + schedule
            with gr.Column(scale=1):
                left_html = gr.HTML(_render_left(SAMPLE_EVENTS), sanitize_html=False)

            # CENTER: live webcam + automatic face recognition
            with gr.Column(scale=2):
                greeting_html = gr.HTML(
                    _greeting_html("Looking for a face…"),
                    sanitize_html=False,
                )
                webcam = gr.Image(
                    sources=["webcam"],
                    streaming=True,
                    type="pil",
                    label="Camera",
                    show_label=False,
                    container=False,
                )

            # RIGHT: weather + system status
            with gr.Column(scale=1):
                right_html = gr.HTML(
                    _render_right(initial_weather, initial_status),
                    sanitize_html=False,
                )

        weather_state      = gr.State(initial_weather)
        events_state       = gr.State(list(SAMPLE_EVENTS))
        status_state       = gr.State(initial_status)
        current_user_state = gr.State("")   # Set when a face is confirmed
        weather_timer      = gr.Timer(value=300.0, active=True)

    return {
        "left_html":          left_html,
        "right_html":         right_html,
        "greeting_html":      greeting_html,
        "webcam":             webcam,
        "weather_state":      weather_state,
        "events_state":       events_state,
        "status_state":       status_state,
        "current_user_state": current_user_state,
        "weather_timer":      weather_timer,
    }


def _welcome_audio(name: str) -> None:
    """Speak a personalised greeting and play music. Runs in a daemon thread."""
    try:
        from ui import voice as _voice
        msg = f"{_time_period()}, {name}! Welcome to your SmartMirror."
        _voice.speak(msg)
    except Exception as exc:
        print(f"[Welcome audio] {exc}")


def wire_display_callbacks(comps: dict, ctx: AppContext) -> None:
    # Reset module-level voting state so each app start is a fresh scan.
    global _votes, _confirmed_name, _confirmed_at
    _votes.clear()
    _confirmed_name = None
    _confirmed_at = 0.0

    # done=True the moment a face (known or unknown) is confirmed.
    # All subsequent stream ticks become instant no-ops — YOLO never runs again.
    _state = {"done": False}

    _PERIODS = ("Good Morning, ", "Good Afternoon, ", "Good Evening, ")

    _NOOP = (gr.update(), gr.update())   # No-op for both outputs

    def _process_frame(img):
        global _current_user
        if _state["done"]:
            return _NOOP

        if img is None:
            return _NOOP

        _, summary = _predict_frame(img)

        if summary == "Unregistered face recognized":
            _state["done"] = True
            return _unregistered_html(), "__unknown__"

        for prefix in _PERIODS:
            if summary.startswith(prefix):
                name = summary[len(prefix):]
                _current_user = name
                _state["done"] = True
                threading.Thread(target=_welcome_audio, args=(name,), daemon=True).start()
                return _recognised_html(name), name

        return _NOOP   # Still scanning — touch nothing

    comps["webcam"].stream(
        fn=_process_frame,
        inputs=[comps["webcam"]],
        outputs=[comps["greeting_html"], comps["current_user_state"]],
        stream_every=1.0,
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
