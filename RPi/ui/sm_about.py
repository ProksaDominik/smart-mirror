"""SmartMirror — Getting Started tab.

Explains the system and shows live completion status for each setup step.
The face recognition model is pre-trained on a fixed set of people; no
in-app face registration is possible without retraining the YOLO model.
"""

from __future__ import annotations

from pathlib import Path

import gradio as gr

from ui.context import AppContext
from ui.smartmirror_theme import (
    C_BG,
    C_BORDER,
    C_CARD,
    C_CYAN,
    C_GREEN,
    C_MUTED,
    C_RED,
    C_WHITE,
    divider,
)

_MODEL_PATH = Path(__file__).resolve().parent.parent.parent / "Laptop" / "best.pt"

# Names the YOLO model was trained to recognise — fixed at training time.
_KNOWN_PEOPLE = ["Dominik", "JP", "Joao", "Liviu", "Lloyd", "Michal", "Radu"]


def _model_exists() -> bool:
    return _MODEL_PATH.exists()


def _calendar_token_exists(base_dir: Path) -> bool:
    tokens_dir = base_dir / "data" / "tokens"
    return tokens_dir.is_dir() and any(tokens_dir.glob("*.json"))


def _step_card(
    number: str,
    title: str,
    description: str,
    state: str,   # "done" | "active" | "pending"
) -> str:
    if state == "done":
        num_html = (
            f'<div style="width:40px;height:40px;border-radius:50%;'
            f'background:{C_GREEN};display:flex;align-items:center;'
            f'justify-content:center;flex-shrink:0;">'
            f'<span style="color:#000;font-size:18px;">✓</span></div>'
        )
        badge_html = ""
        border = f"border:1px solid {C_BORDER};"
    elif state == "active":
        num_html = (
            f'<div style="font-size:22px;font-weight:600;color:{C_CYAN};'
            f'flex-shrink:0;width:40px;">{number}</div>'
        )
        badge_html = (
            f'<span style="border:1px solid {C_CYAN};color:{C_CYAN};'
            f'font-size:10px;letter-spacing:.1em;text-transform:uppercase;'
            f'padding:3px 10px;border-radius:20px;">Action Required</span>'
        )
        border = f"border:2px solid {C_CYAN};"
    else:
        num_html = (
            f'<div style="font-size:22px;font-weight:600;color:{C_BORDER};'
            f'flex-shrink:0;width:40px;">{number}</div>'
        )
        badge_html = ""
        border = f"border:1px solid {C_BORDER};"

    title_color = C_WHITE if state != "pending" else C_MUTED
    desc_color  = C_MUTED if state == "pending" else "#ccc"

    return f"""
<div style="background:{C_CARD};{border}border-radius:12px;padding:24px;margin-bottom:16px;">
    <div style="display:flex;align-items:flex-start;gap:20px;">
        {num_html}
        <div style="flex:1;">
            <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px;">
                <div style="font-size:20px;font-weight:600;color:{title_color};">{title}</div>
                {badge_html}
            </div>
            <div style="font-size:15px;color:{desc_color};line-height:1.7;">{description}</div>
        </div>
    </div>
</div>"""


def _people_pills() -> str:
    pills = "".join(
        f'<span style="display:inline-block;background:rgba(108,92,231,0.12);'
        f'border:1px solid {C_CYAN};color:{C_CYAN};border-radius:20px;'
        f'padding:4px 14px;font-size:13px;font-weight:500;margin:4px 4px 4px 0;">'
        f'{name}</span>'
        for name in _KNOWN_PEOPLE
    )
    return f'<div style="margin-top:12px;">{pills}</div>'


_SIDEBAR = f"""
<div style="font-family:'Inter',sans-serif;padding:40px 32px;
            border-right:1px solid {C_BORDER};height:100%;background:{C_BG};">

    <div style="margin-bottom:32px;">
        <div style="font-size:28px;font-weight:700;color:{C_WHITE};letter-spacing:-0.5px;">
            SmartMirror</div>
        <div style="font-size:10px;letter-spacing:.18em;text-transform:uppercase;
                    color:{C_CYAN};margin-top:4px;border-top:2px solid {C_CYAN};
                    padding-top:6px;display:inline-block;">Morning Assistant</div>
    </div>

    <p style="font-size:13px;color:{C_MUTED};line-height:1.6;margin-bottom:6px;">
        Your AI-powered mirror companion.</p>
    <p style="font-size:13px;color:{C_MUTED};margin-bottom:28px;">
        Face recognition · Weather · Tasks</p>

    {divider()}

    <ul style="list-style:none;padding:0;margin:0 0 32px;">
        {"".join(
            f'<li style="font-size:14px;color:{C_WHITE};padding:7px 0;display:flex;'
            f'align-items:center;gap:10px;">'
            f'<span style="width:8px;height:8px;border-radius:50%;background:{C_CYAN};'
            f'display:inline-block;"></span>{feat}</li>'
            for feat in [
                "Recognises your face in seconds",
                "Shows your daily schedule &amp; tasks",
                "Live weather &amp; temperature",
                "Syncs with Google Calendar",
            ]
        )}
    </ul>

    {divider()}

    <div style="font-size:9px;letter-spacing:.14em;text-transform:uppercase;
                color:{C_MUTED};margin-bottom:12px;">Hardware</div>
    <div style="font-size:12px;color:{C_MUTED};line-height:1.9;">
        10.1" HDMI Touch LCD · 1280×800<br>
        Raspberry Pi · USB Camera Module<br>
        Green/Red LED · Speaker · Button
    </div>
</div>"""


