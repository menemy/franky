/*
 * Franky - XIAO ESP32-S3 ReSpeaker Audio Streaming
 * I2S: 32-bit (XMOS with AEC/AGC/beamforming) → UDP: 16-bit (fits MTU)
 * DC Motor control via relay on D2
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <WiFiUdp.h>
#include "AudioTools.h"
#include <Wire.h>
#include <math.h>

// WiFi credentials
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// Server IP (computer running Python bot)
const char* server_ip = "192.168.1.100";

// UDP ports for audio
const int udp_port_send = 5001;      // ESP32 sends mic audio to this port
const int udp_port_receive = 5002;   // ESP32 receives speaker audio on this port

// MQTT settings (only for control)
const char* mqtt_server = "192.168.2.248";
const int mqtt_port = 1883;
const char* mqtt_topic_jaw = "franky/jaw";
const char* mqtt_topic_eyes = "franky/eyes";
const char* mqtt_topic_volume = "esp32/volume";
const char* mqtt_topic_ip = "franky/esp32/ip";
// Direct GPIO control
const char* mqtt_topic_gpio = "franky/gpio";  // franky/gpio <pin> <state> <inverted>
const char* mqtt_client_id = "franky_xiao_esp32";

// XMOS I2C settings
const int XMOS_I2C_ADDR = 0x2C;
const int I2C_SDA = 5;  // GPIO5 for SDA
const int I2C_SCL = 6;  // GPIO6 for SCL

// AIC3104 Audio Codec I2C settings (for volume control)
const int AIC3104_ADDR = 0x18;
const uint8_t AIC3104_LEFT_DAC_VOLUME = 0x2B;
const uint8_t AIC3104_RIGHT_DAC_VOLUME = 0x2C;
const uint8_t AIC3104_HPLOUT_LEVEL = 0x33;
const uint8_t AIC3104_HPROUT_LEVEL = 0x3A;
const uint8_t AIC3104_LEFT_LOP_LEVEL = 0x56;
const uint8_t AIC3104_RIGHT_LOP_LEVEL = 0x5D;

// Audio settings
const int sample_rate = 16000;
const int channels = 2;
const int bits_i2s = 32;  // XMOS outputs 32-bit I2S (with AEC/AGC/beamforming applied)
const int bits_udp = 16;  // Convert to 16-bit for UDP transmission (avoid MTU fragmentation)

// Volume control (0.0 to 1.0)
volatile float speaker_volume = 0.2;  // Start at 20%

// Audio frames: mic TX uses 40ms (16-bit mono LEFT channel = AEC), speaker RX uses 40ms (16-bit mono)
const int FRAME_MS_TX = 40;  // Mic TX: 40ms mono 16-bit (fits MTU)
const int FRAME_MS_RX = 40;  // Speaker RX: 40ms for smoother playback

const int FRAME_SAMPLES_TX = (sample_rate * FRAME_MS_TX) / 1000;  // 640 samples (40ms)
const int FRAME_SAMPLES_RX = (sample_rate * FRAME_MS_RX) / 1000;  // 640 samples (40ms)

const int FRAME_BYTES_I2S_STEREO = FRAME_SAMPLES_TX * (bits_i2s / 8) * 2; // 5120 bytes 32-bit stereo I2S (40ms mic)
const int FRAME_BYTES_UDP_MONO_TX = FRAME_SAMPLES_TX * (bits_udp / 8) * 1; // 1280 bytes 16-bit mono UDP (40ms mic - LEFT channel converted)
const int FRAME_BYTES_UDP_MONO_RX = FRAME_SAMPLES_RX * (bits_udp / 8) * 1;   // 1280 bytes 16-bit mono UDP (40ms speaker)

// ==== Mic channel selection & anti-clipping (adaptive) ====
// XVF3800 outputs audio in 32-bit I2S slots. Nominal downshift to 16-bit is >>16 (Q1.31).
// If your build is 24-bit left-justified, set MIC_BASE_SHIFT=8.
static int MIC_BASE_SHIFT = 16;
static volatile int mic_extra_shift_bits = 2; // start with ~-12 dB headroom
static const int MIC_SHIFT_MIN = 0, MIC_SHIFT_MAX = 4;
static const int MIC_PEAK_HI = 30000, MIC_PEAK_LO = 9000; // target window ~9k..30k
static const int MIC_ADAPT_FRAMES = 25; // adapt every ~1s (25*40ms)
static const bool MIC_LIMITER_ON = true;
static const int16_t MIC_LIMIT_TH = 30000; // knee
static const int16_t MIC_LIMIT_RATIO_NUM = 1;  // 1/5 over-threshold
static const int16_t MIC_LIMIT_RATIO_DEN = 5;
static volatile int mic_channel_select = 0; // 0=LEFT (AEC-processed), 1=RIGHT (raw)
static uint32_t mic_frame_counter = 0;

// UDP TX buffer for mono 16-bit conversion
uint8_t tx_buffer_mono[FRAME_BYTES_UDP_MONO_TX];  // 16-bit mono (LEFT channel converted)

// UDP packet header
struct __attribute__((packed)) UdpPacketHeader {
  uint8_t type;           // Packet type (0x01 for audio)
  uint8_t flags;          // Flags
  uint16_t payload_len;   // Payload length in bytes
  uint32_t ssrc;          // Synchronization source identifier
  uint32_t timestamp;     // Timestamp (milliseconds)
  uint32_t sequence;      // Sequence number
};

const int HEADER_SIZE = sizeof(UdpPacketHeader);
const int UDP_TX_PACKET_SIZE = HEADER_SIZE + FRAME_BYTES_UDP_MONO_TX;  // Mic: send 32-bit mono LEFT (1296 bytes = 20ms)
const int UDP_RX_PACKET_SIZE = HEADER_SIZE + FRAME_BYTES_UDP_MONO_RX;  // Speaker: receive 16-bit mono (1296 bytes = 40ms)

// I2S - single duplex stream
I2SStream i2s;

// UDP
WiFiUDP udpTx;
WiFiUDP udpRx;

// MQTT
WiFiClient espClient;
PubSubClient mqtt_client(espClient);

// ==== Hardware Control Configuration ====
// Skull Eyes LEDs on D0 (GPIO1)
const int LED_EYES = 1;  // D0 (GPIO1)
const bool LED_INVERTED = false;  // false = HIGH turns LED ON (normal: D0→LED→GND)
bool eyes_state = false;

// DC Motor via Relay on D2 (GPIO3)
const int RELAY_PIN = 3;  // D2 (GPIO3)
const bool RELAY_INVERTED = false;  // false = HIGH turns relay ON (active-high)
bool relay_state = false;

// Helper macros for inverted logic
#define RELAY_ON  (RELAY_INVERTED ? LOW : HIGH)
#define RELAY_OFF (RELAY_INVERTED ? HIGH : LOW)
#define LED_ON    (LED_INVERTED ? LOW : HIGH)
#define LED_OFF   (LED_INVERTED ? HIGH : LOW)

// Jaw pulse timing (non-blocking)
unsigned long jaw_pulse_start = 0;
int jaw_pulse_duration = 0;
bool jaw_pulse_active = false;

// Jitter buffer for RTP-style playback
struct JitterFrame {
  uint32_t seq;
  uint8_t data[FRAME_BYTES_UDP_MONO_RX];
};

JitterFrame jitter_buffer[48];  // Circular buffer (960ms max)
int jitter_count = 0;           // Number of frames in buffer
uint32_t next_play_seq = 0;     // Next sequence to play
bool playback_started = false;
const int PREFILL_FRAMES = 5;  // 200ms prefill (5 * 40ms)

// Last frame for PLC
uint8_t last_frame[FRAME_BYTES_UDP_MONO_RX];
bool has_last_frame = false;

// Debug counters
volatile uint32_t queue_underruns = 0;
volatile uint32_t total_packets_received = 0;
volatile uint32_t plc_count = 0;
volatile uint32_t consecutive_plc = 0;
const uint32_t MAX_CONSECUTIVE_PLC = 25;  // Stop playback after 1 second of PLC (25 * 40ms)

struct AudioChunk {
  uint8_t data[FRAME_BYTES_UDP_MONO_RX];    // 16-bit mono frame (1280 B = 40ms)
  size_t length;                            // should be FRAME_BYTES_UDP_MONO_RX
};

// Buffers
uint8_t tx_accum_i2s[FRAME_BYTES_I2S_STEREO];  // 32-bit I2S accumulator (also used as UDP send buffer - RAW)
size_t tx_accum_used = 0;

// Sequence tracking
uint32_t tx_sequence = 0;
const uint32_t ssrc = 0xFAAC01;

// No ducking - removed to prevent audio manipulation

// AIC3104 register write
void aic3104_reg_write(uint8_t reg, uint8_t val) {
  Wire.beginTransmission(AIC3104_ADDR);
  Wire.write(reg);
  Wire.write(val);
  Wire.endTransmission();
}

// Set hardware volume via AIC3104 codec
// vol: 0.0 to 1.0 (maps to 0-17 levels internally)
void setHardwareVolume(float vol) {
  // Map 0.0-1.0 to 0-17 levels
  int level = (int)(vol * 17.0);
  level = constrain(level, 0, 17);

  if (level <= 8) {
    // DAC attenuation (0dB to -72dB in 9dB steps)
    uint8_t dacVal = level * 9;
    aic3104_reg_write(AIC3104_LEFT_DAC_VOLUME, dacVal);
    aic3104_reg_write(AIC3104_RIGHT_DAC_VOLUME, dacVal);

    // Fixed output levels at 0dB
    aic3104_reg_write(AIC3104_HPLOUT_LEVEL, 0x0D);
    aic3104_reg_write(AIC3104_HPROUT_LEVEL, 0x0D);
    aic3104_reg_write(AIC3104_LEFT_LOP_LEVEL, 0x0B);
    aic3104_reg_write(AIC3104_RIGHT_LOP_LEVEL, 0x0B);
  } else {
    // DAC at 0dB, boost output gain (+1 to +9 dB)
    aic3104_reg_write(AIC3104_LEFT_DAC_VOLUME, 0x00);
    aic3104_reg_write(AIC3104_RIGHT_DAC_VOLUME, 0x00);

    uint8_t gain = (level - 8); // +1 to +9 dB
    uint8_t outVal = (gain << 4) | 0x0B; // Set gain and power/mute bits

    // Use line out (LOP)
    aic3104_reg_write(AIC3104_LEFT_LOP_LEVEL, outVal);
    aic3104_reg_write(AIC3104_RIGHT_LOP_LEVEL, outVal);
  }

  Serial.print("🔊 Hardware volume: ");
  Serial.print((int)(vol * 100));
  Serial.print("% (level ");
  Serial.print(level);
  Serial.println("/17)");
}

void i2c_scan() {
  Serial.println("I2C scan start...");
  byte count = 0;
  for (byte address = 1; address < 127; address++) {
    Wire.beginTransmission(address);
    byte error = Wire.endTransmission();
    if (error == 0) {
      Serial.printf("  ✓ device at 0x%02X\n", address);
      count++;
    } else if (error == 4) {
      Serial.printf("  ? unknown error at 0x%02X\n", address);
    }
  }
  if (count == 0) Serial.println("  (no I2C devices found)");
  Serial.println("I2C scan done.");
}

void setup_wifi() {
  Serial.print("Connecting to WiFi: ");
  Serial.println(ssid);

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  WiFi.setSleep(false);
  WiFi.setTxPower(WIFI_POWER_19_5dBm);

  Serial.println("\nWiFi connected");
  Serial.print("IP: ");
  Serial.println(WiFi.localIP());
}

void mqtt_callback(char* topic, byte* payload, unsigned int length) {
  if (strcmp(topic, mqtt_topic_jaw) == 0) {
    // Parse pulse duration from payload (in milliseconds)
    String value = "";
    for (unsigned int i = 0; i < length; i++) {
      value += (char)payload[i];
    }
    int pulse_duration_ms = value.toInt();

    // Default to 100ms if invalid value
    if (pulse_duration_ms <= 0 || pulse_duration_ms > 5000) {
      pulse_duration_ms = 100;
    }

    Serial.print("💀 Skull trigger: ");
    Serial.print(pulse_duration_ms);
    Serial.println("ms pulse");

    // Start non-blocking pulse
    jaw_pulse_start = millis();
    jaw_pulse_duration = pulse_duration_ms;
    jaw_pulse_active = true;

    // Trigger pulse: relay + eyes ON
    digitalWrite(RELAY_PIN, RELAY_ON);
    digitalWrite(LED_EYES, LED_ON);
    relay_state = true;
    eyes_state = true;
  } else if (strcmp(topic, mqtt_topic_eyes) == 0) {
    // Parse eye state from payload (0 = OFF, 1 = ON)
    String value = "";
    for (unsigned int i = 0; i < length; i++) {
      value += (char)payload[i];
    }
    int state = value.toInt();

    if (state > 0) {
      // Turn eyes ON
      digitalWrite(LED_EYES, LED_ON);
      eyes_state = true;
      Serial.println("👁️  Eyes ON");
    } else {
      // Turn eyes OFF
      digitalWrite(LED_EYES, LED_OFF);
      eyes_state = false;
      Serial.println("👁️  Eyes OFF");
    }
  } else if (strcmp(topic, mqtt_topic_volume) == 0) {
    // Parse volume value (0.0 to 1.0)
    String value = "";
    for (unsigned int i = 0; i < length; i++) {
      value += (char)payload[i];
    }
    float vol = value.toFloat();

    // Clamp between 0.0 and 1.0
    if (vol < 0.0) vol = 0.0;
    if (vol > 1.0) vol = 1.0;

    speaker_volume = vol;

    // Set hardware volume via AIC3104 codec
    setHardwareVolume(vol);
  } else if (strcmp(topic, mqtt_topic_gpio) == 0) {
    // Direct GPIO control: franky/gpio <pin> <state> [inverted]
    // Example: "1 1" = D0 HIGH, "1 0" = D0 LOW, "1 1 inv" = D0 LOW (inverted)
    String value = "";
    for (unsigned int i = 0; i < length; i++) {
      value += (char)payload[i];
    }

    // Parse: pin state [inverted]
    int pin = -1;
    int state = -1;
    bool inverted = false;

    int space1 = value.indexOf(' ');
    if (space1 > 0) {
      pin = value.substring(0, space1).toInt();
      int space2 = value.indexOf(' ', space1 + 1);
      if (space2 > 0) {
        state = value.substring(space1 + 1, space2).toInt();
        String inv_str = value.substring(space2 + 1);
        inv_str.trim();
        if (inv_str == "inv" || inv_str == "inverted" || inv_str == "1") {
          inverted = true;
        }
      } else {
        state = value.substring(space1 + 1).toInt();
      }
    }

    // Validate pin (only D0, D2, D3)
    if (pin == 1 || pin == 2 || pin == 3) {
      // Setup pin as output if not already
      pinMode(pin, OUTPUT);

      // Apply state (with optional inversion)
      int actual_state = inverted ? !state : state;
      digitalWrite(pin, actual_state ? HIGH : LOW);

      Serial.printf("🔧 GPIO D%d = %s (requested: %d, inverted: %s)\n",
        pin,
        actual_state ? "HIGH" : "LOW",
        state,
        inverted ? "yes" : "no"
      );
    } else {
      Serial.printf("❌ Invalid pin: %d (allowed: 1, 2, 3)\n", pin);
    }
  }
}

void reconnect_mqtt() {
  while (!mqtt_client.connected()) {
    Serial.print("MQTT connecting...");
    if (mqtt_client.connect(mqtt_client_id)) {
      Serial.println("connected");
      mqtt_client.subscribe(mqtt_topic_jaw);
      mqtt_client.subscribe(mqtt_topic_eyes);
      mqtt_client.subscribe(mqtt_topic_volume);
      mqtt_client.subscribe(mqtt_topic_gpio);

      // Publish IP address
      String ip = WiFi.localIP().toString();
      mqtt_client.publish(mqtt_topic_ip, ip.c_str());
      Serial.print("Published IP: ");
      Serial.println(ip);

      // Publish current volume
      String vol_str = String(speaker_volume, 2);
      mqtt_client.publish(mqtt_topic_volume, vol_str.c_str());
      Serial.print("Current volume: ");
      Serial.print((int)(speaker_volume * 100));
      Serial.println("%");

      // Publish current eye state
      mqtt_client.publish(mqtt_topic_eyes, eyes_state ? "1" : "0");
      Serial.print("Current eyes state: ");
      Serial.println(eyes_state ? "ON" : "OFF");
    } else {
      Serial.print("failed, rc=");
      Serial.println(mqtt_client.state());
      delay(5000);
    }
  }
}

// ===== Generic XVF3800 Host-Control over I2C (resource/command) =====
bool xmos_ctrl_write(uint8_t resid, uint8_t cmd, const uint8_t* payload, uint8_t plen) {
  Wire.beginTransmission(XMOS_I2C_ADDR);
  Wire.write(resid);
  Wire.write(cmd);
  Wire.write(plen);
  for (uint8_t i = 0; i < plen; ++i) Wire.write(payload[i]);
  return Wire.endTransmission() == 0;
}
bool xmos_ctrl_read(uint8_t resid, uint8_t cmd, uint8_t n_read, uint8_t* status, uint8_t* out) {
  Wire.beginTransmission(XMOS_I2C_ADDR);
  Wire.write(resid);
  Wire.write(uint8_t(cmd | 0x80));
  Wire.write(uint8_t(1 + n_read));              // status + payload
  if (Wire.endTransmission(false) != 0) return false;  // repeated start
  uint8_t need = 1 + n_read;
  if (Wire.requestFrom(XMOS_I2C_ADDR, need) != need) return false;
  *status = Wire.read();
  for (uint8_t i = 0; i < n_read; ++i) out[i] = Wire.read();
  return true;
}
bool xmos_write_int32(uint8_t resid, uint8_t cmd, int32_t value) {
  uint8_t p[4];
  p[0] = (uint8_t)(value & 0xFF);
  p[1] = (uint8_t)((value >> 8) & 0xFF);
  p[2] = (uint8_t)((value >> 16) & 0xFF);
  p[3] = (uint8_t)((value >> 24) & 0xFF);
  return xmos_ctrl_write(resid, cmd, p, 4);
}
bool xmos_write_float(uint8_t resid, uint8_t cmd, float f) {
  union { float f; uint8_t b[4]; } u;
  u.f = f;
  return xmos_ctrl_write(resid, cmd, u.b, 4);
}
bool xmos_read_bytes(uint8_t resid, uint8_t cmd, uint8_t n, uint8_t* out) {
  uint8_t st = 0;
  if (!xmos_ctrl_read(resid, cmd, n, &st, out)) return false;
  if (st != 0) { Serial.printf("XMOS ctrl read status=0x%02X\n", st); return false; }
  return true;
}
// ====================================================================
int splitTokens(String &line, String tokens[], int maxTok) {
  int n = 0;
  int start = 0;
  line.trim();
  while (n < maxTok) {
    int sp = line.indexOf(' ', start);
    if (sp < 0) {
      if (start < line.length()) tokens[n++] = line.substring(start);
      break;
    }
    if (sp > start) tokens[n++] = line.substring(start, sp);
    start = sp + 1;
    while (start < line.length() && line.charAt(start) == ' ') start++;
  }
  return n;
}

// Microphone read task
void microphone_task(void* parameter) {
  uint8_t i2s_buffer_local[4096];
  uint32_t packet_count = 0;
  uint32_t error_count = 0;
  int zero_reads = 0;

  // Log WiFi status at start
  Serial.printf("🎤 Microphone task started\n");
  Serial.printf("WiFi status: %d (3=connected)\n", WiFi.status());
  Serial.printf("ESP32 IP: %s\n", WiFi.localIP().toString().c_str());
  Serial.printf("Target: %s:%d\n", server_ip, udp_port_send);

  while (true) {
    // Read 32-bit I2S stereo audio from XMOS
    size_t bytes_read = i2s.readBytes(i2s_buffer_local, 4096);

    if (bytes_read == 0) {
      zero_reads++;
      if ((zero_reads % 100) == 0) {
        Serial.println("I2S RX: no data");
      }
      vTaskDelay(pdMS_TO_TICKS(1));
      continue;
    }

    zero_reads = 0;
    size_t offset = 0;

    while (bytes_read > 0) {
      size_t to_copy = min(FRAME_BYTES_I2S_STEREO - tx_accum_used, bytes_read);
      memcpy(tx_accum_i2s + tx_accum_used, i2s_buffer_local + offset, to_copy);
      tx_accum_used += to_copy;
      offset += to_copy;
      bytes_read -= to_copy;

      // Send 40ms frames (1280 bytes mono 16-bit + 16 header = 1296 < MTU)
      if (tx_accum_used >= FRAME_BYTES_I2S_STEREO) {
        // Convert 32-bit stereo I2S -> 16-bit mono with adaptive headroom and soft limiter.
        int32_t* stereo_src = (int32_t*)tx_accum_i2s;
        int16_t* mono_dst   = (int16_t*)tx_buffer_mono;

        int shift = MIC_BASE_SHIFT + mic_extra_shift_bits;
        int32_t bias = (shift > 0) ? (1 << (shift - 1)) : 0;

        int16_t peak = 0;

        for (int i = 0; i < FRAME_SAMPLES_TX; i++) {
          // Select channel: 0=LEFT (AEC-processed), 1=RIGHT (raw)
          int32_t s32 = stereo_src[i*2 + mic_channel_select];
          int16_t v = (int16_t)((s32 >= 0 ? s32 + bias : s32 - bias) >> shift);

          // Soft limiter near full-scale
          if (MIC_LIMITER_ON) {
            int32_t a = v >= 0 ? v : -v;
            if (a > MIC_LIMIT_TH) {
              int32_t over = a - MIC_LIMIT_TH;
              int32_t reduced = MIC_LIMIT_TH + (over * MIC_LIMIT_RATIO_NUM) / MIC_LIMIT_RATIO_DEN;
              v = (v >= 0) ? (int16_t)reduced : (int16_t)(-reduced);
            }
            int16_t abs_v = v >= 0 ? v : (int16_t)(-v);
            if (abs_v > peak) peak = abs_v;
          } else {
            int16_t abs_v = v >= 0 ? v : (int16_t)(-v);
            if (abs_v > peak) peak = abs_v;
          }

          mono_dst[i] = v;
        }

        // Adapt headroom every MIC_ADAPT_FRAMES frames
        mic_frame_counter++;
        if ((mic_frame_counter % MIC_ADAPT_FRAMES) == 0) {
          if (peak > MIC_PEAK_HI && mic_extra_shift_bits < MIC_SHIFT_MAX) {
            mic_extra_shift_bits++;
            Serial.printf("⚠️  Mic peak=%d>HI; increase headroom: shift=%d\n", peak, MIC_BASE_SHIFT + mic_extra_shift_bits);
          } else if (peak < MIC_PEAK_LO && mic_extra_shift_bits > MIC_SHIFT_MIN) {
            mic_extra_shift_bits--;
            Serial.printf("ℹ️  Mic peak=%d<LO; decrease headroom: shift=%d\n", peak, MIC_BASE_SHIFT + mic_extra_shift_bits);
          }
        }

        UdpPacketHeader header;
        header.type = 0x01;
        header.flags = 0x00;
        header.payload_len = FRAME_BYTES_UDP_MONO_TX;  // 40ms mono 16-bit (1280 bytes)
        header.ssrc = ssrc;
        header.timestamp = millis();
        header.sequence = tx_sequence++;

        // Send 40ms mono packet
        int result = 0;
        if (udpTx.beginPacket(server_ip, udp_port_send)) {
          udpTx.write((uint8_t*)&header, HEADER_SIZE);
          // Write payload in ≤256 B chunks
          const size_t CHUNK = 256;
          size_t remaining = FRAME_BYTES_UDP_MONO_TX;
          size_t offset_tx = 0;
          while (remaining > 0) {
            size_t to_write = remaining > CHUNK ? CHUNK : remaining;
            udpTx.write(tx_buffer_mono + offset_tx, to_write);
            offset_tx += to_write;
            remaining -= to_write;
          }
          result = udpTx.endPacket();
        }

        packet_count++;
        if (result == 0) {
          error_count++;
        }

        tx_accum_used = 0;

        // Yield to WiFi/LWIP
        delay(0);
      }
    }
  }
}

// Find frame in jitter buffer by sequence number
int find_frame_by_seq(uint32_t seq) {
  for (int i = 0; i < jitter_count; i++) {
    if (jitter_buffer[i].seq == seq) {
      return i;
    }
  }
  return -1;
}

// Remove frame from jitter buffer
void remove_frame(int index) {
  if (index < 0 || index >= jitter_count) return;
  // Shift remaining frames
  for (int i = index; i < jitter_count - 1; i++) {
    jitter_buffer[i] = jitter_buffer[i + 1];
  }
  jitter_count--;
}

// Playback task with jitter buffer and timing
void playback_task(void* parameter) {
  uint32_t frames_played = 0;
  unsigned long last_play_time = 0;
  uint8_t convert_buf[FRAME_BYTES_I2S_STEREO];

  while (true) {
    unsigned long now = millis();

    // Check if we have prefill and not yet started
    if (!playback_started && jitter_count >= PREFILL_FRAMES) {
      playback_started = true;
      // Set next_play_seq to minimum seq in buffer
      uint32_t min_seq = jitter_buffer[0].seq;
      for (int i = 1; i < jitter_count; i++) {
        if (jitter_buffer[i].seq < min_seq) {
          min_seq = jitter_buffer[i].seq;
        }
      }
      next_play_seq = min_seq;
      last_play_time = now;
      Serial.printf("🔊 Playback START (buffer: %d frames, start_seq: %u)\n", jitter_count, next_play_seq);
    }

    // Play frames at 40ms intervals
    if (playback_started && (now - last_play_time) >= FRAME_MS_RX) {
      // Find frame with next_play_seq
      int idx = find_frame_by_seq(next_play_seq);

      if (idx >= 0) {
        // Frame found - play it (40ms frame as single I2S write)
        int16_t* mono16 = (int16_t*)jitter_buffer[idx].data;
        int32_t* stereo32 = (int32_t*)convert_buf;

        // Convert 40ms 16-bit mono to 32-bit stereo for I2S
        for (int i = 0; i < FRAME_SAMPLES_TX; i++) {
          int32_t s32 = ((int32_t)(mono16[i] * speaker_volume)) << 16;
          stereo32[i*2]   = s32;  // L: reference for AEC
          stereo32[i*2+1] = 0;    // R: zero
        }
        i2s.write(convert_buf, FRAME_BYTES_I2S_STEREO);

        // Save for PLC
        memcpy(last_frame, jitter_buffer[idx].data, FRAME_BYTES_UDP_MONO_RX);
        has_last_frame = true;

        // Remove from buffer
        remove_frame(idx);
        frames_played++;
        consecutive_plc = 0;  // Reset PLC counter
      } else {
        // PLC: frame lost
        consecutive_plc++;

        // Stop playback if PLC continues for too long (1 second)
        if (consecutive_plc >= MAX_CONSECUTIVE_PLC) {
          Serial.printf("⛔ Too many PLC (%u), stopping playback\n", consecutive_plc);
          playback_started = false;
          consecutive_plc = 0;
          has_last_frame = false;
          jitter_count = 0;  // Clear buffer
          last_play_time = now;  // Reset timing
        } else if (has_last_frame) {
          // Repeat last frame (40ms frame as single I2S write)
          int16_t* mono16 = (int16_t*)last_frame;
          int32_t* stereo32 = (int32_t*)convert_buf;

          for (int i = 0; i < FRAME_SAMPLES_TX; i++) {
            int32_t s32 = ((int32_t)(mono16[i] * speaker_volume)) << 16;
            stereo32[i*2]   = s32;
            stereo32[i*2+1] = 0;
          }
          i2s.write(convert_buf, FRAME_BYTES_I2S_STEREO);

          plc_count++;
          if (consecutive_plc % 10 == 0) {  // Log every 10th PLC to reduce spam
            Serial.printf("🔁 PLC #%u (repeat last, seq: %u, consecutive: %u)\n", plc_count, next_play_seq, consecutive_plc);
          }
        } else {
          // Silence (40ms as single I2S write)
          memset(convert_buf, 0, FRAME_BYTES_I2S_STEREO);
          i2s.write(convert_buf, FRAME_BYTES_I2S_STEREO);

          plc_count++;
          Serial.printf("🔇 PLC #%u (silence, seq: %u)\n", plc_count, next_play_seq);
        }
      }

      // Move to next sequence
      next_play_seq++;
      last_play_time = now;

      // Log periodically
      if (frames_played % 50 == 0) {
        Serial.printf("📊 Played %u frames, buffer: %d, PLC: %u\n", frames_played, jitter_count, plc_count);
      }

      // Stop if buffer empty for too long
      if (jitter_count == 0) {
        queue_underruns++;
        Serial.printf("⚠️  Buffer empty (underrun #%u)\n", queue_underruns);
        playback_started = false;
        frames_played = 0;
      }
    }

    vTaskDelay(pdMS_TO_TICKS(1));  // Check every 1ms
  }
}

// UDP receive task - add to jitter buffer
void udp_receive_task(void* parameter) {
  uint8_t packet[UDP_RX_PACKET_SIZE];
  uint32_t packets_received = 0;

  while (true) {
    int packetSize = udpRx.parsePacket();
    if (packetSize == UDP_RX_PACKET_SIZE) {
      udpRx.read(packet, UDP_RX_PACKET_SIZE);

      // Parse header
      UdpPacketHeader* header = (UdpPacketHeader*)packet;

      // Validate packet
      if (header->type != 0x01 || header->payload_len != FRAME_BYTES_UDP_MONO_RX) {
        vTaskDelay(1);
        continue;
      }

      packets_received++;
      uint32_t seq = header->sequence;

      // Check if already in buffer (duplicate)
      if (find_frame_by_seq(seq) >= 0) {
        vTaskDelay(1);
        continue;
      }

      // Add to jitter buffer if space available
      if (jitter_count < 48) {
        jitter_buffer[jitter_count].seq = seq;
        memcpy(jitter_buffer[jitter_count].data, packet + HEADER_SIZE, FRAME_BYTES_UDP_MONO_RX);
        jitter_count++;

        if (packets_received % 100 == 0) {
          Serial.printf("📦 RX %u packets, buffer: %d frames\n", packets_received, jitter_count);
        }
      } else {
        // Buffer full - drop oldest (should not happen with proper timing)
        Serial.printf("⚠️  Jitter buffer full, dropping oldest\n");
        remove_frame(0);
        jitter_buffer[jitter_count].seq = seq;
        memcpy(jitter_buffer[jitter_count].data, packet + HEADER_SIZE, FRAME_BYTES_UDP_MONO_RX);
        jitter_count++;
      }
    }
    vTaskDelay(1);
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("Franky ESP32-S3 ReSpeaker - UDP Audio");
  Serial.println("I2S: 32-bit (XMOS AEC/AGC) → UDP: 16-bit");
  Serial.println("==========================================");

  setup_wifi();

  // Setup I2C for XMOS control
  Wire.begin(I2C_SDA, I2C_SCL);
  Serial.println("I2C initialized");

  // Check if XMOS responds
  Wire.beginTransmission(XMOS_I2C_ADDR);
  byte error = Wire.endTransmission();
  if (error == 0) {
    Serial.printf("✓ XMOS found at 0x%02X\n", XMOS_I2C_ADDR);
  } else {
    Serial.printf("⚠ XMOS not found at 0x%02X (error: %d)\n", XMOS_I2C_ADDR, error);
  }

  i2c_scan();

  // Setup relay on D0 (GPIO1) for DC motor
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, RELAY_OFF);
  Serial.printf("Relay initialized on D0 (GPIO1) - %s\n", RELAY_INVERTED ? "Active LOW" : "Active HIGH");

  // Setup skull eyes LEDs on D3 (GPIO3)
  pinMode(LED_EYES, OUTPUT);
  digitalWrite(LED_EYES, LED_OFF);
  Serial.printf("💀 Skull eyes initialized on D3 (GPIO3) - %s\n", LED_INVERTED ? "Inverted" : "Normal");
  Serial.println("Control: franky/jaw (pulse duration ms), franky/eyes (0/1), franky/test (LED test)");

  // Setup MQTT (control only)
  mqtt_client.setServer(mqtt_server, mqtt_port);
  mqtt_client.setCallback(mqtt_callback);
  mqtt_client.setKeepAlive(60);
  mqtt_client.setBufferSize(512);

  // Setup UDP
  if (!udpTx.begin(53001)) { // Use fixed ephemeral port for TX
    Serial.println("⚠️ UDP TX begin(53001) failed, retrying...");
    delay(100);
    udpTx.begin(53001);
  }
  udpRx.begin(udp_port_receive);
  Serial.printf("UDP: send to %s:%d, receive on %d\n", server_ip, udp_port_send, udp_port_receive);

  // Jitter buffer initialized (static array, no queue needed)
  Serial.printf("Free heap: %u bytes\n", (unsigned)ESP.getFreeHeap());

  // Setup I2S duplex (microphone + speaker) - 32-bit audio from XMOS
  auto config = i2s.defaultConfig(RXTX_MODE);
  config.sample_rate = sample_rate;
  config.channels = channels;
  config.bits_per_sample = bits_i2s;
  config.pin_bck = 8;              // Bit clock
  config.pin_ws = 7;               // Word select
  config.pin_data = 44;            // Speaker out (ESP32 -> XMOS)
  config.pin_data_rx = 43;         // Microphone in (XMOS -> ESP32)
  // Seeed wiki references show ESP32 as I2S master:
  // - Record/Playback I2S example: config.is_master = true
  // - UDP Audio Streaming example: config.is_master = true
  // Links:
  // https://wiki.seeedstudio.com/respeaker_xvf3800_xiao_record_playback/
  // https://wiki.seeedstudio.com/respeaker_xvf3800_xiao_udp_audio_stream/
  config.is_master = true;    // Per Seeed wiki: ESP32 generates BCLK/WS
  config.use_apll = true;
  config.buffer_count = 8;
  config.buffer_size = 512;

  i2s.begin(config);
  // Make I2S read non-blocking (short timeout) so we can detect missing clocks
  i2s.setTimeout(5); // milliseconds

  Serial.println("I2S duplex (32-bit) started");

  // Set initial volume via AIC3104 codec
  Serial.println("Setting initial volume...");
  setHardwareVolume(speaker_volume);

  // Start tasks
  xTaskCreatePinnedToCore(microphone_task, "Microphone", 8192, NULL, 3, NULL, 1); // heavy I2S/convert on core 1
  xTaskCreatePinnedToCore(playback_task,  "Playback",   8192, NULL, 2, NULL, 1); // audio out on core 1
  xTaskCreatePinnedToCore(udp_receive_task,"UDP_RX",     8192, NULL, 2, NULL, 0); // networking on core 0

  Serial.println("Setup complete!");
}

// XMOS DFU commands
const uint8_t RES_DFU = 0xF0;          // DFU resource id
const uint8_t DFU_GETVERSION = 88;     // VERSION (decimal 88 == 0x58)
const uint8_t DFU_BLD_MSG = 89;        // BLD_MSG
const uint8_t DFU_BLD_REPO_HASH = 90;  // BLD_REPO_HASH
const uint8_t DFU_BOOT_STATUS = 91;    // BOOT_STATUS

bool xvf_dfu_get_version(uint8_t &maj, uint8_t &min, uint8_t &pat) {
  // Шаг 1: WRITE: resid, (cmd|0x80 для read), expected_len (= status + payload)
  Wire.beginTransmission(XMOS_I2C_ADDR);
  Wire.write(RES_DFU);                                 // 0xF0
  Wire.write(uint8_t(DFU_GETVERSION | 0x80));          // read-команда: 0xD8
  Wire.write(uint8_t(1 /*status*/ + 3 /*MAJ,MIN,PAT*/)); // ожидаем 4 байта всего
  if (Wire.endTransmission(false) != 0) return false;    // repeated start

  // Шаг 2: READ: статус + 3 байта версии
  uint8_t need = 4;
  if (Wire.requestFrom(XMOS_I2C_ADDR, need) != need) return false;
  uint8_t status = Wire.read();           // 0 == OK
  if (status != 0) return false;
  maj = Wire.read();
  min = Wire.read();
  pat = Wire.read();
  return true;
}

