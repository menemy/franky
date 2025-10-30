# 🎃 Franky Devices

This directory contains firmware for all hardware devices used in the Franky project.

## XIAO ESP32-S3 with ReSpeaker

### Hardware Setup

- **Board**: Seeed Studio XIAO ESP32-S3
- **Microphone Array**: ReSpeaker XVF3800 (4-mic with XMOS DSP)
- **GPIO Connections**:
  - D0 (GPIO1) - LED eyes control
  - D2 (GPIO3) - Jaw relay module
  - GPIO 5 (SDA), GPIO 6 (SCL) - I2C for XMOS control
  - GPIO 7 (WS), GPIO 8 (BCK), GPIO 43 (DIN), GPIO 44 (DOUT) - I2S audio

### Prerequisites

Install Arduino CLI:

```bash
# macOS
brew install arduino-cli

# Linux
curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | sh

# Windows
choco install arduino-cli
```

### Setup Arduino CLI

```bash
# Initialize configuration
arduino-cli config init

# Add ESP32 board support
arduino-cli config add board_manager.additional_urls https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json

# Update board index
arduino-cli core update-index

# Install ESP32 core
arduino-cli core install esp32:esp32
```

### Upload Firmware

#### 1. Find USB Port

```bash
# macOS/Linux
ls /dev/cu.usbmodem*

# Linux alternative
ls /dev/ttyACM*

# Windows
# Use Device Manager or:
mode
```

Common ports:
- macOS: `/dev/cu.usbmodem1101`
- Linux: `/dev/ttyACM0`
- Windows: `COM3`

#### 2. Compile and Upload

**From devices directory:**

```bash
cd /path/to/franky/devices/xiao_esp32_respeaker

# Compile
arduino-cli compile --fqbn esp32:esp32:XIAO_ESP32S3

# Upload (replace port with your actual port)
arduino-cli upload -p /dev/cu.usbmodem1101 --fqbn esp32:esp32:XIAO_ESP32S3
```

**One-liner (compile + upload):**

```bash
cd devices/xiao_esp32_respeaker && \
arduino-cli compile --fqbn esp32:esp32:XIAO_ESP32S3 && \
arduino-cli upload -p /dev/cu.usbmodem1101 --fqbn esp32:esp32:XIAO_ESP32S3
```

#### 3. Monitor Serial Output

```bash
arduino-cli monitor -p /dev/cu.usbmodem1101 -c baudrate=115200
```

Or use screen:

```bash
screen /dev/cu.usbmodem1101 115200
```

### Firmware Configuration

The firmware is configured for:
- **WiFi**: SSID `YOUR_WIFI_SSID`, password `YOUR_WIFI_PASSWORD` (edit in .ino file)
- **UDP Audio**: Port 5001 (send mic), Port 5002 (receive speaker)
- **MQTT**: Server at 192.168.1.100:1883
- **Sample Rate**: 16 kHz, 16-bit mono
- **Frame Size**: 40ms (640 samples, 1280 bytes)

### Serial Commands

Once uploaded, you can control the ESP32 via serial monitor:

```bash
info                      # Show system information
gpio <pin> <state>        # Control GPIO (e.g., gpio 1 1 for eyes ON)
mic channel <left|right>  # Switch microphone channel
```

### Troubleshooting

**Upload fails:**
1. Press and hold BOOT button while connecting USB
2. Press RESET button
3. Try upload again

**Port not found:**
```bash
# Check connected devices
arduino-cli board list
```

**Compilation errors:**
```bash
# Reinstall ESP32 core
arduino-cli core uninstall esp32:esp32
arduino-cli core install esp32:esp32
```

**Serial monitor shows garbage:**
- Check baud rate is set to 115200
- Press RESET button on ESP32

### Required Libraries

The firmware uses these libraries (installed automatically via Arduino IDE/CLI):

- ESP32 I2S library (built-in)
- WiFi library (built-in)
- AsyncUDP library (built-in)
- PubSubClient (for MQTT)

Install PubSubClient if needed:

```bash
arduino-cli lib install "PubSubClient"
```