# Setting up the insect camera: a step-by-step guide

This guide takes you from a bare camera board to a working insect camera with pictures on your screen. It assumes you are comfortable using a computer — installing programs, finding files, plugging things in — but **not** that you have ever programmed a microcontroller or used a command line before. Where a command line is unavoidable, every command is given in full for you to copy.

Read [operations.md](operations.md) once you are set up; it is the shorter day-to-day reference. This guide is the one-time setup.

> **Estimated time:** about 45 minutes the first time, most of it waiting for software to install. Setting up a *second* camera afterwards takes about 5 minutes.

---

## Before you start: what you need

**Hardware**

| Item | Notes |
| --- | --- |
| Seeed Studio XIAO ESP32S3 **Sense** | The "Sense" version is essential — it is the one with the camera connector and microSD slot |
| OV3660 camera module | Usually supplied with the board |
| microSD card, 32 GB or smaller | Must be 32 GB or under. Larger cards use a format the camera cannot read |
| USB-C cable | Must be a **data** cable, not charge-only. See troubleshooting if the board is not detected |
| USB battery pack | Any standard phone power bank |
| The enclosure | Not covered here; this guide is about the software |

**Computer**

- Windows 10/11 or macOS. This guide shows Windows paths; on macOS the commands are the same but paths use `/` instead of `\`.
- About 1 GB of free disk space.
- An internet connection **for setup only**. Once set up, the camera and dashboard work entirely offline.

**Optional**

- An Android phone, if you want to use the camera's own control app (see Part 6). *iPhones are not yet supported — see the note in that section.*

---

## Part 1 — Install the software (one time only)

You need two things: **Python** and **PlatformIO**. Python runs the small helper tools; PlatformIO puts the firmware onto the camera board.

### 1.1 Install Python

1. Go to [python.org/downloads](https://www.python.org/downloads/) and download the latest Windows installer.
2. Run it. **Tick "Add python.exe to PATH"** on the first screen — this matters, and it is easy to miss.
3. Click *Install Now* and wait.

To check it worked, open a terminal (press <kbd>Win</kbd>+<kbd>R</kbd>, type `powershell`, press Enter) and type:

```powershell
py --version
```

You should see something like `Python 3.13.1`. If you get an error, Python is not on your PATH — reinstall and make sure that box is ticked.

### 1.2 Install PlatformIO

PlatformIO is the tool that compiles the firmware and sends it to the board. The easiest route is through Visual Studio Code:

1. Install [Visual Studio Code](https://code.visualstudio.com/).
2. Open it, click the **Extensions** icon in the left sidebar (four small squares).
3. Search for `PlatformIO IDE` and click **Install**.
4. Wait. It downloads several hundred megabytes of compiler tools and can take 5–10 minutes. It will tell you when it is finished and ask to reload.

To check it worked, in a terminal:

```powershell
py -m platformio --version
```

You should see `PlatformIO Core, version 6.x.x`.

> **Why `py -m platformio` and not just `pio`?** Both usually work. On some managed or school-issued computers, security policy blocks the short `pio` command while allowing the longer form. The longer form is used throughout this guide because it works in both cases.

### 1.3 USB drivers

On Windows 10/11 and macOS, the XIAO board normally works with no driver installation at all. If the board is not detected later, see [Troubleshooting](#troubleshooting).

---

## Part 2 — Get the project code

The camera software lives inside the wider Kit-for-Kids project, in the folder `software/TomA-insect-ESP32-software`. You download the whole project, then work inside that one folder.

**Option A — download a ZIP (simplest)**

1. Go to [github.com/InsectAI-COST-Action/kit-for-kids](https://github.com/InsectAI-COST-Action/kit-for-kids).
2. Click the green **Code** button, then **Download ZIP**.
3. Unzip it somewhere memorable, e.g. `Documents\kit-for-kids`.

**Option B — use Git (better if you want updates later)**

```powershell
git clone https://github.com/InsectAI-COST-Action/kit-for-kids
```

Either way, from now on **all commands are run from inside the camera-software folder**, not the top of the download. To get there in the terminal:

```powershell
cd "C:\Users\YourName\Documents\kit-for-kids\software\TomA-insect-ESP32-software"
```

You are in the right place if you can see files named `platformio.ini` and `config.example.json`:

```powershell
dir
```

> **Tip:** in File Explorer, navigate to that folder, then right-click while holding <kbd>Shift</kbd> and choose *"Open PowerShell window here"* to skip typing the path.

---

## Part 3 — Put the firmware on the camera board

"Firmware" is the program that runs on the camera itself. You only need to do this once per board, or when updating to a newer version.

### 3.1 Connect the board

1. Attach the camera module to the board if it is not already fitted.
2. Plug the board into your computer with the USB-C cable.

### 3.2 Find which port it is on

```powershell
py -m platformio device list
```

You are looking for a line mentioning a COM port, e.g. `COM4` (on macOS, something like `/dev/cu.usbmodem1101`). Note it down. If nothing appears, see [Troubleshooting](#troubleshooting).

### 3.3 Flash it

Replace `COM4` with your port:

```powershell
py -m platformio run -e xiao_esp32s3 -t upload --upload-port COM4
```

The first time, this downloads the compiler toolchain and can take several minutes. Later runs take under a minute. You want to see:

```
Hash of data verified.
Leaving...
Hard resetting via RTS pin...
========================= [SUCCESS] =========================
```

The board restarts automatically and is now an insect camera.

---

## Part 4 — Prepare the memory card

### 4.1 Format the card

The card must be **FAT32**. Cards of 32 GB or less are usually FAT32 already, but formatting fresh is safest.

1. Put the card in your computer's card reader.
2. In File Explorer, right-click the drive → **Format**.
3. Set *File system* to **FAT32**. Leave everything else alone.
4. Click **Start**.

> ⚠️ **Formatting erases everything on the card.** Check you have the right drive.

### 4.2 Install the dashboard files

The card carries its own picture-viewing software, so it works on any computer with no installation. Replace `D:\` with your card's drive letter:

```powershell
py tools\prepare_sd.py D:\
```

This copies the dashboard, creates the folders the camera needs, and installs a default settings file. It deliberately **does not** overwrite existing pictures or settings, so it is safe to re-run on a card that already has data.

### 4.3 Eject safely

Use *Safely Remove Hardware* (or drag to Trash on macOS) before pulling the card out. Then put the card into the camera board's slot.

---

## Part 5 — Run a capture session

1. **Check the camera is switched off** (nothing plugged in).
2. **Insert the memory card.** Never insert or remove the card while the camera has power.
3. **Connect the battery pack.** The camera starts on its own.
4. It waits 5 seconds for the camera sensor to settle, then begins taking pictures.
5. By default it takes **one picture per second at high quality, for up to one hour**, then stops on its own.

### Stopping safely

**This matters more than anything else in this guide.**

The safest way to stop is from the phone app (Part 6): tap **Finish my adventure**, wait for **"Safe to unplug now"**, then disconnect the battery.

If you are not using the phone app, either let the session run to its natural end, or disconnect the battery between pictures.

> ⚠️ **Why this matters.** The memory card can be damaged if power is cut while it is writing. We have seen this happen once during development: a card became unreadable and a whole session was lost. The firmware protects individual pictures carefully, but the card's own filing system is outside its control. The "Finish" button closes everything down properly first, which removes the risk. Always prefer it where you can.

---

## Part 6 — Use the phone control app (optional, Android)

The camera makes its own small Wi-Fi network so you can check on it, take a peek through its eyes, change settings, and — most usefully — stop it safely.

### Connecting

1. On your phone, open Wi-Fi settings and look for the network **`InsectCam`**.
2. Password: **`antcamera`**
3. Your phone will warn you there is no internet on this network. **This is correct** — you are connected directly to the camera, which has no internet by design. Choose to stay connected.
4. Your phone should offer a **"Sign in"** notification. Tap it and the camera's page opens.
5. If nothing appears, open a browser and go to **`192.168.4.1`**.

If your kit has a QR code sticker, scanning it with the phone's camera joins the network without typing the password.

### What you can do

| | |
| --- | --- |
| **See progress** | How many pictures taken, how long it has been running |
| **Take a peek** | Shows the most recent picture the camera took |
| **Is anything moving?** | A live bar chart, when movement-triggered mode is on |
| **Camera settings** | Under *"Grown-up helper"* — change how often pictures are taken, quality, and how long to run. Save, then tap **Restart now** to apply |
| **Finish my adventure** | Stops safely and tells you when it is safe to unplug |

> **📱 iPhone users:** the control app has only been tested on Android. iPhones handle these camera-created networks differently and it may not work correctly. This is untested, not known-broken — but please do not rely on it until someone has confirmed it. Everything else in this guide works the same on any computer.

---

## Part 7 — Look at the pictures

1. **Stop the camera safely** (Part 5) and disconnect the battery.
2. Remove the memory card and put it in your computer.
3. Open the card in File Explorer and **double-click `dashboard.html`**.

That is all — no installation, no internet needed. It opens in your normal browser.

You will see how many pictures were taken, a gallery you can click through, and:

- **Make my insect movie** — turns the pictures into a fast time-lapse video you can save and share.
- **Motion watch** — a chart of when the camera detected movement (only appears if that mode was used).
- **Camera settings** — change settings for next time, from the computer instead of the phone.
- **Adult details** — a searchable table of every frame, tucked out of the way.

> **Browsers:** tested in Chrome and Edge. Firefox and Safari should work for viewing pictures but have not been formally checked yet. The movie maker and AI features specifically need Chrome or Edge.

### Starting a fresh experiment

Delete the `images`, `raw`, `data`, and `system` folders using File Explorer, then run `py tools\prepare_sd.py D:\` again. There is deliberately no delete button in the dashboard — deleting data should be a considered act, not one click.

---

## Part 8 — The AI helper (experimental, optional)

The dashboard can look through pictures for possible insects, entirely on your own computer. Nothing is uploaded.

> **⚠️ The AI models are not included in the code download.** They are large files kept out of the repository. Without them, the AI button will not work. Ask the project team for the model files if you want to try this — everything else in this guide works without them.

If you have the model files in place:

```powershell
py tools\install_ai_pack.py D:\
```

Then in the dashboard, choose **Find insects with AI**, pick a mode, select the card folder when asked, and press **Start looking**.

> **Please read this before showing results to children.** These are **possible-insect guesses**, not identifications. The models are experimental, trained on very little data, and get things wrong in both directions — missing real insects and flagging things that are not insects. They cannot tell you a species. Treat every result as a prompt to go and look more closely, which is a good scientific habit anyway.

---

## Troubleshooting

**The board does not appear in `device list`**
- Try a different USB-C cable. Many cables charge only and carry no data — this is the most common cause by far.
- Try a different USB port, ideally directly on the computer rather than through a hub.
- Put the board into its flashing mode manually: hold the **BOOT** button, tap **RESET**, release BOOT. Then try again.

**`pio` is not recognised**
- Use `py -m platformio` instead, as shown throughout this guide.

**Flashing fails with "port is busy"**
- Close anything else using the port — a serial monitor, Arduino IDE, another terminal.
- Unplug and replug the board.

**The camera does not take any pictures**
- Check the card is inserted, formatted FAT32, and 32 GB or smaller.
- Check `config.json` exists on the card. If missing, re-run `py tools\prepare_sd.py D:\`.
- Connect to the phone app: if something failed at startup, it will say so in plain language.

**The card will not open on the computer / files look wrong**
- This can happen if power was lost mid-write. Run the read-only check first, which changes nothing:
  ```powershell
  py tools\audit_card.py D:\
  ```
- Do not reformat until you have asked for help — recovery may be possible.

**`dashboard.html` opens but shows no pictures**
- Confirm there are files in the card's `images` folder.
- Confirm you opened the file from the *card* rather than a copy of the project folder.

**Movement-triggered mode saves every single picture**
- Known issue when the phone Wi-Fi is active at the same time: the radio interferes with movement detection. Either use movement mode without the phone app connected, or use normal every-picture mode. Being investigated.

---

## Quick reference

```powershell
# Flash firmware (replace COM4)
py -m platformio run -e xiao_esp32s3 -t upload --upload-port COM4

# Prepare a card (replace D:\)
py tools\prepare_sd.py D:\

# Check a card is healthy (read-only, safe)
py tools\audit_card.py D:\

# Install AI models, if you have them
py tools\install_ai_pack.py D:\

# Try the demo without a real camera
py tools\install_dashboard_demo.py D:\
```

| | |
| --- | --- |
| Wi-Fi network | `InsectCam` |
| Wi-Fi password | `antcamera` |
| Camera page | `192.168.4.1` |
| Default settings | 1 picture/second, high quality, 1 hour maximum |

---

## What is still being worked on

Being straight with you about the current state, so nothing surprises you:

- **The full one-hour session has not yet been formally verified end to end.** Shorter sessions are well tested. If you run a full hour, we would genuinely like to hear how it went.
- **iPhone support for the phone app is untested.**
- **Movement-triggered mode is experimental** and currently conflicts with the phone Wi-Fi (see troubleshooting).
- **The AI models are experimental** and not included in the download.

Everyday use — set up, capture, view pictures, make a movie — is well tested and reliable.