bool xvf_dfu_get_string(uint8_t cmd, char* buffer, size_t max_len) {
  // Read string from DFU (BLD_MSG, BLD_REPO_HASH, etc)
  Wire.beginTransmission(XMOS_I2C_ADDR);
  Wire.write(RES_DFU);
  Wire.write(uint8_t(cmd | 0x80));  // read command
  Wire.write(uint8_t(1 + max_len)); // status + string
  if (Wire.endTransmission(false) != 0) return false;

  // Read response
  size_t need = 1 + max_len;
  if (Wire.requestFrom(XMOS_I2C_ADDR, need) < 1) return false;

  uint8_t status = Wire.read();
  if (status != 0) return false;

  // Read string
  size_t i = 0;
  while (Wire.available() && i < max_len - 1) {
    char c = Wire.read();
    if (c == 0) break;  // null terminator
    buffer[i++] = c;
  }
  buffer[i] = '\0';
  return true;
}

bool xvf_dfu_get_boot_status(uint8_t &status_byte) {
  Wire.beginTransmission(XMOS_I2C_ADDR);
  Wire.write(RES_DFU);
  Wire.write(uint8_t(DFU_BOOT_STATUS | 0x80));
  Wire.write(uint8_t(1 + 1)); // status + 1 byte
  if (Wire.endTransmission(false) != 0) return false;

  if (Wire.requestFrom(XMOS_I2C_ADDR, 2) != 2) return false;
  uint8_t status = Wire.read();
  if (status != 0) return false;
  status_byte = Wire.read();
  return true;
}

