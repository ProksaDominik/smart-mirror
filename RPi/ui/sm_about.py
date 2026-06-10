"""SmartMirror — Getting Started tab (setup wizard).

Shows the four onboarding steps with live completion status derived from
the actual system state (camera open, face dataset photos, Calendar token).
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
    C_PURPLE,
    C_RED,
    C_WHITE,
    divider,
)

# ── Step status helpers ───────────────────────────────────────────────────────

def _camera_ready(ctx: AppContext) -> bool:
    try:
        from inputs.registry import INPUT_RPI_CAMERA
        provider = ctx.providers.get(INPUT_RPI_CAMERA)
        if provider is None:
            return False
        result = provider.sync_preview("320x240", 1.0, None, None, None)
        return result.frame_rgb is not None
    except Exception:
        return False


def _face_dataset_count(base_dir: Path) -> int:
    dataset = base_dir / "dataset" / "faces"
    if not dataset.exists():
        return 0
    return sum(1 for _ in dataset.rglob("*.jpg")) + sum(1 for _ in dataset.rglob("*.png"))


def _calendar_token_exists(base_dir: Path) -> bool:
    return (base_dir / "token.json").exists() or (base_dir / "data" / "token.json").exists()


# ── Step card renderer ────────────────────────────────────────────────────────

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
        num_color = C_MUTED
    elif state == "active":
        num_html = (
            f'<div style="font-size:22px;font-weight:600;color:{C_CYAN};'
            f'flex-shrink:0;width:40px;">{number}</div>'
        )
        badge_html = (
            f'<span style="border:1px solid {C_CYAN};color:{C_CYAN};'
            f'font-size:10px;letter-spacing:.1em;text-transform:uppercase;'
            f'padding:3px 10px;border-radius:20px;">In Progress</span>'
        )
        border = f"border:2px solid {C_CYAN};"
        num_color = C_CYAN
    else:
        num_html = (
            f'<div style="font-size:22px;font-weight:600;color:{C_BORDER};'
            f'flex-shrink:0;width:40px;">{number}</div>'
        )
        badge_html = ""
        border = f"border:1px solid {C_BORDER};"
        num_color = C_MUTED

    title_color = C_WHITE if state != "pending" else C_MUTED
    desc_color = C_MUTED if state == "pending" else "#ccc"

    return f"""
<div style="background:{C_CARD};{border}border-radius:12px;padding:24px;margin-bottom:16px;">
    <div style="display:flex;align-items:flex-start;gap:20px;">
        {num_html}
        <div style="flex:1;">
            <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px;">
                <div style="font-size:18px;font-weight:600;color:{title_color};">{title}</div>
                {badge_html}
            </div>
            <div style="font-size:14px;color:{desc_color};line-height:1.6;">
                {description}</div>
        </div>
    </div>
</div>"""


# ── Sidebar ───────────────────────────────────────────────────────────────────

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
        {"".join(f'<li style="font-size:14px;color:{C_WHITE};padding:7px 0;display:flex;align-items:center;gap:10px;"><span style="width:8px;height:8px;border-radius:50%;background:{C_CYAN};display:inline-block;"></span>{feat}</li>' for feat in ["Recognises your face in seconds", "Shows your daily schedule & tasks", "Live weather & temperature", "Syncs with Google Calendar"])}
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


# ── Page HTML renderer ────────────────────────────────────────────────────────

def render_about(
    cam_ok: bool,
    photo_count: int,
    calendar_ok: bool,
) -> str:
    # Derive step states
    step1 = "done" if cam_ok else "active"
    step2 = "done" if photo_count >= 100 else ("active" if cam_ok else "pending")
    step3 = "done" if calendar_ok else ("active" if photo_count >= 100 else "pending")
    step4 = "done" if (cam_ok and photo_count >= 100 and calendar_ok) else "pending"

    photo_note = ""
    if step2 == "active":
        pct = min(int(photo_count / 100 * 100), 100)
        photo_note = (
            f'<br><span style="color:{C_CYAN};">{photo_count}/100 photos captured</span>'
            f' <span style="color:{C_MUTED};">({pct}%)</span>'
        )

    return f"""
<div style="font-family:'Inter',sans-serif;background:{C_BG};
            min-height:calc(100vh - 48px);display:grid;
            grid-template-columns:360px 1fr;">

    <!-- Sidebar -->
    {_SIDEBAR}

    <!-- Main -->
    <div style="padding:48px 56px;">
        <div style="font-size:40px;font-weight:700;color:{C_WHITE};
                    margin-bottom:8px;">Getting Started</div>
        <div style="font-size:14px;color:{C_MUTED};margin-bottom:40px;">
            Complete these steps to activate your SmartMirror</div>

        {_step_card("01", "Connect Your Device",
            'Power on the Raspberry Pi and connect the 10.1" LCD via HDMI. '
            "Attach the USB camera module and verify the connection.",
            step1)}

        {_step_card("02", "Register Your Face",
            "Stand before the mirror and press the hardware button. The YOLO model "
            f"captures 100 photos to build your unique face profile.{photo_note}",
            step2)}

        {_step_card("03", "Sync Google Calendar",
            "Authorise the SmartMirror on your phone to pull daily events and to-do "
            "items from Google Calendar automatically. Place <code "
            f"style='background:{C_CARD};padding:1px 5px;border-radius:3px;"
            "font-size:12px;'>credentials.json</code> in the RPi folder, "
            "then click <b>Sync Now</b> in the Operating tab.",
            step3)}

        {_step_card("04", "Start Your Morning",
            "You're set! The mirror greets you by name and shows time, weather, and "
            "your schedule — completely hands-free every morning.",
            step4)}
    </div>
</div>"""


# ── Gradio tab builder ────────────────────────────────────────────────────────

def build_about_tab(ctx: AppContext) -> dict:
    with gr.TabItem("Getting Started", id="about"):
        about_html = gr.HTML(
            render_about(cam_ok=False, photo_count=0, calendar_ok=False)
        )
        refresh_btn = gr.Button(
            "↻ Refresh status",
            size="sm",
            variant="secondary",
        )

    return {"about_html": about_html, "refresh_btn": refresh_btn}


def wire_about_callbacks(comps: dict, ctx: AppContext) -> None:
    def _refresh():
        cam = _camera_ready(ctx)
        photos = _face_dataset_count(ctx.base_dir)
        cal = _calendar_token_exists(ctx.base_dir)
        return render_about(cam, photos, cal)

    comps["refresh_btn"].click(
        fn=_refresh,
        inputs=None,
        outputs=[comps["about_html"]],
        show_progress="hidden",
    )

    # Also refresh on page load (via the demo.load callback — wired in dashboard)
