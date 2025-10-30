#!/usr/bin/env python3
"""
Franky Voice Bot - ESP32 UDP Edition
Uses ESP32 via UDP for audio streaming, MQTT only for control
"""

import os
import asyncio
import json
import base64
import random
import numpy as np
import struct
import socket
import argparse
from datetime import datetime
from websockets import connect
from dotenv import load_dotenv
import pygame
from collections import deque
from scipy import signal

try:
    from pedalboard import Pedalboard, Reverb, Chorus, PitchShift, Distortion, Phaser
    PEDALBOARD_AVAILABLE = True
except ImportError:
    PEDALBOARD_AVAILABLE = False
    print("⚠️  Pedalboard not installed. Audio effects disabled. Install with: pip install pedalboard")

load_dotenv()

class RealtimeVoiceBotUDP:
    def __init__(self, voice="alloy", audio_effects=None, output_mode="esp32_udp",
                 enable_camera=True, enable_mqtt=True, enable_jaw=True, enable_eyes=True,
                 esp32_ip_override=None, mqtt_server_override=None, mqtt_port_override=None,
                 log_conversation=False):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.voice = voice
        self.url = "wss://api.openai.com/v1/realtime?model=gpt-realtime-2025-08-28"

        # Feature toggles
        self.output_mode = output_mode  # "esp32_udp" or "speakers"
        self.enable_camera = enable_camera
        self.enable_mqtt = enable_mqtt
        self.enable_jaw = enable_jaw and enable_mqtt  # Jaw requires MQTT
        self.enable_eyes = enable_eyes and enable_mqtt  # Eyes require MQTT
        self.log_conversation = log_conversation

        # Camera setup (only if enabled)
        self.camera_url = os.getenv("CAMERA_RTSP_STREAM") if enable_camera else None
        if not enable_camera:
            self.camera_url = None

        # Audio effects setup
        self.audio_effects_enabled = audio_effects and PEDALBOARD_AVAILABLE
        if self.audio_effects_enabled:
            effects = []
            if 'reverb' in audio_effects:
                effects.append(Reverb(room_size=0.5))
                print("🎛️  Added Reverb effect")
            if 'chorus' in audio_effects:
                effects.append(Chorus())
                print("🎛️  Added Chorus effect")
            if 'pitch' in audio_effects:
                # Lower pitch by 2 semitones for spooky effect
                effects.append(PitchShift(semitones=-2))
                print("🎛️  Added PitchShift effect (-2 semitones)")

            self.pedalboard = Pedalboard(effects) if effects else None
            if self.pedalboard:
                print(f"✅ Pedalboard initialized with {len(effects)} effects")
        else:
            self.pedalboard = None
            if audio_effects and not PEDALBOARD_AVAILABLE:
                print("⚠️  Audio effects requested but Pedalboard not available")

        # Audio settings
        self.ESP32_RATE = 16000   # ESP32 sample rate
        self.ESP32_CHANNELS_RX = 1   # ESP32 sends mono (LEFT=AEC-processed, 16-bit)
        self.ESP32_CHANNELS_TX = 1   # ESP32 receives mono (speaker)
        self.ESP32_BITS_RX = 16   # ESP32 sends 16-bit
        self.ESP32_BITS_TX = 16   # ESP32 receives 16-bit
        self.OPENAI_RATE = 24000  # OpenAI Realtime API uses 24kHz

        # ESP32 uses 40ms frames (mic TX and speaker RX)
        self.FRAME_MS_RX = 40  # ESP32 sends 40ms mic frames
        self.FRAME_MS_TX = 40  # ESP32 expects 40ms speaker frames
        self.FRAME_SAMPLES_RX = (self.ESP32_RATE * self.FRAME_MS_RX) // 1000  # 640 samples (40ms)
        self.FRAME_SAMPLES_TX = (self.ESP32_RATE * self.FRAME_MS_TX) // 1000  # 640 samples (40ms)
        self.FRAME_BYTES_RX = self.FRAME_SAMPLES_RX * (self.ESP32_BITS_RX // 8) * self.ESP32_CHANNELS_RX  # 1280 bytes mono 16-bit (receive from ESP32)
        self.FRAME_BYTES_TX = self.FRAME_SAMPLES_TX * (self.ESP32_BITS_TX // 8) * self.ESP32_CHANNELS_TX  # 1280 bytes mono 16-bit (send to ESP32)

        # UDP packet header structure (16 bytes total)
        # struct UdpPacketHeader {
        #   uint8_t type;           // 1 byte
        #   uint8_t flags;          // 1 byte
        #   uint16_t payload_len;   // 2 bytes
        #   uint32_t ssrc;          // 4 bytes
        #   uint32_t timestamp;     // 4 bytes
        #   uint32_t sequence;      // 4 bytes
        # };
        self.HEADER_FORMAT = '<BBHIII'  # little-endian: byte, byte, short, int, int, int
        self.HEADER_SIZE = 16  # 1+1+2+4+4+4 = 16 bytes

        self.websocket = None
        self.camera = None
        self.last_camera_capture = 0  # Timestamp of last camera capture

        # Create logs directory
        self.logs_dir = "logs"
        os.makedirs(self.logs_dir, exist_ok=True)

        # Conversation logging setup
        if self.log_conversation:
            self.conversation_logs_dir = "conversation_logs"
            os.makedirs(self.conversation_logs_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            self.conversation_log_file = os.path.join(self.conversation_logs_dir, f"conversation_{timestamp}.json")
            self.conversation_log = []
            print(f"📝 Conversation logging enabled: {self.conversation_log_file}")

        # Audio I/O setup based on output mode
        if self.output_mode == "esp32_udp":
            # UDP setup for ESP32 audio
            self.udp_receive_port = 5001  # Receive mic audio from ESP32
            self.udp_send_port = 5002     # Send speaker audio to ESP32
            self.esp32_ip = esp32_ip_override or os.getenv("ESP32_IP", "192.168.2.xxx")  # Will be auto-detected

            self.udp_rx_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_rx_socket.bind(('0.0.0.0', self.udp_receive_port))
            self.udp_rx_socket.setblocking(False)

            self.udp_tx_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

            # Packet tracking
            self.tx_sequence = 0
            self.ssrc = 0xFAAC01

            self.pyaudio_instance = None
            self.output_stream = None
            self.input_stream = None
        elif self.output_mode == "speakers":
            # PyAudio setup for local speakers
            try:
                import pyaudio
                self.pyaudio_instance = pyaudio.PyAudio()
                self.output_stream = None  # Will be created in run()
                self.input_stream = None   # Will be created in run()

                # Audio settings for speaker mode (OpenAI uses 24kHz)
                self.SPEAKER_CHUNK = 1024
                self.SPEAKER_FORMAT = None  # Will be set to pyaudio.paInt16
                self.SPEAKER_CHANNELS = 1
                self.SPEAKER_RATE = 24000  # Native OpenAI rate

                print("🔊 Using local speakers for audio output")
            except ImportError:
                print("❌ PyAudio not installed. Install with: pip install pyaudio")
                raise ImportError("PyAudio is required for speaker mode. Install with: pip install pyaudio")

        # MQTT setup for control only (jaw movement, eyes)
        self.mqtt_client = None
        if self.enable_mqtt:
            try:
                import paho.mqtt.client as mqtt
                self.mqtt_broker = mqtt_server_override or os.getenv("MQTT_SERVER", "192.168.2.243")
                self.mqtt_port = mqtt_port_override or int(os.getenv("MQTT_PORT", "1883"))
                self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
                self.mqtt_client.on_connect = self.on_mqtt_connect
                self.mqtt_client.on_message = self.on_mqtt_message

                self.jaw_topic = "franky/jaw"
                self.eyes_topic = "franky/eyes"
                self.volume_topic = "franky/volume"
            except ImportError:
                print("⚠️  paho-mqtt not installed. Install with: pip install paho-mqtt")
                print("⚠️  MQTT disabled - jaw and eyes control unavailable")
                self.enable_mqtt = False
                self.enable_jaw = False
                self.enable_eyes = False
        else:
            print("⚠️  MQTT disabled - jaw and eyes control unavailable")

        # Output volume control (0.0 to 1.0)
        self.output_volume = 0.2  # Start at 20%

        # Audio buffers - увеличен для плавного приема
        self.audio_input_buffer = deque(maxlen=200)
        self.playback_buffer = deque()  # Buffer for smooth playback (no hard limit)
        self.max_buffer_size = 1000  # Soft limit: 20 seconds max

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
        music_list = "\n".join([f"- {filename}" for filename in sorted(self.available_sounds)]) if self.available_sounds else "(No music files found in sounds/ folder)"

        # Current voice
        self.current_voice = "alloy"

        # Build interaction start instructions based on camera availability
        if self.enable_camera:
            interaction_start = """## Start of Each Interaction (strict sequence)
1. FIRST call **look_at_camera** tool, THEN speak.
2. Brief intro: "I'm Franky, the talking skull!" (in guest's language).
3. Ask for name and **STOP**. Wait for answer, don't invent.
4. After answer: "Oh, [name]! That sounds truly spooky/cool!"
5. Offer treat:
   - RU: "Я приготовила для вас угощения… хотите?"
   - EN: "I cooked up some treats… want one?"
   - ES: "He preparado dulces… ¿quieren?"
6. Invite: "Come inside, let's have fun!" (in guest's language).
7. Proceed to **ONE** short bit (joke/mini-game/riddle), ≤ 15-20 sec."""
        else:
            interaction_start = """## Start of Each Interaction (strict sequence)
1. Brief intro: "I'm Franky, the talking skull!" (in guest's language).
2. Ask for name and **STOP**. Wait for answer, don't invent.
3. After answer: "Oh, [name]! That sounds truly spooky/cool!"
4. Offer treat:
   - RU: "Я приготовила для вас угощения… хотите?"
   - EN: "I cooked up some treats… want one?"
   - ES: "He preparado dulces… ¿quieren?"
5. Invite: "Come inside, let's have fun!" (in guest's language).
6. Proceed to **ONE** short bit (joke/mini-game/riddle), ≤ 15-20 sec."""

        # System prompt
        self.system_prompt = f"""
## Who You Are
You are Franky, a talking Halloween skull. Friendly, funny, with a playful "spooky" twist. Your goal is to lightly scare, amuse, and engage guests in short interactions. Keep responses SHORT by default (~1-2 sentences), but continue if guests are clearly interested.

## Multilingual (REQUIRED)
- **Auto-mirror** the guest's language from their speech. If unsure, greet briefly in English and ask which language they prefer.
- Use **call-and-response** phrases so guests can **finish** them (language-specific examples below).
- Split into simple sentences and speak slightly slower if language switches.
- ⚠️ **NEVER translate jokes from one language to another!** Jokes don't work when translated. If guest speaks Russian, tell RUSSIAN jokes. If English, tell ENGLISH jokes. Create NEW jokes in guest's language, don't translate!

{interaction_start}

## Interaction Rotation (randomness and variety)
Each time choose a **different** type of bit, don't repeat consecutively:
- Joke/pun (skeleton/Halloween themed).
- Light scare "BOO!" with immediate friendly recovery.
- Kids riddle.
- Mini-game (below).
- Costume compliment (general if unsure of details).

## "Skull Starts — Guests Finish" (language-specific)
**Russian (RU)**
- "Сладость или…" → "гадость!"
- "Абра-ка…" → "дабра!"
- "Счастливого Хэлло…" → "уина!"
- "Тук-тук!" → "Кто там?" → "Череп!" → "Череп кто?" → "Череп, который пугает — БУ!"

**English (EN)**
- "Trick or…" → "treat!"
- "Abra-ca…" → "dabra!"
- "Happy Hallow…" → "ween!"
- "Knock, knock!" → "Who's there?" → "Skull!" → "Skull who?" → "Skull that scares you—BOO!"

**Spanish (ES)**
- "Truco o…" → "trato!"
- "A la de una, a la de dos… a la de…" → "¡tres!"
- "Feliz Hallo…" → "ween!"

If guests are small kids, give hint: "Let's say together: Trick or… (pause)".

## Mini-Games (20-60 sec)
- **"Treat or Spell?"**
  Ask for "password": RU "Сладость или гадость!", EN "Trick or treat!", ES "¡Truco o trato!". Joyfully "unlock" treat.
- **"Repeat After the Ghost"**
  Make sounds and ask to repeat: ghost "ooooo", witch "hee-hee-hee", monster "grr-arr". Praise attempts.

## Response Categories (use one at a time)
- **Greetings:** RU: "Добро пожаловать, смельчаки!" / EN: "Welcome, brave souls!"
- **Light Teasing:** RU: "Кто здесь самый страшный?.. ой, это же я!" / EN: "Who's the scariest here… oh wait, it's me!"
- **Questions:** RU: "Вы за ведьм или за вампиров?" / EN: "Team vampires or team werewolves?"
- **Jokes:** RU: "Почему скелеты не дерутся? У них нет кишок!" / EN: "Why don't skeletons fight? They don't have the guts!"
- **Compliments:** RU: "Классный костюм!" / EN: "Awesome costume!" (general if costume unclear)
- **Farewell:** RU: "Страшно весёлой ночи!" / EN: "Have a spooky night!"

## Voice Acting (via set_audio_effects)
- Monsters/demons: pitch DOWN + reverb (maybe light distortion).
- Witches/small creatures: pitch UP, maybe chorus.
- Ghost: reverb.
- Scare scene: "BOO!" with heavy distortion + pitch DOWN **only for that word**, then immediately return normal.
- **Sharp changes:** allowed for short phrases, then return neutral.

## Pauses and Sound
- Keep 0.5-1.0s pauses before punchline/"BOO!" for suspense.
- If **play_sfx** available: can request "creak", "owl", "witch_laugh". If not — imitate with voice.

## Length and Rhythm
- Short by default. If guests linger — offer **one more** bit from different category.
- Don't spam: 1 activity → guest reaction → different activity.

## Safety
- No gore, threats, toxicity. Light scares immediately diffused with joke.
- Be friendly and inclusive.

## If You Didn't Hear
RU: "Ой, мои косточки скрипят — повторите, пожалуйста?"
EN: "Pardon my rattling bones—could you say that again?"

# Available Music Files
{music_list}"""

        # Add Vision section only if camera is enabled
        if self.enable_camera:
            self.system_prompt += """

## Vision and Realism (CRITICAL)
⚠️ DO NOT HALLUCINATE! ⚠️

1. FIRST **look_at_camera**, describe only what you ACTUALLY SEE.
2. If unsure — be vague: "Looks like we have guests!"
3. DON'T invent colors, age, costumes. Can joke: "My skeleton eyes don't see too clearly!"
4. Better vague than wrong."""

        # Build tools list based on enabled features
        self.tools = []

        # Add camera tool only if enabled
        if self.enable_camera:
            self.tools.append({
                "type": "function",
                "name": "look_at_camera",
                "description": "Captures current camera view to see who's at the door. Use this at the START of every new conversation BEFORE greeting.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            })

        # Audio effects (always available)
        self.tools.append({
                "type": "function",
                "name": "set_audio_effects",
                "description": "Changes voice audio effects for spooky atmosphere and voice acting. Available effects: reverb (cave echo), pitch (change voice pitch), chorus (richer voice), distortion (harsh/demonic), phaser (alien/cosmic). Can enable multiple effects at once with adjustable intensity.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "effects": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": ["reverb", "pitch", "chorus", "distortion", "phaser"]
                            },
                            "description": "List of effects to enable. Empty array disables all effects."
                        },
                        "intensity": {
                            "type": "string",
                            "enum": ["light", "medium", "heavy"],
                            "description": "Intensity level for effects: light (subtle), medium (moderate), heavy (extreme). Default: medium."
                        },
                        "pitch_direction": {
                            "type": "string",
                            "enum": ["down", "up"],
                            "description": "Direction of pitch shift: 'down' for lower/deeper voice (monsters, demons), 'up' for higher voice (children, small creatures). Only used when 'pitch' effect is enabled. Default: down."
                        }
                    },
                    "required": ["effects"]
                }
            })

        # Music playback (always available)
        self.tools.append({
                "type": "function",
                "name": "play_scary_music",
                "description": "Plays Halloween background music. Choose from the available music files list.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": f"Name of the music file to play. Must be one of: {', '.join(sorted(self.available_sounds)) if self.available_sounds else 'No music files available'}"
                        }
                    },
                    "required": ["filename"]
                }
            })

        self.tools.append({
                "type": "function",
                "name": "stop_music",
                "description": "Stops the currently playing background music",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            })

    def on_mqtt_connect(self, client, userdata, flags, reason_code, properties):
        """MQTT connection callback - only for control"""
        if reason_code == 0:
            print(f"✅ MQTT connected (control only)")
            # Subscribe to volume control topic
            client.subscribe(self.volume_topic)
            print(f"📢 Subscribed to {self.volume_topic} for volume control")
            print(f"🔊 Current output volume: {self.output_volume * 100:.0f}%")
        else:
            print(f"❌ MQTT connection failed: {reason_code}")

    def on_mqtt_message(self, client, userdata, msg):
        """MQTT message callback for volume control"""
        if msg.topic == self.volume_topic:
            try:
                value = float(msg.payload.decode('utf-8'))
                # Clamp between 0.0 and 1.0
                self.output_volume = max(0.0, min(1.0, value))
                print(f"🔊 Output volume set to {self.output_volume * 100:.0f}%")

                # Forward volume command to ESP32 via MQTT
                # ESP32 will control its amplifier directly
                client.publish("esp32/volume", str(self.output_volume))
            except ValueError:
                print(f"⚠️  Invalid volume value: {msg.payload.decode('utf-8')}")

    def send_udp_packet(self, audio_data):
        """Send audio packet to ESP32 via UDP with header"""
        if not self.esp32_ip or self.esp32_ip == "192.168.2.xxx":
            return  # ESP32 IP not yet detected

        # Build header
        header = struct.pack(
            self.HEADER_FORMAT,
            0x01,                    # type: audio packet
            0x00,                    # flags
            len(audio_data),         # payload_len
            self.ssrc,               # ssrc
            int(asyncio.get_event_loop().time() * 1000) & 0xFFFFFFFF,  # timestamp
            self.tx_sequence         # sequence
        )

        self.tx_sequence = (self.tx_sequence + 1) & 0xFFFFFFFF

        # Send packet
        packet = header + audio_data
        self.udp_tx_socket.sendto(packet, (self.esp32_ip, self.udp_send_port))

    async def receive_udp_audio(self):
        """Receive audio from ESP32 via UDP"""
        loop = asyncio.get_event_loop()
        packet_count = 0

        while True:
            try:
                data, addr = await loop.sock_recvfrom(self.udp_rx_socket, 4096)

                # Auto-detect ESP32 IP from first packet
                if not self.esp32_ip or self.esp32_ip == "192.168.2.xxx":
                    self.esp32_ip = addr[0]
                    print(f"🎯 ESP32 detected at {self.esp32_ip}")

                # Parse packet
                if len(data) < self.HEADER_SIZE:
                    print(f"⚠️  Packet too small: {len(data)} bytes")
                    continue

                header = struct.unpack(self.HEADER_FORMAT, data[:self.HEADER_SIZE])
                packet_type, flags, payload_len, ssrc, timestamp, sequence = header

                # Debug first 10 packets
                if packet_count < 10:
                    print(f"📦 RX packet #{packet_count}: type={packet_type:02x}, len={payload_len}, seq={sequence}")
                    packet_count += 1

                # Validate
                if packet_type != 0x01:
                    print(f"⚠️  Wrong packet type: {packet_type:02x}")
                    continue

                if payload_len != self.FRAME_BYTES_RX:
                    print(f"⚠️  Wrong payload length: {payload_len} (expected {self.FRAME_BYTES_RX})")
                    continue

                # Extract audio payload (16-bit mono from ESP32, LEFT channel = AEC-processed)
                audio_data = data[self.HEADER_SIZE:self.HEADER_SIZE + payload_len]

                if len(audio_data) == self.FRAME_BYTES_RX:
                    # Already 16-bit mono, no conversion needed
                    self.audio_input_buffer.append(audio_data)

            except BlockingIOError:
                await asyncio.sleep(0.001)
            except Exception as e:
                print(f"❌ UDP RX error: {e}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(0.01)

    async def receive_speaker_audio(self):
        """Receive audio from local microphone via PyAudio"""
        import pyaudio

        # Get default input device info
        default_input = self.pyaudio_instance.get_default_input_device_info()
        mic_name = default_input.get('name', 'Unknown')
        print(f"🎤 Using microphone: {mic_name}")

        stream = self.pyaudio_instance.open(
            format=pyaudio.paInt16,
            channels=self.SPEAKER_CHANNELS,
            rate=self.SPEAKER_RATE,
            input=True,
            frames_per_buffer=self.SPEAKER_CHUNK
        )

        print("🎤 Listening... (speak naturally)")

        try:
            while True:
                data = await asyncio.to_thread(stream.read, self.SPEAKER_CHUNK, exception_on_overflow=False)
                self.audio_input_buffer.append(data)
                await asyncio.sleep(0.001)
        except asyncio.CancelledError:
            stream.stop_stream()
            stream.close()
            raise
        except Exception as e:
            print(f"❌ Microphone error: {e}")
            stream.stop_stream()
            stream.close()

    async def send_audio_to_speakers(self):
        """Send buffered audio to local speakers with jaw control"""
        import pyaudio

        print("🔊 Starting audio playback (speakers)")

        # Initialize output stream
        self.output_stream = self.pyaudio_instance.open(
            format=pyaudio.paInt16,
            channels=self.SPEAKER_CHANNELS,
            rate=self.SPEAKER_RATE,
            output=True,
            stream_callback=None  # Non-blocking writes
        )

        frames_sent = 0
        jaw_frame_counter = 0
        smoothed_jaw = 0.0
        smoothing_factor = 0.6

        try:
            while True:
                if len(self.playback_buffer) > 0:
                    chunk = self.playback_buffer.popleft()

                    # Write audio to speakers
                    await asyncio.to_thread(self.output_stream.write, chunk)
                    frames_sent += 1

                    # Move jaw synchronized with playback (if enabled)
                    if self.enable_jaw:
                        jaw_frame_counter += 1
                        if jaw_frame_counter % 3 == 0:  # Every 3rd frame for responsiveness
                            # Calculate jaw position based on audio amplitude
                            audio_array = np.frombuffer(chunk, dtype=np.int16)
                            amplitude = np.abs(audio_array).mean()
                            target_jaw_open = min(1.0, amplitude / 5000.0)

                            # Apply exponential smoothing
                            smoothed_jaw = smoothed_jaw * (1 - smoothing_factor) + target_jaw_open * smoothing_factor

                            # Send smoothed jaw position via MQTT
                            if self.mqtt_client:
                                self.mqtt_client.publish(self.jaw_topic, str(smoothed_jaw))

                    if frames_sent % 50 == 0:  # Log every 50 frames
                        print(f"📤 Sent {frames_sent} frames, buffer: {len(self.playback_buffer)}")
                else:
                    # Buffer empty - close jaw and wait
                    if self.enable_jaw and self.mqtt_client and smoothed_jaw > 0:
                        self.mqtt_client.publish(self.jaw_topic, "0.0")
                        smoothed_jaw = 0.0
                    await asyncio.sleep(0.01)
        except asyncio.CancelledError:
            if self.output_stream:
                self.output_stream.stop_stream()
                self.output_stream.close()
            raise
        except Exception as e:
            print(f"❌ Speaker playback error: {e}")
            if self.output_stream:
                self.output_stream.stop_stream()
                self.output_stream.close()

    def look_at_camera(self):
        """Capture frame from camera and return base64 image"""
        import time

        # Check if camera is enabled
        if not self.enable_camera:
            print("📸 Camera disabled (use --enable-camera to enable)")
            return None

        # Import cv2 only when camera is needed
        try:
            import cv2
        except ImportError:
            print("❌ OpenCV not installed. Install with: pip install opencv-python")
            return None

        start_total = time.time()

        # Rate limit: only capture once every 3 seconds
        current_time = time.time()
        if current_time - self.last_camera_capture < 3.0:
            print(f"📸 Camera rate limited (last capture {current_time - self.last_camera_capture:.1f}s ago)")
            return None

        if not self.camera_url:
            print("❌ Camera not configured (set CAMERA_RTSP_STREAM in .env)")
            return None

        print("📷 [1/6] Starting camera capture...")

        # Always reconnect to get fresh frame from RTSP
        if self.camera:
            self.camera.release()

        start_connect = time.time()
        self.camera = cv2.VideoCapture(self.camera_url, cv2.CAP_FFMPEG)
        if not self.camera.isOpened():
            print("❌ Failed to open camera")
            return None
        connect_time = time.time() - start_connect
        print(f"📷 [2/6] Camera opened: {connect_time:.2f}s")

        # Set timeout for RTSP stream
        self.camera.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 10000)
        self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        start_read = time.time()
        ret, frame = self.camera.read()
        if not ret:
            print("❌ Failed to capture frame")
            return None
        read_time = time.time() - start_read
        print(f"📷 [3/6] Frame captured: {read_time:.2f}s")

        # Get original resolution
        height, width = frame.shape[:2]

        # Generate timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save original to logs
        start_save = time.time()
        log_path_orig = os.path.join(self.logs_dir, f"camera_{timestamp}_original.jpg")
        cv2.imwrite(log_path_orig, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
        save_time = time.time() - start_save
        print(f"📷 [4/6] Saved original ({width}x{height}): {save_time:.2f}s")

        # Resize to 1280px for API
        start_resize = time.time()
        max_width = 1280
        if width > max_width:
            ratio = max_width / width
            new_width = max_width
            new_height = int(height * ratio)
            frame_for_api = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_LANCZOS4)
        else:
            frame_for_api = frame
        resize_time = time.time() - start_resize
        print(f"📷 [5/6] Resized: {resize_time:.2f}s")

        # Save API version and convert to base64
        start_encode = time.time()
        log_path_api = os.path.join(self.logs_dir, f"camera_{timestamp}_sent.jpg")
        cv2.imwrite(log_path_api, frame_for_api, [cv2.IMWRITE_JPEG_QUALITY, 85])

        # Convert to base64
        _, buffer = cv2.imencode('.jpg', frame_for_api, [cv2.IMWRITE_JPEG_QUALITY, 85])
        image_base64 = base64.b64encode(buffer).decode('utf-8')
        encode_time = time.time() - start_encode
        print(f"📷 [6/6] Encoded to base64: {encode_time:.2f}s")

        total_time = time.time() - start_total
        print(f"📷 ✅ Total camera capture time: {total_time:.2f}s")

        self.last_camera_capture = current_time

        return image_base64

    def _save_conversation_log(self):
        """Save conversation log to JSON file"""
        if not self.log_conversation:
            return

        try:
            with open(self.conversation_log_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "session_start": self.conversation_log[0]["timestamp"] if self.conversation_log else None,
                    "total_messages": len(self.conversation_log),
                    "messages": self.conversation_log
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️  Failed to save conversation log: {e}")

    def set_audio_effects(self, effects, intensity="medium", pitch_direction="down"):
        """Enable or disable audio effects dynamically with adjustable intensity and pitch direction"""
        if not PEDALBOARD_AVAILABLE:
            return {"error": "Pedalboard not installed"}

        # Intensity multipliers
        intensity_map = {
            "light": 0.5,
            "medium": 1.0,
            "heavy": 1.5
        }
        multiplier = intensity_map.get(intensity, 1.0)

        # Build new effects chain
        new_effects = []
        if 'reverb' in effects:
            room_size = min(0.3 + (0.4 * multiplier), 0.9)  # 0.3-0.9 range
            new_effects.append(Reverb(room_size=room_size))
            print(f"🎛️  Enabled Reverb effect (room_size={room_size:.2f}, {intensity})")
        if 'chorus' in effects:
            new_effects.append(Chorus())
            print(f"🎛️  Enabled Chorus effect ({intensity})")
        if 'pitch' in effects:
            # Calculate semitones based on direction and intensity
            if pitch_direction == "up":
                semitones = int(1 * multiplier + 1)  # light=+2, medium=+2, heavy=+3
            else:  # down
                semitones = int(-1 * multiplier - 1)  # light=-2, medium=-2, heavy=-3
            new_effects.append(PitchShift(semitones=semitones))
            direction_label = "↑" if pitch_direction == "up" else "↓"
            print(f"🎛️  Enabled PitchShift effect ({direction_label}{abs(semitones)} semitones, {intensity})")
        if 'distortion' in effects:
            drive = 10 * multiplier  # light=5dB, medium=10dB, heavy=15dB
            new_effects.append(Distortion(drive_db=drive))
            print(f"🎛️  Enabled Distortion effect ({drive:.0f}dB, {intensity})")
        if 'phaser' in effects:
            new_effects.append(Phaser())
            print(f"🎛️  Enabled Phaser effect ({intensity})")

        # Update pedalboard
        if new_effects:
            self.pedalboard = Pedalboard(new_effects)
            pitch_info = f" [{pitch_direction}]" if 'pitch' in effects else ""
            print(f"✅ Audio effects updated: {', '.join(effects)} [{intensity}]{pitch_info}")
            return {"status": "enabled", "effects": effects, "intensity": intensity, "pitch_direction": pitch_direction}
        else:
            self.pedalboard = None
            print("🔇 Audio effects disabled")
            return {"status": "disabled"}

    def play_scary_music(self, filename):
        """Play background music"""
        if filename not in self.available_sounds:
            return {"error": f"File {filename} not found"}

        filepath = os.path.join(self.sounds_dir, filename)
        try:
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.play(-1)  # Loop
            self.music_playing = True
            print(f"🎵 Playing: {filename}")
            return {"status": "playing", "file": filename}
        except Exception as e:
            return {"error": str(e)}

    def stop_music(self):
        """Stop background music"""
        pygame.mixer.music.stop()
        self.music_playing = False
        print("🔇 Music stopped")
        return {"status": "stopped"}

    async def handle_function_call(self, function_name, arguments):
        """Handle function calls from OpenAI"""
        print(f"🔧 Function call: {function_name}({arguments})")

        if function_name == "look_at_camera":
            return self.look_at_camera()
        elif function_name == "play_scary_music":
            return self.play_scary_music(arguments.get("filename"))
        elif function_name == "stop_music":
            return self.stop_music()

        return {"error": "Unknown function"}

    async def send_audio_to_openai(self):
        """Send audio from input (ESP32 or microphone) to OpenAI"""
        source = "Microphone" if self.output_mode == "speakers" else "ESP32"
        print(f"🎤 Starting audio send task ({source} → OpenAI)")

        while True:
            if self.audio_input_buffer and self.websocket:
                # Get audio chunk
                audio_chunk = self.audio_input_buffer.popleft()

                # Convert to int16 array
                audio_mono = np.frombuffer(audio_chunk, dtype=np.int16)

                # Resample if needed (ESP32 is 16kHz, speakers are already 24kHz)
                if self.output_mode == "esp32_udp":
                    # Resample from 16kHz to 24kHz for OpenAI
                    resampled = signal.resample(audio_mono, int(len(audio_mono) * self.OPENAI_RATE / self.ESP32_RATE))
                    audio_to_send = np.clip(resampled, -32768, 32767).astype(np.int16)
                else:  # speakers mode - already 24kHz
                    audio_to_send = audio_mono

                # Send to OpenAI
                audio_base64 = base64.b64encode(audio_to_send.tobytes()).decode('utf-8')
                await self.websocket.send(json.dumps({
                    "type": "input_audio_buffer.append",
                    "audio": audio_base64
                }))
            else:
                await asyncio.sleep(0.001)

    async def send_audio_to_esp32(self):
        """Send buffered audio to ESP32 with precise timing"""
        print("🔊 Starting audio send task (OpenAI → ESP32)")

        frames_sent = 0
        last_send_time = None
        jaw_frame_counter = 0

        while True:
            if len(self.playback_buffer) > 0:
                current_time = asyncio.get_event_loop().time()

                # Reset timing if buffer was empty (first frame or after gap)
                if last_send_time is None:
                    last_send_time = current_time
                    print(f"🎬 Starting playback stream, buffer: {len(self.playback_buffer)}")

                # Calculate timing
                expected_time = last_send_time + 0.040  # 40ms per frame
                time_until_next = expected_time - current_time

                if time_until_next > 0:
                    await asyncio.sleep(time_until_next)

                # Send frame
                chunk = self.playback_buffer.popleft()
                self.send_udp_packet(chunk)
                frames_sent += 1
                last_send_time = expected_time

                # Move jaw synchronized with actual playback (if enabled)
                if self.enable_jaw:
                    jaw_frame_counter += 1
                    if jaw_frame_counter % 6 == 0:  # Every 6th frame (240ms intervals) - reduced frequency
                        # Analyze audio amplitude from the chunk being played
                        audio_int16 = np.frombuffer(chunk, dtype=np.int16)
                        amplitude = np.abs(audio_int16).mean()

                        # Map amplitude to jaw pulse duration (20-150ms range)
                        if amplitude > 500:  # Only move jaw if there's significant audio
                            pulse_duration = int(np.clip(20 + (amplitude / 8000.0) * 130, 20, 150))
                            self.mqtt_client.publish(self.jaw_topic, str(pulse_duration))
                            if jaw_frame_counter % 24 == 0:  # Log occasionally
                                print(f"💀 Jaw pulse: {pulse_duration}ms (amp: {amplitude:.0f})")

                if frames_sent % 25 == 0:  # Every 25 frames = 1 second
                    print(f"📤 Sent {frames_sent} frames, buffer: {len(self.playback_buffer)}")
            else:
                # Buffer empty - reset timing for next stream
                if last_send_time is not None:
                    print(f"⏸️  Buffer empty, waiting for audio...")
                    last_send_time = None
                    jaw_frame_counter = 0
                await asyncio.sleep(0.005)  # Wait for buffer to fill

    async def receive_from_openai(self):
        """Receive messages from OpenAI and handle audio/events"""
        print("📥 Starting OpenAI receive task")

        accumulated_audio = bytearray()
        audio_chunks_received = 0

        async for message in self.websocket:
            try:
                msg = json.loads(message)
                msg_type = msg.get("type")

                # Audio from OpenAI
                if msg_type == "response.audio.delta":
                    audio_base64 = msg.get("delta", "")
                    audio_bytes = base64.b64decode(audio_base64)
                    audio_chunks_received += 1

                    audio_int16 = np.frombuffer(audio_bytes, dtype=np.int16)

                    # Resample and apply effects based on output mode
                    if self.output_mode == "esp32_udp":
                        # Convert from 24kHz to 16kHz for ESP32
                        resampled = signal.resample(audio_int16, int(len(audio_int16) * self.ESP32_RATE / self.OPENAI_RATE))
                        audio_processed = np.clip(resampled, -32768, 32767).astype(np.int16)

                        # Apply audio effects if enabled
                        if self.pedalboard and len(audio_processed) > 0:
                            audio_float = audio_processed.astype(np.float32) / 32768.0
                            audio_float = audio_float.reshape(1, -1)
                            processed = self.pedalboard(audio_float, self.ESP32_RATE)
                            audio_processed = np.clip(processed.flatten() * 32768.0, -32768, 32767).astype(np.int16)

                        accumulated_audio.extend(audio_processed.tobytes())

                        # Accumulate into ESP32 frame size (40ms chunks)
                        chunks_dropped = 0
                        while len(accumulated_audio) >= self.FRAME_BYTES_TX:
                            chunk = bytes(accumulated_audio[:self.FRAME_BYTES_TX])

                            if len(self.playback_buffer) < self.max_buffer_size:
                                self.playback_buffer.append(chunk)
                            else:
                                chunks_dropped += 1

                            accumulated_audio = accumulated_audio[self.FRAME_BYTES_TX:]

                        if chunks_dropped > 0:
                            print(f"⚠️  Dropped {chunks_dropped} frames (buffer full)")

                    else:  # speakers mode - no resampling needed, already 24kHz
                        audio_processed = audio_int16

                        # Apply audio effects if enabled
                        if self.pedalboard and len(audio_processed) > 0:
                            audio_float = audio_processed.astype(np.float32) / 32768.0
                            audio_float = audio_float.reshape(1, -1)
                            processed = self.pedalboard(audio_float, self.SPEAKER_RATE)
                            audio_processed = np.clip(processed.flatten() * 32768.0, -32768, 32767).astype(np.int16)

                        # Add directly to playback buffer (no frame segmentation needed)
                        if len(self.playback_buffer) < self.max_buffer_size:
                            self.playback_buffer.append(audio_processed.tobytes())
                        else:
                            print(f"⚠️  Dropped chunk (buffer full)")

                # Response done
                elif msg_type == "response.audio.done":
                    # Reset for next response
                    audio_chunks_received = 0
                    # Close jaw
                    # self.mqtt_client.publish(self.jaw_topic, "0.0")

                # Function call
                elif msg_type == "response.function_call_arguments.done":
                    call_id = msg.get("call_id")
                    function_name = msg.get("name")
                    arguments_str = msg.get("arguments", "{}")
                    arguments = json.loads(arguments_str)

                    if function_name == "look_at_camera":
                        print("📷 Looking at camera...")

                        # Capture frame
                        image_b64 = self.look_at_camera()

                        if image_b64:
                            print("👁️  Captured image, sending to model...")

                            # Complete the function call first
                            await self.websocket.send(json.dumps({
                                "type": "conversation.item.create",
                                "item": {
                                    "type": "function_call_output",
                                    "call_id": call_id,
                                    "output": "Camera image captured successfully"
                                }
                            }))

                            # Add image as a user message in conversation
                            await self.websocket.send(json.dumps({
                                "type": "conversation.item.create",
                                "item": {
                                    "type": "message",
                                    "role": "user",
                                    "content": [
                                        {
                                            "type": "input_image",
                                            "image_url": f"data:image/jpeg;base64,{image_b64}"
                                        }
                                    ]
                                }
                            }))

                            # Trigger response
                            await self.websocket.send(json.dumps({"type": "response.create"}))
                        else:
                            print("❌ Failed to capture frame")
                            await self.websocket.send(json.dumps({
                                "type": "conversation.item.create",
                                "item": {
                                    "type": "function_call_output",
                                    "call_id": call_id,
                                    "output": "ERROR: Failed to capture camera frame"
                                }
                            }))

                            # Trigger response
                            await self.websocket.send(json.dumps({"type": "response.create"}))

                    elif function_name == "set_audio_effects":
                        effects = arguments.get("effects", [])
                        intensity = arguments.get("intensity", "medium")
                        pitch_direction = arguments.get("pitch_direction", "down")
                        print(f"🎚️  set_audio_effects called: effects={effects}, intensity={intensity}, pitch_direction={pitch_direction}")
                        result = self.set_audio_effects(effects, intensity, pitch_direction)
                        await self.websocket.send(json.dumps({
                            "type": "conversation.item.create",
                            "item": {
                                "type": "function_call_output",
                                "call_id": call_id,
                                "output": json.dumps(result)
                            }
                        }))
                        await self.websocket.send(json.dumps({"type": "response.create"}))

                    elif function_name == "play_scary_music":
                        result = self.play_scary_music(arguments.get("filename"))
                        await self.websocket.send(json.dumps({
                            "type": "conversation.item.create",
                            "item": {
                                "type": "function_call_output",
                                "call_id": call_id,
                                "output": json.dumps(result)
                            }
                        }))
                        await self.websocket.send(json.dumps({"type": "response.create"}))

                    elif function_name == "stop_music":
                        result = self.stop_music()
                        await self.websocket.send(json.dumps({
                            "type": "conversation.item.create",
                            "item": {
                                "type": "function_call_output",
                                "call_id": call_id,
                                "output": json.dumps(result)
                            }
                        }))
                        await self.websocket.send(json.dumps({"type": "response.create"}))

                # Speech detected
                elif msg_type == "input_audio_buffer.speech_started":
                    print("👂 Speech detected")
                    # Duck music
                    if self.music_playing:
                        pygame.mixer.music.set_volume(self.music_volume_ducked)

                elif msg_type == "input_audio_buffer.speech_stopped":
                    print("🤫 Speech stopped")
                    # Restore music volume
                    if self.music_playing:
                        pygame.mixer.music.set_volume(self.music_volume_normal)

                # Transcription events (for logging)
                elif msg_type == "conversation.item.input_audio_transcription.completed":
                    transcript = msg.get("transcript", "")
                    if transcript and self.log_conversation:
                        log_entry = {
                            "timestamp": datetime.now().isoformat(),
                            "speaker": "User",
                            "text": transcript
                        }
                        self.conversation_log.append(log_entry)
                        self._save_conversation_log()
                        print(f"📝 Logged user: {transcript[:50]}...")

                elif msg_type == "response.audio_transcript.done":
                    transcript = msg.get("transcript", "")
                    if transcript and self.log_conversation:
                        log_entry = {
                            "timestamp": datetime.now().isoformat(),
                            "speaker": "Franky",
                            "text": transcript
                        }
                        self.conversation_log.append(log_entry)
                        self._save_conversation_log()
                        print(f"📝 Logged Franky: {transcript[:50]}...")

                # Errors
                elif msg_type == "error":
                    print(f"❌ Error from OpenAI: {msg}")

            except Exception as e:
                print(f"Error processing message: {e}")

    async def run(self):
        """Main run loop with auto-reconnect"""
        print("=" * 60)
        mode_title = "Speaker Mode" if self.output_mode == "speakers" else "ESP32 UDP Edition"
        print(f"🎃 Franky Voice Bot - {mode_title}")
        print("=" * 60)

        if self.output_mode == "esp32_udp":
            print(f"ESP32 IP: {self.esp32_ip}")
            print(f"UDP RX Port: {self.udp_receive_port} (listening for mic)")
            print(f"UDP TX Port: {self.udp_send_port} (sending to speaker)")
        else:  # speakers mode
            print(f"🎤 Input: Local microphone (24kHz)")
            print(f"🔊 Output: Local speakers (24kHz)")

        if self.enable_mqtt:
            print(f"MQTT Broker: {self.mqtt_broker}:{self.mqtt_port}")
        else:
            print("MQTT: Disabled")
        print(f"Camera: {self.camera_url if self.camera_url else 'Not configured'}")
        print(f"Music files: {len(self.available_sounds)}")
        print("=" * 60)

        # Connect to MQTT (control only) if enabled
        if self.enable_mqtt:
            try:
                self.mqtt_client.connect(self.mqtt_broker, self.mqtt_port, 60)
                self.mqtt_client.loop_start()
                print("✅ MQTT connected")
            except Exception as e:
                print(f"⚠️  MQTT connection failed: {e}")

        if self.output_mode == "esp32_udp":
            print(f"🎃 Waiting for ESP32 audio packets on UDP port {self.udp_receive_port}...")
        else:
            print(f"🎤 Ready to listen via local microphone...")

        # Auto-reconnect loop with exponential backoff
        reconnect_attempts = 0
        max_reconnect_delay = 60  # Max 60 seconds between retries

        while True:
            try:
                # Connect to OpenAI Realtime API
                if reconnect_attempts > 0:
                    # Calculate backoff delay: 2^attempts seconds (max 60s)
                    delay = min(2 ** reconnect_attempts, max_reconnect_delay)
                    print(f"🔄 Reconnecting to OpenAI (attempt #{reconnect_attempts + 1}, waiting {delay}s)...")
                    await asyncio.sleep(delay)

                print("📡 Connecting to OpenAI Realtime API...")
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "OpenAI-Beta": "realtime=v1"
                }

                async with connect(self.url, additional_headers=headers) as ws:
                    self.websocket = ws
                    print("✅ Connected to OpenAI Realtime API")
                    reconnect_attempts = 0  # Reset counter on successful connection

                    # Configure session
                    await ws.send(json.dumps({
                        "type": "session.update",
                        "session": {
                            "modalities": ["text", "audio"],
                            "instructions": self.system_prompt,
                            "voice": self.voice,
                            "input_audio_format": "pcm16",
                            "output_audio_format": "pcm16",
                            "input_audio_transcription": {"model": "whisper-1"},
                            "turn_detection": {
                                "type": "server_vad",
                                "threshold": 0.5,
                                "prefix_padding_ms": 300,
                                "silence_duration_ms": 500
                            },
                            "tools": self.tools,
                            "tool_choice": "auto",
                            "temperature": 0.8,
                        }
                    }))

                    # Start tasks based on output mode
                    if self.output_mode == "esp32_udp":
                        tasks = [
                            asyncio.create_task(self.receive_udp_audio()),
                            asyncio.create_task(self.send_audio_to_openai()),
                            asyncio.create_task(self.send_audio_to_esp32()),
                            asyncio.create_task(self.receive_from_openai())
                        ]
                    else:  # speakers mode
                        tasks = [
                            asyncio.create_task(self.receive_speaker_audio()),
                            asyncio.create_task(self.send_audio_to_openai()),
                            asyncio.create_task(self.send_audio_to_speakers()),
                            asyncio.create_task(self.receive_from_openai())
                        ]

                    await asyncio.gather(*tasks)

            except KeyboardInterrupt:
                print("\n👋 Shutting down gracefully...")
                break
            except Exception as e:
                reconnect_attempts += 1
                print(f"❌ Connection error (attempt #{reconnect_attempts}): {e}")

                # Clear buffers before reconnecting
                self.playback_buffer.clear()

                # Check if MQTT is still connected, reconnect if needed
                if self.enable_mqtt and not self.mqtt_client.is_connected():
                    print("⚠️  MQTT disconnected, attempting to reconnect...")
                    try:
                        self.mqtt_client.reconnect()
                        print("✅ MQTT reconnected")
                    except Exception as mqtt_error:
                        print(f"⚠️  MQTT reconnect failed: {mqtt_error}")

