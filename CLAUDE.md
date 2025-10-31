# Franky - Development Guide

## ESP32 Firmware

### Build and Upload

Firmware location: `devices/xiao_esp32_respeaker/xiao_esp32_respeaker.ino`

See detailed instructions in [`devices/README.md`](devices/README.md)

**Compile:**
```bash
cd devices/xiao_esp32_respeaker
arduino-cli compile --fqbn esp32:esp32:XIAO_ESP32S3
```

**Upload:**
```bash
# Find USB port (usually /dev/cu.usbmodem1101)
ls /dev/cu.usbmodem*

# Upload from the firmware directory
cd devices/xiao_esp32_respeaker
arduino-cli upload -p /dev/cu.usbmodem1101 --fqbn esp32:esp32:XIAO_ESP32S3
```

**One-liner (compile + upload):**
```bash
cd devices/xiao_esp32_respeaker && \
arduino-cli compile --fqbn esp32:esp32:XIAO_ESP32S3 && \
arduino-cli upload -p /dev/cu.usbmodem1101 --fqbn esp32:esp32:XIAO_ESP32S3
```

### Audio Configuration

- **Sample rate:** 16 kHz between ESP32 and bot (resampled to 24 kHz for OpenAI)
- **I2S format:** 32-bit stereo (XMOS with AEC/AGC/beamforming)
- **UDP format:** 16-bit mono PCM frames
- **Frame size:** 40ms (640 samples, 1280 bytes)
- **Speaker volume:** 0.2 (20%) default; adjust via `franky/volume`

### Network Setup

- **WiFi:** YOUR_WIFI_SSID / YOUR_WIFI_PASSWORD
- **Server IP:** 192.168.1.100
- **UDP ports:**
  - 5001: ESP32 sends mic audio
  - 5002: ESP32 receives speaker audio
- **MQTT:** 192.168.1.100:1883 (jaw, eyes, volume topics)

## Python Voice Bot

### Setup

```bash
pip3 install -r requirements.txt
```

### Run

```bash
python3 franky.py
```

### Configuration (.env)

```
OPENAI_API_KEY=your_key_here
CAMERA_RTSP_STREAM=rtsp://admin:password@192.168.1.102/Preview_01_main
ESP32_IP=192.168.1.101
MQTT_SERVER=192.168.1.100
MQTT_PORT=1883
```

### Architecture

- **ESP32 → Bot:** UDP mic audio (16-bit mono, 1280 bytes/40ms)
- **Bot → ESP32:** UDP speaker audio (16-bit mono, 1280 bytes/40ms)
- **Bot → OpenAI:** 24kHz PCM16 (resampled from 16kHz)
- **OpenAI → Bot:** 24kHz PCM16 (resampled to 16kHz)
- **MQTT:** Jaw position, LED eyes, and output volume topics