void check_xmos_i2c() {
  Serial.println("\n=== XMOS I2C Diagnostic ===");

  // Try to communicate with XMOS
  Wire.beginTransmission(XMOS_I2C_ADDR);
  byte error = Wire.endTransmission();

  if (error == 0) {
    Serial.printf("✓ XMOS responding at 0x%02X\n", XMOS_I2C_ADDR);

    // Read firmware version
    uint8_t maj, min, pat;
    if (xvf_dfu_get_version(maj, min, pat)) {
      Serial.printf("  Firmware version: %u.%u.%u\n", maj, min, pat);
    } else {
      Serial.println("  Could not read firmware version");
    }

    // Read build message
    char build_msg[64];


    if (xvf_dfu_get_string(DFU_BLD_MSG, build_msg, sizeof(build_msg))) {
      Serial.printf("  Build message: %s\n", build_msg);
    } else {
      Serial.println("  Could not read build message");
    }

    // Read repository hash
    char repo_hash[48];
    if (xvf_dfu_get_string(DFU_BLD_REPO_HASH, repo_hash, sizeof(repo_hash))) {
      Serial.printf("  Repository hash: %s\n", repo_hash);
    } else {
      Serial.println("  Could not read repository hash");
    }

    // Read boot status
    uint8_t boot_status;
    if (xvf_dfu_get_boot_status(boot_status)) {
      Serial.printf("  Boot status: 0x%02X ", boot_status);
      switch (boot_status) {
        case 0: Serial.println("(Normal boot)"); break;
        case 1: Serial.println("(DFU mode)"); break;
        default: Serial.println("(Unknown)"); break;
      }
    } else {
      Serial.println("  Could not read boot status");
    }
  } else {
    Serial.printf("✗ XMOS not responding (error: %d)\n", error);
    Serial.println("  Possible issues:");
    Serial.println("  - Wrong I2C address");
    Serial.println("  - XMOS not powered");
    Serial.println("  - Wrong firmware (needs I2S version)");
  }

  Serial.println("===========================\n");
}

