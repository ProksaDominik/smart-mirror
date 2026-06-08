"""SmartMirror — Display tab (the mirror screen).

Renders the live clock, face-recognition greeting, weather widget,
today's schedule, and system-status grid.  Everything is a single
gr.HTML block re-rendered by Gradio timers.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.request
from datetime import datetime
from typing import Any

import gradio as gr
import numpy as np

from inputs.registry import INPUT_RPI_CAMERA
from models.registry import MODEL_YOLO
from ui.context import AppContext
from ui.smartmirror_theme import (
    APP_VERSION,
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

# ── Weather cache ─────────────────────────────────────────────────────────────

_weather_cache: dict[str, Any] = {}
_weather_lock = threading.Lock()
_weather_fetched_at: float = 0.0
_WEATHER_TTL = 300.0

WEATHER_LOCATION = "Kortrijk"


def _weather_icon(desc: str) -> str:
    d = desc.lower()
    if "thunder" in d:
        return "⛈️"
    if "snow" in d or "blizzard" in d:
        return "🌨️"
    if "rain" in d or "drizzle" in d or "shower" in d:
        return "🌧️"
    if "fog" in d or "mist" in d or "haze" in d:
        return "🌫️"
    if "partly" in d:
        return "⛅"
    if "cloud" in d or "overcast" in d:
        return "☁️"
    if "sun" in d or "clear" in d:
        return "☀️"
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
            "temp_c": cc["temp_C"],
            "feels_c": cc["FeelsLikeC"],
            "humidity": cc["humidity"],
            "wind_kmph": cc["windspeedKmph"],
            "uv": cc.get("uvIndex", "--"),
            "desc": desc,
            "icon": _weather_icon(desc),
            "city": city,
            "country": country,
            "forecast": forecast,
        }
    except (KeyError, IndexError, TypeError):
        return {
            "temp_c": "--", "feels_c": "--", "humidity": "--",
            "wind_kmph": "--", "uv": "--", "desc": "Parse error",
            "icon": "🌡️", "city": WEATHER_LOCATION, "country": "Belgium",
            "forecast": [],
        }


# ── Face detection ────────────────────────────────────────────────────────────

def capture_frame(ctx: AppContext) -> np.ndarray | None:
    try:
        provider = ctx.providers.get(INPUT_RPI_CAMERA)
        if provider is None:
            return None
        result = provider.sync_preview("640x480", 5.0, None, None, None)
        return result.frame_rgb
    except Exception:
        return None


def detect_face(ctx: AppContext, frame: np.ndarray | None) -> dict:
    """Run YOLO face detection. Returns {name, conf, active}."""
    if frame is None:
        return {"name": None, "conf": 0.0, "active": False}
    try:
        model = ctx.models.get(MODEL_YOLO)
        if model is None:
            return {"name": None, "conf": 0.0, "active": False}
        result = model.run(frame, conf=0.5, iou=0.4)
        counts: dict[str, int] = result.payload.get("counts", {})
        if not counts:
            return {"name": None, "conf": 0.0, "active": False}
        name = max(counts, key=lambda k: counts[k])
        return {"name": name, "conf": 0.9, "active": True}
    except Exception:
        return {"name": None, "conf": 0.0, "active": False}


# ── Event helpers ─────────────────────────────────────────────────────────────

SAMPLE_EVENTS: list[dict] = [
    {"time": "09:00", "title": "Design Lecture – Room A204", "active": False},
    {"time": "11:30", "title": "SmartMirror Project Check-in", "active": True},
    {"time": "13:00", "title": "Lunch Break", "active": False},
    {"time": "14:30", "title": "Makerlab – Hardware Build", "active": False},
    {"time": "17:00", "title": "Team Stand-up (Google Meet)", "active": False},
]


def _event_tag(title: str) -> str:
    s = title.lower()
    if any(k in s for k in ("lecture", "school", "class", "stand-up", "meet")):
        return tag("School", f"rgba(123,47,255,0.2)", C_PURPLE)
    if any(k in s for k in ("project", "check-in", "lab", "makerlab", "build")):
        return tag("Project", f"rgba(0,245,255,0.15)", C_CYAN)
    return tag("Personal", f"rgba(0,255,136,0.15)", C_GREEN)


def _day_abbr(date_str: str) -> str:
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%a")
    except ValueError:
        return date_str[:3]


# ── HTML renderer ─────────────────────────────────────────────────────────────

def render_display(
    recognition: dict,
    weather_data: dict | None,
    events: list[dict],
    status: dict,
) -> str:
    now = datetime.now()
    time_str = now.strftime("%H:%M")
    date_str = now.strftime("%A, %d %B %Y")
    ampm = now.strftime("%p")

    w = _parse_weather(weather_data)

    # ── Events ──
    events_html = ""
    for ev in events[:6]:
        t = ev.get("time", "")
        title = ev.get("title", "")
        active = ev.get("active", False)
        border = f"border-left:3px solid {C_CYAN};" if active else ""
        bg = "background:rgba(0,245,255,0.05);" if active else ""
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

    # ── Forecast ──
    forecast_html = ""
    for fc in w["forecast"]:
        forecast_html += f"""
        <div style="text-align:center;flex:1;">
            <div style="font-size:10px;color:{C_MUTED};letter-spacing:.08em;
                        text-transform:uppercase;">{_day_abbr(fc['date'])}</div>
            <div style="font-size:20px;margin:4px 0;">{fc['icon']}</div>
            <div style="font-size:12px;color:#fff;">{fc['min']}°</div>
        </div>"""

    # ── Recognition ──
    name = recognition.get("name")
    conf = recognition.get("conf", 0.0)
    if name:
        recog_html = f"""
        <div style="border:2px solid {C_GREEN};border-radius:12px;padding:20px 24px;
                    background:rgba(0,255,136,0.05);">
            <div style="font-size:10px;letter-spacing:.12em;text-transform:uppercase;
                        color:{C_GREEN};margin-bottom:8px;">Recognised</div>
            <div style="font-size:26px;font-weight:500;color:#fff;margin-bottom:16px;">
                Good Morning, {name}</div>
            <div style="height:3px;background:linear-gradient(to right,{C_GREEN},transparent);
                        border-radius:2px;"></div>
        </div>"""
        footer_name = name
        footer_match = f"{conf * 100:.1f}% match"
        match_color = C_GREEN
    else:
        recog_html = f"""
        <div style="border:2px solid {C_BORDER};border-radius:12px;padding:20px 24px;
                    background:{C_CARD};">
            <div style="font-size:10px;letter-spacing:.12em;text-transform:uppercase;
                        color:{C_MUTED};margin-bottom:8px;">Waiting</div>
            <div style="font-size:22px;font-weight:400;color:{C_MUTED};margin-bottom:16px;">
                No face detected</div>
            <div style="height:3px;background:{C_BORDER};border-radius:2px;"></div>
        </div>"""
        footer_name = "—"
        footer_match = "—"
        match_color = C_MUTED

    # ── System status cards ──
    def _scrd(ok_dot: str, label: str, value: str, val_color: str) -> str:
        return (
            f'<div style="background:{C_CARD};border:1px solid {C_BORDER};'
            f'border-radius:10px;padding:14px 16px;">'
            f'<div style="font-size:11px;color:{C_MUTED};margin-bottom:6px;">'
            f'{ok_dot}{label}</div>'
            f'<div style="font-size:14px;font-weight:500;color:{val_color};">{value}</div>'
            f'</div>'
        )

    cam_ok = bool(status.get("camera"))
    led_str = status.get("led", "Off")
    led_ok = led_str.lower() == "green"
    cloud_ok = bool(status.get("cloud"))
    wapi_ok = bool(status.get("weather_api"))
    net_ok = bool(status.get("wifi", True))

    status_html = f"""
    <div style="margin-top:20px;">
        <div style="font-size:10px;letter-spacing:.12em;text-transform:uppercase;
                    color:{C_CYAN};margin-bottom:12px;">System Status</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
            {_scrd(dot(C_GREEN if cam_ok else C_RED), "Camera",
                   "Online" if cam_ok else "Offline",
                   C_GREEN if cam_ok else C_RED)}
            {_scrd(dot(C_GREEN if led_ok else C_RED), "LED",
                   led_str, C_GREEN if led_ok else C_RED)}
            {_scrd(dot(C_GREEN if cloud_ok else C_MUTED), "Cloud Sync",
                   "In Sync" if cloud_ok else "Offline",
                   C_GREEN if cloud_ok else C_MUTED)}
            {_scrd(dot(C_GREEN if wapi_ok else C_MUTED), "Weather API",
                   "Live" if wapi_ok else "Offline",
                   C_GREEN if wapi_ok else C_MUTED)}
        </div>
    </div>"""

    # ── Assemble ──
    return f"""
