#!/bin/bash
# Auto-launches the SmartMirror app + fullscreen kiosk display every time the
# Pi boots. lightdm is already configured for autologin straight into the
# labwc desktop session (see /etc/lightdm/lightdm.conf), and labwc runs
# ~/.config/labwc/autostart on startup — that file calls this script.
#
# Nothing needs to be typed by hand: no SSH, no laptop, no "start" button.
# Recognition itself runs in a background thread inside app.py from the
# moment it starts, so just having this kiosk window open is enough —
# the mirror reacts the instant a face appears in front of the camera.

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
KIOSK_PORT=8501
VENV_ACTIVATE="/home/student/.venv/bin/activate"
LOG="/tmp/smartmirror.log"

# Wait for network — weather/calendar sync need it; recognition itself does not.
for i in $(seq 1 30); do
    ip route get 1.1.1.1 > /dev/null 2>&1 && break
    sleep 1
done

# Wait for Postgres (Docker, restart: unless-stopped) to actually accept
# connections. On a fresh boot Docker can take 30-60s to bring containers up,
# and app.py crashes immediately if it can't reach the DB during init_db().
for i in $(seq 1 60); do
    nc -z 127.0.0.1 5432 > /dev/null 2>&1 && break
    sleep 1
done

# Start the Gradio app in the background, retrying if it crashes (e.g. DB
# still wasn't fully ready) so the kiosk never just sits dead after boot.
# stdin MUST be redirected to /dev/null — without it, anything that touches
# stdin while the process is backgrounded gets SIGTTIN'd and the app freezes
# silently (looks like a hang, not a crash).
(
    cd "$REPO_DIR"
    source "$VENV_ACTIVATE"
    while true; do
        if curl -s --max-time 1 "http://localhost:${KIOSK_PORT}" > /dev/null 2>&1; then
            break
        fi
        python -u app.py < /dev/null > "$LOG" 2>&1
        echo "[boot] app.py exited — retrying in 3s..." >> "$LOG"
        sleep 3
    done
) &

# Wait for the kiosk server to come up before opening the browser.
for i in $(seq 1 90); do
    curl -s --max-time 2 "http://localhost:${KIOSK_PORT}" > /dev/null 2>&1 && break
    sleep 1
done

# Launch fullscreen Chromium directly inside the already-running labwc
# session — no separate compositor (cage) needed. If Chromium ever exits
# (crash, update, etc.) relaunch it automatically so the mirror never just
# goes blank and stays that way.
while true; do
    chromium \
        --ozone-platform=wayland \
        --password-store=basic \
        --kiosk \
        --noerrdialogs \
        --disable-infobars \
        --no-first-run \
        --disable-translate \
        --disable-features=TranslateUI \
        --disable-session-crashed-bubble \
        --disable-restore-background-contents \
        --check-for-update-interval=604800 \
        --disable-pinch \
        "http://localhost:${KIOSK_PORT}"
    echo "[boot] Chromium exited — relaunching in 3s..."
    sleep 3
done
