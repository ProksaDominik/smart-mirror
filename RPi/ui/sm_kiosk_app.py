"""Standalone kiosk Gradio app — no tabs, just the mirror display.

Runs on port 8501. The LCD kiosk browser points here.
The main dashboard (port 8500) remains unchanged for management.
"""

from __future__ import annotations

import threading

import gradio as gr

from ui.sm_display import SAMPLE_EVENTS, fetch_weather
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
.block, .html-container, .svelte-1gfkn6j {
    padding: 0 !important;
    margin: 0 !important;
    height: 100vh !important;
}
"""


def build_kiosk_app() -> gr.Blocks:
    initial_weather = fetch_weather()

    with gr.Blocks(css=_KIOSK_CSS, title="SmartMirror") as demo:
        mirror_html   = gr.HTML(render_mirror(initial_weather, SAMPLE_EVENTS), sanitize_html=False)
        weather_state = gr.State(initial_weather)
        events_state  = gr.State(list(SAMPLE_EVENTS))
        timer         = gr.Timer(value=60.0, active=True)

        def _tick(w, ev):
            new_w = fetch_weather()
            return render_mirror(new_w, ev), new_w

        timer.tick(
            fn=_tick,
            inputs=[weather_state, events_state],
            outputs=[mirror_html, weather_state],
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
    )


def start_kiosk_thread(port: int = 8501) -> None:
    """Launch the kiosk app in a background thread alongside the main dashboard."""
    demo = build_kiosk_app()

    def _run():
        launch_kiosk_app(demo, port)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
