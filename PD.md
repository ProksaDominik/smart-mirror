# Project Definition (PD) — P1 CTAI

Fill in every table below, just like you did with the real PD.

---

## 1. Project identity

| Field                | Your answer                                      |
| -------------------- | ------------------------------------------------ |
| **Working title**    | [Your catchy project title]                      |
| **Student name**     | [First name Last name]                           |
| **Sparring partner** | [Name of classmate]                              |
| **Project type**     | [ ] Vision [ ] Keypoint detection [ ] Non-visual |

---

## 2. Concept & impact

| Topic            | Your answer                                              |
| ---------------- | -------------------------------------------------------- |
| **Objective**    | [Develop a working AI prototype for an everyday problem] |
| **Target group** | [Who specifically benefits?]                             |
| **Core problem** | [The single main issue this project solves]              |
| **Key question** | [One focused question the AI must answer]                |
| **Impact**       | [Benefit for users, community, or yourself]              |

---

## 3. AI & data pipeline

### 3A. Method & data

> **Note:** Standard **image classification only** (single label per image, no boxes/keypoints) is **not allowed**.

| Requirement                    | Your answer                                                                                       |
| ------------------------------ | ------------------------------------------------------------------------------------------------- |
| **Dataset — how & where**      | [How and where you will collect data. Own photos/recordings; no copyrighted or pre-labeled sets.] |
| **Classes (min. 4, target 6)** | 1. … 2. … 3. … 4. … 5. … 6. …                                                                     |
| **Volume**                     | [ ] ≥ 100 annotations **per class** planned (yes/no + rough count per class)                      |

| Class name | Planned # samples / annotations |
| ---------- | ------------------------------- |
|            |                                 |
|            |                                 |
|            |                                 |
|            |                                 |
|            |                                 |
|            |                                 |

### 3B. Training & export

| Project type           | Your choice & model                                                          |
| ---------------------- | ---------------------------------------------------------------------------- |
| **Vision**             | Recent **YOLO** model trained in Python — model name/version:                |
| **Keypoint detection** | Pretrained **MediaPipe** (or similar) → custom classifier on top — describe: |
| **Non-visual**         | Model / approach:                                                            |

| Topic                    | Your answer                                                              |
| ------------------------ | ------------------------------------------------------------------------ |
| **Model information**    | [Architecture, input size, where weights live, export format e.g. `.pt`] |
| **Training environment** | [ ] Laptop [ ] RPi [ ] Cloud — details:                                  |
| **Export to RPi**        | [How the trained model reaches `RPi/ai/` or your app]                    |

---

## 4. Hardware & Makerlab plan

### 4A. Mandatory hardware

| Requirement                       | Your implementation                                                  |
| --------------------------------- | -------------------------------------------------------------------- |
| **Headless-first**                | [ ] Physical button start/stop [ ] Gradio only [ ] Both — describe:  |
| **Visual feedback (mandatory)**   | LCD / OLED type & what it shows:                                     |
| **Hardware feedback (mandatory)** | LEDs / buzzer / servo — what signals what:                           |
| **Extra sensor or actuator**      | [RFID / keypad / relay / env sensor / …] — how it changes behaviour: |

### 4B. Build quality (Makerlab)

| Criterion            | Your plan                                                      |
| -------------------- | -------------------------------------------------------------- |
| **Housing**          | [3D print / laser-cut / repurposed box — sketch or photo link] |
| **Cable management** | [How wires stay inside the enclosure]                          |
| **Safety**           | [No exposed electronics, no trip hazards]                      |
| **Aesthetics**       | [Clean, intentional look — materials, colour, labels]          |

---

## 5. Software & visualisation

### 5A. Gradio interface (mandatory pages)

| Page                   | Content you will show                        |
| ---------------------- | -------------------------------------------- |
| **About & onboarding** | [Project info + user instructions]           |
| **Data**               | [Live sensor readings + AI statistics]       |
| **Operating**          | [Main interaction: camera, buttons, text, …] |
| **Debugging**          | [Direct hardware I/O tests from the Pi]      |

| **Link to kickoff codebase** | [[https://github.com/howest-mct/2025-2026-ProjectOne-CTAI-YourName]](https://github.com/howest-mct/2025-2026-ProjectOne-CTAI-YourName]) |
| ---------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| **Extra pages (optional)**   |                                                                                                                                         |

### 5B. Backend & data

| Component    | Your answer                                                       |
| ------------ | ----------------------------------------------------------------- |
| **Database** | [Which DB, what is stored]                                        |
| **Docker**   | [ ] Yes — compose file location: [ ] No — justification:          |
| **API**      | [Gradio only / Gradio + FastAPI — what talks to DB, AI, hardware] |

---

## 6. System architecture (block diagram)

Paste your diagram below (image or Mermaid). Use these **colours**:

| Colour | Meaning                                  |
| ------ | ---------------------------------------- |
| Red    | Microcontroller (Raspberry Pi) or laptop |
| Green  | Sensors                                  |
| Yellow | Actuators                                |
| Grey   | Display                                  |
| Blue   | Power supply                             |

**Also label:** where AI runs (Pi vs laptop) and what each model does.
