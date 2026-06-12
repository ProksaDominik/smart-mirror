#!/bin/bash
# Starts the SmartMirror Gradio app and opens Chromium on the Mirror tab.
# No desktop environment needed — uses cage (Wayland kiosk compositor).
#
# First-time setup (one command):
#   sudo apt install -y cage
#
# Then just run:
#   ./start_kiosk.sh

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
MAIN_PORT=8500   # main dashboard (management)
KIOSK_PORT=8501  # mirror-only display for the LCD
URL="http://localhost:${KIOSK_PORT}"

# ── 1. Start the Gradio app in the background if not already running ──────────
if ! curl -s --max-time 1 "http://localhost:${MAIN_PORT}" > /dev/null 2>&1; then
    echo "[kiosk] Starting Gradio app..."
    cd "$REPO_DIR"
    python app.py &> /tmp/smartmirror.log &
    echo "[kiosk] Gradio PID: $!"
fi

# ── 2. Wait for the kiosk server to be ready ─────────────────────────────────
echo "[kiosk] Waiting for kiosk display on port ${KIOSK_PORT}..."
for i in $(seq 1 60); do
    curl -s --max-time 2 "http://localhost:${KIOSK_PORT}" > /dev/null 2>&1 && break
    sleep 1
done
echo "[kiosk] Server ready — launching Chromium."

# ── 3. Launch via cage (Wayland kiosk compositor — no desktop needed) ─────────
export LIBSEAT_BACKEND=seatd
export WLR_RENDERER=gles2

exec cage -- "$REPO_DIR/launch_mirror.sh"
