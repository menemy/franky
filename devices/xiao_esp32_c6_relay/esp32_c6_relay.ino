#include <WiFi.h>
#include <esp_wifi.h>
#include <PubSubClient.h>
#include <ArduinoOTA.h>
#include <HTTPUpdate.h>
#include <ArduinoJson.h>

// WiFi credentials
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// MQTT settings
const char* mqtt_server = "192.168.1.100";
const int mqtt_port = 1883;
const char* mqtt_topic_trigger = "witch/trigger";
const char* mqtt_topic_status = "witch/status";
const char* mqtt_topic_info = "witch/info";
const char* mqtt_topic_info_request = "witch/info/request";
const char* mqtt_topic_ota_update = "witch/ota/update";
const char* mqtt_topic_ota_status = "witch/ota/status";
const char* mqtt_topic_ota_progress = "witch/ota/progress";

// Relay pin (Seeed Relay Add-on Module on D1)
const int RELAY1_PIN = 1;  // GPIO1 (D1)

// MQTT client
WiFiClient espClient;
PubSubClient mqttClient(espClient);

// Relay state
bool relay1_state = false;

void setup() {
  // Initialize relay pin
  pinMode(RELAY1_PIN, OUTPUT);
  digitalWrite(RELAY1_PIN, HIGH);  // Turn relay off initially (inverted logic)

  // Connect to WiFi
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    // Enable WiFi power saving mode (modem sleep)
    WiFi.setSleep(true);
    esp_wifi_set_ps(WIFI_PS_MIN_MODEM);

    // Setup OTA
    ArduinoOTA.setHostname("esp32-witch");
    ArduinoOTA.begin();

    // Setup MQTT
    mqttClient.setServer(mqtt_server, mqtt_port);
    mqttClient.setCallback(mqttCallback);
    mqttClient.setBufferSize(512);  // Increase buffer for JSON messages
    reconnectMQTT();
  }
}

void loop() {
  ArduinoOTA.handle();

  // Reconnect MQTT if needed
  if (WiFi.status() == WL_CONNECTED && !mqttClient.connected()) {
    reconnectMQTT();
  }

  mqttClient.loop();
  delay(10);  // Small delay to allow CPU to sleep
}

void mqttCallback(char* topic, byte* payload, unsigned int length) {
  String message;
  for (unsigned int i = 0; i < length; i++) {
    message += (char)payload[i];
  }

  if (String(topic) == mqtt_topic_trigger) {
    triggerRelay();
  } else if (String(topic) == mqtt_topic_info_request) {
    sendDeviceInfo();
  } else if (String(topic) == mqtt_topic_ota_update) {
    handleOTAUpdate(message);
  }
}

void reconnectMQTT() {
  int attempts = 0;
  while (!mqttClient.connected() && attempts < 5) {
    String clientId = "ESP32C6-Witch-";
    clientId += String(WiFi.macAddress());

    if (mqttClient.connect(clientId.c_str())) {
      mqttClient.subscribe(mqtt_topic_trigger);
      mqttClient.subscribe(mqtt_topic_info_request);
      mqttClient.subscribe(mqtt_topic_ota_update);
      mqttClient.publish(mqtt_topic_status, "online");

      // Send device info on connect
      sendDeviceInfo();
      return;
    }
    delay(1000);
    attempts++;
  }
}

void sendDeviceInfo() {
  // Create JSON with IP and RSSI
  JsonDocument doc;
  doc["ip"] = WiFi.localIP().toString();
  doc["rssi"] = WiFi.RSSI();
  doc["mac"] = WiFi.macAddress();

  char buffer[128];
  serializeJson(doc, buffer);
  mqttClient.publish(mqtt_topic_info, buffer);
}

void triggerRelay() {
  // Inverted logic: LOW = ON
  digitalWrite(RELAY1_PIN, LOW);
  relay1_state = true;
  mqttClient.publish(mqtt_topic_status, "triggered");

  delay(200);  // 200ms pulse

  digitalWrite(RELAY1_PIN, HIGH);
  relay1_state = false;
  mqttClient.publish(mqtt_topic_status, "idle");
}

void handleOTAUpdate(String message) {
  mqttClient.publish(mqtt_topic_ota_status, "parsing");

  // Parse JSON message: {"url": "http://192.168.2.243:8000/firmware.bin"}
  JsonDocument doc;
  DeserializationError error = deserializeJson(doc, message);

  if (error) {
    mqttClient.publish(mqtt_topic_ota_status, "error: invalid json");
    return;
  }

  if (!doc.containsKey("url")) {
    mqttClient.publish(mqtt_topic_ota_status, "error: missing url");
    return;
  }

  String firmwareUrl = doc["url"].as<String>();
  mqttClient.publish(mqtt_topic_ota_status, "starting");

  // Setup HTTP update callbacks
  httpUpdate.onProgress([](int current, int total) {
    int progress = (current * 100) / total;
    static int lastProgress = -1;
    if (progress != lastProgress && progress % 10 == 0) {
      char progressMsg[32];
      sprintf(progressMsg, "progress: %d%%", progress);
      mqttClient.publish(mqtt_topic_ota_progress, progressMsg);
      lastProgress = progress;
    }
  });

  httpUpdate.onEnd([]() {
    mqttClient.publish(mqtt_topic_ota_status, "success: rebooting");
  });

  httpUpdate.onError([](int error) {
    char errorMsg[64];
    sprintf(errorMsg, "error: %d", error);
    mqttClient.publish(mqtt_topic_ota_status, errorMsg);
  });

  // Perform HTTP update
  mqttClient.publish(mqtt_topic_ota_status, "downloading");
  WiFiClient client;
  t_httpUpdate_return ret = httpUpdate.update(client, firmwareUrl);

  // Handle result
  switch (ret) {
    case HTTP_UPDATE_FAILED:
      mqttClient.publish(mqtt_topic_ota_status, "failed");
      break;
    case HTTP_UPDATE_NO_UPDATES:
      mqttClient.publish(mqtt_topic_ota_status, "no update available");
      break;
    case HTTP_UPDATE_OK:
      mqttClient.publish(mqtt_topic_ota_status, "complete: rebooting");
      delay(1000);
      ESP.restart();
      break;
  }
}