"""SmartMirror — Mirror tab.

Portrait layout (single column, fills 100 vh):
  ┌─────────────────┐
  │  HH:MM  AM/PM   │  ← clock
  │  Day, DD Month  │
  ├─────────────────┤
  │ TODAY'S SCHEDULE│  ← events
  ├─────────────────┤
  │                 │  ← black mirror area (flex: 1)
  ├─────────────────┤
  │  🌡 22°C Cloudy │  ← weather
  └─────────────────┘
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
    APP_FONT,
    C_BORDER,
    C_CYAN,
)

# Per-person personalised look on the mirror — distinct font + accent color.
# Dominik uses APP_FONT/C_CYAN (the global default) so no entry is needed here.
_PERSON_STYLE = {
    "Radu":  {"font": "'Space Mono', monospace",   "accent": "#FFA630"},
    "Liviu": {"font": "'Playfair Display', serif", "accent": "#FF3DA6"},
}


def render_mirror(
    weather_data: dict | None,
    events: list[dict],
    name: str = "",
    tasks: list[dict] | None = None,
    height_css: str = "100vh",
) -> str:
    from datetime import date as _date
    w = _parse_weather(weather_data)
    M = "#C8C8DC"  # brighter muted for LCD visibility

    person_style = _PERSON_STYLE.get(name, {})
    font_family  = person_style.get("font", APP_FONT)
    accent       = person_style.get("accent", C_CYAN)

    # Idle — no face recognised yet: blank screen, like the display is off
    if not name:
        return f'<div style="background:#000;height:{height_css};width:100vw;"></div>'

    # Unknown face — full-screen warning
    if name == "__unknown__":
        return f"""
<div style="
    font-family:{APP_FONT};
    background:#000;
    height:{height_css};
    width:100vw;
    display:flex;
    flex-direction:column;
    align-items:center;
    justify-content:center;
    box-sizing:border-box;
">
  <div style="font-size:clamp(90px,19vmin,190px);margin-bottom:clamp(28px,6.5vmin,54px);">⚠️</div>
  <div style="font-size:clamp(17px,2.9vmin,26px);letter-spacing:.3em;text-transform:uppercase;
              color:#FF3366;margin-bottom:clamp(18px,4vmin,34px);">Unknown</div>
  <div style="font-size:clamp(40px,10vmin,86px);font-weight:300;color:#fff;text-align:center;
              line-height:1.2;">Unregistered<br>face</div>
  <div style="width:clamp(80px,16vmin,134px);height:3px;background:#FF3366;margin-top:clamp(28px,6.5vmin,54px);border-radius:2px;"></div>
</div>"""

    # Greeting section
    if name and name != "__unknown__":
        from ui.sm_display import _time_period
        greeting_html = (
            f'<div style="margin-bottom:clamp(6px,1.2vmin,8px);">'
            f'<div style="font-size:clamp(15px,2.4vmin,19px);letter-spacing:.16em;text-transform:uppercase;'
            f'color:{accent};margin-bottom:clamp(5px,1vmin,7px);">Welcome</div>'
            f'<div style="font-size:clamp(36px,6.5vmin,44px);font-weight:300;color:#fff;">'
            f'{_time_period()}, {name}</div>'
            f'</div>'
        )
    else:
        greeting_html = ""

    events_html = ""
    for ev in events[:3]:
        t      = ev.get("time", "")
        title  = ev.get("title", "")
        active = ev.get("active", False)
        border = f"border-left:2px solid {accent};padding-left:clamp(13px,2.4vmin,20px);" if active else "padding-left:clamp(16px,2.8vmin,22px);"
        color  = "#fff" if active else M
        events_html += (
            f'<div style="display:flex;align-items:baseline;gap:clamp(16px,3vmin,26px);'
            f'margin-bottom:clamp(11px,2.2vmin,20px);{border}">'
            f'<span style="font-size:clamp(16px,2.8vmin,26px);color:{accent};min-width:clamp(46px,8vmin,74px);font-weight:300;">{t}</span>'
            f'<span style="font-size:clamp(18px,3.2vmin,30px);color:{color};line-height:1.3;font-weight:300;">{title}</span>'
            f'</div>'
        )

    # Tasks section — only genuine to-do items, not calendar events
    # (those are already shown above in the Schedule section)
    tasks_html = ""
    if tasks:
        today = _date.today().isoformat()
        rows = ""
        for t in tasks:
            if t.get("completed") or t.get("source") == "calendar":
                continue
            title = t.get("title", t.get("text", ""))
            due   = t.get("due", "")
            color = accent if due == today else M
            rows += (
                f'<div style="display:flex;align-items:baseline;gap:clamp(11px,2vmin,18px);'
                f'margin-bottom:clamp(11px,2vmin,18px);padding-left:clamp(16px,2.8vmin,22px);">'
                f'<span style="font-size:clamp(14px,2.4vmin,22px);color:{color};font-weight:300;">·</span>'
                f'<span style="font-size:clamp(16px,2.8vmin,24px);color:{M};line-height:1.3;font-weight:300;">{title}</span>'
                f'</div>'
            )
        if rows:
            tasks_html = (
                f'<div style="margin-top:clamp(26px,5vmin,38px);">'
                f'<div style="font-size:clamp(13px,2vmin,18px);letter-spacing:.2em;text-transform:uppercase;'
                f'color:{accent};margin-bottom:clamp(18px,3.4vmin,28px);'
                f'border-bottom:1px solid rgba(108,92,231,0.2);padding-bottom:clamp(6px,1.3vmin,12px);">To-Do</div>'
                f'{rows}'
                f'</div>'
            )

    forecast_html = ""
    for fc in w["forecast"]:
        forecast_html += (
            f'<div style="text-align:center;flex:1;">'
            f'<div style="font-size:clamp(12px,1.8vmin,16px);color:{M};letter-spacing:.06em;'
            f'text-transform:uppercase;margin-bottom:clamp(4px,0.9vmin,8px);">{_day_abbr(fc["date"])}</div>'
            f'<div style="font-size:clamp(16px,2.6vmin,22px);color:#fff;">{fc["min"]}°</div>'
            f'</div>'
        )

    return f"""
