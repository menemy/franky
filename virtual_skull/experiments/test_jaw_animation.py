#!/usr/bin/env python3
"""
Test jaw animation via MQTT
"""
import paho.mqtt.client as mqtt
import time
import math

# Connect to MQTT
client = mqtt.Client()
client.connect("localhost", 1883, 60)

print("🦴 Testing jaw animation...")
print("   0.0 = closed")
print("   1.0 = max open (60°)\n")

try:
    while True:
        # Smooth animation using sine wave
        for i in range(100):
            # Create smooth open-close motion
            t = i / 100.0 * 2 * math.pi
            jaw_position = (math.sin(t) + 1.0) / 2.0  # 0.0 to 1.0

            client.publish("franky/jaw", str(jaw_position))
            print(f"Jaw position: {jaw_position:.2f}", end='\r')
            time.sleep(0.02)  # 50 FPS

        time.sleep(0.5)  # Pause between cycles

except KeyboardInterrupt:
    print("\n\n✅ Animation stopped")
    client.publish("franky/jaw", "0.0")  # Close jaw
    client.disconnect()
