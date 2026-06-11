"""SmartMirror — Mirror tab.

Layout: narrow left panel (clock only) | pure black empty center | narrow right panel (weather only).
The center represents the physical two-way mirror surface — no camera feed here.
"""

from __future__ import annotations

import gradio as gr

from ui.context import AppContext
from ui.sm_display import (
    SAMPLE_EVENTS,
    _day_abbr,
    _parse_weather,
    fetch_weather,
)
from ui.smartmirror_theme import (
    C_BORDER,
    C_CARD,
    C_CYAN,
    C_MUTED,
)

_PANEL_W = 240  # px


def _render_left(events: list[dict]) -> str:
    events_html = ""
    for ev in events[:6]:
        t      = ev.get("time", "")
        title  = ev.get("title", "")
        active = ev.get("active", False)
        border = f"border-left:2px solid {C_CYAN};" if active else ""
        bg     = "background:rgba(0,245,255,0.05);" if active else ""
        events_html += f"""
        <div style="{bg}border-radius:6px;padding:7px 10px;margin-bottom:5px;{border}">
            <div style="font-size:10px;color:{C_MUTED};margin-bottom:1px;">{t}</div>
            <div style="font-size:12px;color:#fff;line-height:1.3;">{title}</div>
        </div>"""

    return f"""
<div style="font-family:'Inter',sans-serif;background:#000;height:100%;
            padding:24px 16px;color:#fff;border-right:1px solid {C_BORDER};">
    <div id="sm2-time" style="font-size:52px;font-weight:300;letter-spacing:-2px;line-height:1;">--:--</div>
    <div id="sm2-date" style="font-size:11px;color:{C_MUTED};margin-top:6px;"></div>
    <div id="sm2-ampm" style="display:inline-block;border:1px solid {C_CYAN};color:{C_CYAN};
                font-size:9px;padding:1px 7px;border-radius:3px;
                margin-top:6px;letter-spacing:.06em;"></div>
    <div style="margin-top:20px;">
        <div style="font-size:9px;letter-spacing:.12em;text-transform:uppercase;
                    color:{C_CYAN};margin-bottom:8px;">Today's Schedule</div>
        {events_html or f'<div style="color:{C_MUTED};font-size:11px;">No events today.</div>'}
    </div>
</div>"""


def _render_right(weather_data: dict | None) -> str:
    w = _parse_weather(weather_data)

    forecast_html = ""
    for fc in w["forecast"]:
        forecast_html += f"""
        <div style="text-align:center;flex:1;">
            <div style="font-size:9px;color:{C_MUTED};letter-spacing:.06em;
                        text-transform:uppercase;">{_day_abbr(fc['date'])}</div>
            <div style="font-size:16px;margin:3px 0;">{fc['icon']}</div>
            <div style="font-size:11px;color:#fff;">{fc['min']}°</div>
        </div>"""

    return f"""
<div style="font-family:'Inter',sans-serif;background:#000;height:100%;
            padding:24px 16px;color:#fff;border-left:1px solid {C_BORDER};">
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">
        <span style="font-size:32px;line-height:1;">{w['icon']}</span>
        <div>
            <div style="font-size:28px;font-weight:300;line-height:1;">{w['temp_c']}°C</div>
            <div style="font-size:10px;color:{C_MUTED};margin-top:3px;">{w['desc']}</div>
            <div style="font-size:10px;color:{C_MUTED};">{w['city']}, {w['country']}</div>
        </div>
    </div>
    <div style="border-top:1px solid {C_BORDER};padding-top:10px;
                display:grid;grid-template-columns:1fr 1fr;gap:8px;">
        <div>
            <div style="font-size:8px;color:{C_MUTED};text-transform:uppercase;
                        letter-spacing:.05em;">Feels</div>
            <div style="font-size:12px;margin-top:2px;">{w['feels_c']}°C</div>
        </div>
        <div>
            <div style="font-size:8px;color:{C_MUTED};text-transform:uppercase;
                        letter-spacing:.05em;">Humidity</div>
            <div style="font-size:12px;margin-top:2px;">{w['humidity']}%</div>
        </div>
        <div>
            <div style="font-size:8px;color:{C_MUTED};text-transform:uppercase;
                        letter-spacing:.05em;">Wind</div>
            <div style="font-size:12px;margin-top:2px;">{w['wind_kmph']} km/h</div>
        </div>
        <div>
            <div style="font-size:8px;color:{C_MUTED};text-transform:uppercase;
                        letter-spacing:.05em;">UV</div>
            <div style="font-size:12px;margin-top:2px;">{w['uv']}</div>
        </div>
    </div>
    {f'<div style="border-top:1px solid {C_BORDER};margin-top:10px;padding-top:10px;display:flex;">' + forecast_html + '</div>' if forecast_html else ''}
</div>"""


def render_display_simple(
    weather_data: dict | None,
    events: list[dict],
) -> tuple[str, str]:
    return _render_left(events), _render_right(weather_data)


def build_display_simple_tab(ctx: AppContext, initial_weather=None) -> dict:
    with gr.TabItem("Mirror", id="mirror", render_children=False):
        with gr.Row(equal_height=True):
            with gr.Column(min_width=_PANEL_W, scale=0):
                left_html = gr.HTML(_render_left(SAMPLE_EVENTS), sanitize_html=False)
            with gr.Column(scale=3):
                gr.HTML(
                    '<div style="background:#000;height:100%;min-height:80vh;'
                    'display:flex;align-items:center;justify-content:center;">'
                    f'<div style="width:60%;height:2px;background:{C_BORDER};'
                    f'opacity:0.3;"></div></div>',
                    sanitize_html=False,
                )
            with gr.Column(min_width=_PANEL_W, scale=0):
                right_html = gr.HTML(_render_right(initial_weather), sanitize_html=False)

        weather_state = gr.State(initial_weather)
        events_state  = gr.State(list(SAMPLE_EVENTS))
        weather_timer = gr.Timer(value=300.0, active=True)

    return {
        "left_html":     left_html,
        "right_html":    right_html,
        "weather_state": weather_state,
        "events_state":  events_state,
        "weather_timer": weather_timer,
    }


def wire_display_simple_callbacks(comps: dict, ctx: AppContext) -> None:
    def _weather_tick(w, ev):
        new_w = fetch_weather()
        return _render_right(new_w), new_w

    comps["weather_timer"].tick(
        fn=_weather_tick,
        inputs=[comps["weather_state"], comps["events_state"]],
        outputs=[comps["right_html"], comps["weather_state"]],
        show_progress="hidden",
    )
