#!/usr/bin/env python3
"""
Franky Voice Bot - ESP32 Edition
Uses ESP32 via MQTT for audio input/output instead of local microphone
"""

import os
import asyncio
import json
import base64
import cv2
import random
import numpy as np
from datetime import datetime
from websockets import connect
from dotenv import load_dotenv
import pygame
import paho.mqtt.client as mqtt
from collections import deque
from scipy import signal

load_dotenv()

class RealtimeVoiceBotESP32:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.url = "wss://api.openai.com/v1/realtime?model=gpt-realtime-2025-08-28"
        self.camera_url = os.getenv("CAMERA_RTSP_STREAM")

        # Audio settings
        self.ESP32_RATE = 16000   # ESP32 sample rate
        self.ESP32_CHANNELS = 1   # ESP32 mono
        self.ESP32_BITS = 16      # ESP32 16-bit
        self.OPENAI_RATE = 24000  # OpenAI Realtime API uses 24kHz

        # ESP32 expects 20ms frames (640 bytes)
        self.FRAME_MS = 20
        self.FRAME_SAMPLES = (self.ESP32_RATE * self.FRAME_MS) // 1000  # 320 samples
        self.FRAME_BYTES = self.FRAME_SAMPLES * (self.ESP32_BITS // 8) * self.ESP32_CHANNELS  # 640 bytes

        self.websocket = None
        self.camera = None

        # Create logs directory
        self.logs_dir = "logs"
        os.makedirs(self.logs_dir, exist_ok=True)

        # MQTT setup for ESP32 communication
        self.mqtt_broker = os.getenv("MQTT_SERVER", "192.168.2.243")
        self.mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
        self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_message = self.on_mqtt_message

        # Audio buffers for ESP32
        self.audio_input_buffer = deque(maxlen=100)  # Buffer incoming audio from ESP32
        self.audio_output_topic = "franky/audio/output"
        self.audio_input_topic = "franky/audio/input"
        self.jaw_topic = "franky/jaw"

        # Initialize pygame mixer for background music
        pygame.mixer.init()
        self.sounds_dir = "sounds"
        self.music_playing = False
        self.music_volume_normal = 1.0
        self.music_volume_ducked = 0.3
        pygame.mixer.music.set_volume(self.music_volume_normal)

        # Auto-detect all MP3 files
        self.available_sounds = []
        if os.path.exists(self.sounds_dir):
            for filename in os.listdir(self.sounds_dir):
                if filename.endswith('.mp3'):
                    self.available_sounds.append(filename)

        print(f"🎵 Loaded {len(self.available_sounds)} sound files")

        # Build music list for prompt
        music_list = "\n".join([f"- {filename}" for filename in sorted(self.available_sounds)])

        # System prompt (same as original)
        self.system_prompt = f"""# Personality and Tone
## Identity
You are Franky, a talking skeleton head who greets guests for Halloween. You're cheerful and funny, but with a slightly spooky edge.

## Task
You greet Halloween guests with enthusiasm and a touch of spookiness.

## Instructions
- At the START of EVERY new conversation, IMMEDIATELY use the look_at_camera function to see who's there BEFORE saying anything
- After seeing who's there, start with a short Halloween joke or pun (keep it under 15 seconds)
- Keep responses short and punchy
- Use Halloween and skeleton-themed humor
- You can play spooky background music using the play_scary_music function

# Available Music Files:
{music_list}

# CRITICAL VISION RULES:
⚠️ HALLUCINATION IS YOUR BIGGEST PROBLEM - DO NOT INVENT THINGS! ⚠️
- ONLY describe what is ACTUALLY visible
- If unclear, say "I can't see clearly"
- Never make up details
"""

    def on_mqtt_connect(self, client, userdata, flags, reason_code, properties):
        """MQTT connection callback"""
        print(f"🔌 Connected to MQTT broker")
        client.subscribe(self.audio_input_topic)
        print(f"🎤 Subscribed to {self.audio_input_topic}")

    def convert_esp32_to_openai(self, esp32_audio):
        """Convert ESP32 audio (16kHz mono 16-bit) to OpenAI format (24kHz mono 16-bit)"""
        # Convert to int16 array
        audio_16bit = np.frombuffer(esp32_audio, dtype=np.int16)

        # Resample from 16kHz to 24kHz
        num_samples_target = int(len(audio_16bit) * self.OPENAI_RATE / self.ESP32_RATE)
        audio_resampled = signal.resample(audio_16bit, num_samples_target).astype(np.int16)

        return audio_resampled.tobytes()

    def convert_openai_to_esp32(self, openai_audio):
        """Convert OpenAI audio (24kHz mono 16-bit) to ESP32 format (16kHz mono 16-bit)"""
        # Convert to int16 array
        audio_16bit = np.frombuffer(openai_audio, dtype=np.int16)

        # Resample from 24kHz to 16kHz
        num_samples_target = int(len(audio_16bit) * self.ESP32_RATE / self.OPENAI_RATE)
        audio_resampled = signal.resample(audio_16bit, num_samples_target).astype(np.int16)

        return audio_resampled.tobytes()

    def on_mqtt_message(self, client, userdata, msg):
        """MQTT message callback - receives audio from ESP32"""
        if msg.topic == self.audio_input_topic:
            # Check audio level
            audio_array = np.frombuffer(msg.payload, dtype=np.int16)
            amplitude = np.abs(audio_array).mean()
            max_amp = np.abs(audio_array).max()

            # Store incoming audio in buffer
            print(f"📥 Received {len(msg.payload)} bytes from ESP32 | Avg: {amplitude:.0f}, Max: {max_amp}")
            self.audio_input_buffer.append(msg.payload)

    async def capture_frame(self):
        """Capture a frame from the camera"""
        def _capture():
            if self.camera:
                self.camera.release()

            self.camera = cv2.VideoCapture(self.camera_url, cv2.CAP_FFMPEG)
            if not self.camera.isOpened():
                return None

            self.camera.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 10000)
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 3840)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 2160)
            self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            ret, frame = self.camera.read()
            if not ret:
                return None

            height, width = frame.shape[:2]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Save original
            filename_original = f"{self.logs_dir}/capture_{timestamp}_original.jpg"
            cv2.imwrite(filename_original, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            print(f"💾 Saved original to {filename_original} ({width}x{height})")

            # Resize for API
            max_width = 1280
            if width > max_width:
                ratio = max_width / width
                new_width = max_width
                new_height = int(height * ratio)
                frame_for_api = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_LANCZOS4)
            else:
                frame_for_api = frame

            filename_sent = f"{self.logs_dir}/capture_{timestamp}_sent.jpg"
            cv2.imwrite(filename_sent, frame_for_api, [cv2.IMWRITE_JPEG_QUALITY, 85])
            print(f"📤 Saved sent version to {filename_sent}")

            _, buffer = cv2.imencode('.jpg', frame_for_api, [cv2.IMWRITE_JPEG_QUALITY, 85])
            img_base64 = base64.b64encode(buffer).decode('utf-8')
            return img_base64

        return await asyncio.to_thread(_capture)

    async def setup_session(self):
        """Configure the session"""
        tools = [
            {
                "type": "function",
                "name": "look_at_camera",
                "description": "Capture and analyze what's in front of the camera.",
                "parameters": {"type": "object", "properties": {}, "required": []}
            },
            {
                "type": "function",
                "name": "play_scary_music",
                "description": "Play Halloween background music through speakers.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "The exact filename of the music to play"
                        }
                    },
                    "required": ["filename"]
                }
            },
            {
                "type": "function",
                "name": "stop_music",
                "description": "Stop the currently playing background music.",
                "parameters": {"type": "object", "properties": {}, "required": []}
            }
        ]

        session_update = {
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "instructions": self.system_prompt,
                "voice": "alloy",
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "tools": tools,
                "tool_choice": "auto",
                "input_audio_transcription": {"model": "whisper-1"},
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 500,
                    "create_response": True
                }
            }
        }
        await self.websocket.send(json.dumps(session_update))

    async def send_audio(self):
        """Send audio from ESP32 MQTT buffer to OpenAI"""
        print("🎤 Listening for audio from ESP32...")

        try:
            while True:
                # Check if there's audio in buffer
                if len(self.audio_input_buffer) > 0:
                    esp32_audio = self.audio_input_buffer.popleft()

                    # Convert ESP32 audio (16kHz stereo 32-bit) to OpenAI format (24kHz mono 16-bit)
                    openai_audio = self.convert_esp32_to_openai(esp32_audio)

                    audio_b64 = base64.b64encode(openai_audio).decode('utf-8')

                    message = {
                        "type": "input_audio_buffer.append",
                        "audio": audio_b64
                    }
                    await self.websocket.send(json.dumps(message))

                await asyncio.sleep(0.01)

        except asyncio.CancelledError:
            raise

    async def receive_messages(self):
        """Receive and process messages from the API"""
        is_responding = False
        audio_queue = asyncio.Queue()
        audio_generation_done = False

        async def play_audio():
            """Send audio to ESP32 via MQTT in 640-byte frames"""
            smoothed_jaw = 0.0
            smoothing_factor = 0.6
            audio_buffer = b''

            while True:
                try:
                    audio_data = await audio_queue.get()
                    if audio_data is None:
                        break

                    # Convert OpenAI audio (24kHz mono 16-bit) to ESP32 format (16kHz mono 16-bit)
                    esp32_audio = self.convert_openai_to_esp32(audio_data)

                    # Add to buffer
                    audio_buffer += esp32_audio

                    # Send complete 640-byte frames to ESP32
                    while len(audio_buffer) >= self.FRAME_BYTES:
                        frame = audio_buffer[:self.FRAME_BYTES]
                        audio_buffer = audio_buffer[self.FRAME_BYTES:]

                        # Calculate jaw position (for future use)
                        # audio_array = np.frombuffer(frame, dtype=np.int16)
                        # amplitude = np.abs(audio_array).mean()
                        # target_jaw_open = min(1.0, amplitude / 5000.0)
                        # smoothed_jaw = smoothed_jaw * (1 - smoothing_factor) + target_jaw_open * smoothing_factor
                        # self.mqtt_client.publish(self.jaw_topic, str(smoothed_jaw))

                        # Send exact 640-byte frame to ESP32
                        self.mqtt_client.publish(self.audio_output_topic, frame)

                except Exception as e:
                    print(f"Error playing audio: {e}")

        # Start audio playback task
        playback_task = asyncio.create_task(play_audio())

        try:
            async for message in self.websocket:
                event = json.loads(message)
                event_type = event.get("type")

                # Log important events
                if event_type in ["session.created", "session.updated", "error"]:
                    print(f"🔍 Event: {event_type}")

                if event_type == "session.created":
                    print("✅ Session created")

                elif event_type == "session.updated":
                    print("✅ Session configured")

                elif event_type == "input_audio_buffer.speech_started":
                    if is_responding:
                        print("🚨 INTERRUPTION detected!")
                        while not audio_queue.empty():
                            try:
                                audio_queue.get_nowait()
                            except asyncio.QueueEmpty:
                                break
                        cancel_msg = {"type": "response.cancel"}
                        await self.websocket.send(json.dumps(cancel_msg))
                        is_responding = False
                    else:
                        print("🗣️  Speech detected...")

                elif event_type == "input_audio_buffer.speech_stopped":
                    print("⏸️  Speech ended, processing...")

                elif event_type == "response.created":
                    is_responding = True
                    audio_generation_done = False
                    print("🤖 Response started")

                elif event_type == "response.audio.delta":
                    audio_b64 = event.get("delta", "")
                    if audio_b64:
                        if self.music_playing and pygame.mixer.music.get_volume() > self.music_volume_ducked:
                            pygame.mixer.music.set_volume(self.music_volume_ducked)
                            print("🔉 Music ducked")

                        audio_chunk = base64.b64decode(audio_b64)
                        await audio_queue.put(audio_chunk)

                elif event_type == "response.audio.done":
                    print("🎵 Audio generation done")
                    audio_generation_done = True
                    if self.music_playing:
                        pygame.mixer.music.set_volume(self.music_volume_normal)
                        print("🔊 Music restored")

                elif event_type == "response.done":
                    is_responding = False
                    print("✅ Response done")

                elif event_type == "response.cancelled":
                    is_responding = False
                    print("❌ Response cancelled")
                    if self.music_playing:
                        pygame.mixer.music.set_volume(self.music_volume_normal)

                elif event_type == "conversation.item.input_audio_transcription.completed":
                    transcript = event.get("transcript", "")
                    print(f"📝 You: {transcript}")

                elif event_type == "response.function_call_arguments.done":
                    call_id = event.get("call_id")
                    function_name = event.get("name")

                    if function_name == "look_at_camera":
                        print("📸 Taking photo...")
                        img_base64 = await self.capture_frame()

                        if img_base64:
                            output = f"data:image/jpeg;base64,{img_base64}"
                        else:
                            output = "ERROR: Could not capture camera frame"
                            print("❌ Camera capture failed")

                        function_output = {
                            "type": "conversation.item.create",
                            "item": {
                                "type": "function_call_output",
                                "call_id": call_id,
                                "output": output
                            }
                        }
                        await self.websocket.send(json.dumps(function_output))
                        response_create = {"type": "response.create"}
                        await self.websocket.send(json.dumps(response_create))

                    elif function_name == "stop_music":
                        print("🔇 Stopping music...")
                        if self.music_playing:
                            pygame.mixer.music.stop()
                            self.music_playing = False
                            output = "Music stopped"
                        else:
                            output = "No music is currently playing"

                        function_output = {
                            "type": "conversation.item.create",
                            "item": {
                                "type": "function_call_output",
                                "call_id": call_id,
                                "output": output
                            }
                        }
                        await self.websocket.send(json.dumps(function_output))
                        response_create = {"type": "response.create"}
                        await self.websocket.send(json.dumps(response_create))

                    elif function_name == "play_scary_music":
                        args_json = event.get("arguments", "{}")
                        try:
                            args = json.loads(args_json)
                            filename = args.get("filename", "")
                            print(f"🎵 Playing music: {filename}")

                            filepath = os.path.join(self.sounds_dir, filename)
                            if os.path.exists(filepath):
                                pygame.mixer.music.load(filepath)
                                pygame.mixer.music.play(-1)
                                self.music_playing = True
                                output = f"Started playing {filename}"
                            else:
                                output = f"ERROR: File {filename} not found"
                                print(f"❌ {output}")
                        except Exception as e:
                            output = f"ERROR: {str(e)}"
                            print(f"❌ Error playing music: {e}")

                        function_output = {
                            "type": "conversation.item.create",
                            "item": {
                                "type": "function_call_output",
                                "call_id": call_id,
                                "output": output
                            }
                        }
                        await self.websocket.send(json.dumps(function_output))
                        response_create = {"type": "response.create"}
                        await self.websocket.send(json.dumps(response_create))

                elif event_type == "response.audio_transcript.done":
                    transcript = event.get("transcript", "")
                    print(f"\n💬 Franky: {transcript}")

                elif event_type == "error":
                    error = event.get("error", {})
                    print(f"❌ Error: {error}")

        except asyncio.CancelledError:
            await audio_queue.put(None)
            await playback_task
            raise

    async def run(self):
        """Main bot loop"""
        # Connect to MQTT
        print("🔌 Connecting to MQTT broker...")
        self.mqtt_client.connect(self.mqtt_broker, self.mqtt_port, 60)
        self.mqtt_client.loop_start()
        print("✅ Connected to MQTT")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "OpenAI-Beta": "realtime=v1"
        }

        print("🚀 Starting Franky Voice Bot (ESP32 Edition)...")
        print(f"📹 Camera: {self.camera_url}")
        print(f"🎤 ESP32 MQTT: {self.mqtt_broker}:{self.mqtt_port}")
        print("Press Ctrl+C to exit\n")

        try:
            async with connect(self.url, additional_headers=headers) as ws:
                self.websocket = ws
                await self.setup_session()
                await asyncio.sleep(0.5)

                send_task = asyncio.create_task(self.send_audio())
                receive_task = asyncio.create_task(self.receive_messages())

                await asyncio.gather(send_task, receive_task)

        except KeyboardInterrupt:
            print("\n👋 Shutting down gracefully...")
        finally:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            if self.camera:
                self.camera.release()
            if self.music_playing:
                pygame.mixer.music.stop()
            print("✅ Cleanup complete")

if __name__ == "__main__":
    bot = RealtimeVoiceBotESP32()
    asyncio.run(bot.run())