void loop() {
  // Check jaw pulse timer (non-blocking)
  if (jaw_pulse_active) {
    if (millis() - jaw_pulse_start >= jaw_pulse_duration) {
      // Time elapsed - turn OFF
      digitalWrite(RELAY_PIN, RELAY_OFF);
      digitalWrite(LED_EYES, LED_OFF);
      relay_state = false;
      eyes_state = false;
      jaw_pulse_active = false;
      Serial.println("💀 Skull pulse complete");
    }
  }

  // MQTT for jaw control
  if (!mqtt_client.connected()) {
    reconnect_mqtt();
  }
  mqtt_client.loop();

  // Serial commands
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    if (cmd.startsWith("mic")) {
      String tmp = cmd;
      String tok[5]; int nt = splitTokens(tmp, tok, 5);
      if (nt == 3 && tok[1] == "channel") {
        String ch = tok[2];
        ch.toLowerCase();
        if (ch == "left" || ch == "l" || ch == "0") {
          mic_channel_select = 0;
          Serial.println("✓ Mic channel: LEFT (AEC-processed)");
        } else if (ch == "right" || ch == "r" || ch == "1") {
          mic_channel_select = 1;
          Serial.println("✓ Mic channel: RIGHT (raw)");
        } else {
          Serial.println("❌ Invalid channel. Use: left/right, l/r, or 0/1");
        }
      } else {
        Serial.println("Usage: mic channel <left|right>   (or: l, r, 0, 1)");
        Serial.printf("Current: %s\n", mic_channel_select == 0 ? "LEFT (AEC)" : "RIGHT (raw)");
      }
    } else if (cmd.startsWith("xmos")) {
      // Syntax:
      //   xmos                      -> quick I2C diagnostic
      //   xmos read  <res> <cmd> <n>
      //   xmos writei <res> <cmd> <int32>
      //   xmos writef <res> <cmd> <float>
      //   xmos writeb <res> <cmd> <b0> [<b1> ...]
      String tmp = cmd;
      String tok[12]; int nt = splitTokens(tmp, tok, 12);
      if (nt == 1) {
        // quick diagnostic
        Wire.beginTransmission(XMOS_I2C_ADDR);
        byte e = Wire.endTransmission();
        if (e == 0) Serial.printf("✓ XMOS responding at 0x%02X\n", XMOS_I2C_ADDR);
        else        Serial.printf("✗ XMOS not responding (err=%d)\n", e);
      } else if (nt >= 5 && tok[1] == "read") {
        uint8_t res = (uint8_t) strtoul(tok[2].c_str(), nullptr, 0);
        uint8_t cc  = (uint8_t) strtoul(tok[3].c_str(), nullptr, 0);
        uint8_t n   = (uint8_t) strtoul(tok[4].c_str(), nullptr, 0);
        uint8_t st=0; uint8_t buf[64];
        if (n > sizeof(buf)) n = sizeof(buf);
        if (xmos_ctrl_read(res, cc, n, &st, buf)) {
          Serial.printf("status=0x%02X, data:", st);
          for (uint8_t i=0;i<n;i++) Serial.printf(" %02X", buf[i]);
          Serial.println();
        } else {
          Serial.println("read failed");
        }
      } else if (nt == 5 && tok[1] == "writei") {
        uint8_t res = (uint8_t) strtoul(tok[2].c_str(), nullptr, 0);
        uint8_t cc  = (uint8_t) strtoul(tok[3].c_str(), nullptr, 0);
        int32_t v   = (int32_t) strtol(tok[4].c_str(), nullptr, 0);
        Serial.println(xmos_write_int32(res, cc, v) ? "OK" : "FAIL");
      } else if (nt == 5 && tok[1] == "writef") {
        uint8_t res = (uint8_t) strtoul(tok[2].c_str(), nullptr, 0);
        uint8_t cc  = (uint8_t) strtoul(tok[3].c_str(), nullptr, 0);
        float vf    = (float) atof(tok[4].c_str());
        Serial.println(xmos_write_float(res, cc, vf) ? "OK" : "FAIL");
      } else if (nt >= 5 && tok[1] == "writeb") {
        uint8_t res = (uint8_t) strtoul(tok[2].c_str(), nullptr, 0);
        uint8_t cc  = (uint8_t) strtoul(tok[3].c_str(), nullptr, 0);
        uint8_t plen = nt - 4;
        uint8_t p[64];
        if (plen > sizeof(p)) plen = sizeof(p);
        for (uint8_t i=0;i<plen;i++) p[i] = (uint8_t) strtoul(tok[4+i].c_str(), nullptr, 0);
        Serial.println(xmos_ctrl_write(res, cc, p, plen) ? "OK" : "FAIL");
      } else {
        Serial.println("Usage:");
        Serial.println("  xmos");
        Serial.println("  xmos read  <res> <cmd> <n>");
        Serial.println("  xmos writei <res> <cmd> <int32>");
        Serial.println("  xmos writef <res> <cmd> <float>");
        Serial.println("  xmos writeb <res> <cmd> <b0> [b1 ...]");
      }
    } else if (cmd == "scan") {
      i2c_scan();
    } else if (cmd == "info") {
      Serial.println("\n=== System Info ===");
      Serial.printf("IP: %s\n", WiFi.localIP().toString().c_str());
      Serial.printf("WiFi status: %d ", WiFi.status());
      switch (WiFi.status()) {
        case WL_CONNECTED: Serial.println("(Connected)"); break;
        case WL_NO_SHIELD: Serial.println("(No shield)"); break;
        case WL_IDLE_STATUS: Serial.println("(Idle)"); break;
        case WL_NO_SSID_AVAIL: Serial.println("(No SSID)"); break;
        case WL_SCAN_COMPLETED: Serial.println("(Scan completed)"); break;
        case WL_CONNECT_FAILED: Serial.println("(Connect failed)"); break;
        case WL_CONNECTION_LOST: Serial.println("(Connection lost)"); break;
        case WL_DISCONNECTED: Serial.println("(Disconnected)"); break;
        default: Serial.println("(Unknown)"); break;
      }
      Serial.printf("WiFi RSSI: %d dBm\n", WiFi.RSSI());
      Serial.printf("MQTT: %s\n", mqtt_client.connected() ? "Connected" : "Disconnected");
      if (mqtt_client.connected()) {
        Serial.printf("MQTT server: %s:%d\n", mqtt_server, mqtt_port);
      }
      Serial.println("===================\n");
    } else if (cmd.startsWith("gpio")) {
      // GPIO control via Serial: gpio <pin> <state> [inverted]
      // Example: gpio 1 1, gpio 2 0, gpio 3 1 inv
      String tmp = cmd;
      String tok[5]; int nt = splitTokens(tmp, tok, 5);

      if (nt >= 3) {
        int pin = tok[1].toInt();
        int state = tok[2].toInt();
        bool inverted = false;

        if (nt >= 4) {
          String inv_str = tok[3];
          inv_str.toLowerCase();
          if (inv_str == "inv" || inv_str == "inverted" || inv_str == "1") {
            inverted = true;
          }
        }

        // Validate pin (only D0, D2, D3)
        if (pin == 1 || pin == 2 || pin == 3) {
          // Setup pin as output if not already
          pinMode(pin, OUTPUT);

          // Apply state (with optional inversion)
          int actual_state = inverted ? !state : state;
          digitalWrite(pin, actual_state ? HIGH : LOW);

          Serial.printf("🔧 GPIO D%d = %s (requested: %d, inverted: %s)\n",
            pin,
            actual_state ? "HIGH" : "LOW",
            state,
            inverted ? "yes" : "no"
          );
        } else {
          Serial.printf("❌ Invalid pin: %d (allowed: 1, 2, 3)\n", pin);
        }
      } else {
        Serial.println("Usage: gpio <pin> <state> [inv]");
        Serial.println("  pin: 1 (D0), 2 (D2), 3 (D3)");
        Serial.println("  state: 0 (LOW) or 1 (HIGH)");
        Serial.println("  inv: optional inversion");
        Serial.println("Examples:");
        Serial.println("  gpio 1 1      - D0 HIGH");
        Serial.println("  gpio 1 0      - D0 LOW");
        Serial.println("  gpio 1 1 inv  - D0 LOW (inverted)");
      }
    } else if (cmd == "help") {
      Serial.println("\nAvailable commands:");
      Serial.println("  info  - Show system info (IP, WiFi, MQTT)");
      Serial.println("  gpio  - Direct GPIO control");
      Serial.println("         gpio <pin> <state> [inv]  (pin: 1=D0, 2=D2, 3=D3)");
      Serial.println("  mic   - Mic controls");
      Serial.println("         mic channel <left|right>  (switch between AEC and raw)");
      Serial.println("  xmos  - I2C diag / raw host-control bridge");
      Serial.println("         xmos read  <res> <cmd> <n>");
      Serial.println("         xmos writei <res> <cmd> <int32>");
      Serial.println("         xmos writef <res> <cmd> <float>");
      Serial.println("         xmos writeb <res> <cmd> <b0> [b1 ...]");
      Serial.println("  scan  - Scan I2C bus for devices");
      Serial.println("  help  - Show this help");
    }
  }

  delay(10);
}