<div style="
    font-family:{font_family};
    background:#000;
    color:#fff;
    height:{height_css};
    width:100vw;
    display:flex;
    flex-direction:column;
    padding:clamp(26px,5.5vmin,68px) clamp(26px,5.5vmin,64px) clamp(20px,4.5vmin,54px);
    box-sizing:border-box;
    overflow:hidden;
">

  <!-- Greeting (only when a face is recognised) -->
  {f'<div style="flex:0 0 auto;padding-bottom:clamp(14px,2.6vmin,26px);">{greeting_html}</div>' if greeting_html else ''}

  <!-- Clock — flex:2 -->
  <div style="flex:2;display:flex;flex-direction:column;justify-content:center;min-height:0;">
    <div style="display:flex;align-items:flex-end;gap:clamp(14px,2.6vmin,26px);">
      <div id="sm2-time"
           style="font-size:clamp(80px,20vmin,210px);font-weight:400;letter-spacing:-4px;line-height:1;color:#fff;">
        --:--
      </div>
      <div id="sm2-ampm"
           style="font-size:clamp(16px,3vmin,30px);color:{accent};border:1px solid {accent};
                  border-radius:4px;padding:clamp(5px,1vmin,10px) clamp(12px,2vmin,18px);
                  margin-bottom:clamp(14px,3.6vmin,30px);letter-spacing:.1em;">
      </div>
    </div>
    <div id="sm2-date"
         style="font-size:clamp(20px,3.8vmin,36px);color:#fff;margin-top:clamp(6px,1.5vmin,14px);
                font-weight:500;letter-spacing:.02em;">
    </div>
  </div>

  <!-- Today's Schedule — flex:3 -->
  <div style="flex:3;min-height:0;overflow:visible;padding-top:clamp(14px,2.6vmin,22px);">
    {events_html or f'<div style="color:{M};font-size:clamp(18px,2.9vmin,28px);font-weight:300;">No events today.</div>'}
    {tasks_html}
  </div>

  <!-- Mirror area — flex:3 (dominant section, the physical glass) -->
  <div style="flex:3;min-height:0;"></div>

  <!-- Weather — flex:2 -->
  <div style="flex:2;min-height:0;display:flex;flex-direction:column;justify-content:center;">
    <div style="font-size:clamp(13px,2vmin,18px);letter-spacing:.2em;text-transform:uppercase;
                color:{accent};margin-bottom:clamp(11px,2.6vmin,22px);
                border-top:1px solid rgba(108,92,231,0.2);padding-top:clamp(11px,2.6vmin,22px);">
      Weather
    </div>
    <div style="display:flex;align-items:baseline;gap:clamp(14px,2.8vmin,26px);margin-bottom:clamp(13px,3vmin,26px);">
      <div style="font-size:clamp(48px,16vmin,130px);font-weight:400;line-height:1;color:#fff;">{w['temp_c']}°C</div>
      <div>
        <div style="font-size:clamp(18px,3.4vmin,32px);color:#fff;font-weight:300;">{w['desc']}</div>
        <div style="font-size:clamp(14px,2.6vmin,24px);color:{M};margin-top:clamp(3px,0.7vmin,7px);">{w['city']}, {w['country']}</div>
      </div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:clamp(11px,2.2vmin,20px);margin-bottom:clamp(11px,2.6vmin,22px);">
      <div>
        <div style="font-size:clamp(12px,1.9vmin,17px);color:{M};text-transform:uppercase;letter-spacing:.06em;">Feels</div>
        <div style="font-size:clamp(20px,3.6vmin,32px);margin-top:clamp(3px,0.7vmin,7px);font-weight:500;color:#fff;">{w['feels_c']}°</div>
      </div>
      <div>
        <div style="font-size:clamp(12px,1.9vmin,17px);color:{M};text-transform:uppercase;letter-spacing:.06em;">Humidity</div>
        <div style="font-size:clamp(20px,3.6vmin,32px);margin-top:clamp(3px,0.7vmin,7px);font-weight:500;color:#fff;">{w['humidity']}%</div>
      </div>
      <div>
        <div style="font-size:clamp(12px,1.9vmin,17px);color:{M};text-transform:uppercase;letter-spacing:.06em;">Wind</div>
        <div style="font-size:clamp(20px,3.6vmin,32px);margin-top:clamp(3px,0.7vmin,7px);font-weight:500;color:#fff;">{w['wind_kmph']} km/h</div>
      </div>
      <div>
        <div style="font-size:clamp(12px,1.9vmin,17px);color:{M};text-transform:uppercase;letter-spacing:.06em;">UV</div>
        <div style="font-size:clamp(20px,3.6vmin,32px);margin-top:clamp(3px,0.7vmin,7px);font-weight:500;color:#fff;">{w['uv']}</div>
      </div>
    </div>
    {f'<div style="display:flex;gap:clamp(14px,2.8vmin,26px);">{forecast_html}</div>' if forecast_html else ''}
  </div>

