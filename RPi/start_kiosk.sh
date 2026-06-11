#!/bin/bash
# Opens Chromium in kiosk mode on the SmartMirror Mirror tab.
# Run this after the Gradio app is already started, or together with it:
#   ./main.py &
#   ./start_kiosk.sh

PORT=8500
URL="http://localhost:${PORT}?kiosk"

echo "[kiosk] Waiting for Gradio on port ${PORT}..."
until curl -s --max-time 2 "http://localhost:${PORT}" > /dev/null 2>&1; do
    sleep 1
done
echo "[kiosk] Server ready — launching Chromium."

# Use the first available display (works on desktop Raspberry Pi OS)
export DISPLAY="${DISPLAY:-:0}"

# Disable screen blanking / power saving
xset s off 2>/dev/null
xset -dpms 2>/dev/null
xset s noblank 2>/dev/null

exec chromium-browser \
    --kiosk \
    --noerrdialogs \
    --disable-infobars \
    --no-first-run \
    --disable-translate \
    --disable-features=TranslateUI \
    --disable-session-crashed-bubble \
    --check-for-update-interval=604800 \
    --disable-pinch \
    "${URL}"
