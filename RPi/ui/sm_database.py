"""SmartMirror — Database tab.

Shows a live view of all tasks in PostgreSQL (same data as Adminer).
Auto-refreshes every 5 s so changes made in Adminer appear automatically.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

import gradio as gr

import db
from ui.context import AppContext
from ui.smartmirror_theme import (
    C_BG, C_BORDER, C_CARD, C_CYAN, C_GREEN,
    C_MUTED, C_PURPLE, C_RED, C_WHITE,
)


def _source_badge(source: str) -> str:
    color = C_CYAN if source == "calendar" else C_PURPLE
    label = "Calendar" if source == "calendar" else "User"
    return (
        f'<span style="font-size:11px;padding:2px 8px;border-radius:4px;'
        f'background:rgba({_hex_to_rgb(color)},0.15);color:{color};'
        f'font-weight:600;letter-spacing:.04em;">{label}</span>'
    )


def _hex_to_rgb(h: str) -> str:
    h = h.lstrip("#")
    return ",".join(str(int(h[i:i+2], 16)) for i in (0, 2, 4))


def _status_badge(completed: bool) -> str:
    if completed:
        return (
            f'<span style="font-size:11px;padding:2px 8px;border-radius:4px;'
            f'background:rgba(0,255,136,0.12);color:{C_GREEN};font-weight:600;">Done</span>'
        )
    return (
        f'<span style="font-size:11px;padding:2px 8px;border-radius:4px;'
        f'background:rgba(0,245,255,0.10);color:{C_CYAN};font-weight:600;">Pending</span>'
    )


def _delete_js(task_id: str) -> str:
    return (
        f"(function(){{var el=document.querySelector('#sm-db-delete textarea,#sm-db-delete input');"
        f"if(!el)return;"
        f"var p=el.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;"
        f"Object.getOwnPropertyDescriptor(p,'value').set.call(el,'{task_id}');"
        f"el.dispatchEvent(new Event('input',{{bubbles:true}}));"
        f"el.dispatchEvent(new Event('change',{{bubbles:true}}));"
        f"}})()"
    )


def render_db_table(tasks: list[dict]) -> str:
    if not tasks:
        return (
            f'<div style="font-family:Inter,sans-serif;color:{C_MUTED};'
            f'text-align:center;padding:40px;font-size:14px;">No tasks in database.</div>'
        )

    header = (
        f'<div style="display:grid;grid-template-columns:1fr 110px 90px 90px 80px;'
        f'gap:8px;padding:8px 12px;font-size:11px;font-weight:700;letter-spacing:.08em;'
        f'text-transform:uppercase;color:{C_MUTED};border-bottom:1px solid {C_BORDER};">'
        f'<div>Task</div><div>Due</div><div>Source</div><div>Status</div><div>Action</div>'
        f'</div>'
    )

    rows = ""
    for t in tasks:
        text = t.get("text") or t.get("task_text") or ""
        due  = t.get("due", "")
        done = t.get("completed", False)
        src  = t.get("source", "user")
        tid  = t["id"]
        strike = f"text-decoration:line-through;color:{C_MUTED};" if done else f"color:{C_WHITE};"
        rows += (
            f'<div style="display:grid;grid-template-columns:1fr 110px 90px 90px 80px;'
            f'gap:8px;padding:10px 12px;border-bottom:1px solid {C_BORDER};'
            f'align-items:center;font-family:Inter,sans-serif;">'
            f'<div style="font-size:14px;{strike}overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{text}</div>'
            f'<div style="font-size:13px;color:{C_MUTED};">{due}</div>'
            f'<div>{_source_badge(src)}</div>'
            f'<div>{_status_badge(done)}</div>'
            f'<div><button onclick="{_delete_js(tid)}" style="background:{C_RED};color:#fff;'
            f'border:none;border-radius:6px;padding:4px 10px;font-size:12px;'
            f'cursor:pointer;font-weight:600;">Delete</button></div>'
            f'</div>'
        )

    return (
        f'<div style="background:{C_CARD};border:1px solid {C_BORDER};'
        f'border-radius:12px;overflow:hidden;">{header}{rows}</div>'
    )


def _load() -> list[dict]:
    try:
        return db.load_tasks()
    except Exception:
        return []


def build_database_tab(ctx: AppContext) -> dict:
    tasks_init = _load()

    with gr.TabItem("Database", id="database"):
        gr.HTML(
            f'<div style="font-family:Inter,sans-serif;padding:18px 32px;'
            f'border-bottom:1px solid {C_BORDER};background:{C_CARD};'
            f'display:flex;align-items:center;justify-content:space-between;">'
            f'<div style="display:flex;align-items:center;gap:8px;">'
            f'<span style="font-size:20px;font-weight:700;color:{C_WHITE};">SmartMirror</span>'
            f'<span style="font-size:16px;color:{C_PURPLE};">&nbsp;/ Database</span>'
            f'</div>'
            f'<div style="font-size:12px;color:{C_MUTED};">Auto-syncs with PostgreSQL every 5 s</div>'
            f'</div>',
            sanitize_html=False,
        )

        with gr.Row():
            with gr.Column(scale=2):
                gr.HTML(
                    f'<div style="font-size:12px;letter-spacing:.10em;text-transform:uppercase;'
                    f'color:{C_CYAN};padding:24px 0 12px;font-family:Inter,sans-serif;">'
                    f'Tasks Table</div>',
                    sanitize_html=False,
                )
                db_table_html = gr.HTML(render_db_table(tasks_init), sanitize_html=False)
                db_tasks_state = gr.State(tasks_init)

                # Hidden textbox that Delete buttons write into
                delete_input = gr.Textbox(
                    value="", visible=True, elem_id="sm-db-delete",
                    label="", container=False,
                )

                refresh_btn = gr.Button("↻ Refresh", variant="secondary", size="sm")
                db_timer = gr.Timer(value=5)

            with gr.Column(scale=1):
                gr.HTML(
                    f'<div style="font-size:12px;letter-spacing:.10em;text-transform:uppercase;'
                    f'color:{C_CYAN};padding:24px 0 12px;font-family:Inter,sans-serif;">'
                    f'Add Task</div>',
                    sanitize_html=False,
                )
                new_text = gr.Textbox(label="Task description", placeholder="e.g. Buy groceries")
                new_due  = gr.Textbox(
                    label="Due date (YYYY-MM-DD)",
                    value=date.today().isoformat(),
                    placeholder="2025-06-15",
                )
                add_btn    = gr.Button("+ Add Task", variant="primary", size="sm")
                add_status = gr.HTML("", sanitize_html=False)

                gr.HTML(
                    f'<div style="margin-top:24px;padding:16px;background:{C_CARD};'
                    f'border:1px solid {C_BORDER};border-radius:10px;">'
                    f'<div style="font-size:12px;color:{C_MUTED};line-height:1.7;">'
                    f'Changes made in <strong style="color:{C_CYAN};">Adminer</strong> '
                    f'(port 8080) are reflected here within 5 seconds.<br>'
                    f'Changes made here are immediately visible in Adminer.'
                    f'</div></div>',
                    sanitize_html=False,
                )

    return {
        "db_table_html":  db_table_html,
        "db_tasks_state": db_tasks_state,
        "delete_input":   delete_input,
        "refresh_btn":    refresh_btn,
        "db_timer":       db_timer,
        "new_text":       new_text,
        "new_due":        new_due,
        "add_btn":        add_btn,
        "add_status":     add_status,
    }


def wire_database_callbacks(comps: dict, ctx: AppContext) -> None:

    def _refresh():
        tasks = _load()
        return tasks, render_db_table(tasks)

    def _add_task(text: str, due: str):
        text = text.strip()
        if not text:
            return (
                gr.update(), gr.update(),
                f'<div style="color:{C_RED};font-size:13px;padding:6px 0;">Task text is required.</div>',
                gr.update(),
            )
        try:
            date.fromisoformat(due.strip())
        except ValueError:
            return (
                gr.update(), gr.update(),
                f'<div style="color:{C_RED};font-size:13px;padding:6px 0;">Invalid date format. Use YYYY-MM-DD.</div>',
                gr.update(),
            )
        task = {
            "id": str(uuid.uuid4())[:8],
            "text": text,
            "due": due.strip(),
            "completed": False,
            "source": "user",
            "gcal_event_id": "",
            "created_at": datetime.now().isoformat(),
        }
        db.save_task(task)
        tasks = _load()
        return (
            tasks,
            render_db_table(tasks),
            f'<div style="color:{C_GREEN};font-size:13px;padding:6px 0;">Task added.</div>',
            "",
        )

    def _delete_task(task_id: str, tasks: list[dict]):
        if not task_id:
            return tasks, render_db_table(tasks), ""
        try:
            db.delete_task(task_id)
        except Exception as exc:
            print(f"[DB tab] delete failed: {exc}")
        tasks = _load()
        return tasks, render_db_table(tasks), ""

    comps["db_timer"].tick(
        fn=_refresh,
        outputs=[comps["db_tasks_state"], comps["db_table_html"]],
        show_progress="hidden",
    )

    comps["refresh_btn"].click(
        fn=_refresh,
        outputs=[comps["db_tasks_state"], comps["db_table_html"]],
        show_progress="hidden",
    )

    comps["add_btn"].click(
        fn=_add_task,
        inputs=[comps["new_text"], comps["new_due"]],
        outputs=[comps["db_tasks_state"], comps["db_table_html"], comps["add_status"], comps["new_text"]],
        show_progress="hidden",
    )

    comps["delete_input"].change(
        fn=_delete_task,
        inputs=[comps["delete_input"], comps["db_tasks_state"]],
        outputs=[comps["db_tasks_state"], comps["db_table_html"], comps["delete_input"]],
        show_progress="hidden",
    )
