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

try:
    from meross_iot.http_api import MerossHttpClient
    from meross_iot.manager import MerossManager
    MEROSS_AVAILABLE = True
except ImportError:
    MEROSS_AVAILABLE = False
    print("⚠️  meross-iot not installed. Smart device control disabled. Install with: pip install meross-iot")

try:
    import tinytuya
    TINYTUYA_AVAILABLE = True
except ImportError:
    TINYTUYA_AVAILABLE = False
    print("⚠️  tinytuya not installed. Smart light control disabled. Install with: pip install tinytuya")

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
        self.use_webcam = os.getenv("USE_WEBCAM", "false").lower() == "true"
        self.save_camera_screenshots = os.getenv("SAVE_CAMERA_SCREENSHOTS", "false").lower() == "true"
        if enable_camera:
            if self.use_webcam:
                # Allow custom webcam index (default 0, but can be 1, 2, etc.)
                webcam_index = int(os.getenv("WEBCAM_INDEX", "0"))
                self.camera_url = webcam_index
                print(f"📷 Using webcam (device {webcam_index})")
            else:
                self.camera_url = os.getenv("CAMERA_RTSP_STREAM")
                if not self.camera_url:
                    print("⚠️  Camera enabled but no RTSP stream configured")
        else:
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

        # Audio device selection for speaker mode
        self.audio_input_device = None  # None = default
        self.audio_output_device = None  # None = default

        if self.output_mode == "speakers":
            # Check for custom audio devices
            input_device_str = os.getenv("AUDIO_INPUT_DEVICE")
            output_device_str = os.getenv("AUDIO_OUTPUT_DEVICE")

            if input_device_str:
                try:
                    self.audio_input_device = int(input_device_str)
                    print(f"🎤 Using custom input device: {self.audio_input_device}")
                except ValueError:
                    print(f"⚠️  Invalid AUDIO_INPUT_DEVICE: {input_device_str}, using default")

            if output_device_str:
                try:
                    self.audio_output_device = int(output_device_str)
                    print(f"🔊 Using custom output device: {self.audio_output_device}")
                except ValueError:
                    print(f"⚠️  Invalid AUDIO_OUTPUT_DEVICE: {output_device_str}, using default")

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

        # Meross smart device setup
        self.meross_enabled = os.getenv("ENABLE_MEROSS_CONTROL", "false").lower() == "true"
        self.meross_manager = None
        self.meross_http_client = None
        self.meross_email = os.getenv("MEROSS_EMAIL")
        self.meross_password = os.getenv("MEROSS_PASSWORD")
        self.aurora_device_name = "Aurora night light"

        if not self.meross_enabled:
            print("⚠️  Meross smart device control disabled (ENABLE_MEROSS_CONTROL=false)")
        elif MEROSS_AVAILABLE and self.meross_email and self.meross_password:
            print("📱 Meross credentials found - smart device control enabled")
        else:
            if not MEROSS_AVAILABLE:
                print("⚠️  Meross smart device control disabled (library not installed)")
            elif not self.meross_email or not self.meross_password:
                print("⚠️  Meross smart device control disabled (credentials not in .env)")
            self.meross_enabled = False

        # Tuya/Smart Life device setup
        self.flood_light_enabled = os.getenv("ENABLE_FLOOD_LIGHT_CONTROL", "false").lower() == "true"
        self.flood_light = None
        self.flood_device_id = os.getenv("FLOOD_LIGHT_DEVICE_ID")
        self.flood_ip = os.getenv("FLOOD_LIGHT_IP")
        self.flood_key = os.getenv("FLOOD_LIGHT_LOCAL_KEY")

        if not self.flood_light_enabled:
            print("⚠️  Smart Flood Light control disabled (ENABLE_FLOOD_LIGHT_CONTROL=false)")
        elif TINYTUYA_AVAILABLE and self.flood_device_id and self.flood_ip and self.flood_key:
            print("💡 Smart Flood Light credentials found - color light control enabled")
            # Initialize device
            self.flood_light = tinytuya.BulbDevice(
                dev_id=self.flood_device_id,
                address=self.flood_ip,
                local_key=self.flood_key,
                version=3.5
            )
        else:
            if not TINYTUYA_AVAILABLE:
                print("⚠️  Smart Flood Light control disabled (tinytuya not installed)")
            elif not self.flood_device_id or not self.flood_ip or not self.flood_key:
                print("⚠️  Smart Flood Light control disabled (credentials not in .env)")
            self.flood_light_enabled = False

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