<div style="font-family:'Inter',sans-serif;background:#0A0A0F;
            min-height:calc(100vh - 48px);padding:32px 32px 0 32px;color:#fff;">

    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:32px;align-items:start;">

        <!-- LEFT: Clock + Schedule -->
        <div>
            <div style="font-size:88px;font-weight:300;color:#fff;letter-spacing:-3px;line-height:1;">
                {time_str}</div>
            <div style="font-size:16px;color:{C_MUTED};margin-top:10px;">{date_str}</div>
            <div style="display:inline-block;border:1px solid {C_CYAN};color:{C_CYAN};
                        font-size:11px;padding:2px 10px;border-radius:4px;
                        margin-top:10px;letter-spacing:.06em;">{ampm}</div>

            <div style="margin-top:32px;">
                <div style="font-size:10px;letter-spacing:.12em;text-transform:uppercase;
                            color:{C_CYAN};margin-bottom:12px;">Today's Schedule</div>
                {events_html or f'<div style="color:{C_MUTED};font-size:14px;">No events today.</div>'}
            </div>
        </div>

        <!-- CENTER: Recognition -->
        <div style="padding-top:16px;">
            {recog_html}
        </div>

        <!-- RIGHT: Weather + System Status -->
        <div>
            <div style="background:{C_CARD};border:1px solid {C_BORDER};
                        border-radius:12px;padding:20px;margin-bottom:16px;">
                <div style="display:flex;align-items:center;gap:16px;margin-bottom:16px;">
                    <span style="font-size:44px;line-height:1;">{w['icon']}</span>
                    <div>
                        <div style="font-size:36px;font-weight:300;line-height:1;">
                            {w['temp_c']}°C</div>
                        <div style="font-size:14px;color:{C_MUTED};margin-top:4px;">
                            {w['desc']}</div>
                        <div style="font-size:12px;color:{C_MUTED};">
                            {w['city']}, {w['country']}</div>
                    </div>
                </div>
                <div style="border-top:1px solid {C_BORDER};padding-top:12px;">
                    <div style="display:grid;grid-template-columns:repeat(4,1fr);
                                gap:4px;text-align:center;">
                        <div>
                            <div style="font-size:9px;color:{C_MUTED};
                                        letter-spacing:.05em;text-transform:uppercase;">Feels</div>
                            <div style="font-size:13px;margin-top:4px;">{w['feels_c']}°C</div>
                        </div>
                        <div>
                            <div style="font-size:9px;color:{C_MUTED};
                                        letter-spacing:.05em;text-transform:uppercase;">Humidity</div>
                            <div style="font-size:13px;margin-top:4px;">{w['humidity']}%</div>
                        </div>
                        <div>
                            <div style="font-size:9px;color:{C_MUTED};
                                        letter-spacing:.05em;text-transform:uppercase;">Wind</div>
                            <div style="font-size:13px;margin-top:4px;">
                                {w['wind_kmph']} km/h</div>
                        </div>
                        <div>
                            <div style="font-size:9px;color:{C_MUTED};
                                        letter-spacing:.05em;text-transform:uppercase;">UV</div>
                            <div style="font-size:13px;margin-top:4px;">{w['uv']}</div>
                        </div>
                    </div>
                </div>
                {f'<div style="border-top:1px solid {C_BORDER};padding-top:12px;display:flex;">' + forecast_html + '</div>' if forecast_html else ''}
            </div>

            {status_html}
        </div>
    </div>

    <!-- Footer bar -->
    <div style="border-top:1px solid {C_BORDER};margin-top:28px;
                padding:12px 0 16px;display:flex;justify-content:space-between;
                align-items:center;font-size:12px;color:{C_MUTED};">
        <span>SmartMirror {APP_VERSION}</span>
        <span style="color:{C_GREEN};">Connected</span>
        <span>{footer_name}</span>
        <span style="color:{match_color};">{footer_match}</span>
        <span>{now.strftime('%I:%M %p')}</span>
        <span>{w['city']} {w['temp_c']}°C</span>
        <span style="color:{C_CYAN};">Wi-Fi</span>
    </div>
