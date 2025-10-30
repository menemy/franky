# ESP32-C6 Witch Relay Controller

MQTT-controlled relay module with OTA update support for ESP32-C6.

## Overview

Battery-optimized relay controller that triggers via MQTT commands. Features WiFi power saving, OTA updates, and automatic device info reporting.

## Hardware

- **Board:** Seeed Studio XIAO ESP32-C6
- **Relay Module:** Seeed Relay Add-on Module (1-channel)
- **Relay Pin:** GPIO1 (D1)
- **Logic:** Active LOW (relay OFF = GPIO HIGH, no current draw through optocoupler)

## Features

- ✅ MQTT control via WiFi
- ✅ 200ms relay pulse trigger
- ✅ WiFi power saving (modem sleep)
- ✅ OTA updates via MQTT (HTTP download)
- ✅ ArduinoOTA support (local network)
- ✅ Device info reporting (IP, RSSI, MAC)
- ✅ Low power consumption with active-LOW logic

## Network Configuration

- **WiFi SSID:** YOUR_WIFI_SSID (configure in .ino file)
- **WiFi Password:** YOUR_WIFI_PASSWORD (configure in .ino file)
- **MQTT Broker:** 192.168.1.100:1883
- **Device Hostname:** esp32-witch

## MQTT Topics

### Control Topics

| Topic | Direction | Purpose | Payload |
|-------|-----------|---------|---------|
| `witch/trigger` | Subscribe | Trigger relay pulse (200ms) | Any value |
| `witch/info/request` | Subscribe | Request device info | Any value |
| `witch/ota/update` | Subscribe | Trigger OTA update | JSON: `{"url": "http://..."}` |

### Status Topics

| Topic | Direction | Purpose | Payload Example |
|-------|-----------|---------|-----------------|
| `witch/status` | Publish | Relay status | `online`, `triggered`, `idle` |
| `witch/info` | Publish | Device information | `{"ip":"192.168.2.246","rssi":-69,"mac":"7C:2C:67:64:BE:B0"}` |
| `witch/ota/status` | Publish | OTA update status | `downloading`, `success: rebooting`, `error: ...` |
| `witch/ota/progress` | Publish | OTA download progress | `progress: 50%` |

## Usage

### Basic Commands

**Trigger Relay (200ms pulse):**
```bash
mosquitto_pub -h 192.168.2.243 -t "witch/trigger" -m "1"
```

**Request Device Info:**
```bash
mosquitto_pub -h 192.168.2.243 -t "witch/info/request" -m "1"
```

**Monitor All Activity:**
```bash
mosquitto_sub -h 192.168.2.243 -t "witch/#"
```

### Python Control

Use the included test script:
```bash
python3 test_witch_mqtt.py
```

Commands:
- `t` or `trigger` - Trigger relay
- `q` or `quit` - Exit

### Device Info

Device automatically publishes info on:
- Initial connection/startup
- Reconnection after disconnect
- Manual request via `witch/info/request`

Example response:
```json
{
  "ip": "192.168.2.246",
  "rssi": -69,
  "mac": "7C:2C:67:64:BE:B0"
}
```

## Building and Uploading

### Prerequisites

Install ESP32 platform:
```bash
arduino-cli core install esp32:esp32
arduino-cli lib install "PubSubClient"
arduino-cli lib install "ArduinoJson"
```

### Compile

```bash
cd esp32_c6_relay
arduino-cli compile --fqbn esp32:esp32:XIAO_ESP32C6
```

### Upload via USB

Find USB port:
```bash
ls /dev/cu.usbmodem*  # macOS
ls /dev/ttyACM*       # Linux
```

Upload:
```bash
arduino-cli upload -p /dev/cu.usbmodem11301 --fqbn esp32:esp32:XIAO_ESP32C6
```

### Build Script

Use the interactive build script:
```bash
./build.sh
```

Options:
1. Upload via USB
2. OTA update via MQTT
3. Just build

## OTA Updates

### Method 1: Using ota_update.py Script

**From local file:**
```bash
python3 ota_update.py --file ./build/esp32_c6_relay.ino.bin
```

The script automatically:
- Starts HTTP server on port 8000
- Publishes OTA command to MQTT
- Monitors update progress
- Stops HTTP server when complete

**From external URL:**
```bash
python3 ota_update.py --url http://192.168.2.243:8000/firmware.bin
```

**Custom port:**
```bash
python3 ota_update.py --file ./firmware.bin --port 9000
```

### Method 2: Manual MQTT Command

1. Host firmware file on HTTP server:
```bash
cd build
python3 -m http.server 8000
```

2. Send OTA command via MQTT:
```bash
mosquitto_pub -h 192.168.2.243 -t "witch/ota/update" \
  -m '{"url":"http://192.168.2.243:8000/esp32_c6_relay.ino.bin"}'
```

3. Monitor progress:
```bash
mosquitto_sub -h 192.168.2.243 -t "witch/ota/#"
```

### Method 3: ArduinoOTA (Local Network)

```bash
arduino-ide  # Open Arduino IDE
# Tools > Port > Network ports > esp32-witch
# Upload as normal
```

### OTA Update Process