## Lighting Effects for Atmosphere
You can control colored lights to enhance the spooky atmosphere! Use lighting to amplify scares and create mood:
- **UV Light (Aurora):** Blinking UV creates ghostly glowing effects. Use for mysterious/scary moments.
- **Flood Light (RGB):** Can set single colors or create sequences:
  - Red: Danger, demons, scary moments
  - Blue: Ghost, cold, eerie atmosphere
  - Purple: Witch, magic, mystical
  - Orange: Halloween, pumpkin glow
  - Color sequences: Red-white-red-white for police/alarm effect, or gradual color changes for atmosphere
  - Blinking: Fast blinking for scares, slow for mystery
- **When to use:** During scary stories, before "BOO!", during mini-games, to match voice effects
- **Keep it short:** 5-10 seconds of effects, then return to normal or subtle lighting
- Don't overuse - save for key moments to maximize impact!

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

        # Add UV light control if Meross is enabled
        if self.meross_enabled and MEROSS_AVAILABLE and self.meross_email and self.meross_password:
            self.tools.append({
                "type": "function",
                "name": "control_uv_light",
                "description": "Controls the Aurora night light UV (ultraviolet) light. Supports blinking/flashing effects! Use for spooky glowing atmosphere - UV light makes white things glow in the dark.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["on", "off", "blink"],
                            "description": "Action: 'on' (turn on), 'off' (turn off), 'blink' (flash on/off repeatedly for scary effect)"
                        },
                        "duration": {
                            "type": "number",
                            "description": "Duration in seconds for 'blink' action (default: 10). How long to keep blinking."
                        },
                        "interval": {
                            "type": "number",
                            "description": "Interval in seconds between blinks (default: 0.5). Faster = more intense effect."
                        }
                    },
                    "required": ["action"]
                }
            })

        # Add Smart Flood Light control if enabled
        if self.flood_light_enabled and TINYTUYA_AVAILABLE and self.flood_light:
            self.tools.append({
                "type": "function",
                "name": "control_flood_light",
                "description": "Controls Smart Flood Light with RGB colors and effects! Create spooky atmosphere with color sequences like red-white-red-white or single colors. Perfect for scary lighting effects!",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["on", "off", "color", "sequence", "blink"],
                            "description": "Action: 'on'=turn on, 'off'=turn off, 'color'=set single color, 'sequence'=play color sequence, 'blink'=flash on/off"
                        },
                        "color": {
                            "type": "string",
                            "enum": ["red", "green", "blue", "purple", "orange", "yellow", "cyan", "magenta", "white"],
                            "description": "Color name for 'color' action"
                        },
                        "sequence": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": ["red", "green", "blue", "purple", "orange", "yellow", "cyan", "magenta", "white", "off"]
                            },
                            "description": "Sequence of colors for 'sequence' action, e.g. ['red', 'white', 'red', 'white'] for scary flashing effect"
                        },
                        "duration": {
                            "type": "number",
                            "description": "Duration in seconds for 'blink' action or time per color in sequence (default: blink=10s, sequence=1s per color)"
                        },
                        "interval": {
                            "type": "number",
                            "description": "Interval between changes in seconds (default: 0.5s for blink, 1s for sequence)"
                        },
                        "brightness": {
                            "type": "number",
                            "description": "Brightness 0-100% (default: 100)"
                        }
                    },
                    "required": ["action"]
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

        # Get input device info
        if self.audio_input_device is not None:
            device_info = self.pyaudio_instance.get_device_info_by_index(self.audio_input_device)
            mic_name = device_info.get('name', 'Unknown')
            print(f"🎤 Using microphone: {mic_name} (device {self.audio_input_device})")
        else:
            default_input = self.pyaudio_instance.get_default_input_device_info()
            mic_name = default_input.get('name', 'Unknown')
            print(f"🎤 Using microphone: {mic_name}")

        stream = self.pyaudio_instance.open(
            format=pyaudio.paInt16,
            channels=self.SPEAKER_CHANNELS,
            rate=self.SPEAKER_RATE,
            input=True,
            input_device_index=self.audio_input_device,
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

        # Get output device info
        if self.audio_output_device is not None:
            device_info = self.pyaudio_instance.get_device_info_by_index(self.audio_output_device)
            speaker_name = device_info.get('name', 'Unknown')
            print(f"🔊 Using speaker: {speaker_name} (device {self.audio_output_device})")
        else:
            default_output = self.pyaudio_instance.get_default_output_device_info()
            speaker_name = default_output.get('name', 'Unknown')
            print(f"🔊 Using speaker: {speaker_name}")

        print("🔊 Starting audio playback")

        # Initialize output stream
        self.output_stream = self.pyaudio_instance.open(
            format=pyaudio.paInt16,
            channels=self.SPEAKER_CHANNELS,
            rate=self.SPEAKER_RATE,
            output=True,
            output_device_index=self.audio_output_device,
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

        # Always reconnect to get fresh frame
        if self.camera:
            self.camera.release()

        start_connect = time.time()

        # Use appropriate backend based on camera type
        if self.use_webcam:
            # Use AVFoundation for webcam on macOS (no FFMPEG warning)
            import platform
            if platform.system() == "Darwin":  # macOS
                self.camera = cv2.VideoCapture(self.camera_url, cv2.CAP_AVFOUNDATION)
            else:
                self.camera = cv2.VideoCapture(self.camera_url)
        else:
            # Use FFMPEG for RTSP streams
            self.camera = cv2.VideoCapture(self.camera_url, cv2.CAP_FFMPEG)
            # Set timeout for RTSP stream
            self.camera.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 10000)
            self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        if not self.camera.isOpened():
            print("❌ Failed to open camera")
            return None
        connect_time = time.time() - start_connect
        print(f"📷 [2/7] Camera opened: {connect_time:.2f}s")

        # Webcam warm-up: skip first few frames (they're often black)
        if self.use_webcam:
            print(f"📷 [3/7] Warming up webcam...")
            for _ in range(5):
                self.camera.read()  # Discard first frames
                time.sleep(0.1)

        start_read = time.time()
        ret, frame = self.camera.read()
        if not ret:
            print("❌ Failed to capture frame")
            return None
        read_time = time.time() - start_read
        print(f"📷 [4/7] Frame captured: {read_time:.2f}s")

        # Get original resolution
        height, width = frame.shape[:2]

        # Generate timestamp for logging
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

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

        # Convert to base64 and optionally save
        start_encode = time.time()
        _, buffer = cv2.imencode('.jpg', frame_for_api, [cv2.IMWRITE_JPEG_QUALITY, 85])
        image_base64 = base64.b64encode(buffer).decode('utf-8')
        encode_time = time.time() - start_encode
        print(f"📷 [6/6] Encoded to base64: {encode_time:.2f}s")

        # Save sent image to logs (if enabled)
        if self.save_camera_screenshots:
            log_path = os.path.join(self.logs_dir, f"camera_{timestamp}.jpg")
            cv2.imwrite(log_path, frame_for_api, [cv2.IMWRITE_JPEG_QUALITY, 85])
            print(f"💾 Saved to: {log_path}")

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

    async def init_meross_manager(self):
        """Initialize Meross manager if not already initialized"""
        if not MEROSS_AVAILABLE or not self.meross_email or not self.meross_password:
            return False

        if self.meross_manager is not None:
            return True  # Already initialized

        try:
            print("🔄 Initializing Meross manager...")
            # Setup HTTP client
            self.meross_http_client = await MerossHttpClient.async_from_user_password(
                email=self.meross_email,
                password=self.meross_password,
                api_base_url="https://iotx-us.meross.com"
            )

            # Setup manager
            self.meross_manager = MerossManager(http_client=self.meross_http_client)
            await self.meross_manager.async_init()
            await self.meross_manager.async_device_discovery()
            print("✅ Meross manager initialized")
            return True

        except Exception as e:
            print(f"❌ Failed to initialize Meross: {e}")
            return False

    async def control_uv_light(self, action, duration=10, interval=0.5):
        """Control Aurora UV light via Meross with blink support"""
        if not await self.init_meross_manager():
            return {"error": "Meross not available"}

        try:
            # Find Aurora device
            devices = self.meross_manager.find_devices(device_name=self.aurora_device_name)

            if not devices:
                print(f"❌ Device '{self.aurora_device_name}' not found")
                return {"error": f"Device '{self.aurora_device_name}' not found"}

            device = devices[0]
            await device.async_update()

            # Perform action
            if action == "on":
                await device.async_turn_on()
                print(f"💡 UV light turned ON")
                return {"status": "on", "device": self.aurora_device_name}
            elif action == "off":
                await device.async_turn_off()
                print(f"💡 UV light turned OFF")
                return {"status": "off", "device": self.aurora_device_name}
            elif action == "blink":
                print(f"⚡ UV light blinking for {duration}s (interval: {interval}s)")
                start_time = asyncio.get_event_loop().time()
                blink_count = 0
                while (asyncio.get_event_loop().time() - start_time) < duration:
                    await device.async_turn_on()
                    await asyncio.sleep(interval)
                    await device.async_turn_off()
                    await asyncio.sleep(interval)
                    blink_count += 1
                # Leave on after blinking
                await device.async_turn_on()
                print(f"💡 UV light blinked {blink_count} times, now ON")
                return {"status": "blinked", "device": self.aurora_device_name, "count": blink_count}
            else:
                return {"error": f"Invalid action: {action}"}

        except Exception as e:
            print(f"❌ Failed to control UV light: {e}")
            return {"error": str(e)}

    async def control_flood_light(self, action, color=None, sequence=None, duration=None, interval=None, brightness=100):
        """Control Smart Flood Light with colors and sequences"""
        if not self.flood_light:
            return {"error": "Flood light not available"}

        # Color mapping
        colors = {
            "red": (255, 0, 0),
            "green": (0, 255, 0),
            "blue": (0, 0, 255),
            "purple": (128, 0, 128),
            "orange": (255, 165, 0),
            "yellow": (255, 255, 0),
            "cyan": (0, 255, 255),
            "magenta": (255, 0, 255),
            "white": (255, 255, 255),
            "off": None
        }

        try:
            # Set brightness
            if brightness != 100:
                self.flood_light.set_brightness_percentage(brightness)
                await asyncio.sleep(0.1)

            if action == "on":
                self.flood_light.turn_on()
                print(f"💡 Flood light turned ON")
                return {"status": "on"}

            elif action == "off":
                self.flood_light.turn_off()
                print(f"💡 Flood light turned OFF")
                return {"status": "off"}

            elif action == "color":
                if not color or color not in colors:
                    return {"error": f"Invalid color: {color}"}
                self.flood_light.turn_on()
                await asyncio.sleep(0.1)
                r, g, b = colors[color]
                self.flood_light.set_colour(r, g, b)
                print(f"💡 Flood light set to {color.upper()} ({r},{g},{b})")
                return {"status": "color", "color": color}

            elif action == "sequence":
                if not sequence or len(sequence) == 0:
                    return {"error": "Empty sequence"}

                # Default interval for sequence
                seq_interval = interval if interval is not None else 1.0

                print(f"🎨 Playing color sequence: {' → '.join(sequence)}")
                for color_name in sequence:
                    if color_name not in colors:
                        continue
                    if color_name == "off":
                        self.flood_light.turn_off()
                    else:
                        self.flood_light.turn_on()
                        await asyncio.sleep(0.1)
                        r, g, b = colors[color_name]
                        self.flood_light.set_colour(r, g, b)
                    await asyncio.sleep(seq_interval)

                print(f"✅ Sequence completed ({len(sequence)} colors)")
                return {"status": "sequence", "count": len(sequence)}

            elif action == "blink":
                blink_duration = duration if duration is not None else 10
                blink_interval = interval if interval is not None else 0.5

                print(f"⚡ Flood light blinking for {blink_duration}s (interval: {blink_interval}s)")
                start_time = asyncio.get_event_loop().time()
                blink_count = 0
                while (asyncio.get_event_loop().time() - start_time) < blink_duration:
                    self.flood_light.turn_on()
                    await asyncio.sleep(blink_interval)
                    self.flood_light.turn_off()
                    await asyncio.sleep(blink_interval)
                    blink_count += 1

                # Leave on after blinking
                self.flood_light.turn_on()
                print(f"💡 Flood light blinked {blink_count} times, now ON")
                return {"status": "blinked", "count": blink_count}

            else:
                return {"error": f"Invalid action: {action}"}

        except Exception as e:
            print(f"❌ Failed to control flood light: {e}")
            return {"error": str(e)}

    async def handle_function_call(self, function_name, arguments):
        """Handle function calls from OpenAI"""
        print(f"🔧 Function call: {function_name}({arguments})")

        if function_name == "look_at_camera":
            return self.look_at_camera()
        elif function_name == "play_scary_music":
            return self.play_scary_music(arguments.get("filename"))
        elif function_name == "stop_music":
            return self.stop_music()
        elif function_name == "control_uv_light":
            return await self.control_uv_light(
                action=arguments.get("action"),
                duration=arguments.get("duration", 10),
                interval=arguments.get("interval", 0.5)
            )
        elif function_name == "control_flood_light":
            return await self.control_flood_light(
                action=arguments.get("action"),
                color=arguments.get("color"),
                sequence=arguments.get("sequence"),
                duration=arguments.get("duration"),
                interval=arguments.get("interval"),
                brightness=arguments.get("brightness", 100)
            )

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

                    await asyncio.gather(*tasks, return_exceptions=True)

            except KeyboardInterrupt:
                print("\n👋 Shutting down gracefully...")
                # Cancel all running tasks
                for task in tasks:
                    task.cancel()
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

        # Cleanup resources
        print("🧹 Cleaning up...")

        # Close websocket
        if self.websocket:
            try:
                await self.websocket.close()
                print("✅ WebSocket closed")
            except:
                pass

        # Release camera
        if self.camera:
            try:
                self.camera.release()
                print("✅ Camera released")
            except:
                pass

        # Stop MQTT
        if self.enable_mqtt:
            try:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
                print("✅ MQTT disconnected")
            except:
                pass

        # Stop pygame mixer
        try:
            pygame.mixer.quit()
            print("✅ Audio mixer stopped")
        except:
            pass

        # Cleanup Meross connection
        if self.meross_manager is not None:
            try:
                self.meross_manager.close()
                if self.meross_http_client is not None:
                    await self.meross_http_client.async_logout()
                print("✅ Meross connection closed")
            except Exception as e:
                print(f"⚠️  Meross cleanup error: {e}")

        print("👋 Goodbye!")

async def main():
    # Read defaults from .env file
    output_mode_default = os.getenv("OUTPUT_MODE", "esp32_udp")
    enable_camera_default = os.getenv("ENABLE_CAMERA", "true").lower() == "true"
    enable_mqtt_default = os.getenv("ENABLE_MQTT", "true").lower() == "true"
    enable_jaw_default = os.getenv("ENABLE_JAW", "true").lower() == "true"
    enable_eyes_default = os.getenv("ENABLE_EYES", "true").lower() == "true"

    parser = argparse.ArgumentParser(
        description="Franky - AI-Powered Halloween Talking Skull",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with configuration from .env
  python3 franky.py

  # Use different voice
  python3 franky.py --voice echo

  # Override .env settings via command line
  python3 franky.py --output speakers --no-camera --no-mqtt
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
        default=output_mode_default,
        choices=["esp32_udp", "speakers"],
        help=f"Audio output destination (default from .env: {output_mode_default})"
    )

    # Hardware toggles
    parser.add_argument(
        "--enable-camera",
        dest="enable_camera",
        action="store_true",
        default=enable_camera_default,
        help=f"Enable camera vision (default from .env: {enable_camera_default})"
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
        default=enable_mqtt_default,
        help=f"Enable MQTT for jaw/eyes control (default from .env: {enable_mqtt_default})"
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
        default=enable_jaw_default,
        help=f"Enable jaw movement control (default from .env: {enable_jaw_default})"
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
        default=enable_eyes_default,
        help=f"Enable LED eyes control (default from .env: {enable_eyes_default})"
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

    try:
        await bot.run()
    except KeyboardInterrupt:
        print("\n✅ Shutdown complete")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        import sys
        sys.exit(0)