</div>"""


_MIRROR_TAB_CSS = """
<style>
/* The Mirror tab's HTML uses height:100% — give its ancestor chain the
   real available height (viewport minus the tab nav bar) so vmin-based
   sizing inside doesn't overflow into other sections. */
#mirror, #mirror > .block, #mirror .html-container, #mirror .gradio-html {
    height: calc(100vh - 52px) !important;
    max-height: calc(100vh - 52px) !important;
    width: 100% !important;
    padding: 0 !important;
    margin: 0 !important;
    overflow: hidden !important;
}
</style>
"""


_TAB_HEIGHT_CSS = "calc(100vh - 52px)"  # full viewport minus the dashboard's tab nav bar


def build_display_simple_tab(ctx: AppContext, initial_weather=None) -> dict:
    with gr.TabItem("Mirror", id="mirror", render_children=False):
        gr.HTML(_MIRROR_TAB_CSS, sanitize_html=False)
        mirror_html   = gr.HTML(render_mirror(initial_weather, [], height_css=_TAB_HEIGHT_CSS), sanitize_html=False)
        weather_state = gr.State(initial_weather)
        events_state  = gr.State([])
        name_state    = gr.State("")
        tasks_state   = gr.State([])
        weather_timer = gr.Timer(value=300.0, active=True)
        sync_timer    = gr.Timer(value=2.0, active=True)

    return {
        "mirror_html":   mirror_html,
        "weather_state": weather_state,
        "events_state":  events_state,
        "name_state":    name_state,
        "tasks_state":   tasks_state,
        "weather_timer": weather_timer,
        "sync_timer":    sync_timer,
    }


def wire_display_simple_callbacks(comps: dict, ctx: AppContext) -> None:
    def _weather_tick(w, ev, name, tasks):
        new_w = fetch_weather()
        return render_mirror(new_w, ev, name, tasks, height_css=_TAB_HEIGHT_CSS), new_w

    comps["weather_timer"].tick(
        fn=_weather_tick,
        inputs=[comps["weather_state"], comps["events_state"], comps["name_state"], comps["tasks_state"]],
        outputs=[comps["mirror_html"], comps["weather_state"]],
        show_progress="hidden",
    )

    def _sync_tick(last_name, ev, tasks, w):
        import ui.sm_display as _disp
        name = _disp._current_user
        new_w = fetch_weather()

        if not name or name == last_name:
            return gr.update(), gr.update(), gr.update(), last_name

        try:
            from ui.sm_operating import try_google_calendar_sync, events_to_cal_tasks
            new_ev, msg = try_google_calendar_sync(ctx.base_dir, name)
            print(f"[MIRROR] {name}: {len(new_ev)} events — {msg}")
            new_tasks = events_to_cal_tasks(new_ev)
        except Exception as exc:
            print(f"[MIRROR] sync failed: {exc}")
            new_ev, new_tasks = ev, tasks

        return render_mirror(new_w, new_ev, name, new_tasks, height_css=_TAB_HEIGHT_CSS), new_ev, new_tasks, name

    comps["sync_timer"].tick(
        fn=_sync_tick,
        inputs=[comps["name_state"], comps["events_state"], comps["tasks_state"], comps["weather_state"]],
        outputs=[comps["mirror_html"], comps["events_state"], comps["tasks_state"], comps["name_state"]],
        show_progress="hidden",
    )