</div>"""


# ── Gradio tab builder ────────────────────────────────────────────────────────

def build_display_tab(ctx: AppContext) -> dict:
    """Build the Display tab and return a dict of components for wiring."""
    with gr.TabItem("Display", id="display"):
        initial_status = {
            "camera": False, "led": "Green",
            "cloud": False, "weather_api": False, "wifi": True,
        }
        display_html = gr.HTML(
            render_display(
                recognition={"name": None, "conf": 0.0},
                weather_data=None,
                events=SAMPLE_EVENTS,
                status=initial_status,
            )
        )
        weather_state    = gr.State(None)
        recognition_state = gr.State({"name": None, "conf": 0.0})
        events_state     = gr.State(list(SAMPLE_EVENTS))
        status_state     = gr.State(initial_status)

        clock_timer   = gr.Timer(value=1.0,   active=True)
        face_timer    = gr.Timer(value=2.0,   active=True)
        weather_timer = gr.Timer(value=300.0, active=True)

    return {
        "display_html":      display_html,
        "weather_state":     weather_state,
        "recognition_state": recognition_state,
        "events_state":      events_state,
        "status_state":      status_state,
        "clock_timer":       clock_timer,
        "face_timer":        face_timer,
        "weather_timer":     weather_timer,
    }


def wire_display_callbacks(comps: dict, ctx: AppContext) -> None:
    """Attach timer callbacks for the Display tab."""
    html       = comps["display_html"]
    w_state    = comps["weather_state"]
    rec_state  = comps["recognition_state"]
    ev_state   = comps["events_state"]
    st_state   = comps["status_state"]

    # 1-second clock tick — just re-renders HTML with latest state
    comps["clock_timer"].tick(
        fn=lambda w, r, ev, st: render_display(r, w, ev, st),
        inputs=[w_state, rec_state, ev_state, st_state],
        outputs=[html],
        show_progress="hidden",
    )

    # 2-second face detection tick
    def _face_tick(w, r, ev, st):
        frame = capture_frame(ctx)
        new_r = detect_face(ctx, frame)
        new_st = {**st, "camera": frame is not None}
        return render_display(new_r, w, ev, new_st), new_r, new_st

    comps["face_timer"].tick(
        fn=_face_tick,
        inputs=[w_state, rec_state, ev_state, st_state],
        outputs=[html, rec_state, st_state],
        show_progress="hidden",
    )

    # 5-minute weather tick
    def _weather_tick(w, r, ev, st):
        new_w = fetch_weather()
        new_st = {**st, "weather_api": new_w is not None}
        return render_display(r, new_w, ev, new_st), new_w, new_st

    comps["weather_timer"].tick(
        fn=_weather_tick,
        inputs=[w_state, rec_state, ev_state, st_state],
        outputs=[html, w_state, st_state],
        show_progress="hidden",
    )
