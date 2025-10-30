# 🚀 Quick Start Guide (macOS)

Get Franky running in 5 minutes on your Mac!

---

## Prerequisites

- **macOS** 10.15 or later
- **Python 3.9+** (comes with macOS)
- **OpenAI API Key** ([get one here](https://platform.openai.com/api-keys))
- **ESP32 device** (optional, can test with computer mic/speakers first)

---

## Step 1: Clone Repository

```bash
cd ~/Projects  # or any directory you prefer
git clone https://github.com/menemy/franky.git
cd franky
```

---

## Step 2: Setup Python Environment

Use macOS built-in Python:

```bash
# Check Python version (should be 3.9+)
python3 --version

# Install dependencies
pip3 install -r requirements.txt
```

**If you get permission errors:**
```bash
# Use user install (no sudo needed)
pip3 install --user -r requirements.txt
```

**Alternative: Use virtual environment (recommended)**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## Step 3: Configure Environment

We have 3 preset configurations:

### Preset 1: Local Testing (Recommended for first run)

**No hardware needed - just Python on your Mac!**

```bash
cp .env.example.local .env
```

Then edit and add your OpenAI API key:
```bash
nano .env  # or use: open -e .env
```

Replace `YOUR_API_KEY_HERE` with your actual key.

### Preset 2: Minimal (Just API key)

```bash
cp .env.example.minimal .env
nano .env  # Add your API key
```

### Preset 3: Full Setup (All hardware)

```bash
cp .env.example.full .env
nano .env  # Configure all devices
```

**Minimum required:** Only `OPENAI_API_KEY` is needed to start!

Press `Ctrl+X`, then `Y`, then `Enter` to save in nano.

---

## Step 4: Test Audio

Make sure your Mac audio works:

```bash
# Check audio devices
python3 -c "import pyaudio; p = pyaudio.PyAudio(); print([p.get_device_info_by_index(i)['name'] for i in range(p.get_device_count())])"
```

**Set correct audio device:**
- Open **System Settings** → **Sound**
- Set **Input**: Built-in Microphone (or external USB mic)
- Set **Output**: Built-in Speakers (or external speakers)

---

## Step 5: Run Franky!

### Option A: Test with Mac Speakers (No ESP32 needed)

**Use the integrated speaker mode:**

```bash
python3 franky.py --output speakers --no-camera --no-mqtt
```

This will:
- ✅ Connect to OpenAI Realtime API
- ✅ Use your Mac's microphone
- ✅ Play audio through Mac speakers
- ✅ Skip all hardware (camera, MQTT, ESP32)

**Perfect for testing the AI and voice system before building hardware!**

### Option B: With ESP32 Hardware

Make sure ESP32 is:
1. Powered on
2. Connected to same WiFi network
3. Firmware uploaded (see `devices/README.md`)

Then run:
```bash
python3 franky.py
```

You should see:
```
🎃 Franky Voice Bot - ESP32 UDP Edition
============================================================
ESP32 IP: 192.168.1.101
UDP RX Port: 5001 (listening for mic)
UDP TX Port: 5002 (sending to speaker)
MQTT Broker: 192.168.1.100:1883
Camera: Not configured
Music files: 0
============================================================
✅ MQTT connected
🎯 ESP32 detected at 192.168.1.101
```

---

## ⚙️ Configuration Options

Franky now supports flexible configuration via CLI arguments:

```bash
# Test without any hardware (local speakers + mic)
python3 franky.py --output speakers --no-camera --no-mqtt

# Use ESP32 audio only, disable jaw and camera
python3 franky.py --no-jaw --no-camera

# Disable conversation logging (enabled by default)
python3 franky.py --no-log-conversation

# Custom network configuration
python3 franky.py --esp32-ip 192.168.1.50 --mqtt-server 192.168.1.100
```

**Key options:**
- `--output speakers` - Use Mac speakers instead of ESP32
- `--no-camera` - Disable camera vision
- `--no-mqtt` - Disable MQTT (jaw/eyes control)
- `--no-jaw` - Keep jaw still
- `--no-eyes` - Disable LED eyes
- `--log-conversation` / `--no-log-conversation` - Conversation logging (default: enabled)

See [README.md](README.md#⚙️-configuration-options) for full list.

---

## 🎤 Using Different Voices

Franky supports multiple AI voices:

```bash
# Default voice (ash)
python3 franky.py

# Deep mysterious voice
python3 franky.py --voice echo

# Ethereal ghostly voice
python3 franky.py --voice shimmer

# High-pitched witch voice
python3 franky.py --voice ballad
```

**Available voices:** `alloy`, `ash`, `ballad`, `coral`, `echo`, `sage`, `shimmer`, `verse`, `marin`, `cedar`

---

## 🎵 Adding Background Music

1. **Get some spooky music:**
   - Download Halloween music MP3s
   - Or use royalty-free tracks from [FreePD](https://freepd.com/)

2. **Add to sounds folder:**
   ```bash
   # Create sounds folder if it doesn't exist
   mkdir -p sounds

   # Copy your MP3 files
   cp ~/Downloads/spooky_theme.mp3 sounds/
   cp ~/Downloads/creepy_ambience.mp3 sounds/
   ```

3. **Bot will auto-detect them:**
   ```
   🎵 Loaded 2 sound files
   ```

4. **Franky can play them during conversation!**
   - Just ask: "Play some spooky music"
   - Or: "Stop the music"

---

## 🐛 Common Issues

### Issue: `ModuleNotFoundError: No module named 'pyaudio'`

PyAudio needs system dependencies on Mac:

```bash
# Install Homebrew if not already installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install PortAudio
brew install portaudio

# Reinstall pyaudio
pip3 install --upgrade --force-reinstall pyaudio
```

### Issue: `Permission denied` for microphone

macOS needs permission:

1. **System Settings** → **Privacy & Security** → **Microphone**
2. Enable **Terminal** or **iTerm**
3. Restart terminal and try again

### Issue: `Connection refused` to OpenAI API

Check your API key:
```bash
# Verify .env file
cat .env | grep OPENAI_API_KEY

# Test API key
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $(grep OPENAI_API_KEY .env | cut -d '=' -f2)"
```

If you see models list - your key works! ✅

### Issue: No sound output

Check volume:
```bash
# Check system volume
osascript -e "output volume of (get volume settings)"

# Set volume to 50%
osascript -e "set volume output volume 50"
```

### Issue: ESP32 not detected

```bash
# Check if ESP32 is sending packets
sudo tcpdump -i en0 udp port 5001

# Check WiFi network
networksetup -getairportnetwork en0

# Ping ESP32
ping 192.168.1.101
```

---

## 🔧 Optional: Install MQTT for Testing

If you want to test jaw/LED control:

```bash
# Install Mosquitto (MQTT broker and client)
brew install mosquitto

# Start MQTT broker
brew services start mosquitto

# Test publishing commands
mosquitto_pub -h localhost -t "franky/jaw" -m "100"
mosquitto_pub -h localhost -t "franky/eyes" -m "1"
```

---

## 🎯 Next Steps

### Learn More
- Read full [README.md](README.md) for detailed documentation
- Check [DIY Build Guide](devices/xiao_esp32_respeaker/DIY_GUIDE.md) to build hardware
- Upload [ESP32 Firmware](devices/README.md) for full features

### Customize Franky
- Edit system prompt in `franky.py` (line ~157)
- Adjust audio effects (reverb, pitch shift)
- Add custom mini-games
- Create multilingual responses

### Troubleshooting
- Enable debug mode: Add `print()` statements
- Check logs: Bot prints all events
- Test components separately (mic, speaker, MQTT)

---

## 📺 Demo Video

Watch Franky in action: [Coming Soon]

---

## 🆘 Need Help?

- **Issues**: [GitHub Issues](https://github.com/menemy/franky/issues)
- **Discussions**: [GitHub Discussions](https://github.com/menemy/franky/discussions)
- **Email**: Create an issue and we'll respond!

---

## 🎃 Quick Commands Reference

```bash
# Start Franky
python3 franky.py

# Different voice
python3 franky.py --voice echo

# Test jaw (MQTT)
mosquitto_pub -h localhost -t "franky/jaw" -m "100"

# Test eyes (MQTT)
mosquitto_pub -h localhost -t "franky/eyes" -m "1"

# Stop everything
Ctrl+C
```

---

**Happy Haunting! 🎃💀**

*Any questions? Just ask - Franky loves to help!*
