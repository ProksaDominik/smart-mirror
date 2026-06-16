"""SmartMirror — Operating tab.

Left panel : schedule & tasks (Today / Upcoming / Completed) with checkboxes.
Right panel: Google Calendar sync card + link calendar.
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


# ── Calendar helpers ──────────────────────────────────────────────────────────

_KNOWN_PEOPLE = ["Dominik", "JP", "Joao", "Liviu", "Lloyd", "Michal", "Radu"]

_last_sync_time: str = "never"
_sync_event_count: int = 0

_GCAL_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def _token_path(base_dir: Path, name: str | None) -> Path:
    if name:
        token_dir = base_dir / "data" / "tokens"
        token_dir.mkdir(parents=True, exist_ok=True)
        return token_dir / f"{name}.json"
    return base_dir / "token.json"


def _creds_path(base_dir: Path) -> Path | None:
    for p in [base_dir / "credentials.json", base_dir / "data" / "credentials.json"]:
        if p.exists():
            return p
    return None


def link_google_calendar(base_dir: Path, name: str) -> str:
    """Run the OAuth flow for one person and save their token."""
    cp = _creds_path(base_dir)
    if cp is None:
        return "credentials.json not found. Download it from Google Cloud Console and place it in the RPi/ folder."
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        flow = InstalledAppFlow.from_client_secrets_file(str(cp), _GCAL_SCOPES)
        creds = flow.run_local_server(port=0)
        _token_path(base_dir, name).write_text(creds.to_json())
        return f"Google Calendar linked for {name}."
    except Exception as exc:
        return f"Failed: {exc}"


def try_google_calendar_sync(base_dir: Path, name: str | None = None) -> tuple[list[dict], str]:
    cp = _creds_path(base_dir)
    if cp is None:
        return [],"credentials.json not found — using sample events."
    tp = _token_path(base_dir, name)
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build as gapi_build

        creds = None
        if tp.exists():
            creds = Credentials.from_authorized_user_file(str(tp), _GCAL_SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                tp.write_text(creds.to_json())
            else:
                who = name or "this account"
                return [],f"No calendar linked for {who}. Use 'Link Calendar' below."

        service = gapi_build("calendar", "v3", credentials=creds)
        today_start = datetime.combine(date.today(), datetime.min.time()).isoformat() + "Z"
        today_end   = datetime.combine(date.today(), datetime.max.time()).isoformat() + "Z"
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
            t = (
                datetime.fromisoformat(start.replace("Z", "+00:00")).strftime("%H:%M")
                if "T" in start else start
            )
            events.append({"time": t, "title": item.get("summary", "(no title)"), "active": False, "gcal_id": item["id"]})
        global _last_sync_time, _sync_event_count
        _last_sync_time   = datetime.now().strftime("%H:%M:%S")
        _sync_event_count = len(events)
        who = name or "calendar"
        return events, f"Synced {len(events)} events for {who}."
    except ImportError:
        return [],"google-api-python-client not installed."
    except Exception as exc:
        return [],f"Sync failed: {exc}"


def delete_google_calendar_event(base_dir: Path, name: str | None, event_id: str) -> None:
    if not event_id:
        return
    tp = _token_path(base_dir, name)
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build as gapi_build

        creds = None
        if tp.exists():
            creds = Credentials.from_authorized_user_file(str(tp), _GCAL_SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                tp.write_text(creds.to_json())
            else:
                return
        service = gapi_build("calendar", "v3", credentials=creds)
        service.events().delete(calendarId="primary", eventId=event_id).execute()
    except Exception as exc:
        print(f"[GCal] Could not delete event {event_id}: {exc}")


# ── HTML render helpers ───────────────────────────────────────────────────────

_DAY_NAMES   = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _fmt_due(due_iso: str) -> str:
    try:
        d = date.fromisoformat(due_iso)
        return f"{_DAY_NAMES[d.weekday()]}, {d.day} {_MONTH_NAMES[d.month - 1]}"
    except Exception:
        return due_iso


def _render_task_row(task: dict, is_today: bool = True) -> str:
    done   = task["completed"]
    tid    = task["id"]
    source = task.get("source", "user")
    text   = task["text"]

    # Calendar events stored as "HH:MM – Class Name" — split for better display
    if source == "calendar" and " – " in text:
        time_part, class_name = text.split(" – ", 1)
    else:
        time_part  = None
        class_name = None

    strike       = f"text-decoration:line-through;color:{C_MUTED};" if done else ""
    check_bg     = C_GREEN if done else "transparent"
    check_border = C_GREEN if done else (C_CYAN if is_today else C_BORDER)
    check_icon   = "&#10003;" if done else ""

    row_style = (
        f"border-left:3px solid {C_CYAN};background:rgba(0,245,255,0.05);"
        if is_today and not done else ""
    )

    toggle_js = (
        f"(function(t){{var el=document.querySelector('#sm-task-action textarea');"
        f"if(!el)el=document.querySelector('#sm-task-action input');"
        f"if(!el)return;"
        f"var p=el.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;"
        f"Object.getOwnPropertyDescriptor(p,'value').set.call(el,t);"
        f"el.dispatchEvent(new Event('input',{{bubbles:true}}));"
        f"el.dispatchEvent(new Event('change',{{bubbles:true}}));"
        f"}})(\'{tid}\')"
    )

    # Date label shown above non-today tasks
    date_label = ""
    if not is_today:
        due = task.get("due", "")
        if due:
            date_label = (
                f'<div style="font-size:13px;font-weight:700;color:{C_PURPLE};'
                f'margin-bottom:6px;letter-spacing:.02em;">'
                f'📅 {_fmt_due(due)}</div>'
            )

    if class_name:
        # Calendar event: class name big, time as small badge
        text_html = (
            f'<div style="flex:1;">'
            f'{date_label}'
            f'<div style="font-size:15px;font-weight:600;color:{C_WHITE};{strike}">{class_name}</div>'
            f'<div style="font-size:11px;color:{C_CYAN if is_today else C_MUTED};margin-top:3px;">'
            f'⏰ {time_part}</div>'
            f'</div>'
        )
    else:
        text_html = (
            f'<div style="flex:1;">'
            f'{date_label}'
            f'<div style="font-size:15px;color:{C_WHITE};{strike}">{text}</div>'
            f'</div>'
        )

    return (
        f'<div style="display:flex;align-items:flex-start;gap:12px;padding:12px;'
        f'border-radius:8px;margin-bottom:4px;{row_style}" id="task-{tid}">'
        f'<div onclick="{toggle_js}" '
        f'style="width:20px;height:20px;border-radius:4px;border:2px solid {check_border};'
        f'background:{check_bg};display:flex;align-items:center;justify-content:center;'
        f'font-size:12px;color:#000;flex-shrink:0;cursor:pointer;user-select:none;margin-top:2px;">'
        f'{check_icon}</div>'
        f'{text_html}'
        f'</div>'
    )


def _render_filter_tabs(active: str) -> str:
    tabs = [("Tasks", "Today", 0), ("Completed", "Completed", 1)]
    items = ""
    for label, value, idx in tabs:
        is_active = value == active
        bg     = C_CYAN if is_active else "transparent"
        color  = "#000" if is_active else C_MUTED
        border = f"border:1px solid {C_CYAN};" if is_active else f"border:1px solid {C_BORDER};"
        js     = f"(function(){{var r=document.querySelectorAll('#sm-filter-radio input[type=radio]');if(r[{idx}])r[{idx}].click();}})()"
        items += (
            f'<div onclick="{js}" style="padding:8px 20px;border-radius:8px;{border}'
            f'background:{bg};color:{color};font-size:13px;font-weight:600;'
            f'cursor:pointer;user-select:none;font-family:Inter,sans-serif;">{label}</div>'
        )
    return f'<div style="display:flex;gap:8px;margin-bottom:16px;">{items}</div>'


def render_task_list(tasks: list[dict], filter_mode: str) -> str:
    today = _today_iso()
    if filter_mode == "Completed":
        rows = "".join(_render_task_row(t, t.get("due", "") == today) for t in tasks if t["completed"])
        empty_msg = "No completed tasks yet."
    else:
        today_tasks = [t for t in tasks if t.get("due", "") == today and not t["completed"]]
        other_tasks = sorted(
            [t for t in tasks if t.get("due", "") != today and not t["completed"]],
            key=lambda t: t.get("due", ""),
        )
        today_section = ""
        if today_tasks:
            today_header = (
                f'<div style="font-size:11px;font-weight:700;letter-spacing:.1em;'
                f'text-transform:uppercase;color:{C_CYAN};padding:8px 0 6px;'
                f'border-bottom:1px solid {C_CYAN};margin-bottom:8px;">Today</div>'
            )
            today_section = today_header + "".join(_render_task_row(t, True) for t in today_tasks)
        other_section = ""
        if other_tasks:
            other_header = (
                f'<div style="font-size:11px;font-weight:700;letter-spacing:.1em;'
                f'text-transform:uppercase;color:{C_MUTED};padding:16px 0 6px;'
                f'border-bottom:1px solid {C_BORDER};margin-bottom:8px;">Upcoming</div>'
            )
            other_section = other_header + "".join(_render_task_row(t, False) for t in other_tasks)
        rows = today_section + other_section
        empty_msg = "No tasks scheduled."

    empty = (
        f'<div style="color:{C_MUTED};font-size:14px;padding:16px 0;">{empty_msg}</div>'
        if not rows else ""
    )
    return f'<div style="font-family:Inter,sans-serif;">{rows}{empty}</div>'


def _render_event_row(ev: dict, is_active: bool = False) -> str:
    border    = f"border-left:3px solid {C_CYAN};" if is_active else ""
    bg        = "background:rgba(0,245,255,0.05);" if is_active else f"background:{C_CARD};"
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


def events_to_cal_tasks(events: list[dict]) -> list[dict]:
    """Convert Google Calendar event dicts to task dicts."""
    now_str = datetime.now().isoformat()
    today   = _today_iso()
    tasks   = []
    for ev in events:
        uid = str(uuid.uuid5(uuid.NAMESPACE_DNS, ev.get("time", "") + ev.get("title", "")))[:8]
        tasks.append({
            "id":            f"gcal-{uid}",
            "text":          f"{ev.get('time', '')} – {ev.get('title', '')}".strip(" –"),
            "due":           today,
            "completed":     False,
            "source":        "calendar",
            "gcal_event_id": ev.get("gcal_id", ""),
            "created_at":    now_str,
        })
    return tasks


def _cal_card(last_sync: str, event_count: int, cal_ok: bool) -> str:
    status_dot  = dot(C_GREEN) if cal_ok else dot(C_MUTED)
    status_text = "Connected" if cal_ok else "Not connected"
    last        = last_sync if last_sync != "never" else "—"
    return f"""
