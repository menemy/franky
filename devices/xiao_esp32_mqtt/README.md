# Franky Simple MQTT Control Firmware

Simple ESP32 firmware for controlling jaw servo and LED eyes via MQTT. **No audio** - use your laptop/PC for audio in speaker mode.

## Hardware

- **ESP32 board:** XIAO ESP32-S3, ESP32-C3, or any ESP32
- **Servo motor:** SG90, MG90S, or similar (GPIO 9)
- **LED eyes:** 5mm red LEDs (GPIO 10)
- **Power:** 5V 2A power supply

## Wiring

```
Servo (Jaw):
  - Signal → GPIO 9
  - VCC → 5V
  - GND → GND

LED Eyes:
  - Anode (+) → GPIO 10 → 330Ω resistor
  - Cathode (-) → GND
```

## Setup

1. **Install Arduino IDE** and ESP32 board support

2. **Install libraries:**
   - ESP32Servo
   - PubSubClient

3. **Edit firmware:**
   - Open `xiao_esp32_mqtt.ino`
   - Update WiFi credentials
   - Update MQTT broker IP

4. **Upload:**
   - Connect ESP32 via USB
   - Select board: "XIAO ESP32-S3" or your ESP32 board
   - Select port
   - Click Upload

## Configuration

Edit these values in the `.ino` file:

```cpp
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";
const char* mqtt_server = "192.168.1.100";
```

## MQTT Topics

- **`franky/jaw`** - Jaw angle (0-180 degrees)
  ```bash
  mosquitto_pub -h 192.168.1.100 -t "franky/jaw" -m "90"
  ```

- **`franky/eyes`** - LED eyes (0=off, 1=on)
  ```bash
  mosquitto_pub -h 192.168.1.100 -t "franky/eyes" -m "1"
  ```

## Testing

```bash
# Test jaw movement
mosquitto_pub -h localhost -t "franky/jaw" -m "0"
mosquitto_pub -h localhost -t "franky/jaw" -m "90"
mosquitto_pub -h localhost -t "franky/jaw" -m "180"

# Test eyes
mosquitto_pub -h localhost -t "franky/eyes" -m "1"
mosquitto_pub -h localhost -t "franky/eyes" -m "0"
```

## Audio Setup

This firmware **does not handle audio**. For audio, use your laptop/PC in speaker mode:

In `.env`:
```env
OUTPUT_MODE=speakers
ENABLE_MQTT=true
MQTT_SERVER=192.168.1.100
```

Then run:
```bash
python3 franky.py
```

The Python bot will:
- Handle audio input/output on your laptop
- Send jaw/eyes commands to ESP32 via MQTT
- Control smart lights and other features

## Troubleshooting

**ESP32 not connecting to WiFi:**
- Check SSID and password
- Ensure 2.4GHz WiFi (ESP32 doesn't support 5GHz)

**MQTT not working:**
- Check MQTT broker is running
- Check IP address is correct
- Check broker port (default 1883)

**Servo not moving:**
- Check wiring
- Ensure 5V power supply (not just USB)
- Try different GPIO pins

**Eyes not lighting:**
- Check LED polarity
- Check resistor value (330Ω)
- Try different GPIO pin
