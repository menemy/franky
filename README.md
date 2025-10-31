<div align="center">

<img src="franky.png" width="400" alt="Franky the Halloween Skull">

# 🎃 FRANKY 💀
### *The AI-Powered Halloween Talking Skull*

[![OpenAI](https://img.shields.io/badge/OpenAI-Realtime%20API-412991?logo=openai)](https://platform.openai.com)
[![ESP32](https://img.shields.io/badge/ESP32-S3-E7352C?logo=espressif)](https://www.espressif.com)
[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?logo=python)](https://www.python.org)
[![Halloween](https://img.shields.io/badge/Halloween-2025-FF6600?logo=ghost)](https://github.com)

---

https://github.com/user-attachments/assets/a5666c29-cffe-434e-b68e-94e56bf40a9a

*Watch Franky in action!* 🎬

---

*Where AI meets the afterlife* ☠️✨

</div>

---

## 👻 What is This Unholy Creation?

**Franky** is a talking Halloween skull that uses cutting-edge AI to scare, entertain, and engage with trick-or-treaters in real-time. Powered by OpenAI's GPT-4o Realtime API, this possessed decoration comes alive with:

- 🗣️ **Natural voice conversations** - Speaks with human-like fluency in multiple languages
- 🧠 **Computer vision** - Actually sees who's at your door through RTSP or webcam
- 🎭 **Dynamic voice acting** - Transforms voice on-the-fly for different spooky characters
- 💀 **Animated jaw** - Perfectly synced mouth movements
- 👁️ **Glowing LED eyes** - Programmable eye lighting effects
- 🎮 **Interactive games** - Mini-games for kids (and adults!)
- 🎵 **Real-time audio effects** - Professional-grade voice manipulation

<div align="center">

### 🌍 Speaks Your Language

**English by default**, but auto-detects and responds in many other languages

</div>

---

## ⚡ Quick Start (Laptop/PC)

Want to try Franky without any hardware? Just use your laptop's built-in microphone, speakers, and webcam!

### 🚀 5 Simple Steps

**1. Get OpenAI API Access:**

You need an OpenAI account with Realtime API access:

1. Go to [OpenAI Platform](https://platform.openai.com)
2. Sign up / Log in
3. Add payment method (go to [Billing](https://platform.openai.com/account/billing))
4. Add credits (minimum $5-10 recommended)
5. Create API key at [API Keys page](https://platform.openai.com/api-keys)

**Cost:** Realtime API is affordable - typically in the range of **$10-20 per hour** of conversation, depending on usage patterns. **Always check current pricing** at [OpenAI Pricing](https://openai.com/api/pricing/) as rates may change.

> 💡 **Tip:** Start with $10-20 credit to test everything. You can always add more!

**2. Setup Python virtual environment (recommended):**
```bash
# Create virtual environment
python3 -m venv .venv

# Activate it
source .venv/bin/activate  # macOS/Linux
# OR on Windows: .venv\Scripts\activate
```

> 💡 **Why venv?** Keeps Franky's dependencies isolated from your system Python. You'll need to run `source .venv/bin/activate` each time you open a new terminal.

**3. Install Python dependencies:**
```bash
pip install -r requirements.txt
```

**4. Create `.env` file with your OpenAI API key:**
```bash
cp .env.example .env
```

Edit `.env` and add your key:
```env
OPENAI_API_KEY=sk-proj-your_api_key_here

# Quick start: use laptop speakers/mic (no hardware needed)
OUTPUT_MODE=speakers
ENABLE_MQTT=false
ENABLE_CAMERA=true
USE_WEBCAM=true
WEBCAM_INDEX=0  # Try 0, 1, or 2 if default doesn't work
```

**5. Run Franky:**
```bash
python3 franky.py
```

That's it! Franky will use your laptop's built-in microphone, speakers, and camera. Just start talking! 🎃

> 💡 **Tip:** On macOS, if webcam isn't working, try changing `WEBCAM_INDEX` in `.env` (0=iPhone Continuity, 1=built-in camera)

### 📹 Advanced: Using RTSP IP Camera + BT Speaker

For outdoor/door placement, use an IP camera at the door and a Bluetooth speaker with microphone nearby. Your laptop stays inside running the bot.

**1. Find your camera's RTSP URL:**

Common formats:
```
rtsp://admin:password@192.168.1.102/stream1
rtsp://admin:password@192.168.1.102/Preview_01_main
rtsp://username:password@camera_ip:554/stream
```

**Popular camera brands:**
- **Hikvision:** `rtsp://admin:password@IP/Streaming/Channels/101`
- **Dahua:** `rtsp://admin:password@IP/cam/realmonitor?channel=1&subtype=0`
- **TP-Link:** `rtsp://admin:password@IP/stream1`
- **Generic ONVIF:** `rtsp://admin:password@IP:554/stream1`

**2. Test RTSP stream with VLC:**
```bash
# macOS/Linux
vlc rtsp://admin:password@192.168.1.102/Preview_01_main

# Or use VLC GUI: Media -> Open Network Stream
```

**3. Connect Bluetooth speaker with microphone:**

Pair your Bluetooth speaker/microphone to your laptop, then check it's set as default audio device in system settings.

**4. Configure `.env` file:**
```env
# Use RTSP camera instead of webcam
USE_WEBCAM=false
CAMERA_RTSP_STREAM=rtsp://admin:password@192.168.1.102/Preview_01_main

# Use laptop speakers (which will output to BT device)
OUTPUT_MODE=speakers
ENABLE_MQTT=false
ENABLE_CAMERA=true
```

**5. Run Franky:**
```bash
python3 franky.py
```

Now the camera watches the door, BT speaker plays at the door, and your laptop runs everything from inside!

**Troubleshooting:**
- Check camera IP is reachable: `ping 192.168.1.102`
- Verify credentials (default often `admin:admin`)
- Try different stream paths (`stream1`, `stream2`, `h264`, etc.)
- Check camera settings for RTSP port (usually 554)
- Ensure camera is on same network as your PC

**Finding RTSP URL:**
1. Check camera manual/documentation
2. Use ONVIF Device Manager (Windows)
3. Use manufacturer's mobile app settings
4. Search online: "CAMERA_MODEL rtsp url format"

### 🤖 Expert: Full Hardware Setup (Arduino/ESP32)

Want the complete experience? Build a physical animatronic skull with moving jaw and glowing eyes!

**Required Hardware:**
- ESP32 or Arduino board (XIAO ESP32-S3 recommended)
- Servo motor for jaw (SG90 or MG90S) or simple DC motor
- LED eyes (5mm red LEDs)
- Halloween skull decoration/toy
- Power supply (5V 2A)
- Wires and breadboard

**Architecture:**
```
┌──────────────┐   MQTT    ┌──────────────┐   Servo    ┌──────────┐
│   Python     │──────────▶│   ESP32      │───────────▶│   Jaw    │
│   Franky     │           │   Arduino    │            │  Motor   │
│     Bot      │◀──────────│   Firmware   │            └──────────┘
└──────────────┘   WiFi    └──────────────┘
                                   │
                                   │ GPIO
                                   ▼
                            ┌──────────────┐
                            │   LED Eyes   │
                            └──────────────┘
```

**Step 1: Set up MQTT Broker**

**Option A: Docker (Recommended):**
```bash
# Run from project directory
docker compose -f mqtt/docker-compose.yml up -d

# Test broker
mosquitto_sub -h localhost -t "franky/#"
```

**Option B: Install locally:**
```bash
# macOS
brew install mosquitto
brew services start mosquitto

# Linux
sudo apt install mosquitto mosquitto-clients
sudo systemctl start mosquitto

# Test broker
mosquitto_sub -h localhost -t "franky/#"
```

**Step 2: Wire the Hardware**

Basic wiring for ESP32:
```
Servo (Jaw):
  - Signal → GPIO 9
  - VCC → 5V
  - GND → GND

LED Eyes:
  - Anode (+) → GPIO 10 → 330Ω resistor
  - Cathode (-) → GND
```

**Step 3: Flash ESP32 Firmware**

Use the included simple MQTT firmware:

```bash
cd devices/xiao_esp32_mqtt
# Edit xiao_esp32_mqtt.ino with your WiFi credentials
# Upload using Arduino IDE or arduino-cli
```

The firmware:
- Connects to WiFi and MQTT broker
- Subscribes to `franky/jaw` (0-180 degrees) and `franky/eyes` (0/1) topics
- Controls servo motor and LED GPIO pins

See `devices/xiao_esp32_mqtt/README.md` for detailed instructions.

**Step 4: Configure `.env` for full setup**

```env
OPENAI_API_KEY=sk-proj-your_key_here

# Use laptop/PC for audio (not ESP32)
OUTPUT_MODE=speakers

# MQTT for jaw/eyes control
ENABLE_MQTT=true
MQTT_SERVER=192.168.1.100
MQTT_PORT=1883

# Camera (RTSP or webcam)
CAMERA_RTSP_STREAM=rtsp://admin:password@192.168.1.102/Preview_01_main
# OR
USE_WEBCAM=true
WEBCAM_INDEX=0
```

**Step 5: Run Franky**

```bash
python3 franky.py
```

Laptop handles audio, ESP32 handles jaw/eyes via MQTT.

**Step 6: Test Hardware**

```bash
# Test jaw movement (0-180 degrees)
mosquitto_pub -h 192.168.1.100 -t "franky/jaw" -m "90"
mosquitto_pub -h 192.168.1.100 -t "franky/jaw" -m "0"

# Test eyes (0=off, 1=on)
mosquitto_pub -h 192.168.1.100 -t "franky/eyes" -m "1"
mosquitto_pub -h 192.168.1.100 -t "franky/eyes" -m "0"
```

**Advanced Ideas:**

- **Smooth jaw movement:** Use PWM and gradual angle changes
- **Multiple servos:** Control eyebrows, head tilt, etc.
- **Power supply:** Use external 5V PSU for servos (not USB)
- **DC motor:** Replace servo with DC motor + driver for continuous rotation
- **Relay control:** Add relay for fog machine, lights, or other effects
- **Smart devices:** Connect WiFi smart plugs/lights (Meross, Tuya) - AI can control fog machines, colored lights, and UV effects to enhance atmosphere during scary moments! See `.env.example` for Meross and Smart Flood Light setup

This setup uses your laptop/PC for audio (speaker mode) and ESP32 only for jaw/eyes control.

### 🎙️ Ultimate: ReSpeaker for Outdoor Use

The most advanced setup uses a **ReSpeaker microphone array** for reliable voice pickup outdoors with echo cancellation!

**Why ReSpeaker for outdoor/door setup?**
- **Far-field pickup** - Hears trick-or-treaters clearly from 3+ meters away
- **Echo cancellation** - Eliminates speaker feedback (crucial when speaker and mic are close)
- **Beamforming** - Focuses on voices, ignores wind and background noise
- **Automatic gain** - Normalizes quiet and loud voices
- **Works in noisy environments** - Street noise, wind, multiple people talking

> ⚠️ **IMPORTANT:** For echo cancellation to work, the **speaker must be connected to ESP32** (not your PC)! The ReSpeaker needs to know what audio is being played to cancel it from the microphone input.

**Supported Hardware:**

1. **XIAO ESP32-S3 + ReSpeaker Lite** (Recommended)
   - Compact 2-mic array
   - I2S digital audio
   - Easy integration with ESP32

2. **XIAO ESP32-S3 + ReSpeaker 4-Mic Array**
   - Professional 4-mic circular array
   - Hardware echo cancellation
   - 360° pickup pattern

**Architecture with ReSpeaker:**

```
┌────────────────┐        ┌─────────┐  UDP    ┌──────────┐
│   ReSpeaker    │───────▶│  ESP32  │────────▶│  Python  │
│   4-Mic Array  │  I2S   │   S3    │  16kHz  │  Franky  │
│   (with AEC)   │◀───┐   │         │         │   Bot    │
└────────────────┘    │   └─────────┘         └──────────┘
                      │         │
                Reference      │ UDP
                 Signal        ▼
                      │   ┌──────────┐
                      └───│ Speaker  │◀── Must be connected
                          │  Output  │    to ESP32!
                          └──────────┘
```
**Key:** The ReSpeaker module needs to "hear" what the speaker is playing to cancel echo. Connect speaker to ESP32, not your PC!

**Benefits over single mic:**
- 🎯 **Direction-aware** - knows where voice is coming from
- 🔇 **No echo** - removes speaker feedback completely
- 📢 **Far-field** - picks up voice from across the room
- 🎵 **Clean audio** - better speech recognition

**Setup (ESP32 + ReSpeaker):**

1. **Hardware connection:**
```
ReSpeaker → ESP32 XIAO S3:
  - Connect via I2S (GPIO 4, 5, 6, 7)
  - Power: 5V, GND

Speaker → ESP32 XIAO S3:
  - Connect to ESP32's I2S output
  - ⚠️ CRITICAL: Speaker MUST be connected to ESP32, not your PC!
```

> **Why speaker must connect to ESP32:** The ReSpeaker module needs to know what audio is being played to cancel echo. If speaker is connected to your PC, echo cancellation won't work!

2. **Flash firmware:**
```bash
cd xiao_esp32_respeaker
arduino-cli compile --fqbn esp32:esp32:XIAO_ESP32S3
arduino-cli upload -p /dev/cu.usbmodem1101 --fqbn esp32:esp32:XIAO_ESP32S3
```

3. **Configure `.env`:**
```env
OPENAI_API_KEY=sk-proj-your_key_here

# ESP32 with ReSpeaker (UDP audio streaming)
ESP32_IP=192.168.1.101  # Auto-detected on first run

# MQTT for jaw/eyes
MQTT_SERVER=192.168.1.100
MQTT_PORT=1883

# Camera
USE_WEBCAM=true
WEBCAM_INDEX=0
```

4. **Run Franky:**
```bash
python3 franky.py
```

Make sure `.env` has:
```env
OUTPUT_MODE=esp32_udp
ENABLE_MQTT=true
```

**Setup Comparison:**

| Setup | Best For | Echo Cancel | Noise/Wind | Far-field | Outdoor |
|-------|----------|-------------|------------|-----------|---------|
| Laptop mic | Indoor testing | ❌ | ❌ | ❌ | ❌ |
| Bluetooth speaker | Indoor door | Basic | Basic | ❌ | ⚠️ |
| ReSpeaker 2-mic | Outdoor door | ✅ | ✅ | ✅ | ✅ |
| ReSpeaker 4-mic | Outdoor, noisy area | ✅✅ | ✅✅ | ✅✅ | ✅✅ |

**Where to buy:**
- [Seeed Studio ReSpeaker Lite](https://www.seeedstudio.com/ReSpeaker-Lite-p-5928.html)
- [ReSpeaker 4-Mic Array](https://www.seeedstudio.com/ReSpeaker-Mic-Array-v2-0.html)
- [XIAO ESP32-S3](https://www.seeedstudio.com/XIAO-ESP32S3-p-5627.html)

This is the **recommended setup for outdoor Halloween decorations** - place everything at your door and let Franky handle trick-or-treaters! 🎃✨

For detailed firmware build instructions, see [`CLAUDE.md`](CLAUDE.md).

### 💡 Smart Lighting & Atmosphere Control

Franky can control smart devices to create immersive atmosphere! The AI automatically decides when to use lighting effects during conversations.

**Supported Devices:**

**1. Meross Smart Plugs/Lights** (WiFi, cloud-based)
- UV lights for glowing effects
- Fog machines (on/off control)
- Any device plugged into Meross socket

**2. Tuya/Smart Life Devices** (WiFi, local control)
- RGB flood lights with color sequences
- Smart bulbs with millions of colors
- Compatible with most WiFi smart devices

**Setup Example:**

```env
# In your .env file

# Meross UV light / fog machine
ENABLE_MEROSS_CONTROL=true
MEROSS_EMAIL=your@email.com
MEROSS_PASSWORD=your_password

# Smart RGB Flood Light (Tuya)
ENABLE_FLOOD_LIGHT_CONTROL=true
FLOOD_LIGHT_DEVICE_ID=your_device_id
FLOOD_LIGHT_LOCAL_KEY=your_local_key
FLOOD_LIGHT_IP=192.168.1.104
```

**How it works:**

The AI has access to lighting control tools and will use them contextually:
- 🔴 **Red light** during scary moments and demon voices
- 🔵 **Blue light** for ghost stories and cold atmosphere
- 🟣 **Purple light** for witch/magic themes
- 🟠 **Orange light** for classic Halloween ambiance
- ⚡ **Blinking** for jump scares and dramatic effects
- 🌈 **Color sequences** (red-white-red-white) for alarm/police effects

**Example AI behaviors:**
- Before a "BOO!" → Blinks UV light rapidly
- During scary story → Slow red pulse on flood light
- Mini-game countdown → Color sequence (3-2-1)
- Witch character → Purple light with mystical effects

**Getting credentials:**

- **Meross:** Just use your app email/password
- **Tuya/Smart Life:** Run `python3 -m tinytuya wizard` to extract device credentials

The AI automatically moderates lighting effects to avoid overuse - effects are short (5-10 seconds) and saved for key moments to maximize impact! 🎃

### 🎵 Background Music & Sound Effects

Franky can play spooky background music during conversations! Just put MP3 files in the `sounds/` folder and the AI can play them.

**How it works:**
1. Create a `sounds/` folder in the project directory
2. Add your MP3 files (spooky music, sound effects, etc.)
3. The AI automatically detects all MP3 files
4. During conversations, AI can play/stop music as needed
5. Music automatically ducks (lowers volume) when people talk

**Free Halloween Sound Packs:**
- [Pixabay Halloween Sounds](https://pixabay.com/sound-effects/search/halloween/) - Royalty-free, no attribution required
- [99Sounds Halloween Collection](https://99sounds.org/halloween-sound-effects/) - Free horror sound effects
- [Orange Free Sounds](https://orangefreesounds.com/halloween-scary-sounds/) - 26 scary sound clips
- [Mixkit Halloween SFX](https://mixkit.co/free-sound-effects/halloween/) - Free high-quality effects
- [Zapsplat Horror & Halloween](https://www.zapsplat.com/sound-effect-category/horror-and-halloween/) - Free royalty-free music

**Example usage:**
```bash
# Create sounds folder and add music
mkdir sounds
# Download or copy your MP3 files to sounds/
cp ~/Downloads/spooky_theme.mp3 sounds/
cp ~/Downloads/thunder.mp3 sounds/
```

The AI will see available files and play them contextually during interactions! 🎃

---

## 🦴 The Unholy Trinity: Features

### 🧙‍♂️ Personality & Interaction

- **Multilingual AI** - Detects guest language and responds naturally
- **Call-and-response phrases** - Interactive "Trick or..." → "TREAT!" moments
- **Mini-games** - "Treat or Spell?", "Repeat After the Ghost", and more
- **Vision-aware** - Adapts behavior based on what (or who) it sees
- **Safe scares** - Spooky but family-friendly interactions

### 🎛️ Technical Sorcery

- **OpenAI Realtime API** - gpt-5-realtime with native audio I/O
- **4-Mic Array** - ReSpeaker XVF3800 with XMOS DSP
  - Acoustic Echo Cancellation (AEC)
  - Automatic Gain Control (AGC)
  - Beamforming for clear audio

### ⚡ Hardware Haunting

- **XIAO ESP32-S3** - Microcontroller with WiFi
- **UDP Audio Streaming** - 16kHz low-latency audio
- **MQTT Control** - Jaw servos and LED eye control
- **RTSP Camera** - Real-time video stream for vision

---

## 🔮 Audio Pipeline Architecture

```
┌─────────────┐      ┌─────────┐      ┌────────┐      ┌──────────┐      ┌─────────────┐
│  4-Mic      │ I2S  │  XMOS   │ I2S  │ ESP32  │ UDP  │  Python  │ WS   │   OpenAI    │
│  Array      │─────▶│  XVF    │─────▶│  S3    │─────▶│   Bot    │─────▶│  Realtime   │
│  (Audio)    │      │  (AEC)  │      │        │ 5001 │          │      │  API (GPT)  │
└─────────────┘      └─────────┘      └────────┘      └──────────┘      └─────────────┘
                                            ▲                │
                                            │                │
                                       UDP 5002              ▼
                                            │           ┌───────┐
                                        ┌───────┐      │Speaker│
                                        │Speaker│◀─────│ I2S   │
                                        │       │  I2S │ Output│
                                        └───────┘      └───────┘
```

---

## 🎮 Testing the Dark Powers

### 💀 Test Jaw Movement

```bash
mosquitto_pub -h 192.168.1.100 -t "franky/jaw" -m "100"
```

### 👁️ Control The Eyes

```bash
# Turn eyes ON
mosquitto_pub -h 192.168.1.100 -t "franky/eyes" -m "1"

# Turn eyes OFF
mosquitto_pub -h 192.168.1.100 -t "franky/eyes" -m "0"
```

### 🔊 Adjust Volume

```bash
# Set volume to 70%
mosquitto_pub -h 192.168.1.100 -t "esp32/volume" -m "0.7"
```

---

## 💀 Virtual Skull Visualization

> ⚠️ **Work in Progress** - This feature is currently under development

For an enhanced visual experience, Franky includes a 3D skull viewer that displays a realistic skull model with animated jaw and glowing eyes.

### ✨ Features

- 🦴 **Realistic 3D skull model** - High-quality anatomical model
- 🗣️ **Animated jaw** - 60° rotation range, synced with speech
- 👁️ **Glowing eyes** - Red eyes that brighten when speaking
- 🔄 **Auto-rotation** - Smooth 360° view
- 📡 **MQTT sync** - Real-time synchronization with Franky's speech

### 🚀 Quick Start

```bash
# Install dependencies
cd virtual_skull
pip install -r requirements.txt

# Run the viewer
./run_viewer.sh
```

---

## 🗂️ Graveyard Structure

```
franky/
├── 🎃 franky.png                    # Project mascot image
├── 🤖 franky.py                     # Main AI voice bot
├── 📋 requirements.txt              # Python dependencies
├── ⚙️ .env.example                  # Configuration template
├── 🙈 .gitignore                    # Git ignore rules
│
├── 🔧 devices/                      # Hardware firmware
│   ├── README.md                    # Device setup instructions
│   ├── xiao_esp32_mqtt/             # Simple MQTT control (jaw/eyes only)
│   ├── xiao_esp32_respeaker/        # Full setup with ReSpeaker audio
│   ├── xiao_esp32_c6_relay/         # Relay control board
│   └── xiao_mg24_relay/             # Alternative relay board
│
├── 💀 virtual_skull/                # 3D skull visualization
│   ├── README.md                    # Skull viewer setup
│   ├── BLENDER_GUIDE.md             # Model processing guide
│   ├── skull_viewer.py              # Realistic 3D skull renderer
│   ├── jaw_viewer_process.py        # Simple geometric viewer
│   ├── blender_separate_jaw.py      # Automated jaw separation
│   └── models/                      # 3D models (skull_original.glb)
│
├── 📡 mqtt/                         # MQTT broker setup
│   ├── docker-compose.yml           # Docker setup for Mosquitto
│   └── mosquitto.conf               # MQTT broker configuration
│
├── 📸 logs/                         # Camera captures and conversation logs (git-ignored)
└── 📖 README.md                     # You are here!
```

---

## 🎃 Network Configuration

### 📡 WiFi Settings
```
SSID: YOUR_WIFI_SSID
Password: YOUR_WIFI_PASSWORD
```

### 🌐 IP Addresses
| Device | IP Address | Purpose |
|--------|------------|---------|
| 🖥️ Server/PC | `192.168.1.100` | Main bot |
| 📡 ESP32 | `192.168.1.101` | Audio I/O |
| 📹 Camera | `192.168.1.102` | Vision |

### 🔌 Port Map
| Port | Protocol | Direction | Purpose |
|------|----------|-----------|---------|
| `5001` | UDP | ESP32 → Server | Microphone audio |
| `5002` | UDP | Server → ESP32 | Speaker audio |
| `1883` | MQTT | Bidirectional | Control commands |
| `554` | RTSP | Camera → Server | Video stream |

---

## 🧙‍♂️ Voice Acting Magic

Franky can transform its voice in real-time for different characters:

| Character Type | Effects | Example |
|----------------|---------|---------|
| 👹 **Monsters/Demons** | Pitch DOWN + Heavy Reverb | Deep, terrifying voice |
| 🧙 **Witches** | Pitch UP + Chorus | Cackling, mystical |
| 👻 **Ghosts** | Reverb + Light Phaser | Ethereal, haunting |
| 🎪 **Normal Franky** | Light Reverb | Friendly skull |
| ⚡ **Jump Scares** | Pitch DOWN + Distortion | "BOO!" moments |

Effects are applied dynamically during conversation via the `set_audio_effects` function.

---

## 🐛 Troubleshooting the Curse

### 🔧 ESP32 Not Responding

1. Check USB connection
2. Press **RESET** button on XIAO ESP32-S3
3. Re-upload firmware from `devices/` directory
4. Check serial monitor: `arduino-cli monitor -p /dev/cu.usbmodem1101`

### 🔇 No Audio

1. Verify ESP32 IP in logs: `🎯 ESP32 detected at 192.168.1.101`
2. Check MQTT connection: `✅ MQTT connected`
3. Test MQTT: `mosquitto_pub -h 192.168.1.100 -t "franky/test" -m "1"`
4. Verify volume setting: `mosquitto_pub -h 192.168.1.100 -t "esp32/volume" -m "0.8"`

### 📷 Camera Issues

Check logs for timing breakdown:
```
📷 [1/6] Starting camera capture...
📷 [2/6] Camera opened: 0.45s
📷 [3/6] Frame captured: 0.12s
📷 ✅ Total camera capture time: 0.89s
```

If camera fails:
- Verify RTSP URL in `.env`
- Test with VLC: `vlc rtsp://admin:password@192.168.1.102/Preview_01_main`
- Check network connectivity to camera

### 🎵 Audio Effects Not Working

```bash
# Reinstall Pedalboard
pip uninstall pedalboard
pip install pedalboard

# Check for warning in logs
⚠️ Pedalboard not installed, audio effects disabled
```

---

## 💻 Development

For build instructions and development guidelines, see:
- [`CLAUDE.md`](CLAUDE.md) - Main development guide
- [`devices/README.md`](devices/README.md) - Firmware development

---

## 📜 License

**MIT License** - Feel free to use this code for your own spooky creations!

See [LICENSE](LICENSE) file for full details.

---

## 🙏 Credits & Dark Acknowledgments

This unholy creation was made possible by:

- **[OpenAI](https://openai.com)** - Realtime API and GPT-4o language model
- **[Seeed Studio](https://www.seeedstudio.com/)** - ReSpeaker XVF3800 microphone array
- **[Espressif](https://www.espressif.com/)** - ESP32-S3 platform
- **[Anthropic Claude Code](https://claude.ai/code)** - Entire project vibe-coded with AI assistance
- **My Daughter** - For testing the skull and choosing the best spooky phrases 🎃
- **The Halloween Spirit** - For inspiring spooky projects everywhere 🎃

---

<div align="center">

### 🎃 Happy Halloween! 🎃

**Made with 💀 and ⚡ for Halloween 2025**

*"Some things are better left undead..."*

---

**Created by Nagaev Maksim**

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-0077B5?logo=linkedin)](http://linkedin.com/in/nagaev-maksim/)
[![Claude Code](https://img.shields.io/badge/Vibe--Coded_with-Claude_Code-5A67D8?logo=anthropic)](https://claude.ai/code)

</div>
