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
from ui.sm_debug import build_debug_tab, wire_debug_callbacks
from ui.sm_display import (
    _render_left,
    _render_display_tasks,
    build_display_tab,
    fetch_weather,
    reset_scan_state,
    wire_display_callbacks,
)
from ui.sm_display_simple import (
    build_display_simple_tab,
    render_mirror,
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
    // Phase 0: need to click "Click to Access Webcam"
    // Phase 1: webcam clicked, waiting for recording button
    // Phase 2: streaming active
    var _smPhase = 0;
    var _smObs = null;

    function smClickAccessWebcam() {
        var btns = document.querySelectorAll('button');
        for (var i = 0; i < btns.length; i++) {
            var b = btns[i];
            if (b.offsetParent !== null && b.textContent &&
                    b.textContent.toLowerCase().indexOf('access webcam') !== -1) {
                b.click();
                _smPhase = 1;
                return true;
            }
        }
        return false;
    }

    function smClickRecord() {
        // In Gradio 6, the streaming button has an inner element with title="start recording"
        var recEl = document.querySelector('[title="start recording"]');
        if (recEl && recEl.offsetParent !== null) {
            // Walk up to the parent <button>
            var el = recEl;
            while (el && el.tagName !== 'BUTTON' && el.tagName !== 'BODY') {
                el = el.parentElement;
            }
            if (el && el.tagName === 'BUTTON') {
                el.click();
                _smPhase = 2;
                if (_smObs) { _smObs.disconnect(); _smObs = null; }
                return true;
            }
        }
        // Fallback: aria-label="capture photo" is the same button in image mode
        var capBtn = document.querySelector('button[aria-label="capture photo"]');
        if (capBtn && capBtn.offsetParent !== null) {
            capBtn.click();
            _smPhase = 2;
            if (_smObs) { _smObs.disconnect(); _smObs = null; }
            return true;
        }
        return false;
    }

    function smStep() {
        if (_smPhase === 2) return;
        if (_smPhase < 1) {
            // If video is already visible the user already clicked access webcam
            if (document.querySelector('video')) {
                _smPhase = 1;
            } else {
                smClickAccessWebcam();
            }
        }
        if (_smPhase >= 1) {
            smClickRecord();
        }
    }

    // Retry schedule — covers both "user hasn't clicked yet" and
    // "user already clicked but recording button appeared after our JS ran"
    setTimeout(smStep, 400);
    setTimeout(smStep, 1000);
    setTimeout(smStep, 2000);
    setTimeout(smStep, 3500);
    setTimeout(smStep, 6000);

    // MutationObserver for dynamic DOM changes (webcam permission, button swap)
    _smObs = new MutationObserver(smStep);
    _smObs.observe(document.body, {childList: true, subtree: true});
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
        // Remove all Gradio padding so the mirror fills 100vh
        var container = document.querySelector('.gradio-container');
        if (container) {
            container.style.setProperty('padding', '0', 'important');
            container.style.setProperty('margin', '0', 'important');
            container.style.setProperty('height', '100vh', 'important');
            container.style.setProperty('overflow', 'hidden', 'important');
        }
        // Also remove padding from tabitem wrapper
        document.querySelectorAll('.tabitem,.tab-content').forEach(function(el) {
            el.style.setProperty('padding', '0', 'important');
            el.style.setProperty('height', '100vh', 'important');
        });
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
            debug_comps     = build_debug_tab()

        wire_display_callbacks(display_comps, ctx, op_comps=operating_comps)
        wire_display_simple_callbacks(mirror_comps, ctx)
        wire_about_callbacks(about_comps, ctx)
        wire_operating_callbacks(operating_comps, ctx)
        wire_debug_callbacks(debug_comps)

        def _on_load():
            reset_scan_state()  # Always first — must not be delayed by anything below
            from ui.sm_about import _calendar_token_exists, _model_exists, render_about
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

        # When a face is confirmed → sync calendar and update all panels including Mirror tab
        def _on_user_confirmed(name, tasks, mode, mirror_w):
            print(f"[SYNC] _on_user_confirmed called with name={name!r}")
            if not name or name == "__unknown__":
                return gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update()
            from ui.sm_operating import (
                try_google_calendar_sync,
                events_to_cal_tasks,
                render_task_list,
            )
            from ui.sm_display import _render_display_tasks
            import db
            print(f"[SYNC] syncing calendar for {name!r} from {ctx.base_dir}")
            events, msg = try_google_calendar_sync(ctx.base_dir, name)
            print(f"[SYNC] got {len(events)} events, msg={msg!r}")
            cal_tasks = events_to_cal_tasks(events)
            try:
                db.replace_calendar_tasks(cal_tasks)
            except Exception as exc:
                print(f"[DB] face-sync failed: {exc}")
            mirror = render_mirror(mirror_w, events, name, cal_tasks)
            return (
                events,
                _render_left(events),
                _render_display_tasks(cal_tasks),
                cal_tasks,
                render_task_list(cal_tasks, mode),
                mirror,
                name,
                cal_tasks,
            )

        display_comps["current_user_state"].change(
            fn=_on_user_confirmed,
            inputs=[
                display_comps["current_user_state"],
                operating_comps["tasks_state"],
                operating_comps["filter_state"],
                mirror_comps["weather_state"],
            ],
            outputs=[
                display_comps["events_state"],
                display_comps["left_html"],
                display_comps["tasks_html"],
                operating_comps["tasks_state"],
                operating_comps["task_list_html"],
                mirror_comps["mirror_html"],
                mirror_comps["name_state"],
                mirror_comps["tasks_state"],
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
            fn=lambda ev, w, name, tasks: render_mirror(w, ev, name, tasks),
            inputs=[operating_comps["events_state"], mirror_comps["weather_state"],
                    mirror_comps["name_state"], mirror_comps["tasks_state"]],
            outputs=[mirror_comps["mirror_html"]],
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
