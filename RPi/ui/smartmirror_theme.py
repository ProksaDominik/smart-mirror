"""SmartMirror design system — colors, CSS, and small HTML helpers."""

# ── Palette (design.pdf) ──────────────────────────────────────────────────────
C_BG     = "#0A0A0F"
C_CARD   = "#12121E"
C_CYAN   = "#6C5CE7"
C_GREEN  = "#00FF88"
C_PURPLE = "#7B2FFF"
C_RED    = "#FF3366"
C_WHITE  = "#FFFFFF"
C_MUTED  = "#8B8BA8"
C_BORDER = "#1E1E2E"

APP_FONT = "'Bebas Neue', sans-serif"

APP_VERSION = "v1.3"

SM_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Space+Mono:wght@400;700&family=Playfair+Display:wght@400;500;700&family=Bebas+Neue&display=swap');

*, *::before, *::after { box-sizing: border-box; }

/* Kiosk display has no mouse interaction — hide the cursor everywhere */
*, *::before, *::after { cursor: none !important; }

body,
.gradio-container,
.gradio-container > .main,
.wrap {
    background: #0A0A0F !important;
    color: #ffffff !important;
    font-family: 'Bebas Neue', sans-serif !important;
    font-size: 18px !important;
}

.gradio-container {
    max-width: 100% !important;
    padding: 0 !important;
    margin: 0 !important;
}

footer { display: none !important; }

/* ── Tabs ─────────────────────────────────────────────────────────────────── */
.tabs { background: #0A0A0F !important; border: none !important; }

.tab-nav {
    background: #12121E !important;
    border-bottom: 1px solid #1E1E2E !important;
    padding: 0 28px !important;
}

.tab-nav button {
    color: #8B8BA8 !important;
    font-family: 'Bebas Neue', sans-serif !important;
    font-size: 19px !important;
    font-weight: 500 !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
    padding: 22px 32px !important;
    border: none !important;
    background: transparent !important;
    border-bottom: 3px solid transparent !important;
    transition: color 0.2s, border-color 0.2s !important;
}

.tab-nav button.selected,
.tab-nav button[aria-selected="true"] {
    color: #6C5CE7 !important;
    border-bottom-color: #6C5CE7 !important;
}

.tab-nav button:hover:not(.selected) { color: #ffffff !important; }

.tabitem {
    background: #0A0A0F !important;
    padding: 0 !important;
    border: none !important;
}

/* ── Remove default Gradio block chrome ───────────────────────────────────── */
.block {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}

/* ── SM header strip ─────────────────────────────────────────────────────── */
.sm-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 32px;
    border-bottom: 1px solid #1E1E2E;
    background: #12121E;
}

/* ── Input / Slider overrides ────────────────────────────────────────────── */
input[type=range] { accent-color: #6C5CE7 !important; }

input[type=text],
textarea {
    background: #12121E !important;
    border: 1px solid #1E1E2E !important;
    color: #ffffff !important;
    border-radius: 8px !important;
    font-family: 'Bebas Neue', sans-serif !important;
    font-size: 17px !important;
}

input[type=text]:focus,
textarea:focus {
    border-color: #7B2FFF !important;
    outline: none !important;
}

/* ── Gradio HTML wrapper reset ───────────────────────────────────────────── */
.html-container { padding: 0 !important; }

/* ── Kill Gradio streaming animations (prevent greeting from flashing) ───── */
/* Gradio adds .generating / .pending during every stream tick, which applies
   a pulsing border and opacity animation. Suppress all of it globally so
   gr.HTML components never visually react to background stream activity. */
.generating,
.generating *,
.pending,
.pending * {
    animation: none !important;
    transition: none !important;
    border-color: transparent !important;
}
.block.generating { border: none !important; box-shadow: none !important; }

/* ── Hide Gradio status/progress overlay (the "Waiting" / "Processing" pill) */
.wrap.svelte-1uj8rng { display: none !important; }

/* ── Scrollbar ───────────────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #0A0A0F; }
::-webkit-scrollbar-thumb { background: #1E1E2E; border-radius: 3px; }
"""


# ── Tiny HTML helpers ─────────────────────────────────────────────────────────

def dot(color: str) -> str:
    return (
        f'<span style="display:inline-block;width:8px;height:8px;'
        f'border-radius:50%;background:{color};margin-right:6px;'
        f'vertical-align:middle;"></span>'
    )


def tag(label: str, bg: str, color: str) -> str:
    return (
        f'<span style="background:{bg};color:{color};padding:5px 14px;'
        f'border-radius:20px;font-size:14px;font-weight:500;">{label}</span>'
    )


def divider() -> str:
    return f'<div style="height:1px;background:{C_BORDER};margin:16px 0;"></div>'
