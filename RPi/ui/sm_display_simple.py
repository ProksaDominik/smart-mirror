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
    C_BORDER,
    C_CYAN,
)


def render_mirror(
    weather_data: dict | None,
    events: list[dict],
    name: str = "",
    tasks: list[dict] | None = None,
) -> str:
    from datetime import date as _date
    w = _parse_weather(weather_data)
    M = "#C8C8DC"  # brighter muted for LCD visibility

    # Greeting section
    if name and name != "__unknown__":
        from ui.sm_display import _time_period
        greeting_html = (
            f'<div style="margin-bottom:6px;">'
            f'<div style="font-size:11px;letter-spacing:.16em;text-transform:uppercase;'
            f'color:{C_CYAN};margin-bottom:4px;">Welcome</div>'
            f'<div style="font-size:28px;font-weight:300;color:#fff;">'
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
        border = f"border-left:2px solid {C_CYAN};padding-left:12px;" if active else "padding-left:14px;"
        color  = "#fff" if active else M
        events_html += (
            f'<div style="display:flex;align-items:baseline;gap:16px;'
            f'margin-bottom:12px;{border}">'
            f'<span style="font-size:14px;color:{C_CYAN};min-width:44px;font-weight:300;">{t}</span>'
            f'<span style="font-size:16px;color:{color};line-height:1.3;font-weight:300;">{title}</span>'
            f'</div>'
        )

    # Tasks section (to-do list from calendar)
    tasks_html = ""
    if tasks:
        today = _date.today().isoformat()
        rows = ""
        for t in tasks:
            if t.get("completed"):
                continue
            title = t.get("title", t.get("text", ""))
            due   = t.get("due", "")
            color = C_CYAN if due == today else M
            rows += (
                f'<div style="display:flex;align-items:baseline;gap:10px;'
                f'margin-bottom:10px;padding-left:14px;">'
                f'<span style="font-size:13px;color:{color};font-weight:300;">·</span>'
                f'<span style="font-size:14px;color:{M};line-height:1.3;font-weight:300;">{title}</span>'
                f'</div>'
            )
        if rows:
            tasks_html = (
                f'<div style="margin-top:16px;">'
                f'<div style="font-size:10px;letter-spacing:.2em;text-transform:uppercase;'
                f'color:{C_CYAN};margin-bottom:10px;'
                f'border-bottom:1px solid rgba(0,245,255,0.2);padding-bottom:6px;">To-Do</div>'
                f'{rows}'
                f'</div>'
            )

    forecast_html = ""
    for fc in w["forecast"]:
        forecast_html += (
            f'<div style="text-align:center;flex:1;">'
            f'<div style="font-size:11px;color:{M};letter-spacing:.06em;'
            f'text-transform:uppercase;margin-bottom:4px;">{_day_abbr(fc["date"])}</div>'
            f'<div style="font-size:14px;color:#fff;">{fc["min"]}°</div>'
            f'</div>'
        )

    return f"""
<div style="
    font-family:'Inter',sans-serif;
    background:#000;
    color:#fff;
    height:100vh;
    width:100%;
    display:flex;
    flex-direction:column;
    padding:44px 40px 36px;
    box-sizing:border-box;
    overflow:hidden;
">

  <!-- Greeting (only when a face is recognised) -->
  {f'<div style="flex:0 0 auto;padding-bottom:16px;">{greeting_html}</div>' if greeting_html else ''}

  <!-- Clock — flex:2 -->
  <div style="flex:2;display:flex;flex-direction:column;justify-content:center;min-height:0;">
    <div style="display:flex;align-items:flex-end;gap:16px;">
      <div id="sm2-time"
           style="font-size:100px;font-weight:400;letter-spacing:-4px;line-height:1;color:#fff;">
        --:--
      </div>
      <div id="sm2-ampm"
           style="font-size:16px;color:{C_CYAN};border:1px solid {C_CYAN};
                  border-radius:4px;padding:4px 10px;margin-bottom:16px;
                  letter-spacing:.1em;">
      </div>
    </div>
    <div id="sm2-date"
         style="font-size:18px;color:{M};margin-top:6px;font-weight:300;letter-spacing:.02em;">
    </div>
  </div>

  <!-- Today's Schedule — flex:3 -->
  <div style="flex:3;min-height:0;overflow:visible;">
    <div style="font-size:10px;letter-spacing:.2em;text-transform:uppercase;
                color:{C_CYAN};margin-bottom:12px;
                border-bottom:1px solid rgba(0,245,255,0.2);padding-bottom:6px;">
      Today's Schedule
    </div>
    {events_html or f'<div style="color:{M};font-size:15px;font-weight:300;">No events today.</div>'}
    {tasks_html}
  </div>

  <!-- Mirror area — flex:3 (dominant section, the physical glass) -->
  <div style="flex:3;min-height:0;"></div>

  <!-- Weather — flex:2 -->
  <div style="flex:2;min-height:0;display:flex;flex-direction:column;justify-content:center;">
    <div style="font-size:10px;letter-spacing:.2em;text-transform:uppercase;
                color:{C_CYAN};margin-bottom:12px;
                border-top:1px solid rgba(0,245,255,0.2);padding-top:12px;">
      Weather
    </div>
    <div style="display:flex;align-items:baseline;gap:16px;margin-bottom:14px;">
      <div style="font-size:56px;font-weight:400;line-height:1;color:#fff;">{w['temp_c']}°C</div>
      <div>
        <div style="font-size:16px;color:#fff;font-weight:300;">{w['desc']}</div>
        <div style="font-size:13px;color:{M};margin-top:2px;">{w['city']}, {w['country']}</div>
      </div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:10px;margin-bottom:12px;">
      <div>
        <div style="font-size:10px;color:{M};text-transform:uppercase;letter-spacing:.06em;">Feels</div>
        <div style="font-size:18px;margin-top:3px;font-weight:500;color:#fff;">{w['feels_c']}°</div>
      </div>
      <div>
        <div style="font-size:10px;color:{M};text-transform:uppercase;letter-spacing:.06em;">Humidity</div>
        <div style="font-size:18px;margin-top:3px;font-weight:500;color:#fff;">{w['humidity']}%</div>
      </div>
      <div>
        <div style="font-size:10px;color:{M};text-transform:uppercase;letter-spacing:.06em;">Wind</div>
        <div style="font-size:18px;margin-top:3px;font-weight:500;color:#fff;">{w['wind_kmph']} km/h</div>
      </div>
      <div>
        <div style="font-size:10px;color:{M};text-transform:uppercase;letter-spacing:.06em;">UV</div>
        <div style="font-size:18px;margin-top:3px;font-weight:500;color:#fff;">{w['uv']}</div>
      </div>
    </div>
    {f'<div style="display:flex;gap:16px;">{forecast_html}</div>' if forecast_html else ''}
  </div>

</div>"""


def build_display_simple_tab(ctx: AppContext, initial_weather=None) -> dict:
    with gr.TabItem("Mirror", id="mirror", render_children=False):
        mirror_html   = gr.HTML(render_mirror(initial_weather, []), sanitize_html=False)
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
        return render_mirror(new_w, ev, name, tasks), new_w

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

        return render_mirror(new_w, new_ev, name, new_tasks), new_ev, new_tasks, name

    comps["sync_timer"].tick(
        fn=_sync_tick,
        inputs=[comps["name_state"], comps["events_state"], comps["tasks_state"], comps["weather_state"]],
        outputs=[comps["mirror_html"], comps["events_state"], comps["tasks_state"], comps["name_state"]],
        show_progress="hidden",
    )
