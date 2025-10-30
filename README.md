<div align="center">

<img src="franky.png" width="400" alt="Franky the Halloween Skull">

# 🎃 FRANKY 💀
### *The AI-Powered Halloween Talking Skull*

[![OpenAI](https://img.shields.io/badge/OpenAI-Realtime%20API-412991?logo=openai)](https://platform.openai.com)
[![ESP32](https://img.shields.io/badge/ESP32-S3-E7352C?logo=espressif)](https://www.espressif.com)
[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?logo=python)](https://www.python.org)
[![Halloween](https://img.shields.io/badge/Halloween-2024-FF6600?logo=ghost)](https://github.com)

*Where AI meets the afterlife* ☠️✨

</div>

---

## 👻 What is This Unholy Creation?

**Franky** is a talking Halloween skull that uses cutting-edge AI to scare, entertain, and engage with trick-or-treaters in real-time. Powered by OpenAI's GPT-4o Realtime API, this possessed decoration comes alive with:

- 🗣️ **Natural voice conversations** - Speaks with human-like fluency in multiple languages
- 🧠 **Computer vision** - Actually sees who's at your door through an RTSP camera
- 🎭 **Dynamic voice acting** - Transforms voice on-the-fly for different spooky characters
- 💀 **Animated jaw** - Perfectly synced mouth movements
- 👁️ **Glowing LED eyes** - Programmable eye lighting effects
- 🎮 **Interactive games** - Mini-games for kids (and adults!)
- 🎵 **Real-time audio effects** - Professional-grade voice manipulation

<div align="center">

### 🌍 Speaks Your Language

Franky auto-detects and responds in **English**, **Russian**, or **Spanish**

</div>

---

## 🦴 The Unholy Trinity: Features

### 🧙‍♂️ Personality & Interaction

- **Multilingual AI** - Detects guest language and responds naturally
- **Call-and-response phrases** - Interactive "Trick or..." → "TREAT!" moments
- **Mini-games** - "Treat or Spell?", "Repeat After the Ghost", and more
- **Vision-aware** - Adapts behavior based on what (or who) it sees
- **Safe scares** - Spooky but family-friendly interactions

### 🎛️ Technical Sorcery

- **OpenAI Realtime API** - GPT-4o with native audio I/O
- **4-Mic Array** - ReSpeaker XVF3800 with XMOS DSP
  - Acoustic Echo Cancellation (AEC)
  - Automatic Gain Control (AGC)
  - Beamforming for clear audio
- **Real-time Effects** - Powered by Spotify's Pedalboard library
  - Reverb (cave echoes)
  - Pitch shifting (±12 semitones for monsters/witches)
  - Distortion (demonic voices)
  - Chorus & Phaser (ethereal effects)

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
                                            ▲                ▲
                                            │                │
                                       UDP 5002         Pedalboard
                                            │             Effects
                                            │                │
                                        ┌───────┐       ┌──────────┐
                                        │Speaker│◀──────│  Reverb  │
                                        │       │       │  Pitch   │
                                        └───────┘       │ Distort  │
                                                        └──────────┘
```

---

## 🧪 Summoning Ritual (Installation)

### 📦 Step 1: Python Incantations

```bash
# Install dependencies
pip install -r requirements.txt
```

**Required Python packages:**
- `pyaudio` - Audio I/O
- `websockets` - OpenAI Realtime API connection
- `opencv-python` - Camera vision
- `paho-mqtt` - Hardware control
- `pedalboard` - Audio effects magic
- `numpy`, `scipy` - Audio processing

### ⚙️ Step 2: ESP32 Firmware

See detailed instructions in [`devices/README.md`](devices/README.md)

**Quick start:**
```bash
cd devices/xiao_esp32_respeaker
arduino-cli compile --fqbn esp32:esp32:XIAO_ESP32S3
arduino-cli upload -p /dev/cu.usbmodem1101 --fqbn esp32:esp32:XIAO_ESP32S3
```

### 🔑 Step 3: Configuration Secrets

Create your `.env` file:
```bash
cp .env.example .env
```

Fill in your dark secrets:
```env
OPENAI_API_KEY=sk-proj-your_api_key_here
CAMERA_RTSP_STREAM=rtsp://admin:password@192.168.1.102/Preview_01_main
ESP32_IP=192.168.1.101
MQTT_SERVER=192.168.1.100
MQTT_PORT=1883
```

---

## 🎬 Bring Franky to Life

### 🚀 Launch the Soul

```bash
python3 franky.py
```

### 🎭 Choose a Voice

```bash
# Use different voice personalities
python3 franky.py --voice echo    # Deep and mysterious
python3 franky.py --voice shimmer # Ethereal and ghostly
python3 franky.py --voice ash     # Default balanced voice
```

**Available voices:** `alloy`, `ash`, `ballad`, `coral`, `echo`, `sage`, `shimmer`, `verse`, `marin`, `cedar`

### ⚙️ Configuration Options

Franky supports comprehensive CLI arguments for flexible deployment:

```bash
# Test without ESP32 hardware (local speakers + mic)
python3 franky.py --output speakers --no-camera --no-mqtt

# Disable specific hardware components
python3 franky.py --no-jaw          # Disable jaw movement
python3 franky.py --no-eyes         # Disable LED eyes
python3 franky.py --no-camera       # Disable vision

# Custom network configuration
python3 franky.py --esp32-ip 192.168.1.50 --mqtt-server 192.168.1.100

# Disable conversation logging (enabled by default)
python3 franky.py --no-log-conversation
```

**All available options:**
- `--voice` - Select AI voice (alloy, ash, ballad, coral, echo, sage, shimmer, verse, marin, cedar)
- `--output` - Audio output: `esp32_udp` (default) or `speakers`
- `--enable-camera` / `--no-camera` - Toggle camera vision (default: enabled)
- `--enable-mqtt` / `--no-mqtt` - Toggle MQTT control (default: enabled)
- `--enable-jaw` / `--no-jaw` - Toggle jaw movement (default: enabled)
- `--enable-eyes` / `--no-eyes` - Toggle LED eyes (default: enabled)
- `--esp32-ip` - Override ESP32 IP address
- `--mqtt-server` - Override MQTT broker address
- `--mqtt-port` - Override MQTT broker port (default: 1883)
- `--log-conversation` / `--no-log-conversation` - Conversation logging (default: enabled)

**Examples:**

```bash
# Full hardware setup (default)
python3 franky.py

# Test without ESP32 hardware (local speakers + mic)
python3 franky.py --output speakers --no-camera --no-mqtt

# ESP32 audio only, no jaw/camera
python3 franky.py --no-jaw --no-camera

# Different voice (logging always enabled by default)
python3 franky.py --voice echo
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

### 🎨 Customization

The skull model needs to be processed in Blender to enable jaw animation:

1. See [`virtual_skull/BLENDER_GUIDE.md`](virtual_skull/BLENDER_GUIDE.md) for step-by-step instructions
2. Use the provided Blender script for automatic separation
3. Or manually separate the mandible for precise control

**Included models:**
- Simple geometric skull (ready to use, basic animation)
- CC-BY realistic skull model (requires Blender processing)

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
│   ├── xiao_esp32_respeaker/        # Main audio board
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
├── 🧪 experiments/                  # Test scripts (git-ignored)
├── 📸 logs/                         # Camera captures (git-ignored)
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
- **[Spotify](https://spotify.github.io/pedalboard/)** - Pedalboard audio effects library
- **[Seeed Studio](https://www.seeedstudio.com/)** - ReSpeaker XVF3800 microphone array
- **[Espressif](https://www.espressif.com/)** - ESP32-S3 platform
- **The Halloween Spirit** - For inspiring spooky projects everywhere 🎃

---

<div align="center">

### 🎃 Happy Halloween! 🎃

**Made with 💀 and ⚡ for Halloween 2025**

*"Some things are better left undead..."*

[![GitHub](https://img.shields.io/badge/GitHub-Repository-181717?logo=github)](https://github.com/yourusername/franky)

</div>