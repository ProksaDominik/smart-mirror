# 4. Production

We autostart the Gradio app for demos and production. First confirm everything works on the **real Pi IP** — especially after home Wi‑Fi — then enable systemd.

**Lab Ethernet** often uses `192.168.168.167`. **That address is not valid on home Wi‑Fi.** Do not hardcode it in scripts, bookmarks, or the systemd unit.

Complete [3_Next_steps.md](3_Next_steps.md) (Wi‑Fi, training, extending the app) before locking in production autostart.

---

## Network

This Pi connects to the Wi‑Fi network **`Howest-SmartTech-Hub`**. If it ever needs to be reconnected (factory reset, new Pi, moved location), join that network — the IP addresses below are only valid while on it:

- Ethernet (lab): `192.168.168.167`
- Wi‑Fi: `10.32.2.37` (changes if the network's DHCP lease changes)

Check the current IPs anytime with:

```bash
hostname -I
```

---

## Autostart — what's actually configured on this Pi

The generic systemd instructions in Step 2 below are kept for reference, but **this Pi does not use them**. Instead, autostart is wired through the desktop session, because the kiosk display needs an actual graphical (Wayland/labwc) session to show Chromium fullscreen on the HDMI screen — a bare systemd service can start the Python process but can't put a browser window on the physical display.

What's in place:

1. **`lightdm`** is configured for autologin as user `student` straight into the `rpd-labwc` desktop session (`/etc/lightdm/lightdm.conf`: `autologin-user=student`, `autologin-session=rpd-labwc`). This happens automatically on every boot — no login screen, no password.
2. **`~/.config/labwc/autostart`** runs automatically once that desktop session starts. It first replicates the normal desktop autostart (panel, wallpaper, etc. — copied from `/etc/xdg/labwc/autostart` so nothing is lost), then launches `RPi/start_on_boot.sh` in the background.
3. **`RPi/start_on_boot.sh`** waits for the network, starts `python -u app.py` (with `stdin` redirected to `/dev/null` — without that, anything touching stdin while backgrounded freezes the whole process with SIGTTIN), waits for port `8501` to respond, then launches Chromium in `--kiosk` fullscreen mode pointed at `http://localhost:8501`. If Chromium ever exits, it relaunches automatically.
4. **Face recognition runs in its own always-on background thread inside `app.py`** (`ui/sm_display.py`, `_recognition_loop`) — it does **not** depend on any browser tab being open. The Pi camera capture thread, YOLO recognition, voice greeting, and calendar sync are all already running the moment `app.py` starts. The kiosk window is just a *display* for that state — opening or closing it doesn't start or stop recognition.
5. **Auto-reset after 5 minutes**: once someone is recognised, the mirror holds their greeting/tasks for 5 minutes (`_AUTO_RESET_SEC` in `ui/sm_display.py`), then automatically resets so the next person who steps in front of the camera gets recognised fresh, with their own correctly-synced to-do list — no manual page refresh needed.

End result: power on the Pi, wait about a minute, and the mirror is live on the HDMI screen with no keyboard, mouse, laptop, or SSH session ever needed. Standing in front of the camera is the only "start button."

To check it's running without touching anything:

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8501   # 200 = kiosk server up
tail -f /tmp/smartmirror.log                                      # live app log
```

To make manual changes during development, you still kill/relaunch like normal — the autostart only fires on boot/login, it won't fight you while you're actively working:

```bash
kill $(ps aux | grep "python -u app.py" | grep -v grep | awk '{print $2}')
pkill -f chromium
# edit code, then just reboot, or manually re-run RPi/start_on_boot.sh
```

---

## Step 1 — Find the Pi IP and test services

Connect the Pi to Wi‑Fi if needed ([3_Next_steps.md](3_Next_steps.md) or [2_Kickoff.md](2_Kickoff.md)).

```bash
hostname -I
ip -4 addr show wlan0
```

Pick the LAN address your laptop can reach. From the laptop (same network), open:

| Service        | URL                             |
| -------------- | ------------------------------- |
| Gradio         | `http://<pi-ip>:7860`           |
| FastAPI health | `http://<pi-ip>:8000/health`    |
| FastAPI DB     | `http://<pi-ip>:8000/db-health` |
| pgAdmin        | `http://<pi-ip>:5050`           |

Run the app manually before enabling autostart:

```bash
cd ~/2025-2026-ProjectOne-CTAI-<yourname>/RPi
source ~/.venv/bin/activate
python app.py
```

Stop any old site service while debugging:

```bash
sudo systemctl stop p1.service    # if present
sudo systemctl stop myproject.service
```

---

## Step 2 — systemd unit for `app.py`

Create `myproject.service` on the Pi:

```ini
[Unit]
Description=ProjectOne Gradio app
After=network.target
Wants=network.target

[Service]
ExecStart=/home/student/.venv/bin/python -u /home/student/<name_of_your_repo>/RPi/app.py
WorkingDirectory=/home/student/<name_of_your_repo>/RPi
StandardOutput=journal
StandardError=journal
Restart=always
User=student

[Install]
WantedBy=multi-user.target
```

Replace `<name_of_your_repo>` with `2025-2026-ProjectOne-CTAI-<yourname>`.

Install and test:

```bash
sudo cp myproject.service /etc/systemd/system/myproject.service
sudo systemctl daemon-reload
sudo systemctl start myproject.service
sudo systemctl status myproject.service
```

Open Gradio at `http://<pi-ip>:7860` again (Wi‑Fi IP, not `192.168.168.167` unless you are on lab Ethernet).

Enable on boot:

```bash
sudo systemctl enable myproject.service
```

Logs:

```bash
sudo journalctl -u myproject.service -f
```

Stop / disable:

```bash
sudo systemctl stop myproject.service
sudo systemctl disable myproject.service
```

---

## Step 3 — Docker stack at boot (optional)

The database stack is separate from Gradio. To start Postgres, pgAdmin, and the API on boot:

```bash
cd ~/2025-2026-ProjectOne-CTAI-<yourname>/RPi/api
docker compose up -d
```

For a systemd unit, set `WorkingDirectory` to `RPi/api`, `ExecStart=/usr/bin/docker compose up -d`, and add `After=docker.service` / `Requires=docker.service`. Ensure `.env` exists before enable.

Test pgAdmin and `/db-health` on `http://<pi-ip>:...` after reboot.

---

## Step 4 — Shutdown button (optional)

The UI may call `sudo poweroff`. Allow passwordless shutdown once:

```bash
sudo visudo
```

Add:

```text
student ALL=(ALL) NOPASSWD: /sbin/poweroff, /usr/sbin/poweroff
```

---

## Checklist before presenting

- [ ] `hostname -I` on the presentation network (Wi‑Fi or lab)
- [ ] Gradio loads on `http://<pi-ip>:7860`
- [ ] `docker compose ps` OK if the DB demo is required
- [ ] `http://<pi-ip>:8000/db-health` connected
- [ ] `systemctl status myproject.service` active after reboot test

---

See also: [Appendix.md](Appendix.md) (port forwarding, `p1.service`, upgrades).
