# 🎃 Franky DIY Build Guide

Complete step-by-step guide to build your own AI-powered talking skull.

---

## 📦 Parts List

### Required Electronics

| Item | Link | Price (approx) |
|------|------|----------------|
| **XIAO ESP32-S3** | [Seeed Studio](https://www.seeedstudio.com/XIAO-ESP32S3-p-5627.html) | $6-8 |
| **ReSpeaker 4-Mic Array** | [Seeed Studio](https://www.seeedstudio.com/ReSpeaker-4-Mic-Array-for-Raspberry-Pi.html) | $15-20 |
| **Relay Module** (1-channel, 5V) | AliExpress/Amazon | $2-5 |
| **LED Strip** or individual LEDs | Any color (red/orange for eyes) | $3-5 |
| **Jumper Wires** | Female-to-female, male-to-female | $5 |
| **USB-C Cable** | For ESP32-S3 programming | $3 |

**Total electronics cost:** ~$35-50

### Mechanical Parts (Option A: Halloween Animatronic)

**Buy a cheap Halloween animatronic skull** - extract the motor and LEDs:
- [Temu Animatronic Skull](https://www.temu.com/goods_snapshot.html?goods_id=601102810850226) (~$15-25)
- Or any Halloween decoration with moving jaw/mouth
- Or search "animated skull" on Amazon/AliExpress

**What to salvage:**
- ✅ **DC Motor** (for jaw movement) - usually 3-6V
- ✅ **LED eyes** (or light sockets)
- ✅ **Battery compartment** (optional, for power reference)
- ✅ **Skull housing** (the plastic skull itself)
- ❌ Remove: Original electronics, sound module, sensors

### Mechanical Parts (Option B: DIY from Scratch)

If you want to build from scratch:
- **3D printed skull** or store-bought plastic skull
- **Small DC motor** (3-6V, 0.5A) for jaw movement
- **2x LEDs** (5mm or 10mm) for eyes
- **Servo or linkage** to connect motor to jaw
- **Resistors** (220Ω for LEDs)

---

## 🔧 Assembly Steps

### Step 1: Disassemble the Animatronic

1. **Open the skull** (usually screws on the back or bottom)
2. **Locate the motor** - it's connected to the jaw mechanism
3. **Remove original circuit board** - carefully desolder or cut wires
4. **Keep these parts:**
   - Motor with gear mechanism
   - LED wires/sockets
   - Jaw linkage/rod
   - Battery compartment (for reference)

**⚠️ Take photos before disassembly!** You'll need to remember how the jaw mechanism works.

### Step 2: Wire the Motor to Relay

The relay acts as a switch controlled by ESP32 to move the jaw.

```
ESP32 D2 (GPIO3) ──→ Relay IN
ESP32 GND ──→ Relay GND
ESP32 5V ──→ Relay VCC

Motor (+) ──→ Relay NO (Normally Open)
Motor (-) ──→ External Power GND
External Power (+3-6V) ──→ Relay COM
```

**Power source for motor:**
- Option A: Use original battery compartment (2-4 AA batteries)
- Option B: USB power bank (use step-down converter if needed)
- Option C: Separate 5V power supply

**⚠️ Do NOT power motor directly from ESP32!** It will damage the board.

### Step 3: Wire the LEDs to ESP32

LED eyes controlled directly by ESP32.

```
ESP32 D0 (GPIO1) ──→ LED+ (through 220Ω resistor)
LED- ──→ ESP32 GND
```

For 2 LEDs in parallel:
```
ESP32 D0 ──→ Resistor 220Ω ──┬──→ LED1+ ──→ GND
                              └──→ LED2+ ──→ GND
```

**LED colors:**
- Red/Orange: Classic spooky eyes
- Green: Zombie/monster theme
- RGB LEDs: Programmable color changes

### Step 4: Connect ReSpeaker to ESP32

ReSpeaker connects via I2S and I2C.

| ReSpeaker Pin | ESP32-S3 Pin | Description |
|---------------|--------------|-------------|
| **VCC** | 3.3V | Power |
| **GND** | GND | Ground |
| **SCL** | GPIO6 | I2C Clock (XMOS control) |
| **SDA** | GPIO5 | I2C Data (XMOS control) |
| **BCLK** | GPIO8 | I2S Bit Clock |
| **LRCLK/WS** | GPIO7 | I2S Word Select |
| **DIN** | GPIO43 | I2S Data In (mic) |
| **DOUT** | GPIO44 | I2S Data Out (speaker) |

**⚠️ Power:**
- ReSpeaker needs 3.3V (NOT 5V!)
- ESP32-S3 provides 3.3V output pin

**Mounting tip:** Use hot glue or double-sided tape to secure ReSpeaker inside skull's forehead area.

### Step 5: Final Assembly

1. **Mount ESP32** inside skull (hot glue or velcro)
2. **Position ReSpeaker** facing forward (towards mouth opening)
3. **Route wires neatly** (use zip ties or twist ties)
4. **Secure relay module** away from moving parts
5. **Install LEDs in eye sockets**
6. **Test jaw movement** before closing skull
7. **Close and secure skull housing**

**Cable management:**
- Leave USB-C port accessible for programming
- Cut a small slot for power cable exit
- Use cable clips inside skull to prevent tangling

---

## 🔌 Wiring Diagram

```
                           ESP32-S3 XIAO
                         ┌──────────────┐
                         │              │
    ReSpeaker ───I2S────▶│ GPIO 7,8     │
    (4-Mic Array) I2C────▶│ GPIO 5,6     │
                         │ GPIO 43,44   │
                         │              │
    Relay Module ────────▶│ D2 (GPIO3)   │──→ Motor
                         │              │
    LED Eyes ────────────▶│ D0 (GPIO1)   │──→ LEDs
                         │              │
    USB-C Power ─────────▶│ 5V, GND      │
                         └──────────────┘
```

**Power distribution:**
- ESP32: Powered via USB-C (5V)
- ReSpeaker: Powered from ESP32 3.3V pin
- Motor: Powered separately (3-6V batteries or external supply)
- LEDs: Powered from ESP32 GPIO (with resistor!)

---

## 💡 Tips & Tricks

### Motor Control

The firmware uses **amplitude-based jaw movement**:
- Loud sound = wide jaw opening
- Soft sound = small jaw opening
- Silence = jaw closed

**If jaw movement is reversed:**
- Swap motor polarity (+ and - wires)

**If jaw is too fast/slow:**
- Adjust `JAW_DURATION` in firmware (default 100ms)
- Change relay switching frequency

### Audio Quality

**Microphone placement:**
- Face forward, towards where people will stand
- Keep away from speakers (prevents echo)
- At least 20cm from mouth opening

**Speaker setup:**
- Internal speaker: Mount inside skull
- External speaker: Position near skull
- Volume: 50% recommended for AEC to work properly

### Power Management

**Battery life (with 4x AA batteries):**
- Standby: ~24 hours
- Active talking: ~4-6 hours
- LED only: ~12 hours

**Power-saving tips:**
- Turn off LEDs when idle
- Lower WiFi TX power in firmware
- Use sleep mode between interactions

### Troubleshooting

**Motor doesn't move:**
1. Check relay LED - should blink when talking
2. Verify motor voltage (use multimeter)
3. Test motor directly with batteries
4. Check relay wiring (NO vs NC terminals)

**No microphone input:**
1. Check ReSpeaker power LED
2. Verify I2S pin connections
3. Test with serial monitor: `info` command
4. Check I2C communication: `i2cdetect`

**LEDs don't light:**
1. Check resistor value (220Ω for 5V)
2. Test LED polarity (swap + and -)
3. Measure GPIO voltage (should be 3.3V HIGH)
4. Try blinking LED from serial: `gpio 1 1`

---

## 🎨 Customization Ideas

### Advanced Features

**Add more outputs:**
- D1 (GPIO2): Second relay for head turning
- D3 (GPIO4): Third relay for arm movement
- D4 (GPIO5): RGB LED strip for ambient effects

**Sensor additions:**
- PIR motion sensor: Auto-trigger on approach
- Distance sensor: Adjust volume based on proximity
- Light sensor: Nighttime-only activation

**Visual upgrades:**
- RGB eyes with color animation
- LED strips inside mouth
- UV reactive paint
- Fog machine trigger
- Strobe lights for jump scares

### Character Themes

**Classic Skull:**
- Red LED eyes
- Deep voice (pitch shift DOWN)
- Heavy reverb

**Friendly Ghost:**
- Blue/white LED eyes
- Normal voice
- Light echo effect

**Evil Demon:**
- Orange/yellow flickering LEDs
- Very deep voice + distortion
- Multiple jaw movements (stutter effect)

**Witch:**
- Green LED eyes
- High-pitched voice (pitch shift UP)
- Cackling sound effects

---

## 📸 Build Photos

**Recommended photo documentation:**
1. Original animatronic (before disassembly)
2. Internal mechanism layout
3. Motor and linkage system
4. Wiring before final assembly
5. Completed installation
6. Final assembled skull

**Share your build:**
- Post in GitHub Discussions
- Tag @menemy on social media
- Include video of it working!

---

## ⚠️ Safety Warnings

1. **Never connect motor directly to ESP32** - always use relay
2. **Use correct voltage for motor** - check original power rating
3. **Add resistors to LEDs** - 220Ω minimum to prevent burnout
4. **Insulate all connections** - use heat shrink or electrical tape
5. **Keep wires away from moving parts** - prevent snagging
6. **Secure hot glue properly** - avoid loose components
7. **Test outside skull first** - verify everything works before assembly

---

## 🎯 Next Steps

After hardware assembly:

1. **Flash firmware**: See [main README](../README.md)
2. **Configure WiFi**: Edit credentials in .ino file
3. **Test hardware**: Use serial commands to verify motor/LEDs
4. **Run Python bot**: Follow setup in main README
5. **Customize prompt**: Edit personality in voice_bot code
6. **Add music files**: Drop MP3s in `sounds/` folder
7. **Tune audio effects**: Experiment with reverb/pitch shift

**Need help?** Open an issue on GitHub!

---

## 📚 Additional Resources

- [ESP32-S3 Pinout](https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/)
- [ReSpeaker Documentation](https://wiki.seeedstudio.com/ReSpeaker_4_Mic_Array_for_Raspberry_Pi/)
- [Arduino ESP32 Core](https://github.com/espressif/arduino-esp32)
- [Relay Module Guide](https://arduinomodules.info/ky-019-5v-relay-module/)
- [LED Resistor Calculator](https://www.digikey.com/en/resources/conversion-calculators/conversion-calculator-led-series-resistor)

---

**Happy Building! 🎃💀⚡**

*Made with love for the maker community*
