/*
 * Franky - Simple MQTT Control (Jaw & Eyes)
 *
 * Hardware: XIAO ESP32-S3 or any ESP32 board
 * Features: MQTT control for jaw servo and LED eyes
 * Audio: Use laptop/PC speakers (not handled by this firmware)
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <ESP32Servo.h>

// WiFi credentials
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// MQTT broker
const char* mqtt_server = "192.168.1.100";
const int mqtt_port = 1883;

// GPIO pins
const int JAW_SERVO_PIN = 9;
const int EYES_LED_PIN = 10;

// Objects
WiFiClient espClient;
PubSubClient mqtt(espClient);
Servo jawServo;

// MQTT topics
const char* TOPIC_JAW = "franky/jaw";
const char* TOPIC_EYES = "franky/eyes";

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("\n=== Franky MQTT Control ===");

  // Setup hardware
  setupHardware();

  // Connect WiFi
  connectWiFi();

  // Setup MQTT
  mqtt.setServer(mqtt_server, mqtt_port);
  mqtt.setCallback(mqttCallback);

  Serial.println("Setup complete!");
}

void loop() {
  // Maintain WiFi connection
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }

  // Maintain MQTT connection
  if (!mqtt.connected()) {
    reconnectMQTT();
  }
  mqtt.loop();

  delay(10);
}

void setupHardware() {
  Serial.println("Setting up hardware...");

  // Setup servo
  jawServo.attach(JAW_SERVO_PIN);
  jawServo.write(0);  // Start closed
  Serial.println("✓ Jaw servo attached (GPIO " + String(JAW_SERVO_PIN) + ")");

  // Setup LED eyes
  pinMode(EYES_LED_PIN, OUTPUT);
  digitalWrite(EYES_LED_PIN, LOW);  // Start off
  Serial.println("✓ LED eyes ready (GPIO " + String(EYES_LED_PIN) + ")");
}

void connectWiFi() {
  Serial.print("Connecting to WiFi: ");
  Serial.println(ssid);

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n✓ WiFi connected!");
    Serial.print("IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\n✗ WiFi connection failed!");
  }
}

void reconnectMQTT() {
  if (mqtt.connected()) return;

  Serial.print("Connecting to MQTT broker: ");
  Serial.println(mqtt_server);

  String clientId = "franky-" + String((uint32_t)ESP.getEfuseMac(), HEX);

  if (mqtt.connect(clientId.c_str())) {
    Serial.println("✓ MQTT connected!");

    // Subscribe to control topics
    mqtt.subscribe(TOPIC_JAW);
    mqtt.subscribe(TOPIC_EYES);

    Serial.println("✓ Subscribed to: " + String(TOPIC_JAW));
    Serial.println("✓ Subscribed to: " + String(TOPIC_EYES));

  } else {
    Serial.print("✗ MQTT connection failed, rc=");
    Serial.println(mqtt.state());
    delay(5000);
  }
}

void mqttCallback(char* topic, byte* payload, unsigned int length) {
  // Convert payload to string
  String value = "";
  for (unsigned int i = 0; i < length; i++) {
    value += (char)payload[i];
  }

  Serial.print("MQTT received [");
  Serial.print(topic);
  Serial.print("]: ");
  Serial.println(value);

  // Handle jaw control
  if (strcmp(topic, TOPIC_JAW) == 0) {
    int angle = value.toInt();
    angle = constrain(angle, 0, 180);  // Safety limit
    jawServo.write(angle);
    Serial.println("→ Jaw moved to " + String(angle) + "°");
  }

  // Handle eyes control
  else if (strcmp(topic, TOPIC_EYES) == 0) {
    int state = value.toInt();
    digitalWrite(EYES_LED_PIN, state ? HIGH : LOW);
    Serial.println("→ Eyes: " + String(state ? "ON" : "OFF"));
  }
}