async def main():
    parser = argparse.ArgumentParser(
        description="Franky - AI-Powered Halloween Talking Skull",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with ESP32 hardware (default, logging enabled)
  python3 franky.py

  # Use different voice
  python3 franky.py --voice echo

  # Test without hardware (speakers only)
  python3 franky.py --output speakers --no-camera --no-mqtt

  # Disable conversation logging
  python3 franky.py --no-log-conversation

  # Custom configuration
  python3 franky.py --esp32-ip 192.168.1.50 --mqtt-server 192.168.1.100
        """
    )

    # Voice selection
    parser.add_argument(
        "--voice",
        type=str,
        default="ash",
        choices=["alloy", "ash", "ballad", "coral", "echo", "sage", "shimmer", "verse", "marin", "cedar"],
        help="OpenAI voice to use (default: ash)"
    )

    # Audio output
    parser.add_argument(
        "--output",
        type=str,
        default="esp32_udp",
        choices=["esp32_udp", "speakers"],
        help="Audio output destination: esp32_udp (default) or speakers"
    )

    # Hardware toggles
    parser.add_argument(
        "--enable-camera",
        dest="enable_camera",
        action="store_true",
        default=True,
        help="Enable camera vision (default: enabled)"
    )
    parser.add_argument(
        "--no-camera",
        dest="enable_camera",
        action="store_false",
        help="Disable camera vision"
    )

    parser.add_argument(
        "--enable-mqtt",
        dest="enable_mqtt",
        action="store_true",
        default=True,
        help="Enable MQTT for jaw/eyes control (default: enabled)"
    )
    parser.add_argument(
        "--no-mqtt",
        dest="enable_mqtt",
        action="store_false",
        help="Disable MQTT"
    )

    parser.add_argument(
        "--enable-jaw",
        dest="enable_jaw",
        action="store_true",
        default=True,
        help="Enable jaw movement control (default: enabled)"
    )
    parser.add_argument(
        "--no-jaw",
        dest="enable_jaw",
        action="store_false",
        help="Disable jaw movement"
    )

    parser.add_argument(
        "--enable-eyes",
        dest="enable_eyes",
        action="store_true",
        default=True,
        help="Enable LED eyes control (default: enabled)"
    )
    parser.add_argument(
        "--no-eyes",
        dest="enable_eyes",
        action="store_false",
        help="Disable LED eyes"
    )

    # Network configuration
    parser.add_argument(
        "--esp32-ip",
        type=str,
        help="ESP32 IP address (overrides .env)"
    )

    parser.add_argument(
        "--mqtt-server",
        type=str,
        help="MQTT broker address (overrides .env)"
    )

    parser.add_argument(
        "--mqtt-port",
        type=int,
        default=1883,
        help="MQTT broker port (default: 1883)"
    )

    # Logging
    parser.add_argument(
        "--log-conversation",
        dest="log_conversation",
        action="store_true",
        default=True,
        help="Log all conversation text to conversation_logs/ folder (default: enabled)"
    )
    parser.add_argument(
        "--no-log-conversation",
        dest="log_conversation",
        action="store_false",
        help="Disable conversation logging"
    )

    args = parser.parse_args()

    # Display configuration
    print("=" * 60)
    print("🎃 FRANKY - AI-Powered Halloween Talking Skull")
    print("=" * 60)
    print(f"🎙️  Voice: {args.voice}")
    print(f"🔊 Output: {args.output}")
    print(f"📹 Camera: {'✅ Enabled' if args.enable_camera else '❌ Disabled'}")
    print(f"📡 MQTT: {'✅ Enabled' if args.enable_mqtt else '❌ Disabled'}")
    if args.enable_mqtt:
        print(f"   └─ Jaw: {'✅' if args.enable_jaw else '❌'}")
        print(f"   └─ Eyes: {'✅' if args.enable_eyes else '❌'}")
    print(f"📝 Logging: {'✅ Enabled' if args.log_conversation else '❌ Disabled'}")
    print("=" * 60)

    bot = RealtimeVoiceBotUDP(
        voice=args.voice,
        output_mode=args.output,
        enable_camera=args.enable_camera,
        enable_mqtt=args.enable_mqtt,
        enable_jaw=args.enable_jaw,
        enable_eyes=args.enable_eyes,
        esp32_ip_override=args.esp32_ip,
        mqtt_server_override=args.mqtt_server,
        mqtt_port_override=args.mqtt_port,
        log_conversation=args.log_conversation
    )
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())
