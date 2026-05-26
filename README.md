# Project Title

**FIRST & LAST NAME:** Dominik Proksa

**Sparring Partner:** Michal Heles

**Project Summary in max 10 words:** 
SmartMirror – Morning Assistant

SmartMirror is an AI-powered Raspberry Pi mirror that uses YOLO face recognition to identify users and instantly display their personalised time, weather, and Google Calendar to-do list on a 10.1-inch LCD — giving busy people all the info they need to start their day, hands-free, without touching their phone.

---

See [PD](PD.md)

---

For Docs, see [Docs/README.md](Docs/README.md)



1. Project identity version: 1.3

Working Title

SmartMirror - Morning assistent

Student Name

Dominik Proksa

Sparring Partner

Michal Heles

Project Type

Vision

2. Concept & Impact

Objective: Develop a working AI prototype for people who don't want to reach for their phone on busy mornings, so they have all the information to start their day on the mirror, and for people that want to schedule tasks and make a to-do list for every day.

Target Group: Busy people, students, and families with hectic morning routines who need quick access to personalized daily info without grabbing their phone.

Core Problem: On rushed mornings, people fumble for phones to check time, weather, calendar, and tasks, breaking their morning flow and wasting precious minutes.
Key Question: how can a gadget(mirror) help people have quicker mornings?
Impact: Makes mornings faster with quick, hands-free info (saves 10-15 min daily), cuts phone use.
3. AI & Data Pipeline

A. Method & Data

Dataset: It won't take 100+ pictures; just the scan of the face - YOLO26 model will be scanning if there is a face and whos face it is

Classes: 6 unique faces(me and my colleagues or friends)
Volume: photos of each persons face
B. Training & Export

Yolo 26 - take 100 photos of each person

4. Hardware & Makerlab plan

A. Mandatory Hardware

-10.1-inch HDMI touch LCD for to-do list, time, weather, and status icons

- lights up green for recognition success, red for failure, speaker for voice recordings (good morning, good evening…)

- button

B. Build Quality (Makerlab)

-Laser-cut wooden frame with acrylic one-way mirror

-all USB/HDMI/power routed through back panel glands

-low-voltage only

-matte black wood, flush glass, hidden cables, LED accents for modern smart-home vibe

5. Software & Visualisation

About & Onboarding:
]
Operating: camera readings and a button
-
Debugging:
-GPIO toggle for LED for camera test

B. Backend & Data

Users - name and ID of each person.
Face data - pretrained face label or model file for each user.
To-do list - tasks for each user. - Google Calendar API to sync calendar with to do list.
Forecasts - Google Forecast API to provide live weather updates based on the user's location
Recognition logs - who was detected and when.
Settings -refresh time, and display settings.
Gradio pages:

About - explains what the mirror does and how it works.

Data - shows the detected user, weather, and task data.

Operating - lets the user manage the to-do list manually.

Debugging - tests the camera, model, database, and display.

We do not need any keyboard because it will all be controlled by phone . All syncs with our google cloud.

User → Updates Google Calendar on their Phone.

Phone → Syncs to Google Cloud.

Mirror (Raspberry Pi) → Detects Face.

Mirror → Requests data from Google API for that specific ID.

Mirror → Displays the info on the LCD.

6. System Architecture (Block Diagram)

Paste your block diagram here following these color codes

Red: (Raspberry Pi) or Laptop
Green: Sensors
Yellow: Actuators
Grey: Display
Blue: Power supply
Note: Clearly label where the AI is running and what it is doing



No ai was used