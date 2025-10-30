// XIAO MG24 Relay Controller with BLE
// Note: MG24 has BLE/Thread, not WiFi

// Relay pin (Seeed Relay Add-on Module on D1)
const int RELAY1_PIN = 1;  // GPIO1 (D1)

// Relay state
bool relay1_state = false;

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("\n\nXIAO MG24 Relay Controller");
  Serial.println("==========================");
  Serial.println("Note: This board uses BLE, not WiFi");

  // Initialize relay pin
  pinMode(RELAY1_PIN, OUTPUT);
  digitalWrite(RELAY1_PIN, HIGH);  // Turn relay off initially (inverted logic)

  Serial.println("Relay initialized on GPIO1 (D1)");
  Serial.println("\nSerial commands:");
  Serial.println("  on       - Turn relay ON");
  Serial.println("  off      - Turn relay OFF");
  Serial.println("  press    - Press button (200ms pulse)");
  Serial.println("  status   - Show relay state");
  Serial.println("  help     - Show this help");
  Serial.println();
}

void loop() {
  // Handle serial commands
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    command.toLowerCase();
    handleSerialCommand(command);
  }
}

void handleSerialCommand(String cmd) {
  if (cmd == "status") {
    printStatus();
  } else if (cmd == "help") {
    printHelp();
  } else if (cmd == "on") {
    setRelay(true);
  } else if (cmd == "off") {
    setRelay(false);
  } else if (cmd == "press") {
    pressButton();
  } else if (cmd.length() > 0) {
    Serial.println("Unknown command. Type 'help' for available commands.");
  }
}

void setRelay(bool state) {
  // Inverted logic for optocoupler: LOW = ON, HIGH = OFF
  digitalWrite(RELAY1_PIN, state ? LOW : HIGH);
  relay1_state = state;

  Serial.print("Relay turned ");
  Serial.println(state ? "ON" : "OFF");
}

void pressButton() {
  Serial.println("Button press triggered");

  // Inverted logic: LOW = ON
  digitalWrite(RELAY1_PIN, LOW);
  relay1_state = true;
  delay(200);  // 200ms pulse
  digitalWrite(RELAY1_PIN, HIGH);
  relay1_state = false;

  Serial.println("Button press complete");
}

void printStatus() {
  Serial.println("\n========== RELAY STATUS ==========");
  Serial.print("Relay: ");
  Serial.println(relay1_state ? "ON" : "OFF");
  Serial.println("==================================\n");
}

void printHelp() {
  Serial.println("\n========== SERIAL COMMANDS ==========");
  Serial.println("on       - Turn relay ON");
  Serial.println("off      - Turn relay OFF");
  Serial.println("press    - Press button (200ms pulse)");
  Serial.println("status   - Show relay state");
  Serial.println("help     - Show this help");
  Serial.println("=====================================\n");
}
