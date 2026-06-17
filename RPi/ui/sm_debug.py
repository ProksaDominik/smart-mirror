"""SmartMirror — Debug tab. Test hardware components."""

from __future__ import annotations

import subprocess

import gradio as gr

from ui.smartmirror_theme import C_BORDER, C_CARD, C_CYAN, C_GREEN, C_MUTED, C_RED, C_WHITE


def _status_html(msg: str) -> str:
    if msg == "idle":
        return f'<div style="font-family:Bebas Neue,sans-serif;color:{C_MUTED};font-size:14px;">Ready.</div>'
    if msg == "playing":
        return f'<div style="font-family:Bebas Neue,sans-serif;font-size:14px;color:{C_CYAN};">▶ Playing…</div>'
    if msg == "ok":
        return f'<div style="font-family:Bebas Neue,sans-serif;font-size:14px;color:{C_GREEN};">✔ Speakers OK</div>'
    if msg == "stopped":
        return f'<div style="font-family:Bebas Neue,sans-serif;font-size:14px;color:{C_MUTED};">⏹ Stopped</div>'
    return f'<div style="font-family:Bebas Neue,sans-serif;font-size:14px;color:{C_RED};">✘ {msg}</div>'


def build_debug_tab() -> dict:
    with gr.TabItem("Debug", id="debug"):
        gr.HTML(
            f'<div style="font-family:Bebas Neue,sans-serif;padding:18px 32px;'
            f'border-bottom:1px solid {C_BORDER};background:{C_CARD};">'
            f'<span style="font-size:20px;font-weight:700;color:{C_WHITE};">SmartMirror</span>'
            f'<span style="font-size:16px;color:#7B2FFF;"> / Debug</span>'
            f'</div>',
            sanitize_html=False,
        )

        with gr.Row():
            with gr.Column(scale=1):
                gr.HTML(
                    f'<div style="font-size:12px;letter-spacing:.1em;text-transform:uppercase;'
                    f'color:{C_CYAN};padding:24px 0 12px;font-family:Bebas Neue,sans-serif;">🔊 Speakers</div>',
                    sanitize_html=False,
                )
                with gr.Row():
                    play_btn = gr.Button("▶ Play", variant="primary", size="sm")
                    stop_btn = gr.Button("⏹ Stop", variant="stop", size="sm")
                speaker_status = gr.HTML(_status_html("idle"), sanitize_html=False)

    return {
        "play_btn":       play_btn,
        "stop_btn":       stop_btn,
        "speaker_status": speaker_status,
    }


def wire_debug_callbacks(comps: dict) -> None:

    def _play_audio():
        yield _status_html("playing")
        try:
            result = subprocess.run(
                ["speaker-test", "-t", "sine", "-f", "440", "-l", "1", "-c", "2"],
                capture_output=True, timeout=6,
            )
            if result.returncode == 0:
                yield _status_html("ok")
                return
        except (FileNotFoundError, Exception):
            pass
        try:
            from ui import voice as _voice
            from ui import music as _music
            _voice.speak("Speaker test. Audio is working.")
            _music.stop()
            yield _status_html("ok")
        except Exception as exc:
            yield _status_html(f"error: {exc}")

    def _stop_audio():
        try:
            import pygame
            pygame.mixer.stop()
        except Exception:
            pass
        return _status_html("stopped")

    comps["play_btn"].click(
        fn=_play_audio,
        outputs=[comps["speaker_status"]],
        show_progress="hidden",
    )
    comps["stop_btn"].click(
        fn=_stop_audio,
        outputs=[comps["speaker_status"]],
        show_progress="hidden",
    )
