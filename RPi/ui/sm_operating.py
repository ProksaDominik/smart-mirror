"""SmartMirror — Operating tab.

Left panel : to-do list (All / Today / This Week / Completed) + today's events.
Right panel: Google Calendar sync card + mirror settings (brightness, refresh,
             wake-on-face-detect, voice greeting).
"""

from __future__ import annotations

import time
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import gradio as gr

import db
from ui.context import AppContext
from ui.sm_display import SAMPLE_EVENTS, fetch_weather
from ui.smartmirror_theme import (
    C_BG,
    C_BORDER,
    C_CARD,
    C_CYAN,
    C_GREEN,
    C_MUTED,
    C_PURPLE,
    C_RED,
    C_WHITE,
    divider,
    dot,
    tag,
)

# ── Task persistence ──────────────────────────────────────────────────────────

def load_tasks(base_dir: Path) -> list[dict]:
    try:
        return db.load_tasks()
    except Exception:
        return []


def save_tasks(base_dir: Path, tasks: list[dict]) -> None:
    try:
        db.save_all_tasks(tasks)
    except Exception:
        pass


def _new_task(text: str, due: str = "") -> dict:
    return {
        "id": str(uuid.uuid4())[:8],
        "text": text.strip(),
        "due": due or date.today().isoformat(),
        "completed": False,
        "created_at": datetime.now().isoformat(),
    }


def _today_iso() -> str:
    return date.today().isoformat()


def _this_week_end() -> str:
    return (date.today() + timedelta(days=7 - date.today().weekday())).isoformat()


# ── Events / Calendar helpers ─────────────────────────────────────────────────

_last_sync_time: str = "never"
_sync_event_count: int = 0


def try_google_calendar_sync(base_dir: Path) -> tuple[list[dict], str]:
    """Try to sync Google Calendar. Returns (events, status_message)."""
    token_path = base_dir / "token.json"
    creds_path = base_dir / "credentials.json"
    if not creds_path.exists():
        alt = base_dir / "data" / "credentials.json"
        if alt.exists():
            creds_path = alt
        else:
            return SAMPLE_EVENTS, "credentials.json not found — using sample events."
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build as gapi_build

        SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
        creds = None
        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
                creds = flow.run_local_server(port=0)
            token_path.write_text(creds.to_json())

        service = gapi_build("calendar", "v3", credentials=creds)
        today_start = datetime.combine(date.today(), datetime.min.time()).isoformat() + "Z"
        today_end = datetime.combine(date.today(), datetime.max.time()).isoformat() + "Z"
        items = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=today_start,
                timeMax=today_end,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
            .get("items", [])
        )
        events = []
        for item in items:
            start = item["start"].get("dateTime", item["start"].get("date", ""))
            t = datetime.fromisoformat(start.replace("Z", "+00:00")).strftime("%H:%M") if "T" in start else start
            events.append({"time": t, "title": item.get("summary", "(no title)"), "active": False})
        global _last_sync_time, _sync_event_count
        _last_sync_time = datetime.now().strftime("%H:%M:%S")
        _sync_event_count = len(events)
        return events, f"Synced {len(events)} events."
    except ImportError:
        return SAMPLE_EVENTS, "google-api-python-client not installed — using sample events."
    except Exception as exc:
        return SAMPLE_EVENTS, f"Sync failed: {exc}"


# ── HTML render helpers ───────────────────────────────────────────────────────

def _render_task_row(task: dict) -> str:
    text = task["text"]
    done = task["completed"]
    tid = task["id"]
    strike = f"text-decoration:line-through;color:{C_MUTED};" if done else ""
    check_color = C_GREEN if done else C_BORDER
    check_icon = "✓" if done else ""
    return f"""
<div style="display:flex;align-items:center;gap:12px;padding:12px 0;
            border-bottom:1px solid {C_BORDER};" id="task-{tid}">
    <div style="width:18px;height:18px;border-radius:4px;border:2px solid {check_color};
                display:flex;align-items:center;justify-content:center;
                font-size:11px;color:{C_GREEN};flex-shrink:0;">{check_icon}</div>
    <span style="font-size:14px;color:{C_WHITE};{strike}flex:1;">{text}</span>
    <span style="font-size:11px;color:{C_MUTED};">{task.get('due','')}</span>
</div>"""


def render_task_list(tasks: list[dict], filter_mode: str) -> str:
    today = _today_iso()
    week_end = _this_week_end()

    if filter_mode == "Today":
        shown = [t for t in tasks if t.get("due", "") == today and not t["completed"]]
    elif filter_mode == "This Week":
        shown = [t for t in tasks if today <= t.get("due", today) <= week_end and not t["completed"]]
    elif filter_mode == "Completed":
        shown = [t for t in tasks if t["completed"]]
    else:
        shown = [t for t in tasks if not t["completed"]]

    rows = "".join(_render_task_row(t) for t in shown)
    empty = (
        f'<div style="color:{C_MUTED};font-size:14px;padding:16px 0;">No tasks here.</div>'
        if not rows
        else ""
    )
    return f'<div style="font-family:Inter,sans-serif;">{rows}{empty}</div>'


