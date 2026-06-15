#!/bin/bash
# Runs inside the cage Wayland session.
# Rotates the display 90° then opens Chromium on the mirror page.

PORT=8501

# Detect the first connected output and rotate it to portrait
OUTPUT=$(wlr-randr 2>/dev/null | awk 'NR==1{print $1}')
if [ -n "$OUTPUT" ]; then
    echo "[mirror] Rotating $OUTPUT 90°"
    wlr-randr --output "$OUTPUT" --transform 270
fi

# Reset Chromium exit state so it never shows the "restore pages?" dialog
PREFS="$HOME/.config/chromium/Default/Preferences"
if [ -f "$PREFS" ]; then
    sed -i 's/"exit_type":"Crashed"/"exit_type":"Normal"/g' "$PREFS"
    sed -i 's/"exit_type": "Crashed"/"exit_type": "Normal"/g' "$PREFS"
fi

exec chromium \
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
    "http://localhost:${PORT}"
