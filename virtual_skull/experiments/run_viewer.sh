#!/bin/bash
# Quick launcher for Virtual Skull viewer

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}🦴 Franky Virtual Skull Viewer${NC}"
echo "=================================="

# Check if model exists
if [ ! -f "models/skull_original.glb" ]; then
    echo -e "${RED}❌ Model not found: models/skull_original.glb${NC}"
    echo "Please download the skull model first. See README.md"
    exit 1
fi

# Check if separated model exists
if [ -f "models/skull_separated.glb" ]; then
    echo -e "${GREEN}✅ Using separated skull model (with jaw animation)${NC}"
    MODEL_FILE="models/skull_separated.glb"
else
    echo -e "${YELLOW}⚠️  Using original model (jaw not separated yet)${NC}"
    echo "For jaw animation, process in Blender. See BLENDER_GUIDE.md"
    MODEL_FILE="models/skull_original.glb"
fi

# Check if MQTT is running
echo -n "Checking MQTT broker... "
if nc -z localhost 1883 2>/dev/null; then
    echo -e "${GREEN}✅ Running${NC}"
else
    echo -e "${YELLOW}⚠️  Not running${NC}"
    echo "Start MQTT broker: cd ../mqtt && docker-compose up -d"
fi

# Run viewer
echo ""
echo "Starting viewer..."
echo "Controls:"
echo "  - Jaw position: MQTT topic 'franky/jaw' (0.0-1.0)"
echo "  - Speaking: MQTT topic 'franky/speaking' (0/1)"
echo ""

python3 skull_viewer.py