def render_about(
    cam_ok: bool,
    model_ok: bool,
    calendar_ok: bool,
) -> str:
    step1 = "done" if cam_ok    else "active"
    step2 = "done" if model_ok  else "active"
    step3 = "done" if calendar_ok else ("active" if model_ok else "pending")
    step4 = "done" if (cam_ok and model_ok and calendar_ok) else "pending"

    model_note = ""
    if not model_ok:
        model_note = (
            f'<br><span style="color:{C_RED};">Model file not found: '
            f'<code style="font-size:12px;background:{C_CARD};padding:1px 5px;'
            f'border-radius:3px;">Laptop/best.pt</code></span>'
        )

    step2_desc = (
        "This mirror uses a YOLO model trained on a fixed set of people. "
        "It cannot learn new faces without retraining. "
        "The people it currently recognises are shown below. "
        "If your face is not in this list you will see "
        "<b style='color:#fff;'>Unregistered face recognized</b> on the Display tab."
        f"{model_note}"
        f"{_people_pills()}"
    )

    return f"""
<div style="font-family:'Inter',sans-serif;background:{C_BG};
            min-height:calc(100vh - 48px);display:grid;
            grid-template-columns:360px 1fr;">

    {_SIDEBAR}

    <div style="padding:48px 56px;">
        <div style="font-size:46px;font-weight:700;color:{C_WHITE};
                    margin-bottom:8px;">About</div>
        <div style="font-size:16px;color:{C_MUTED};margin-bottom:40px;">
            Complete these steps to activate your SmartMirror</div>

        {_step_card("01", "Connect Your Device",
            'Power on the Raspberry Pi and connect the display via HDMI.',
            step1)}

        {_step_card("02", "Recognised Users",
            step2_desc,
            step2)}

        {_step_card("03", "Sync Google Calendar",
            "Authorise the SmartMirror to access your Google Calendar. "
            "Go to the Operating tab and click <b>Link Calendar</b>.",
            step3)}

        {_step_card("04", "Start Your Morning",
            "You're set! The mirror greets you by name and shows time, weather, and "
            "your schedule — completely hands-free every morning.",
            step4)}
    </div>
</div>"""


def build_about_tab(ctx: AppContext) -> dict:
    with gr.TabItem("About", id="about"):
        about_html = gr.HTML(
            render_about(cam_ok=True, model_ok=_model_exists(), calendar_ok=False),
            sanitize_html=False,
        )
        refresh_btn = gr.Button("↻ Refresh status", size="sm", variant="secondary")

        gr.HTML(
            f'<div style="font-family:Bebas Neue,sans-serif;font-size:12px;letter-spacing:.10em;'
            f'text-transform:uppercase;color:#6C5CE7;padding:24px 0 12px;">Camera Test</div>',
            sanitize_html=False,
        )
        with gr.Row():
            with gr.Column(scale=1):
                cam_preview = gr.Image(
                    label="Pi Camera Live Preview",
                    interactive=False,
                    show_label=True,
                )
                cam_status = gr.Textbox(
                    label="Status", value="Waiting for first frame…",
                    interactive=False, show_label=True,
                )
                cam_test_timer = gr.Timer(value=1.0, active=True)
            with gr.Column(scale=1):
                gr.HTML(
                    f'<div style="font-family:Bebas Neue,sans-serif;padding:16px;'
                    f'background:#12121E;border:1px solid #1E1E2E;border-radius:10px;">'
                    f'<div style="font-size:13px;color:#8B8BA8;line-height:1.8;">'
                    f'This preview shows the raw Raspberry Pi camera feed without YOLO processing.<br><br>'
                    f'If the image is blank or shows an error, check that:<br>'
                    f'&nbsp;· The camera ribbon cable is firmly seated<br>'
                    f'&nbsp;· <code>libcamera-hello</code> works in a terminal<br>'
                    f'&nbsp;· <code>picamera2</code> is installed in the venv'
                    f'</div></div>',
                    sanitize_html=False,
                )

    return {
        "about_html":      about_html,
        "refresh_btn":     refresh_btn,
        "cam_preview":     cam_preview,
        "cam_status":      cam_status,
        "cam_test_timer":  cam_test_timer,
    }


def wire_about_callbacks(comps: dict, ctx: AppContext) -> None:
    def _refresh():
        return render_about(
            cam_ok=True,
            model_ok=_model_exists(),
            calendar_ok=_calendar_token_exists(ctx.base_dir),
        )

    comps["refresh_btn"].click(
        fn=_refresh,
        inputs=None,
        outputs=[comps["about_html"]],
        show_progress="hidden",
    )

    def _cam_test_tick():
        from ui.sm_display import capture_frame
        import numpy as np
        from PIL import Image
        img = capture_frame()
        if img is None:
            return gr.update(), "Camera not available — check connection and picamera2 install."
        mirrored = Image.fromarray(np.fliplr(np.array(img)))
        return gr.update(value=mirrored), f"OK — {img.width}×{img.height} px"

    comps["cam_test_timer"].tick(
        fn=_cam_test_tick,
        outputs=[comps["cam_preview"], comps["cam_status"]],
        show_progress="hidden",
    )
