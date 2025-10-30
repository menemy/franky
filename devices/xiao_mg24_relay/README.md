# XIAO MG24 Relay Controller

Simple relay controller for XIAO MG24 with serial command interface.

## Important Notes

**MG24 does NOT have WiFi!** The XIAO MG24 (Silicon Labs EFR32MG24) supports:
- Bluetooth Low Energy 5.3 (BLE)
- Thread/Matter
- **NO WiFi**

This firmware provides basic serial control. For wireless control, you would need to add BLE functionality.

## Hardware

- **Board:** Seeed Studio XIAO MG24
- **Relay Module:** Seeed Relay Add-on Module (1-channel)
- **Relay Pin:** GPIO1 (D1)

## Features

- Serial command interface
- ON/OFF relay control
- Status monitoring

## Build and Upload

### Prerequisites

Install SiliconLabs platform:

```bash
arduino-cli config add board_manager.additional_urls https://siliconlabs.github.io/arduino/package_arduinosilabs_index.json
arduino-cli core update-index
arduino-cli core install SiliconLabs:silabs
```

### Compile

```bash
cd xiao_mg24_relay
arduino-cli compile --fqbn SiliconLabs:silabs:xiao_mg24
```

### Upload

Find your USB port:

```bash
ls /dev/tty.usbmodem*  # macOS
ls /dev/ttyACM*        # Linux
```

Upload firmware:

```bash
arduino-cli upload -p /dev/tty.usbmodem3C8317873 --fqbn SiliconLabs:silabs:xiao_mg24
```

### One-liner (compile + upload)

```bash
cd xiao_mg24_relay && \
arduino-cli compile --fqbn SiliconLabs:silabs:xiao_mg24 && \
arduino-cli upload -p /dev/tty.usbmodem3C8317873 --fqbn SiliconLabs:silabs:xiao_mg24
```

## Usage

### Serial Monitor

Connect to serial monitor:

```bash
arduino-cli monitor -p /dev/tty.usbmodem3C8317873 -c baudrate=115200
```

### Serial Commands

- `on` - Turn relay ON
- `off` - Turn relay OFF
- `status` - Show relay state
- `help` - Show help

### Examples

```bash
# Open serial monitor
arduino-cli monitor -p /dev/tty.usbmodem3C8317873 -c baudrate=115200

# Type commands:
on       # Turn relay ON
off      # Turn relay OFF
status   # Check state
help     # Show commands
```

## Differences from ESP32-C6 Version

| Feature | ESP32-C6 | MG24 |
|---------|----------|------|
| WiFi | ✅ Yes | ❌ No |
| BLE | ✅ Yes (5.0) | ✅ Yes (5.3) |
| Thread/Matter | ❌ No | ✅ Yes |
| Web Interface | ✅ Yes | ❌ No (no WiFi) |
| REST API | ✅ Yes | ❌ No (no WiFi) |
| Serial Control | ✅ Yes | ✅ Yes |

## Adding Wireless Control

To add wireless control to MG24, you would need to implement BLE functionality. Example:

```cpp
// Add BLE library
#include <SiliconLabsBLE.h>

// Create BLE service for relay control
// Characteristic for pulse trigger
// etc.
```

For WiFi functionality, you would need an external WiFi module (e.g., ESP-AT command set module).

## Pin Configuration

The relay module connects to:
- **Relay Control:** GPIO1 (D1)
- **VCC:** 3.3V or 5V (depending on relay module)
- **GND:** Ground

## Troubleshooting

### Upload Failed

1. Press RESET button twice quickly to enter bootloader mode
2. Check USB cable (must support data transfer)
3. Verify correct port selection
4. Try different USB port

### Relay Not Responding

1. Check GPIO1 connection
2. Verify relay module power
3. Check serial monitor for debug messages
4. Ensure relay module is compatible with 3.3V logic

### Serial Monitor Not Working

1. Close any other programs using the port
2. Check baud rate (115200)
3. Try unplugging and replugging USB

## Resources

- [XIAO MG24 Wiki](https://wiki.seeedstudio.com/xiao_mg24_getting_started/)
- [Silicon Labs Arduino Core](https://github.com/SiliconLabs/arduino)
- [EFR32MG24 Datasheet](https://www.silabs.com/wireless/zigbee/efr32mg24-series-2-socs)

## License

Open source - use freely for your projects.
