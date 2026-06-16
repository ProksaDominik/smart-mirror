"""Standalone kiosk Gradio app — no tabs, just the mirror display.

Runs on port 8501. The LCD kiosk browser points here.
The main dashboard (port 8500) remains unchanged for management.
"""

from __future__ import annotations

import threading
from pathlib import Path

import gradio as gr

from ui.sm_display import fetch_weather
from ui.sm_display_simple import render_mirror
from ui.smartmirror_theme import SM_CSS

_CLOCK_JS = """
() => {
    var D=['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
    var M=['January','February','March','April','May','June','July','August',
           'September','October','November','December'];
    function p(n){return String(n).padStart(2,'0');}
    function tick(){
        var n=new Date(), h=n.getHours(), m=n.getMinutes();
        var el=document.getElementById('sm2-time'); if(el) el.textContent=p(h)+':'+p(m);
        el=document.getElementById('sm2-date');
        if(el) el.textContent=D[n.getDay()]+', '+p(n.getDate())+' '+M[n.getMonth()]+' '+n.getFullYear();
        el=document.getElementById('sm2-ampm'); if(el) el.textContent=h>=12?'PM':'AM';
    }
    if(window._smClock) clearInterval(window._smClock);
    tick();
    window._smClock = setInterval(tick, 1000);
}
"""

_KIOSK_CSS = SM_CSS + """
html, body, .gradio-container, .gradio-container > .main {
    margin: 0 !important;
    padding: 0 !important;
    height: 100vh !important;
    overflow: hidden !important;
}
.block, .html-container {
    padding: 0 !important;
    margin: 0 !important;
    height: 100vh !important;
}
"""


def build_kiosk_app(base_dir: Path) -> gr.Blocks:
    initial_weather = fetch_weather()

    with gr.Blocks(title="SmartMirror") as demo:
        mirror_html    = gr.HTML(render_mirror(initial_weather, []), sanitize_html=False)
        weather_state  = gr.State(initial_weather)
        events_state   = gr.State([])
        tasks_state    = gr.State([])
        synced_user    = gr.State("")
        timer          = gr.Timer(value=2.0, active=True)

        def _tick(w, ev, tasks, last_user):
            import ui.sm_display as _disp
            name = _disp._current_user

            # Refresh weather every call (cached for 5 min)
            new_w = fetch_weather()

            # If user hasn't changed, just re-render with current data
            if not name or name == last_user:
                return render_mirror(new_w, ev, name, tasks), new_w, ev, tasks, last_user

            # Unknown face — show message on mirror but skip calendar sync
            if name == "__unknown__":
                return render_mirror(new_w, ev, name, tasks), new_w, ev, tasks, name

            # New user recognised — sync their calendar
            try:
                from ui.sm_operating import try_google_calendar_sync, events_to_cal_tasks
                new_ev, msg = try_google_calendar_sync(base_dir, name)
                print(f"[KIOSK] {name}: {len(new_ev)} events — {msg}")
                new_tasks = events_to_cal_tasks(new_ev)
            except Exception as exc:
                print(f"[KIOSK] calendar sync failed: {exc}")
                new_ev, new_tasks = ev, tasks

            return render_mirror(new_w, new_ev, name, new_tasks), new_w, new_ev, new_tasks, name

        timer.tick(
            fn=_tick,
            inputs=[weather_state, events_state, tasks_state, synced_user],
            outputs=[mirror_html, weather_state, events_state, tasks_state, synced_user],
            show_progress="hidden",
        )

        demo.load(fn=None, js=_CLOCK_JS)

    return demo


def launch_kiosk_app(demo: gr.Blocks, port: int = 8501) -> None:
    demo.launch(
        server_name="0.0.0.0",
        server_port=port,
        show_error=False,
        prevent_thread_lock=True,
        css=_KIOSK_CSS,
    )


def start_kiosk_thread(port: int = 8501, base_dir: Path = Path(".")) -> None:
    """Launch the kiosk app in a background thread alongside the main dashboard."""
    demo = build_kiosk_app(base_dir)

    def _run():
        launch_kiosk_app(demo, port)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
