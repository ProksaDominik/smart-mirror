"""SmartMirror Gradio dashboard — assembles all four pages.

Tabs:
  Display        — clock/schedule | webcam + YOLO detection | weather/status
  Mirror         — narrow side panels + plain black center
  Getting Started— onboarding wizard with step-status cards
  Operating      — to-do list · calendar sync · mirror settings
"""

from __future__ import annotations

import gradio as gr

from hardware.setup import start_gpio
from ui.context import AppContext
from ui.sm_about import build_about_tab, wire_about_callbacks
from ui.sm_display import (
    SAMPLE_EVENTS,
    _render_left,
    _render_right,
    build_display_tab,
    fetch_weather,
    wire_display_callbacks,
)
from ui.sm_display_simple import (
    build_display_simple_tab,
    render_display_simple,
    wire_display_simple_callbacks,
)
from ui.sm_operating import build_operating_tab, wire_operating_callbacks
from ui.smartmirror_theme import SM_CSS

_SM_THEME = gr.themes.Base(
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
)


_CLOCK_JS = """
() => {
    function smStartClocks() {
        var D=['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
        var M=['January','February','March','April','May','June','July','August',
               'September','October','November','December'];
        function p(n){return String(n).padStart(2,'0');}
        function tick(){
            var n=new Date(), h=n.getHours(), m=n.getMinutes();
            var ts=p(h)+':'+p(m);
            ['sm-time','sm2-time'].forEach(function(id){
                var el=document.getElementById(id); if(el) el.textContent=ts;
            });
            var ds=D[n.getDay()]+', '+p(n.getDate())+' '+M[n.getMonth()]+' '+n.getFullYear();
            ['sm-date','sm2-date'].forEach(function(id){
                var el=document.getElementById(id); if(el) el.textContent=ds;
            });
            var ap=h>=12?'PM':'AM';
            ['sm-ampm','sm2-ampm'].forEach(function(id){
                var el=document.getElementById(id); if(el) el.textContent=ap;
            });
        }
        if(window._smClock) clearInterval(window._smClock);
        tick();
        window._smClock=setInterval(tick,1000);
    }
    smStartClocks();
    // Re-run after Gradio finishes rendering components
    setTimeout(smStartClocks, 1000);
    setTimeout(smStartClocks, 3000);
}
"""


def build_smartmirror_dashboard(ctx: AppContext) -> gr.Blocks:
    with gr.Blocks(title="SmartMirror") as demo:

        with gr.Tabs():
            # ── Tab 1: Display ────────────────────────────────────────────────
            display_comps = build_display_tab(ctx)

            # ── Tab 2: Mirror ─────────────────────────────────────────────────
            mirror_comps = build_display_simple_tab(ctx)

            # ── Tab 3: Getting Started ────────────────────────────────────────
            about_comps = build_about_tab(ctx)

            # ── Tab 4: Operating ─────────────────────────────────────────────
            operating_comps = build_operating_tab(ctx)

        # ── Wire callbacks ────────────────────────────────────────────────────
        wire_display_callbacks(display_comps, ctx)
        wire_display_simple_callbacks(mirror_comps, ctx)
        wire_about_callbacks(about_comps, ctx)
        wire_operating_callbacks(operating_comps, ctx)

        # ── Seed initial weather on load ──────────────────────────────────────
        def _on_load():
            from ui.sm_about import (
                _calendar_token_exists,
                _face_dataset_count,
                render_about,
            )
            weather = fetch_weather()
            status = {
                "camera": False, "led": "Green",
                "cloud": False, "weather_api": weather is not None, "wifi": True,
            }
            display_right = _render_right(weather, status)
            mirror_left, mirror_right = render_display_simple(
                weather_data=weather, events=SAMPLE_EVENTS
            )
            photos     = _face_dataset_count(ctx.base_dir)
            cal_ok     = _calendar_token_exists(ctx.base_dir)
            about_html = render_about(False, photos, cal_ok)
            return display_right, weather, status, mirror_left, mirror_right, weather, about_html

        demo.load(
            fn=_on_load,
            inputs=None,
            outputs=[
                display_comps["right_html"],
                display_comps["weather_state"],
                display_comps["status_state"],
                mirror_comps["left_html"],
                mirror_comps["right_html"],
                mirror_comps["weather_state"],
                about_comps["about_html"],
            ],
            show_progress="hidden",
        )

        # ── Start clock via JS on page load ───────────────────────────────────
        demo.load(fn=None, js=_CLOCK_JS)

        # ── Wire Operating calendar sync into Display + Mirror ────────────────
        operating_comps["events_state"].change(
            fn=lambda ev: _render_left(ev),
            inputs=[operating_comps["events_state"]],
            outputs=[display_comps["left_html"]],
            show_progress="hidden",
        )
        operating_comps["events_state"].change(
            fn=lambda ev, w: render_display_simple(w, ev),
            inputs=[operating_comps["events_state"], mirror_comps["weather_state"]],
            outputs=[mirror_comps["left_html"], mirror_comps["right_html"]],
            show_progress="hidden",
        )

    # ── Start GPIO ────────────────────────────────────────────────────────────
    from ui.inference_handlers import InferenceHandlers
    from ui.history import HistoryStore

    history    = HistoryStore()
    _inference = InferenceHandlers(ctx, history)

    try:
        ctx.gpio = start_gpio(
            ctx.cfg,
            on_short_press=_inference.on_gpio_short_press,
            on_hold_press=_inference.shutdown_now,
        )
    except Exception as exc:
        print(f"[GPIO] Could not initialize button (pin {ctx.cfg.shutdown_button_pin}): {exc} — running without hardware button")

    return demo


def launch_smartmirror_dashboard(ctx: AppContext, demo: gr.Blocks) -> None:
    demo.queue(default_concurrency_limit=4).launch(
        server_name=ctx.cfg.gradio_host,
        server_port=ctx.cfg.gradio_port,
        show_error=True,
        theme=_SM_THEME,
        css=SM_CSS,
    )