<div style="background:{C_CARD};border:1px solid {C_CYAN};border-radius:12px;
            padding:20px;margin-bottom:24px;">
    <div style="display:flex;align-items:center;gap:16px;">
        <div style="background:{C_CYAN};border-radius:8px;width:44px;height:44px;
                    display:flex;align-items:center;justify-content:center;
                    font-size:20px;flex-shrink:0;">📅</div>
        <div style="flex:1;">
            <div style="font-size:16px;font-weight:600;color:{C_WHITE};">Google Calendar</div>
            <div style="font-size:12px;color:{C_MUTED};margin-top:2px;">
                Last synced: {last} &nbsp;·&nbsp; {event_count} events today</div>
        </div>
        <div style="font-size:14px;">{status_dot}
            <span style="color:{'#00FF88' if cal_ok else C_MUTED};">{status_text}</span>
        </div>
    </div>
</div>"""


# ── Database table renderer ───────────────────────────────────────────────────

def _hex_to_rgb(h: str) -> str:
    h = h.lstrip("#")
    return ",".join(str(int(h[i:i+2], 16)) for i in (0, 2, 4))


def _render_db_table(tasks: list[dict]) -> str:
    if not tasks:
        return (
            f'<div style="font-family:Inter,sans-serif;color:{C_MUTED};'
            f'text-align:center;padding:32px;font-size:14px;">No tasks in database.</div>'
        )
    header = (
        f'<div style="display:grid;grid-template-columns:1fr 110px 90px 90px 80px;'
        f'gap:8px;padding:8px 12px;font-size:11px;font-weight:700;letter-spacing:.08em;'
        f'text-transform:uppercase;color:{C_MUTED};border-bottom:1px solid {C_BORDER};">'
        f'<div>Task</div><div>Due</div><div>Source</div><div>Status</div><div>Action</div></div>'
    )
    rows = ""
    for t in tasks:
        text = t.get("text") or t.get("task_text") or ""
        due  = t.get("due", "")
        done = t.get("completed", False)
        src  = t.get("source", "user")
        tid  = t["id"]
        strike = f"text-decoration:line-through;color:{C_MUTED};" if done else f"color:{C_WHITE};"
        src_color = C_CYAN if src == "calendar" else C_PURPLE
        src_label = "Calendar" if src == "calendar" else "User"
        src_badge = (
            f'<span style="font-size:11px;padding:2px 8px;border-radius:4px;'
            f'background:rgba({_hex_to_rgb(src_color)},0.15);color:{src_color};font-weight:600;">'
            f'{src_label}</span>'
        )
        status_badge = (
            f'<span style="font-size:11px;padding:2px 8px;border-radius:4px;'
            f'background:rgba(0,255,136,0.12);color:{C_GREEN};font-weight:600;">Done</span>'
            if done else
            f'<span style="font-size:11px;padding:2px 8px;border-radius:4px;'
            f'background:rgba(0,245,255,0.10);color:{C_CYAN};font-weight:600;">Pending</span>'
        )
        del_js = (
            f"(function(){{var el=document.querySelector('#sm-db-delete textarea,#sm-db-delete input');"
            f"if(!el)return;"
            f"var p=el.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;"
            f"Object.getOwnPropertyDescriptor(p,'value').set.call(el,'{tid}');"
            f"el.dispatchEvent(new Event('input',{{bubbles:true}}));"
            f"el.dispatchEvent(new Event('change',{{bubbles:true}}));"
            f"}})()"
        )
        rows += (
            f'<div style="display:grid;grid-template-columns:1fr 110px 90px 90px 80px;'
            f'gap:8px;padding:10px 12px;border-bottom:1px solid {C_BORDER};align-items:center;">'
            f'<div style="font-size:14px;{strike}overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{text}</div>'
            f'<div style="font-size:13px;color:{C_MUTED};">{due}</div>'
            f'<div>{src_badge}</div><div>{status_badge}</div>'
            f'<div><button onclick="{del_js}" style="background:{C_RED};color:#fff;border:none;'
            f'border-radius:6px;padding:4px 10px;font-size:12px;cursor:pointer;font-weight:600;">'
            f'Delete</button></div></div>'
        )
    return (
        f'<div style="background:{C_CARD};border:1px solid {C_BORDER};'
        f'border-radius:12px;overflow:hidden;font-family:Inter,sans-serif;">{header}{rows}</div>'
    )


# ── Gradio tab builder ────────────────────────────────────────────────────────

def build_operating_tab(ctx: AppContext) -> dict:
    # Calendar syncs on face scan only — clear any stale calendar tasks from DB
    cal_ok_init = False
    try:
        db.replace_calendar_tasks([])
    except Exception as exc:
        print(f"[DB] startup clear failed: {exc}")
    tasks_init = load_tasks(ctx.base_dir)

    with gr.TabItem("Data", id="operating"):

        gr.HTML(
            f'<style>'
            f'#sm-filter-radio{{position:absolute;left:-9999px;opacity:0;pointer-events:none;}}'
            f'#sm-task-action{{position:absolute;left:-9999px;width:1px;height:1px;overflow:hidden;opacity:0;}}'
            f'</style>'
            f'<div style="font-family:Inter,sans-serif;padding:18px 32px;'
            f'border-bottom:1px solid {C_BORDER};background:{C_CARD};'
            f'display:flex;align-items:center;justify-content:space-between;">'
            f'<div style="display:flex;align-items:center;gap:8px;">'
            f'<span style="font-size:20px;font-weight:700;color:{C_WHITE};">SmartMirror</span>'
            f'<span style="font-size:16px;color:{C_PURPLE};">&nbsp;/ Operating</span>'
            f'</div>'
            f'<div style="display:flex;align-items:center;gap:10px;">'
            f'<div style="width:36px;height:36px;border-radius:50%;background:{C_PURPLE};'
            f'display:flex;align-items:center;justify-content:center;font-size:16px;">👤</div>'
            f'<div>'
            f'<div style="font-size:14px;font-weight:500;color:{C_WHITE};">Dominik Prokša</div>'
            f'<div style="font-size:11px;color:{C_GREEN};">Connected</div>'
            f'</div></div></div>',
            sanitize_html=False,
        )

        with gr.Row():
            # LEFT: to-do list + today's events
            with gr.Column(scale=1):
                gr.HTML(
                    f'<div style="font-size:12px;letter-spacing:.10em;text-transform:uppercase;'
                    f'color:{C_CYAN};padding:24px 0 12px;font-family:Inter,sans-serif;">'
                    f'Schedule &amp; Tasks</div>',
                    sanitize_html=False,
                )
                filter_state = gr.State("Today")

                tasks_state    = gr.State(tasks_init)
                task_action    = gr.Textbox(value="", visible=True, elem_id="sm-task-action", label="", container=False)
                task_list_html = gr.HTML(render_task_list(tasks_init, "Today"), sanitize_html=False)

                events_state = gr.State([])

            # RIGHT: calendar sync + mirror settings
            with gr.Column(scale=1):
                gr.HTML(
                    f'<div style="font-size:12px;letter-spacing:.10em;text-transform:uppercase;'
                    f'color:{C_CYAN};padding:24px 0 12px;font-family:Inter,sans-serif;">'
                    f'Calendar Sync</div>',
                    sanitize_html=False,
                )
                cal_state = gr.State({
                    "ok": cal_ok_init,
                    "last_sync": _last_sync_time,
                    "count": _sync_event_count,
                })
                cal_html = gr.HTML(
                    _cal_card(_last_sync_time, _sync_event_count, cal_ok_init),
                    sanitize_html=False,
                )
                sync_status = gr.Textbox(
                    label="Sync status", value="", interactive=False, visible=False,
                )
                with gr.Row():
                    sync_btn = gr.Button("↻ Sync Now", variant="primary", size="sm")

                gr.HTML(
                    f'<div style="font-size:12px;letter-spacing:.10em;text-transform:uppercase;'
                    f'color:{C_CYAN};padding:20px 0 10px;font-family:Inter,sans-serif;">'
                    f'Link a Google Calendar</div>'
                    f'<div style="font-size:13px;color:{C_MUTED};margin-bottom:12px;">'
                    f'Select a person, then click Link. A browser window will open on this Pi — '
                    f'the person logs in with their Google account. Only needed once per person.'
                    f'</div>',
                    sanitize_html=False,
                )
                link_person = gr.Dropdown(
                    choices=_KNOWN_PEOPLE,
                    value=_KNOWN_PEOPLE[0],
                    label="Person",
                    container=True,
                )
                link_btn    = gr.Button("🔗 Link Calendar", variant="secondary", size="sm")
                link_status = gr.Textbox(
                    label="Link status", value="", interactive=False, visible=False,
                )


        # ── Database section ──────────────────────────────────────────────────
        gr.HTML(
            f'<div style="font-family:Inter,sans-serif;padding:16px 0 0;'
            f'border-top:1px solid {C_BORDER};margin-top:8px;">'
            f'<div style="font-size:12px;letter-spacing:.10em;text-transform:uppercase;'
            f'color:{C_CYAN};padding:16px 0 12px;">Database</div></div>',
            sanitize_html=False,
        )

        with gr.Row():
            with gr.Column(scale=2):
                db_table_html  = gr.HTML(_render_db_table(tasks_init), sanitize_html=False)
                db_tasks_state = gr.State(tasks_init)
                delete_input   = gr.Textbox(value="", visible=True, elem_id="sm-db-delete", label="", container=False)
                db_timer       = gr.Timer(value=5)
                refresh_btn    = gr.Button("↻ Refresh", variant="secondary", size="sm")

            with gr.Column(scale=1):
                gr.HTML(
                    f'<div style="font-size:12px;letter-spacing:.10em;text-transform:uppercase;'
                    f'color:{C_CYAN};padding:0 0 12px;font-family:Inter,sans-serif;">Add Task</div>',
                    sanitize_html=False,
                )
                new_text   = gr.Textbox(label="Task description", placeholder="e.g. Buy groceries")
                new_due    = gr.Textbox(label="Due date (YYYY-MM-DD)", value=date.today().isoformat())
                add_btn    = gr.Button("+ Add Task", variant="primary", size="sm")
                add_status = gr.HTML("", sanitize_html=False)
                gr.HTML(
                    f'<div style="margin-top:16px;padding:14px;background:{C_CARD};'
                    f'border:1px solid {C_BORDER};border-radius:10px;">'
                    f'<div style="font-size:12px;color:{C_MUTED};line-height:1.7;">'
                    f'Changes in <strong style="color:{C_CYAN};">Adminer</strong> (port 8080) '
                    f'appear here within 5 s. Changes here are instantly visible in Adminer.'
                    f'</div></div>',
                    sanitize_html=False,
                )

        gr.HTML(
            f'<div style="font-family:Inter,sans-serif;padding:12px 0;'
            f'border-top:1px solid {C_BORDER};text-align:right;'
            f'font-size:12px;color:{C_GREEN};">All systems operational</div>',
            sanitize_html=False,
        )

    return {
        "filter_state":     filter_state,
        "tasks_state":      tasks_state,
        "task_action":      task_action,
        "task_list_html":   task_list_html,
        "events_state":     events_state,
        "cal_state":        cal_state,
        "cal_html":         cal_html,
        "sync_btn":         sync_btn,
        "sync_status":      sync_status,
        "link_person":      link_person,
        "link_btn":         link_btn,
        "link_status":      link_status,
        # database
        "db_table_html":    db_table_html,
        "db_tasks_state":   db_tasks_state,
        "delete_input":     delete_input,
        "db_timer":         db_timer,
        "refresh_btn":      refresh_btn,
        "new_text":         new_text,
        "new_due":          new_due,
        "add_btn":          add_btn,
        "add_status":       add_status,
    }


# ── Callbacks ─────────────────────────────────────────────────────────────────

def wire_operating_callbacks(comps: dict, ctx: AppContext) -> None:

    def _toggle_task(task_id: str, tasks: list[dict], mode: str):
        if not task_id:
            return tasks, render_task_list(tasks, mode), ""
        new_tasks = []
        for t in tasks:
            if t["id"] == task_id:
                toggled = {**t, "completed": not t["completed"]}
                # When marking a calendar event done, remove it from Google Calendar too
                if toggled["completed"] and t.get("source") == "calendar":
                    from ui.sm_display import _current_user
                    delete_google_calendar_event(
                        ctx.base_dir,
                        _current_user or None,
                        t.get("gcal_event_id", ""),
                    )
                    try:
                        db.delete_task(t["id"])
                    except Exception as exc:
                        print(f"[DB] delete_task failed: {exc}")
                new_tasks.append(toggled)
            else:
                new_tasks.append(t)
        save_tasks(ctx.base_dir, new_tasks)
        return new_tasks, render_task_list(new_tasks, mode), ""

    comps["task_action"].change(
        fn=_toggle_task,
        inputs=[comps["task_action"], comps["tasks_state"], comps["filter_state"]],
        outputs=[comps["tasks_state"], comps["task_list_html"], comps["task_action"]],
        show_progress="hidden",
    )

    def _sync_calendar(cal_state: dict, ev_state: list[dict], tasks: list[dict], mode: str):
        from ui.sm_display import _current_user
        name   = _current_user or None
        events, msg = try_google_calendar_sync(ctx.base_dir, name)
        now_str   = datetime.now().strftime("%H:%M:%S")
        ok        = "failed" not in msg.lower() and "not found" not in msg.lower() and "no calendar" not in msg.lower()
        new_cal   = {"ok": ok, "last_sync": now_str, "count": len(events)}
        cal_tasks = events_to_cal_tasks(events)
        user_tasks = [t for t in tasks if t.get("source") != "calendar"]
        new_tasks = user_tasks + cal_tasks
        try:
            db.replace_calendar_tasks(cal_tasks)
        except Exception as exc:
            print(f"[DB] replace_calendar_tasks failed: {exc}")
        return (
            new_cal,
            _cal_card(now_str, len(events), ok),
            events,
            new_tasks,
            render_task_list(new_tasks, mode),
            msg,
        )

    comps["sync_btn"].click(
        fn=_sync_calendar,
        inputs=[comps["cal_state"], comps["events_state"], comps["tasks_state"], comps["filter_state"]],
        outputs=[
            comps["cal_state"],
            comps["cal_html"],
            comps["events_state"],
            comps["tasks_state"],
            comps["task_list_html"],
            comps["sync_status"],
        ],
        show_progress="hidden",
    )

    def _link_calendar(name: str):
        msg = link_google_calendar(ctx.base_dir, name)
        ok  = "linked" in msg.lower()
        return gr.update(value=msg, visible=True), gr.update(
            value=msg, visible=True,
        )

    comps["link_btn"].click(
        fn=_link_calendar,
        inputs=[comps["link_person"]],
        outputs=[comps["link_status"], comps["sync_status"]],
        show_progress="hidden",
    )

    # ── Database callbacks ────────────────────────────────────────────────────

    def _db_refresh():
        tasks = load_tasks(ctx.base_dir)
        return tasks, _render_db_table(tasks)

    comps["db_timer"].tick(
        fn=_db_refresh,
        outputs=[comps["db_tasks_state"], comps["db_table_html"]],
        show_progress="hidden",
    )

    comps["refresh_btn"].click(
        fn=_db_refresh,
        outputs=[comps["db_tasks_state"], comps["db_table_html"]],
        show_progress="hidden",
    )

    def _add_task(text: str, due: str, tasks: list[dict], mode: str):
        text = text.strip()
        if not text:
            return (
                tasks, _render_db_table(tasks), tasks, render_task_list(tasks, mode),
                f'<div style="color:{C_RED};font-size:13px;padding:4px 0;">Task text required.</div>',
                gr.update(),
            )
        try:
            date.fromisoformat(due.strip())
        except ValueError:
            return (
                tasks, _render_db_table(tasks), tasks, render_task_list(tasks, mode),
                f'<div style="color:{C_RED};font-size:13px;padding:4px 0;">Invalid date. Use YYYY-MM-DD.</div>',
                gr.update(),
            )
        new_task = {
            "id": str(uuid.uuid4())[:8],
            "text": text,
            "due": due.strip(),
            "completed": False,
            "source": "user",
            "gcal_event_id": "",
            "created_at": datetime.now().isoformat(),
        }
        db.save_task(new_task)
        all_tasks = load_tasks(ctx.base_dir)
        return (
            all_tasks, _render_db_table(all_tasks),
            all_tasks, render_task_list(all_tasks, mode),
            f'<div style="color:{C_GREEN};font-size:13px;padding:4px 0;">Task added.</div>',
            "",
        )

    comps["add_btn"].click(
        fn=_add_task,
        inputs=[comps["new_text"], comps["new_due"], comps["db_tasks_state"], comps["filter_state"]],
        outputs=[
            comps["db_tasks_state"], comps["db_table_html"],
            comps["tasks_state"], comps["task_list_html"],
            comps["add_status"], comps["new_text"],
        ],
        show_progress="hidden",
    )

    def _delete_task(task_id: str, tasks: list[dict], mode: str):
        if not task_id:
            return tasks, _render_db_table(tasks), tasks, render_task_list(tasks, mode), ""
        try:
            db.delete_task(task_id)
        except Exception as exc:
            print(f"[DB tab] delete failed: {exc}")
        all_tasks = load_tasks(ctx.base_dir)
        return all_tasks, _render_db_table(all_tasks), all_tasks, render_task_list(all_tasks, mode), ""

    comps["delete_input"].change(
        fn=_delete_task,
        inputs=[comps["delete_input"], comps["db_tasks_state"], comps["filter_state"]],
        outputs=[
            comps["db_tasks_state"], comps["db_table_html"],
            comps["tasks_state"], comps["task_list_html"],
            comps["delete_input"],
        ],
        show_progress="hidden",
    )
