"""SmartMirror Gradio dashboard — assembles all four pages.

Tabs:
  Display        — clock/schedule | streaming webcam + YOLO face recognition | weather/status
  Mirror         — narrow side panels + plain black center (physical mirror area)
  Getting Started— onboarding wizard with step-status cards
  Operating      — to-do list · calendar sync · mirror settings
"""

from __future__ import annotations

import gradio as gr

from hardware.setup import start_gpio
from ui.context import AppContext
from ui.sm_about import build_about_tab, wire_about_callbacks
from ui.sm_display import (
    _render_left,
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

_WEBCAM_JS = """
() => {
    function smHandleWebcamButtons() {
        var vid = document.querySelector('video');
        if (!vid) return;
        // Walk up from the <video> until we find a container that has buttons
        var el = vid.parentElement;
        for (var depth = 0; el && el.tagName !== 'BODY' && depth < 8; depth++) {
            var btns = el.querySelectorAll('button');
            if (btns.length) {
                btns.forEach(function(btn) {
                    // Click the first non-hidden button to start the stream
                    if (btn.offsetParent !== null) btn.click();
                    // Then hide it so it never shows
                    btn.style.setProperty('display', 'none', 'important');
                    btn.style.setProperty('visibility', 'hidden', 'important');
                    btn.style.setProperty('pointer-events', 'none', 'important');
                });
                return;
            }
            el = el.parentElement;
        }
    }
    // Run immediately and on retries in case the component mounts late
    setTimeout(smHandleWebcamButtons, 200);
    setTimeout(smHandleWebcamButtons, 700);
    setTimeout(smHandleWebcamButtons, 1500);
    // MutationObserver catches any button that appears after initial load
    new MutationObserver(smHandleWebcamButtons)
        .observe(document.body, {childList: true, subtree: true});
}
"""

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
    setTimeout(smStartClocks, 1000);
    setTimeout(smStartClocks, 3000);
}
"""


_KIOSK_JS = """
() => {
    if (!new URLSearchParams(window.location.search).has('kiosk')) return;
    function smKioskInit() {
        // Find and click the Mirror tab
        var btns = document.querySelectorAll('.tab-nav button');
        for (var i = 0; i < btns.length; i++) {
            if (btns[i].textContent.trim() === 'Mirror') {
                btns[i].click();
                break;
            }
        }
        // Hide the tab nav bar so only the mirror content is visible
        var nav = document.querySelector('.tab-nav');
        if (nav) nav.style.setProperty('display', 'none', 'important');
        // Remove scrollbars
        document.documentElement.style.overflow = 'hidden';
        document.body.style.overflow = 'hidden';
    }
    smKioskInit();
    setTimeout(smKioskInit, 500);
    setTimeout(smKioskInit, 1500);
}
"""


def build_smartmirror_dashboard(ctx: AppContext) -> gr.Blocks:
    initial_weather = fetch_weather()

    with gr.Blocks(title="SmartMirror") as demo:

        with gr.Tabs():
            display_comps   = build_display_tab(ctx, initial_weather=initial_weather)
            mirror_comps    = build_display_simple_tab(ctx, initial_weather=initial_weather)
            about_comps     = build_about_tab(ctx)
            operating_comps = build_operating_tab(ctx)

        wire_display_callbacks(display_comps, ctx)
        wire_display_simple_callbacks(mirror_comps, ctx)
        wire_about_callbacks(about_comps, ctx)
        wire_operating_callbacks(operating_comps, ctx)

        def _on_load():
            from ui.sm_about import (
                _calendar_token_exists,
                _model_exists,
                render_about,
            )
            return render_about(
                cam_ok=True,
                model_ok=_model_exists(),
                calendar_ok=_calendar_token_exists(ctx.base_dir),
            )

        demo.load(
            fn=_on_load,
            inputs=None,
            outputs=[about_comps["about_html"]],
            show_progress="hidden",
        )

        demo.load(fn=None, js=_CLOCK_JS)
        demo.load(fn=None, js=_WEBCAM_JS)
        demo.load(fn=None, js=_KIOSK_JS)

        # When a face is confirmed → sync that person's calendar into all panels
        def _on_user_confirmed(name, tasks, mode):
            if not name or name == "__unknown__":
                return gr.update(), gr.update(), gr.update(), gr.update()
            from ui.sm_operating import (
                try_google_calendar_sync,
                events_to_cal_tasks,
                render_task_list,
            )
            import db
            events, _ = try_google_calendar_sync(ctx.base_dir, name)
            cal_tasks = events_to_cal_tasks(events)
            try:
                db.replace_calendar_tasks(cal_tasks)
            except Exception as exc:
                print(f"[DB] face-sync failed: {exc}")
            user_tasks = [t for t in tasks if t.get("source") != "calendar"]
            new_tasks  = user_tasks + cal_tasks
            return events, _render_left(events), new_tasks, render_task_list(new_tasks, mode)

        display_comps["current_user_state"].change(
            fn=_on_user_confirmed,
            inputs=[
                display_comps["current_user_state"],
                operating_comps["tasks_state"],
                operating_comps["filter_state"],
            ],
            outputs=[
                display_comps["events_state"],
                display_comps["left_html"],
                operating_comps["tasks_state"],
                operating_comps["task_list_html"],
            ],
            show_progress="hidden",
        )

        # Propagate calendar events into Display and Mirror panels
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

    # GPIO: short press does nothing extra; hold shuts down
    def _noop():
        pass

    def _shutdown():
        import sys
        print("[SmartMirror] Shutdown button held — exiting.")
        sys.exit(0)

    try:
        ctx.gpio = start_gpio(
            ctx.cfg,
            on_short_press=_noop,
            on_hold_press=_shutdown,
        )
    except Exception as exc:
        print(f"[GPIO] Could not initialise button: {exc} — running without hardware button")

    return demo


def launch_smartmirror_dashboard(ctx: AppContext, demo: gr.Blocks) -> None:
    demo.launch(
        server_name=ctx.cfg.gradio_host,
        server_port=ctx.cfg.gradio_port,
        show_error=True,
        theme=_SM_THEME,
        css=SM_CSS,
    )
