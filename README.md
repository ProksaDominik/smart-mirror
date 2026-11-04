# Smart Mirror — a morning assistant that knows who you are

![The mirror greeting its user with the time, weather and to-do list](docs/mirror.jpg)

▶ **[Watch the 1-minute demo](docs/demo.mp4)**

A Raspberry Pi mirror that recognises the person standing in front of it and
shows *their* day: time, weather and their Google Calendar to-do list on a
10.1-inch screen, with a voice assistant you can talk to — no phone needed on a
busy morning.

Built in four weeks (May–June 2026) as my first-year Project One at Howest
(Creative Technologies & AI), starting from the course's Raspberry Pi template.

## Results

**Face recognition:** a YOLO26n model, fine-tuned from the pretrained
checkpoint on my own dataset — about 3,000 photos of 7 people, labelled in
Roboflow, 100 epochs on Google Colab. Scores of the model running on the mirror,
on the validation photos of its training run:

| Precision | Recall | mAP50 | mAP50-95 |
|---:|---:|---:|---:|
| 97.5% | 99.1% | 99.0% | 68.3% |

- **Precision:** of the faces it names, how many are the right person.
- **Recall:** of the faces in the photos, how many it finds.
- **mAP50:** the standard detection score — 100% means it finds and names everyone.

**Be careful with these numbers:** the validation photos come from the same
photo sessions as the training photos, so they are easier than real life. In
front of the mirror — other light, other angles, other clothes — accuracy will
be lower; that was not measured separately.

The model is small (2.4 M parameters) and takes about 35 ms per photo on a
laptop CPU.

## What it does

1. **Recognises you** — a camera on the mirror runs the face model; a green
   light for a known person, red for an unknown one.
2. **Shows your day** — time, the weather, and your own Google Calendar to-do
   list (read-only), on a 10.1-inch touch screen.
3. **Talks with you** — speech-to-text runs on the Pi itself (faster-whisper);
   replies are spoken with ElevenLabs, with Microsoft Edge voices as a fallback.
4. **Runs on its own** — starts in kiosk mode when the Pi boots, with a button,
   buzzer, LCD and 7-segment display for status.

## What I built, and what came from the template

The course gave every student the same Raspberry Pi starting point: the `Docs/`
folder, camera inputs, the model registry and the basic hardware layer. My work
on top of it:

| Part | Where |
|---|---|
| The mirror interface: display, operating screen, dashboard, kiosk mode, theme | [`RPi/ui/`](RPi/ui/) (`sm_*.py`, `smartmirror_*.py`) |
| The voice assistant | [`RPi/ui/voice.py`](RPi/ui/voice.py) |
| Users and their calendars | [`RPi/db.py`](RPi/db.py), [`RPi/ui/sm_database.py`](RPi/ui/sm_database.py) |
| Training and testing the face model | [`Laptop/yolo.ipynb`](Laptop/yolo.ipynb) |
| Buzzer, 7-segment display, LCD status | [`RPi/hardware/`](RPi/hardware/) |
| Project definition | [`PD.md`](PD.md) |

## Hardware

Raspberry Pi with a camera (CSI or USB), a 10.1-inch HDMI touch screen, LEDs, a
buzzer, a button, an LCD and a speaker.

## Privacy

The face photos, the trained model and the Google credentials are **not** in
this repository: the model recognises real people. To run it yourself, train
your own model and put it at `RPi/ai/best.pt`.

## Running it

On the Raspberry Pi:

```bash
cd RPi
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# Google Calendar: a credentials.json from Google Cloud (Calendar API, read-only) next to app.py
# your trained face model: RPi/ai/best.pt
./launch_mirror.sh          # or ./start_kiosk.sh for full-screen kiosk mode
```

Setup details from the course template: [`Docs/`](Docs/README.md).
