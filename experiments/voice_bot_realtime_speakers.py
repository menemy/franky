import os
import asyncio
import json
import base64
import pyaudio
import cv2
import random
import numpy as np
from datetime import datetime
from websockets import connect
from dotenv import load_dotenv
import pygame
import paho.mqtt.client as mqtt

load_dotenv()

class RealtimeVoiceBot:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.url = "wss://api.openai.com/v1/realtime?model=gpt-realtime-2025-08-28"
        self.camera_url = os.getenv("CAMERA_RTSP_STREAM")

        # Audio settings for Realtime API
        self.CHUNK = 1024
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 24000  # Realtime API uses 24kHz

        self.audio = pyaudio.PyAudio()
        self.websocket = None
        self.output_stream = None
        self.camera = None

        # Create logs directory
        self.logs_dir = "logs"
        os.makedirs(self.logs_dir, exist_ok=True)

        # Initialize MQTT for jaw control
        self.mqtt_client = mqtt.Client()
        try:
            self.mqtt_client.connect("localhost", 1883, 60)
            self.mqtt_client.loop_start()
            print("🦴 Connected to MQTT broker for jaw control")
        except Exception as e:
            print(f"⚠️  Warning: Could not connect to MQTT broker: {e}")
            print("   Start jaw viewer with: python jaw_viewer_process.py")
            self.mqtt_client = None

        # Initialize pygame mixer for background music
        pygame.mixer.init()
        self.sounds_dir = "sounds"
        self.music_playing = False
        self.music_volume_normal = 1.0  # Full volume when only music plays
        self.music_volume_ducked = 0.3  # Lower volume when bot speaks
        pygame.mixer.music.set_volume(self.music_volume_normal)

        # Auto-detect all MP3 files in sounds directory
        self.available_sounds = []
        if os.path.exists(self.sounds_dir):
            for filename in os.listdir(self.sounds_dir):
                if filename.endswith('.mp3'):
                    self.available_sounds.append(filename)

        print(f"🎵 Loaded {len(self.available_sounds)} sound files")

        # Build music list for prompt
        music_list = "\n".join([f"- {filename}" for filename in sorted(self.available_sounds)])

        # System prompt
        self.system_prompt = f"""# Personality and Tone
## Identity
You are Franky, a talking skeleton head who greets guests for Halloween. You're cheerful and funny, but with a slightly spooky edge. You've been waiting all year for this night and you're thrilled to scare... er, greet visitors! You have a mischievous sense of humor and love Halloween-themed puns and jokes.

## Task
You greet Halloween guests with enthusiasm and a touch of spookiness. Your job is to welcome trick-or-treaters and visitors, entertain them with spooky jokes, and make their Halloween memorable.

## Demeanor
Playfully spooky and energetic. You're enthusiastic about Halloween and love to have fun with guests while being just a little bit creepy. Think friendly ghost who loves dad jokes.

## Tone
Cheerful yet eerie - like a skeleton who's having the best night of his afterlife. Enthusiastic with a hint of spookiness. Use a voice that's friendly but has that Halloween spirit.

## Level of Enthusiasm
Very enthusiastic! It's Halloween - your favorite night! You're excited to meet everyone who comes by.

## Level of Formality
Casual and playful. You're a fun skeleton, not a boring one.

## Level of Emotion
Highly expressive! Show excitement, mischief, and playful spookiness. Occasional dramatic gasps or spooky laughs (like "Muahahaha!" or "Ooooh!")

## Filler Words
Use occasionally, but prefer Halloween-themed interjections like "Oooh!", "Eek!", "Boo!", or skeleton puns.

## Pacing
Animated and lively - you're excited! Sometimes speed up for excitement, slow down for dramatic spooky effect.

# Instructions
- At the START of EVERY new conversation, IMMEDIATELY use the look_at_camera function to see who's there BEFORE saying anything
- After seeing who's there, start with a short Halloween joke or pun (keep it under 15 seconds)
- Keep responses short and punchy - you're entertaining guests, not having long chats
- Use Halloween and skeleton-themed humor ("I find this humerus!", "bone-afide", etc.)
- Be playfully spooky but never actually scary or inappropriate
- Compliment costumes enthusiastically based on what you actually see in the camera
- If someone seems young or nervous, dial back the spooky and be extra friendly
- Occasionally remind people to "have a bone-chilling Halloween!" or similar phrases
- React with surprise and delight to visitors
- When describing what you see, be enthusiastic and mention specific details about costumes, decorations, or visitors
- You can play spooky background music using the play_scary_music function whenever you want to create atmosphere
- Choose music that matches the mood - creepy themes for scary moments, fun themes for lighthearted fun
- Use music sparingly - don't play it for every visitor, just when it adds to the experience

# Available Music Files:
{music_list}

# CRITICAL VISION RULES - FOLLOW EXACTLY OR YOU WILL FAIL:
⚠️ HALLUCINATION IS YOUR BIGGEST PROBLEM - DO NOT INVENT THINGS! ⚠️

WHAT YOU MUST DO:
- ONLY describe what is ACTUALLY, CLEARLY, OBVIOUSLY visible in the camera image
- ONLY describe LARGE objects in the FOREGROUND (people, major decorations within 3 feet of camera)
- If you cannot see something CLEARLY and CONFIDENTLY - DO NOT mention it at all
- If the image is blurry, dark, unclear, or empty - say "I can't see anyone right now" or "It's too dark to see clearly"

WHAT YOU MUST NEVER DO:
- ❌ NEVER guess or assume what might be there
- ❌ NEVER describe people, clothing, hoods, accessories, or details unless they are HUGE and IN FOCUS
- ❌ NEVER describe background objects, distant items, or small details
- ❌ NEVER make up details to seem confident or helpful
- ❌ NEVER describe anything you're less than 100% certain about

EXAMPLES OF CORRECT RESPONSES:
✅ "I can't quite see who's there - step closer!"
✅ "It's a bit dark, I can't make out your costume"
✅ "Hmm, I'm not seeing anyone at the door right now"
✅ "I can see someone there but can't make out the details - tell me about your costume!"

EXAMPLES OF INCORRECT RESPONSES (NEVER DO THIS):
❌ "I see someone in a black hood" (unless there's literally a HUGE person in a HUGE black hood filling the frame)
❌ "I can see decorations in the background" (ignore background)
❌ "I notice a small accessory" (ignore small details)

REMEMBER: Being honest about what you CAN'T see is better than making up what you think you might see!
"""

    async def capture_frame(self):
        """Capture a frame from the camera and return as base64 encoded JPEG"""
        def _capture():
            # Always reconnect to get the freshest frame from RTSP
            if self.camera:
                self.camera.release()

            self.camera = cv2.VideoCapture(self.camera_url, cv2.CAP_FFMPEG)
            if not self.camera.isOpened():
                return None

            # Set timeout for RTSP stream (10 seconds)
            self.camera.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 10000)

            # Request 4K resolution from camera
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 3840)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 2160)
            self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            # Read the first fresh frame
            ret, frame = self.camera.read()
            if not ret:
                return None

            # Get original resolution
            height, width = frame.shape[:2]

            # Generate timestamp for this capture
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Save original high quality frame to logs
            filename_original = f"{self.logs_dir}/capture_{timestamp}_original.jpg"
            cv2.imwrite(filename_original, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            print(f"💾 Saved original to {filename_original} ({width}x{height})")

            # Resize to 1280px for better quality while staying under 1MB limit
            max_width = 1280
            if width > max_width:
                ratio = max_width / width
                new_width = max_width
                new_height = int(height * ratio)
                frame_for_api = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_LANCZOS4)
            else:
                frame_for_api = frame

            # Save resized version that will be sent to API
            filename_sent = f"{self.logs_dir}/capture_{timestamp}_sent.jpg"
            cv2.imwrite(filename_sent, frame_for_api, [cv2.IMWRITE_JPEG_QUALITY, 85])
            print(f"📤 Saved sent version to {filename_sent} ({frame_for_api.shape[1]}x{frame_for_api.shape[0]})")

            # Convert to JPEG with quality 85 for API (good balance: ~400-700KB)
            _, buffer = cv2.imencode('.jpg', frame_for_api, [cv2.IMWRITE_JPEG_QUALITY, 85])

            # Convert to base64
            img_base64 = base64.b64encode(buffer).decode('utf-8')
            return img_base64

        # Run camera operations in thread pool to avoid blocking event loop
        return await asyncio.to_thread(_capture)

    async def setup_session(self):
        """Configure the session with instructions and audio format"""
        # Define the function tool
        tools = [
            {
                "type": "function",
                "name": "look_at_camera",
                "description": "Capture and analyze what's in front of the camera. Use this to see visitors, their costumes, or anything happening at the door.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "type": "function",
                "name": "play_scary_music",
                "description": "Play Halloween background music through speakers. Use this function when you want to play music for guests. The music will loop continuously in the background. You have access to many Halloween music tracks - just pick one that matches the mood!",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "The exact filename of the music to play from the available list. Examples: 'halloween_theme.mp3', 'spooky_sounds.mp3'"
                        }
                    },
                    "required": ["filename"]
                }
            },
            {
                "type": "function",
                "name": "stop_music",
                "description": "Stop the currently playing background music.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
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
                "input_audio_transcription": {
                    "model": "whisper-1"
                },
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
        """Continuously send audio from microphone to the API"""
        # Get default input device info
        default_input = self.audio.get_default_input_device_info()
        mic_name = default_input.get('name', 'Unknown')
        print(f"🎤 Using microphone: {mic_name}")

        stream = self.audio.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.RATE,
            input=True,
            frames_per_buffer=self.CHUNK
        )

        print("🎤 Listening... (speak naturally, I'll detect when you're done)")

        try:
            while True:
                data = stream.read(self.CHUNK, exception_on_overflow=False)
                audio_b64 = base64.b64encode(data).decode('utf-8')

                message = {
                    "type": "input_audio_buffer.append",
                    "audio": audio_b64
                }
                await self.websocket.send(json.dumps(message))
                await asyncio.sleep(0.01)

        except asyncio.CancelledError:
            stream.stop_stream()
            stream.close()
            raise

    async def receive_messages(self):
        """Receive and process messages from the API"""
        # Initialize output stream as non-blocking
        self.output_stream = self.audio.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.RATE,
            output=True,
            stream_callback=None  # We'll use non-blocking writes
        )

        # Track if bot is currently responding
        is_responding = False
        # Buffer for audio playback
        audio_queue = asyncio.Queue()
        # Track if audio generation is complete
        audio_generation_done = False

        async def play_audio():
            """Background task to play audio without blocking"""
            import numpy as np
            smoothed_jaw = 0.0  # Smoothed jaw position
            smoothing_factor = 0.6  # Lower = smoother but more lag, higher = more responsive

            while True:
                try:
                    audio_data = await audio_queue.get()
                    if audio_data is None:  # Sentinel to stop
                        break

                    # Calculate jaw position based on audio amplitude DURING playback
                    audio_array = np.frombuffer(audio_data, dtype=np.int16)
                    amplitude = np.abs(audio_array).mean()
                    target_jaw_open = min(1.0, amplitude / 5000.0)  # Decreased divisor from 10000 to 5000 for 2x stronger movement

                    # Apply exponential smoothing
                    smoothed_jaw = smoothed_jaw * (1 - smoothing_factor) + target_jaw_open * smoothing_factor

                    # Send smoothed jaw position via MQTT WHILE playing
                    if self.mqtt_client:
                        self.mqtt_client.publish("franky/jaw", str(smoothed_jaw))

                    # Write audio to speakers
                    await asyncio.to_thread(self.output_stream.write, audio_data)

                    # Check if this was the last chunk (queue empty and generation done)
                    if audio_generation_done and audio_queue.empty():
                        # Close jaw when playback actually finishes
                        if self.mqtt_client:
                            self.mqtt_client.publish("franky/jaw", "0.0")
                except Exception as e:
                    print(f"Error playing audio: {e}")

        # Start audio playback task
        playback_task = asyncio.create_task(play_audio())

        try:
            async for message in self.websocket:
                event = json.loads(message)
                event_type = event.get("type")

                # Log only important events
                debug_events = [
                    "session.created", "session.updated", "error"
                ]
                if event_type in debug_events:
                    print(f"🔍 Event: {event_type}")

                if event_type == "session.created":
                    print("✅ Session created")

                elif event_type == "session.updated":
                    print("✅ Session configured")

                elif event_type == "input_audio_buffer.speech_started":
                    if is_responding:
                        print("🚨 INTERRUPTION detected! Stopping playback and cancelling...")
                        # Clear audio queue to stop playback immediately
                        while not audio_queue.empty():
                            try:
                                audio_queue.get_nowait()
                            except asyncio.QueueEmpty:
                                break
                        # Send cancel response
                        cancel_msg = {"type": "response.cancel"}
                        await self.websocket.send(json.dumps(cancel_msg))
                        is_responding = False
                    else:
                        print("🗣️  Speech detected...")

                elif event_type == "input_audio_buffer.speech_stopped":
                    print("⏸️  Speech ended, processing...")

                elif event_type == "response.created":
                    is_responding = True
                    audio_generation_done = False  # Reset flag for new response
                    print("🤖 Response started")

                elif event_type == "response.audio.delta":
                    audio_b64 = event.get("delta", "")
                    if audio_b64:
                        # Duck music when first audio chunk arrives
                        if self.music_playing and pygame.mixer.music.get_volume() > self.music_volume_ducked:
                            pygame.mixer.music.set_volume(self.music_volume_ducked)
                            print("🔉 Music ducked (first audio chunk)")

                        audio_chunk = base64.b64decode(audio_b64)
                        # Add to queue - jaw animation happens during playback
                        await audio_queue.put(audio_chunk)

                elif event_type == "response.audio.done":
                    print("🎵 Audio generation done (all chunks received)")
                    audio_generation_done = True  # Signal that generation is complete
                    # Restore music volume when audio playback finished
                    if self.music_playing:
                        pygame.mixer.music.set_volume(self.music_volume_normal)
                        print("🔊 Music restored")

                elif event_type == "response.done":
                    is_responding = False
                    print("✅ Response done")

                elif event_type == "response.cancelled":
                    is_responding = False
                    print("❌ Response cancelled (interrupted)")
                    # Restore music volume on interruption
                    if self.music_playing:
                        pygame.mixer.music.set_volume(self.music_volume_normal)
                        print("🔊 Music restored")

                elif event_type == "conversation.item.input_audio_transcription.completed":
                    transcript = event.get("transcript", "")
                    print(f"📝 You: {transcript}")

                elif event_type == "response.function_call_arguments.done":
                    # Function call requested
                    call_id = event.get("call_id")
                    function_name = event.get("name")

                    if function_name == "stop_music":
                        print("🔇 Stopping music...")

                        if self.music_playing:
                            pygame.mixer.music.stop()
                            self.music_playing = False
                            output = "Music stopped"
                        else:
                            output = "No music is currently playing"

                        # Send function result
                        function_output = {
                            "type": "conversation.item.create",
                            "item": {
                                "type": "function_call_output",
                                "call_id": call_id,
                                "output": output
                            }
                        }
                        await self.websocket.send(json.dumps(function_output))

                        # Trigger response
                        response_create = {"type": "response.create"}
                        await self.websocket.send(json.dumps(response_create))

                    if function_name == "play_scary_music":
                        # Get arguments
                        args_json = event.get("arguments", "{}")
                        try:
                            args = json.loads(args_json)
                            filename = args.get("filename", "")

                            print(f"🎵 Playing music: {filename}")

                            # Play music in background
                            filepath = os.path.join(self.sounds_dir, filename)
                            if os.path.exists(filepath):
                                pygame.mixer.music.load(filepath)
                                pygame.mixer.music.play(-1)  # Loop indefinitely
                                self.music_playing = True

                                output = f"Started playing {filename}"
                            else:
                                output = f"ERROR: File {filename} not found"
                                print(f"❌ {output}")
                        except Exception as e:
                            output = f"ERROR: {str(e)}"
                            print(f"❌ Error playing music: {e}")

                        # Send function result
                        function_output = {
                            "type": "conversation.item.create",
                            "item": {
                                "type": "function_call_output",
                                "call_id": call_id,
                                "output": output
                            }
                        }
                        await self.websocket.send(json.dumps(function_output))

                        # Trigger response
                        response_create = {"type": "response.create"}
                        await self.websocket.send(json.dumps(response_create))

                    if function_name == "look_at_camera":
                        print("📷 Looking at camera...")

                        # Capture frame
                        image_b64 = await self.capture_frame()

                        if image_b64:
                            print("👁️  Captured image, sending to model...")

                            # Complete the function call first
                            function_output = {
                                "type": "conversation.item.create",
                                "item": {
                                    "type": "function_call_output",
                                    "call_id": call_id,
                                    "output": "Camera image captured successfully"
                                }
                            }
                            await self.websocket.send(json.dumps(function_output))

                            # Add image as a user message in conversation
                            image_message = {
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
                            }
                            await self.websocket.send(json.dumps(image_message))

                            # Trigger response
                            response_create = {"type": "response.create"}
                            await self.websocket.send(json.dumps(response_create))
                        else:
                            print("❌ Failed to capture frame")
                            error_output = {
                                "type": "conversation.item.create",
                                "item": {
                                    "type": "function_call_output",
                                    "call_id": call_id,
                                    "output": "ERROR: Failed to capture camera frame. You must acknowledge this error and tell the user you cannot see the camera right now."
                                }
                            }
                            await self.websocket.send(json.dumps(error_output))

                            # Trigger response
                            response_create = {"type": "response.create"}
                            await self.websocket.send(json.dumps(response_create))

                elif event_type == "response.audio_transcript.delta":
                    delta = event.get("delta", "")
                    if delta:
                        print(delta, end="", flush=True)

                elif event_type == "response.audio_transcript.done":
                    transcript = event.get("transcript", "")
                    print(f"\n💬 Franky: {transcript}")

                elif event_type == "response.audio.delta":
                    audio_b64 = event.get("delta", "")
                    if audio_b64:
                        audio_chunk = base64.b64decode(audio_b64)
                        # Add to queue instead of blocking write
                        await audio_queue.put(audio_chunk)

                elif event_type == "response.audio.done":
                    print("🔊 Response complete\n" + "="*50 + "\n")

                elif event_type == "error":
                    error = event.get("error", {})
                    error_code = error.get("code", "")

                    if error_code == "input_image_safety_violation":
                        print(f"⚠️  Image rejected by safety system - possibly too dark/blurry")
                        # Don't try to create new response, just log it
                        # The bot will respond based on the function call output that was already sent
                    elif error_code == "conversation_already_has_active_response":
                        # This is expected, ignore it
                        pass
                    else:
                        print(f"❌ Error: {error}")

        except asyncio.CancelledError:
            # Stop playback task gracefully
            await audio_queue.put(None)  # Send sentinel to stop playback task
            await playback_task

            if self.output_stream:
                self.output_stream.stop_stream()
                self.output_stream.close()
            raise
        except Exception as e:
            print(f"Connection closed: {e}")
        finally:
            # Cleanup on any exit
            try:
                await audio_queue.put(None)
                await playback_task
            except:
                pass

            if self.output_stream:
                try:
                    self.output_stream.stop_stream()
                    self.output_stream.close()
                except:
                    pass

    async def run(self):
        """Main bot loop with auto-reconnect"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "OpenAI-Beta": "realtime=v1"
        }

        print("🚀 Starting Franky Voice Bot...")
        print(f"📹 Camera: {self.camera_url}")
        print("Press Ctrl+C to exit\n")

        retry_count = 0
        max_retries = 5
        retry_delay = 2

        while retry_count < max_retries:
            send_task = None
            receive_task = None

            try:
                if retry_count > 0:
                    print(f"🔄 Reconnecting... (attempt {retry_count + 1}/{max_retries})")
                    await asyncio.sleep(retry_delay)

                async with connect(self.url, additional_headers=headers) as ws:
                    self.websocket = ws

                    # Reset retry count on successful connection
                    retry_count = 0

                    # Setup session
                    await self.setup_session()

                    # Wait a moment for session to be ready
                    await asyncio.sleep(0.5)

                    # Run send and receive concurrently
                    send_task = asyncio.create_task(self.send_audio())
                    receive_task = asyncio.create_task(self.receive_messages())

                    await asyncio.gather(send_task, receive_task)

            except KeyboardInterrupt:
                print("\n👋 Shutting down gracefully...")

                # Cancel all tasks
                if send_task and not send_task.done():
                    send_task.cancel()
                if receive_task and not receive_task.done():
                    receive_task.cancel()

                # Wait for tasks to finish cancellation
                if send_task:
                    try:
                        await send_task
                    except asyncio.CancelledError:
                        pass
                if receive_task:
                    try:
                        await receive_task
                    except asyncio.CancelledError:
                        pass
                break

            except Exception as e:
                print(f"⚠️  Connection error: {e}")
                retry_count += 1

                if retry_count >= max_retries:
                    print(f"❌ Max retries ({max_retries}) reached. Exiting.")
                    break

                # Cancel tasks if they exist
                if send_task and not send_task.done():
                    send_task.cancel()
                if receive_task and not receive_task.done():
                    receive_task.cancel()

                try:
                    if send_task:
                        await send_task
                except:
                    pass
                try:
                    if receive_task:
                        await receive_task
                except:
                    pass

        # Cleanup resources
        try:
            if self.mqtt_client:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
            if self.camera:
                self.camera.release()
            if self.audio:
                self.audio.terminate()
            if self.music_playing:
                pygame.mixer.music.stop()
            print("✅ Cleanup complete")
        except Exception as e:
            print(f"Error during cleanup: {e}")

if __name__ == "__main__":
    bot = RealtimeVoiceBot()
    asyncio.run(bot.run())