1. ESP32-C6 receives OTA command via MQTT
2. Downloads firmware from HTTP URL
3. Reports progress every 10% (`witch/ota/progress`)
4. Validates firmware
5. Flashes new firmware
6. Automatically reboots
7. Publishes device info on startup

**Expected output:**
```
📡 Status: parsing
📡 Status: starting
📡 Status: downloading
📥 progress: 10%
📥 progress: 20%
...
📥 progress: 100%
📡 Status: success: rebooting
```

## Power Optimization

### WiFi Power Saving
- **Mode:** Modem sleep (WIFI_PS_MIN_MODEM)
- **Behavior:** Radio sleeps between packets
- **Impact:** Minimal latency increase (<0.5s), significant power savings

### Relay Logic
- **Active LOW:** Relay OFF = GPIO HIGH
- **Benefit:** No current flows through optocoupler LED when relay is idle
- **Result:** Minimal battery drain in standby

### CPU Sleep
- Small delays in main loop allow CPU to enter light sleep between MQTT packets

## Typical Usage Scenario

### Integration with Voice Bot

From `franky.py` or similar:
```python
import paho.mqtt.publish as publish

def trigger_witch_relay():
    """Trigger the witch relay via MQTT"""
    publish.single(
        "witch/trigger",
        payload="1",
        hostname="192.168.2.243",
        port=1883
    )
```

### Docker Deployment

If using Docker for your application:
```yaml
version: '3'
services:
  mqtt:
    image: eclipse-mosquitto
    ports:
      - "1883:1883"
    volumes:
      - ./mosquitto.conf:/mosquitto/config/mosquitto.conf

  voice_bot:
    build: .
    environment:
      - MQTT_SERVER=mqtt
      - MQTT_PORT=1883
    depends_on:
      - mqtt
```

## Troubleshooting

### Device Not Responding

1. Check if device is online:
```bash
mosquitto_sub -h 192.168.2.243 -t "witch/status"
```

2. Request device info:
```bash
mosquitto_pub -h 192.168.2.243 -t "witch/info/request" -m "1"
mosquitto_sub -h 192.168.2.243 -t "witch/info"
```

3. Check serial output:
```bash
arduino-cli monitor -p /dev/cu.usbmodem11301 -c baudrate=115200
```

### OTA Update Failed

**Connection errors:**
- Ensure HTTP server is accessible from ESP32-C6
- Check firewall settings
- Verify ESP32-C6 can reach the IP address

**Download errors:**
- Confirm .bin file exists and is valid
- Check available flash space (firmware must be <1.3MB)
- Ensure stable WiFi connection

**Verification errors:**
- Recompile firmware
- Try USB upload first to verify firmware works

### Relay Not Clicking

1. Verify GPIO1 connection to relay module
2. Check relay module power (3.3V or 5V depending on module)
3. Test with direct trigger:
```bash
mosquitto_pub -h 192.168.2.243 -t "witch/trigger" -m "1"
```
4. Monitor MQTT response for confirmation

### WiFi Connection Issues

- Check WiFi credentials in code
- Verify 2.4GHz network (ESP32-C6 doesn't support 5GHz)
- Check router DHCP settings
- Device attempts connection for 10 seconds (20 attempts × 500ms)

## Development

### Project Structure

```
esp32_c6_relay/
├── esp32_c6_relay.ino  # Main firmware
├── build/              # Compiled output
│   └── *.bin          # Firmware binary
├── ota_update.py      # OTA update script
├── build.sh           # Build automation script
└── README.md          # This file
```

### Modifying Code

1. Edit `esp32_c6_relay.ino`
2. Compile and test:
```bash
./build.sh
# Select option 1 (USB) for first upload
```
3. After confirming it works, use OTA for future updates:
```bash
./build.sh
# Select option 2 (OTA)
```

### Adding Features

**New MQTT topics:**
1. Add topic constant at top of file
2. Subscribe in `reconnectMQTT()`
3. Handle in `mqttCallback()`

**New status messages:**
```cpp
mqttClient.publish("witch/custom", "message");
```

## Pin Configuration

| Pin | Function | Notes |
|-----|----------|-------|
| GPIO1 (D1) | Relay control | Active LOW (HIGH=OFF, LOW=ON) |

## Technical Specifications

- **Flash Usage:** ~1.07 MB (81% of 1.31 MB)
- **RAM Usage:** 46 KB (14% of 327 KB)
- **WiFi:** 2.4 GHz 802.11 b/g/n (WiFi 6 capable)
- **Power Saving:** WIFI_PS_MIN_MODEM
- **MQTT Buffer:** 512 bytes (for JSON messages)
- **OTA Timeout:** 120 seconds

## Dependencies

- **PubSubClient** (MQTT client library)
- **ArduinoJson** v7+ (JSON parsing/serialization)
- **WiFi** (ESP32 built-in)
- **HTTPUpdate** (ESP32 built-in)
- **ArduinoOTA** (ESP32 built-in)

## License

Open source - use freely for your projects.

## Related Files

- `test_witch_mqtt.py` - Python MQTT testing script (in parent directory)
- `ota_update.py` - OTA update automation script
- `build.sh` - Build and deployment script
- Parent project: Franky voice bot with ESP32 integration
