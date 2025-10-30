#!/bin/bash
# ESP32-C6 Firmware Build Script
# Builds the firmware and optionally uploads it or triggers OTA update

set -e

SKETCH_DIR="/Users/maksimnagaev/Projects/franky/esp32_c6_relay"
FQBN="esp32:esp32:XIAO_ESP32C6"
BUILD_DIR="${SKETCH_DIR}/build"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}ESP32-C6 Relay Build Script${NC}"
echo -e "${BLUE}================================${NC}\n"

# Create build directory if it doesn't exist
mkdir -p "$BUILD_DIR"

# Build firmware
echo -e "${YELLOW}[1/4] Building firmware...${NC}"
cd "$SKETCH_DIR"
arduino-cli compile --fqbn "$FQBN" --output-dir "$BUILD_DIR"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Build successful${NC}\n"
else
    echo -e "${RED}✗ Build failed${NC}"
    exit 1
fi

# Get firmware file path
FIRMWARE_BIN="${BUILD_DIR}/esp32_c6_relay.ino.bin"

if [ ! -f "$FIRMWARE_BIN" ]; then
    echo -e "${RED}✗ Firmware binary not found: $FIRMWARE_BIN${NC}"
    exit 1
fi

# Get file size
FIRMWARE_SIZE=$(ls -lh "$FIRMWARE_BIN" | awk '{print $5}')
echo -e "${YELLOW}[2/4] Firmware info:${NC}"
echo -e "  File: $FIRMWARE_BIN"
echo -e "  Size: $FIRMWARE_SIZE\n"

# Ask user what to do
echo -e "${YELLOW}[3/4] What do you want to do?${NC}"
echo "  1) Upload via USB"
echo "  2) OTA update via MQTT"
echo "  3) Just build (done)"
read -p "Select option [1-3]: " option

case $option in
    1)
        echo -e "\n${YELLOW}[4/4] Uploading via USB...${NC}"
        # Find USB port
        PORT=$(ls /dev/cu.usbmodem* 2>/dev/null | head -n 1)
        if [ -z "$PORT" ]; then
            echo -e "${RED}✗ No USB device found${NC}"
            exit 1
        fi
        echo -e "Using port: $PORT"
        arduino-cli upload -p "$PORT" --fqbn "$FQBN" --input-dir "$BUILD_DIR"
        echo -e "${GREEN}✓ Upload complete${NC}"
        ;;
    2)
        echo -e "\n${YELLOW}[4/4] Triggering OTA update...${NC}"
        if [ ! -f "${SKETCH_DIR}/ota_update.py" ]; then
            echo -e "${RED}✗ ota_update.py not found${NC}"
            exit 1
        fi
        python3 "${SKETCH_DIR}/ota_update.py" --file "$FIRMWARE_BIN"
        ;;
    3)
        echo -e "\n${GREEN}✓ Build complete${NC}"
        ;;
    *)
        echo -e "${RED}✗ Invalid option${NC}"
        exit 1
        ;;
esac

echo -e "\n${GREEN}================================${NC}"
echo -e "${GREEN}Done!${NC}"
echo -e "${GREEN}================================${NC}"