def _render_event_row(ev: dict, is_active: bool = False) -> str:
    border = f"border-left:3px solid {C_CYAN};" if is_active else ""
    bg = "background:rgba(0,245,255,0.05);" if is_active else f"background:{C_CARD};"
    dot_color = C_CYAN if is_active else C_PURPLE
    return f"""
<div style="{bg}{border}border-radius:10px;padding:12px 16px;margin-bottom:8px;">
    <div style="display:flex;align-items:center;gap:10px;">
        <div style="width:10px;height:10px;border-radius:50%;
                    background:{dot_color};flex-shrink:0;"></div>
        <div>
            <div style="font-size:12px;color:{C_MUTED};">{ev.get('time','')}</div>
            <div style="font-size:14px;color:{C_WHITE};">{ev.get('title','')}</div>
        </div>
    </div>
</div>"""


def render_events_panel(events: list[dict]) -> str:
    rows = "".join(_render_event_row(ev, ev.get("active", False)) for ev in events[:6])
    return rows or f'<div style="color:{C_MUTED};font-size:14px;">No events today.</div>'


def _cal_card(last_sync: str, event_count: int, cal_ok: bool) -> str:
    status_dot = dot(C_GREEN) if cal_ok else dot(C_MUTED)
    status_text = "Connected" if cal_ok else "Not connected"
    last = last_sync if last_sync != "never" else "—"
    return f"""
<div style="background:{C_CARD};border:1px solid {C_CYAN};border-radius:12px;
            padding:20px;margin-bottom:24px;">
    <div style="display:flex;align-items:center;gap:16px;">
        <div style="background:{C_CYAN};border-radius:8px;width:44px;height:44px;
                    display:flex;align-items:center;justify-content:center;
                    font-size:20px;flex-shrink:0;">📅</div>
        <div style="flex:1;">
            <div style="font-size:16px;font-weight:600;color:{C_WHITE};">
                Google Calendar</div>
            <div style="font-size:12px;color:{C_MUTED};margin-top:2px;">
                Last synced: {last} &nbsp;·&nbsp; {event_count} events today</div>
        </div>
        <div style="font-size:14px;">{status_dot}
            <span style="color:{'#00FF88' if cal_ok else C_MUTED};">{status_text}</span>
        </div>
    </div>
</div>"""


# ── Gradio tab builder ────────────────────────────────────────────────────────

