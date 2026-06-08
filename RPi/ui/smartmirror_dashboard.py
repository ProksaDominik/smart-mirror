"""SmartMirror Gradio dashboard — assembles all three pages.

Tabs:
  Display        — live mirror screen (clock · weather · face recognition · schedule)
  Getting Started— onboarding wizard with step-status cards
  Operating      — to-do list · calendar sync · mirror settings
"""

from __future__ import annotations

import gradio as gr

from hardware.setup import start_gpio
from models.registry import MODEL_YOLO
from ui.context import AppContext
from ui.sm_about import build_about_tab, wire_about_callbacks
from ui.sm_display import (
    SAMPLE_EVENTS,
    build_display_tab,
    fetch_weather,
    render_display,
    wire_display_callbacks,
)
from ui.sm_operating import build_operating_tab, wire_operating_callbacks
from ui.smartmirror_theme import SM_CSS


def build_smartmirror_dashboard(ctx: AppContext) -> gr.Blocks:
    with gr.Blocks(
        title="SmartMirror",
        css=SM_CSS,
        theme=gr.themes.Base(
            primary_hue="cyan",
            secondary_hue="purple",
            font=gr.themes.GoogleFont("Inter"),
        ).set(
            body_background_fill="#0A0A0F",
            body_text_color="#ffffff",
            background_fill_primary="#0A0A0F",
            background_fill_secondary="#12121E",
            border_color_primary="#1E1E2E",
            color_accent_soft="#00F5FF",
            input_background_fill="#12121E",
            button_primary_background_fill="#00F5FF",
            button_primary_text_color="#000000",
            block_label_text_color="#8B8BA8",
        ),
    ) as demo:

        with gr.Tabs():
            # ── Tab 1: Display ────────────────────────────────────────────────
            display_comps = build_display_tab(ctx)

            # ── Tab 2: Getting Started ────────────────────────────────────────
            about_comps = build_about_tab(ctx)

            # ── Tab 3: Operating ─────────────────────────────────────────────
            operating_comps = build_operating_tab(ctx)

        # ── Wire callbacks ────────────────────────────────────────────────────
        wire_display_callbacks(display_comps, ctx)
        wire_about_callbacks(about_comps, ctx)
        wire_operating_callbacks(operating_comps, ctx)

        # ── Seed initial weather + about status on load ───────────────────────
        def _on_load():
            from ui.sm_about import (
                _calendar_token_exists,
                _camera_ready,
                _face_dataset_count,
                render_about,
            )
            weather = fetch_weather()
            status = {
                "camera": False, "led": "Green",
                "cloud": False, "weather_api": weather is not None,
                "wifi": True,
            }
            display_html = render_display(
                recognition={"name": None, "conf": 0.0},
                weather_data=weather,
                events=SAMPLE_EVENTS,
                status=status,
            )
            cam_ok   = _camera_ready(ctx)
            photos   = _face_dataset_count(ctx.base_dir)
            cal_ok   = _calendar_token_exists(ctx.base_dir)
            about_html = render_about(cam_ok, photos, cal_ok)
            return display_html, weather, status, about_html

        demo.load(
            fn=_on_load,
            inputs=None,
            outputs=[
                display_comps["display_html"],
                display_comps["weather_state"],
                display_comps["status_state"],
                about_comps["about_html"],
            ],
            show_progress="hidden",
        )

        # ── Wire Operating events into Display tab ────────────────────────────
        # When the user syncs calendar in Operating, update the Display schedule too.
        operating_comps["events_state"].change(
            fn=lambda ev, w, r, st: render_display(r, w, ev, st),
            inputs=[
                operating_comps["events_state"],
                display_comps["weather_state"],
                display_comps["recognition_state"],
                display_comps["status_state"],
            ],
            outputs=[display_comps["display_html"]],
            show_progress="hidden",
        )

    # ── Start GPIO ────────────────────────────────────────────────────────────
    from ui.inference_handlers import InferenceHandlers
    from ui.history import HistoryStore

    history  = HistoryStore()
    _inference = InferenceHandlers(ctx, history)

    ctx.gpio = start_gpio(
        ctx.cfg,
        on_short_press=_inference.on_gpio_short_press,
        on_hold_press=_inference.shutdown_now,
    )

    return demo


def launch_smartmirror_dashboard(ctx: AppContext, demo: gr.Blocks) -> None:
    demo.queue().launch(
        server_name=ctx.cfg.gradio_host,
        server_port=ctx.cfg.gradio_port,
        show_error=True,
    )
