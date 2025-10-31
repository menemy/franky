#!/bin/bash
# Quick launcher for Simple Skull Viewer (no jaw separation needed)

echo "🦴 Franky Simple Skull Viewer"
echo "=============================="
echo ""
echo "This viewer works with ANY skull model"
echo "No Blender processing needed!"
echo ""
echo "Features:"
echo "  ✅ Shows full 3D skull"
echo "  ✅ Glowing red eyes when speaking"
echo "  ✅ Auto-rotation"
echo "  ✅ MQTT sync with Franky"
echo ""

# Check MQTT
if nc -z localhost 1883 2>/dev/null; then
    echo "✅ MQTT broker is running"
else
    echo "⚠️  MQTT broker not running"
    echo "   Start it: cd ../mqtt && docker-compose up -d"
fi

echo ""
echo "Starting viewer..."

# Use virtual environment if available
if [ -f "../.venv/bin/python3" ]; then
    echo "Using virtual environment..."
    ../.venv/bin/python3 skull_viewer_final.py
else
    python3 skull_viewer_final.py
fi