def build_operating_tab(ctx: AppContext) -> dict:
    tasks_init = load_tasks(ctx.base_dir)
    cal_ok_init = (ctx.base_dir / "token.json").exists()

    with gr.TabItem("Operating", id="operating"):

        # ── Header ──
        gr.HTML(f"""
<div style="font-family:'Inter',sans-serif;padding:18px 32px;
            border-bottom:1px solid {C_BORDER};background:{C_CARD};
            display:flex;align-items:center;justify-content:space-between;">
    <div style="display:flex;align-items:center;gap:8px;">
        <span style="font-size:20px;font-weight:700;color:{C_WHITE};">SmartMirror</span>
        <span style="font-size:16px;color:{C_PURPLE};">&nbsp;/ Operating</span>
    </div>
    <div style="display:flex;align-items:center;gap:10px;">
        <div style="width:36px;height:36px;border-radius:50%;background:{C_PURPLE};
                    display:flex;align-items:center;justify-content:center;
                    font-size:16px;">👤</div>
        <div>
            <div style="font-size:14px;font-weight:500;color:{C_WHITE};">Dominik Prokša</div>
            <div style="font-size:11px;color:{C_GREEN};">Connected</div>
        </div>
    </div>
</div>""")

        with gr.Row():
            # ── LEFT COLUMN ──────────────────────────────────────────────────
            with gr.Column(scale=1):
                gr.HTML(
                    f'<div style="font-size:10px;letter-spacing:.12em;'
                    f'text-transform:uppercase;color:{C_CYAN};'
                    f'padding:24px 0 12px;font-family:Inter,sans-serif;">'
                    f'To-Do List</div>'
                )

                filter_tabs = gr.Radio(
                    choices=["All", "Today", "This Week", "Completed"],
                    value="All",
                    label="",
                    container=False,
                )

                with gr.Row():
                    task_input = gr.Textbox(
                        placeholder="+ Add a new task for today...",
                        label="",
                        container=False,
                        scale=5,
                    )
                    add_btn = gr.Button("+", size="sm", scale=1, variant="primary")

                tasks_state = gr.State(tasks_init)
                task_list_html = gr.HTML(render_task_list(tasks_init, "All"))

                gr.HTML(
                    f'<div style="font-size:10px;letter-spacing:.12em;'
                    f'text-transform:uppercase;color:{C_CYAN};'
                    f'padding:24px 0 12px;font-family:Inter,sans-serif;">'
                    f'Today\'s Events</div>'
                )

                events_state = gr.State(list(SAMPLE_EVENTS))
                events_html = gr.HTML(render_events_panel(SAMPLE_EVENTS))

            # ── RIGHT COLUMN ─────────────────────────────────────────────────
            with gr.Column(scale=1):
                gr.HTML(
                    f'<div style="font-size:10px;letter-spacing:.12em;'
                    f'text-transform:uppercase;color:{C_CYAN};'
                    f'padding:24px 0 12px;font-family:Inter,sans-serif;">'
                    f'Calendar Sync</div>'
                )

                cal_state = gr.State({
                    "ok": cal_ok_init,
                    "last_sync": _last_sync_time,
                    "count": _sync_event_count,
                })
                cal_html = gr.HTML(
                    _cal_card(_last_sync_time, _sync_event_count, cal_ok_init)
                )
                sync_status = gr.Textbox(
                    label="Sync status", value="", interactive=False,
                    visible=False,
                )
                sync_btn = gr.Button("↻ Sync Now", variant="primary", size="sm")

                gr.HTML(
                    f'<div style="font-size:10px;letter-spacing:.12em;'
                    f'text-transform:uppercase;color:{C_CYAN};'
                    f'padding:24px 0 12px;font-family:Inter,sans-serif;">'
                    f'Mirror Settings</div>'
                )

                brightness = gr.Slider(
                    minimum=0, maximum=100, value=100, step=1,
                    label="Display Brightness",
                )
                refresh_interval = gr.Slider(
                    minimum=10, maximum=300, value=60, step=10,
                    label="Refresh Interval (seconds)",
                )
                wake_on_face = gr.Checkbox(value=True, label="Wake on Face Detect")
                voice_greeting = gr.Checkbox(value=True, label="Voice Greeting")

                gr.HTML(f'<div style="height:16px;"></div>')

        # ── Footer ──
        gr.HTML(f"""
<div style="font-family:'Inter',sans-serif;padding:12px 32px;
            border-top:1px solid {C_BORDER};text-align:right;
            font-size:12px;color:{C_GREEN};">
    All systems operational
</div>""")

    return {
        "filter_tabs":      filter_tabs,
        "task_input":       task_input,
        "add_btn":          add_btn,
        "tasks_state":      tasks_state,
        "task_list_html":   task_list_html,
        "events_state":     events_state,
        "events_html":      events_html,
        "cal_state":        cal_state,
        "cal_html":         cal_html,
        "sync_btn":         sync_btn,
        "sync_status":      sync_status,
        "brightness":       brightness,
        "refresh_interval": refresh_interval,
        "wake_on_face":     wake_on_face,
        "voice_greeting":   voice_greeting,
    }


# ── Callbacks ─────────────────────────────────────────────────────────────────

def wire_operating_callbacks(comps: dict, ctx: AppContext) -> None:

    def _add_task(text: str, tasks: list[dict], filter_mode: str):
        if not text.strip():
            return tasks, render_task_list(tasks, filter_mode), ""
        tasks = list(tasks) + [_new_task(text)]
        save_tasks(ctx.base_dir, tasks)
        return tasks, render_task_list(tasks, filter_mode), ""

    comps["add_btn"].click(
        fn=_add_task,
        inputs=[comps["task_input"], comps["tasks_state"], comps["filter_tabs"]],
        outputs=[comps["tasks_state"], comps["task_list_html"], comps["task_input"]],
        show_progress="hidden",
    )

    comps["task_input"].submit(
        fn=_add_task,
        inputs=[comps["task_input"], comps["tasks_state"], comps["filter_tabs"]],
        outputs=[comps["tasks_state"], comps["task_list_html"], comps["task_input"]],
        show_progress="hidden",
    )

    def _filter_change(tasks: list[dict], filter_mode: str):
        return render_task_list(tasks, filter_mode)

    comps["filter_tabs"].change(
        fn=_filter_change,
        inputs=[comps["tasks_state"], comps["filter_tabs"]],
        outputs=[comps["task_list_html"]],
        show_progress="hidden",
    )

    def _sync_calendar(cal_state: dict, ev_state: list[dict]):
        events, msg = try_google_calendar_sync(ctx.base_dir)
        now_str = datetime.now().strftime("%H:%M:%S")
        new_cal = {"ok": "failed" not in msg.lower() and "not found" not in msg.lower(),
                   "last_sync": now_str, "count": len(events)}
        new_cal_html = _cal_card(now_str, len(events), new_cal["ok"])
        new_ev_html = render_events_panel(events)
        return new_cal, new_cal_html, events, new_ev_html, msg

    comps["sync_btn"].click(
        fn=_sync_calendar,
        inputs=[comps["cal_state"], comps["events_state"]],
        outputs=[
            comps["cal_state"],
            comps["cal_html"],
            comps["events_state"],
            comps["events_html"],
            comps["sync_status"],
        ],
        show_progress="hidden",
    )
