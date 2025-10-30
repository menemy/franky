#!/usr/bin/env python3
"""
ESP32-C6 OTA Update Script via MQTT

Usage:
    python3 ota_update.py --url http://192.168.2.243:8000/firmware.bin
    python3 ota_update.py --file ./build/esp32_c6_relay.ino.bin
"""

import paho.mqtt.client as mqtt
import json
import sys
import argparse
import time
import http.server
import socketserver
import threading
import os

# MQTT Configuration
MQTT_SERVER = "192.168.2.243"
MQTT_PORT = 1883

# MQTT Topics
TOPIC_OTA_UPDATE = "witch/ota/update"
TOPIC_OTA_STATUS = "witch/ota/status"
TOPIC_OTA_PROGRESS = "witch/ota/progress"

# Global variables
ota_complete = False
http_server = None
http_thread = None


class QuietHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP request handler with minimal output"""
    def log_message(self, format, *args):
        # Only log if not a GET request for firmware
        if not (self.command == 'GET' and '.bin' in self.path):
            super().log_message(format, *args)


def start_http_server(port=8000, directory="."):
    """Start a simple HTTP server in background thread"""
    global http_server, http_thread

    os.chdir(directory)
    handler = QuietHTTPRequestHandler
    http_server = socketserver.TCPServer(("", port), handler)

    http_thread = threading.Thread(target=http_server.serve_forever, daemon=True)
    http_thread.start()

    print(f"✓ HTTP server started on port {port}")


def stop_http_server():
    """Stop the HTTP server"""
    global http_server
    if http_server:
        http_server.shutdown()
        http_server.server_close()
        print("✓ HTTP server stopped")


def on_connect(client, userdata, flags, rc, properties=None):
    """Callback when connected to MQTT broker"""
    if rc == 0:
        print(f"✓ Connected to MQTT broker at {MQTT_SERVER}:{MQTT_PORT}")
        client.subscribe(TOPIC_OTA_STATUS)
        client.subscribe(TOPIC_OTA_PROGRESS)
    else:
        print(f"✗ Failed to connect to MQTT broker, return code {rc}")


def on_message(client, userdata, msg):
    """Callback when MQTT message received"""
    global ota_complete

    topic = msg.topic
    payload = msg.payload.decode('utf-8')

    if topic == TOPIC_OTA_STATUS:
        print(f"📡 Status: {payload}")

        if "success" in payload or "complete" in payload:
            ota_complete = True
        elif "error" in payload or "failed" in payload:
            print(f"✗ OTA update failed: {payload}")
            ota_complete = True

    elif topic == TOPIC_OTA_PROGRESS:
        print(f"📥 {payload}")


def trigger_ota_update(firmware_url):
    """Send OTA update command via MQTT"""
    global ota_complete

    # Create MQTT client
    client = mqtt.Client(client_id="ota_updater", protocol=mqtt.MQTTv5)
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        # Connect to MQTT broker
        print(f"Connecting to MQTT broker {MQTT_SERVER}:{MQTT_PORT}...")
        client.connect(MQTT_SERVER, MQTT_PORT, 60)
        client.loop_start()

        # Wait for connection
        time.sleep(2)

        # Send OTA update command
        ota_command = {"url": firmware_url}
        print(f"\n🚀 Triggering OTA update...")
        print(f"   Firmware URL: {firmware_url}")

        client.publish(TOPIC_OTA_UPDATE, json.dumps(ota_command))

        # Wait for OTA to complete
        print("\n⏳ Waiting for OTA update to complete...\n")
        timeout = 120  # 2 minutes timeout
        start_time = time.time()

        while not ota_complete and (time.time() - start_time) < timeout:
            time.sleep(0.5)

        if ota_complete:
            print("\n✅ OTA update process completed!")
            print("   ESP32-C6 should reboot with new firmware")
        else:
            print("\n⏱ Timeout waiting for OTA completion")

        client.loop_stop()
        client.disconnect()

    except Exception as e:
        print(f"✗ Error: {e}")
        return False

    return ota_complete


def get_local_ip():
    """Get local IP address"""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip


def main():
    parser = argparse.ArgumentParser(
        description='ESP32-C6 OTA Update via MQTT',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Update from external URL
  python3 ota_update.py --url http://192.168.2.243:8000/firmware.bin

  # Update from local file (starts HTTP server automatically)
  python3 ota_update.py --file ./build/esp32_c6_relay.ino.bin

  # Update from local file with custom port
  python3 ota_update.py --file ./firmware.bin --port 9000
        '''
    )

    parser.add_argument('--url', type=str, help='Firmware URL (http://...)')
    parser.add_argument('--file', type=str, help='Local firmware file path')
    parser.add_argument('--port', type=int, default=8000, help='HTTP server port (default: 8000)')

    args = parser.parse_args()

    if not args.url and not args.file:
        parser.print_help()
        sys.exit(1)

    firmware_url = args.url

    # If local file is specified, start HTTP server
    if args.file:
        if not os.path.exists(args.file):
            print(f"✗ Error: File not found: {args.file}")
            sys.exit(1)

        file_dir = os.path.dirname(os.path.abspath(args.file))
        file_name = os.path.basename(args.file)

        local_ip = get_local_ip()
        firmware_url = f"http://{local_ip}:{args.port}/{file_name}"

        print(f"Starting HTTP server for local file...")
        start_http_server(port=args.port, directory=file_dir)
        time.sleep(1)

    try:
        # Trigger OTA update
        success = trigger_ota_update(firmware_url)

        # Stop HTTP server if started
        if args.file:
            time.sleep(2)
            stop_http_server()

        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        if args.file:
            stop_http_server()
        sys.exit(1)


if __name__ == "__main__":
    main()
