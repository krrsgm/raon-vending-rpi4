/*
  vending_controller.ino
  ESP32 RXTX Controller for 64-output vending machine using 4 x CD74HC4067 multiplexers.
  
  RXTX Communication (Raspberry Pi ↔ ESP32):
    - Baud rate: 115200
    - ESP32 RX on GPIO 3  (receives from Raspberry Pi TX on GPIO 14)
    - ESP32 TX on GPIO 1  (sends to Raspberry Pi RX on GPIO 15)
    - GND connected between both boards
    
  Protocol (text-based commands, terminated with newline):
    - PULSE <slot> <ms>   : pulse output for <ms> milliseconds (slot numbers 1..64)
    - OPEN <slot>         : set output on continuously
    - CLOSE <slot>        : set output off
    - OPENALL             : set all outputs on
    - CLOSEALL            : set all outputs off
    - STATUS              : returns comma-separated list of ON slots (1-based)
    
  Example commands:
    PULSE 12 800\n        → pulse slot 12 for 800ms
    STATUS\n              → returns "1,5,12\n" if slots 1, 5, 12 are on
*/

#include <Arduino.h>
#include <CD74HC4067.h>

// ============================================================================
// CONFIGURATION
// ============================================================================

const unsigned long BAUD_RATE = 115200;
const int NUM_OUTPUTS = 64;          // 4 multiplexers × 16 channels
const int MOTORS_PER_MUX = 16;       // channels per multiplexer
const int NUM_MUXES = 4;             // number of multiplexers

// RXTX Serial pins for communication with Raspberry Pi
const int SERIAL2_RX_PIN = 3;        // ESP32 receives from Pi TX (GPIO 14)
const int SERIAL2_TX_PIN = 1;        // ESP32 sends to Pi RX (GPIO 15)

// ============================================================================
// MULTIPLEXER PIN DEFINITIONS
// ============================================================================

// Multiplexer 1: Slots 1-16
const int MUX1_S0 = 13;
const int MUX1_S1 = 12;
const int MUX1_S2 = 14;
const int MUX1_S3 = 27;
const int MUX1_SIG = 23;

// Multiplexer 2: Slots 17-32
const int MUX2_S0 = 26;
const int MUX2_S1 = 25;
const int MUX2_S2 = 33;
const int MUX2_S3 = 32;
const int MUX2_SIG = 22;

// Multiplexer 3: Slots 33-48
const int MUX3_S0 = 15;
const int MUX3_S1 = 2;
const int MUX3_S2 = 4;
const int MUX3_S3 = 16;
const int MUX3_SIG = 21;

// Multiplexer 4: Slots 49-64
const int MUX4_S0 = 17;
const int MUX4_S1 = 5;
const int MUX4_S2 = 18;
const int MUX4_S3 = 19;
const int MUX4_SIG = 35;

// ============================================================================
// STATE TRACKING
// ============================================================================

unsigned long active_until[NUM_OUTPUTS];  // when each pulse expires
bool outputs_state[NUM_OUTPUTS];          // current ON/OFF state
String inputBuffer2 = "";                 // RXTX command buffer

// Multiplexer objects
CD74HC4067 mux1(MUX1_S0, MUX1_S1, MUX1_S2, MUX1_S3);
CD74HC4067 mux2(MUX2_S0, MUX2_S1, MUX2_S2, MUX2_S3);
CD74HC4067 mux3(MUX3_S0, MUX3_S1, MUX3_S2, MUX3_S3);
CD74HC4067 mux4(MUX4_S0, MUX4_S1, MUX4_S2, MUX4_S3);

// ============================================================================
// FORWARD DECLARATIONS
// ============================================================================

void setOutput(int idx, bool on);
void processCommand(String cmd, Stream &out);

// ============================================================================
// SETUP
// ============================================================================

void setup() {
  // Initialize all multiplexer selector pins as outputs
  // Multiplexer 1
  pinMode(MUX1_S0, OUTPUT);
  pinMode(MUX1_S1, OUTPUT);
  pinMode(MUX1_S2, OUTPUT);
  pinMode(MUX1_S3, OUTPUT);
  pinMode(MUX1_SIG, OUTPUT);

  // Multiplexer 2
  pinMode(MUX2_S0, OUTPUT);
  pinMode(MUX2_S1, OUTPUT);
  pinMode(MUX2_S2, OUTPUT);
  pinMode(MUX2_S3, OUTPUT);
  pinMode(MUX2_SIG, OUTPUT);

  // Multiplexer 3
  pinMode(MUX3_S0, OUTPUT);
  pinMode(MUX3_S1, OUTPUT);
  pinMode(MUX3_S2, OUTPUT);
  pinMode(MUX3_S3, OUTPUT);
  pinMode(MUX3_SIG, OUTPUT);

  // Multiplexer 4
  pinMode(MUX4_S0, OUTPUT);
  pinMode(MUX4_S1, OUTPUT);
  pinMode(MUX4_S2, OUTPUT);
  pinMode(MUX4_S3, OUTPUT);
  pinMode(MUX4_SIG, OUTPUT);

  // Initialize all outputs to OFF
  for (int i = 0; i < NUM_OUTPUTS; i++) {
    active_until[i] = 0;
    outputs_state[i] = false;
    setOutput(i, false);
  }

  // Initialize USB serial for debugging
  Serial.begin(BAUD_RATE);
  delay(100);

  // Initialize Serial2 (RXTX) for Raspberry Pi communication
  // Explicitly bind to GPIO 3 (RX) and GPIO 1 (TX)
  Serial2.begin(BAUD_RATE, SERIAL_8N1, SERIAL2_RX_PIN, SERIAL2_TX_PIN);
  
  Serial.println("=============================================================");
  Serial.println("ESP32 Vending Controller - RXTX Communication Mode");
  Serial.println("=============================================================");
  Serial.print("Serial2 (RXTX) initialized:");
  Serial.print(" RX=GPIO"); Serial.print(SERIAL2_RX_PIN);
  Serial.print(" TX=GPIO"); Serial.println(SERIAL2_TX_PIN);
  Serial.print("Baud rate: "); Serial.println(BAUD_RATE);
  Serial.println("Waiting for commands from Raspberry Pi...");
  Serial.println("=============================================================");
}

// ============================================================================
// MAIN LOOP
// ============================================================================

void loop() {
  // Read commands from Raspberry Pi via Serial2 (RXTX)
  while (Serial2.available()) {
    char c = Serial2.read();
    
    if (c == '\n' || c == '\r') {
      if (inputBuffer2.length() > 0) {
        // Command received - process it
        Serial.print("[RXTX] Command: ");
        Serial.println(inputBuffer2);
        processCommand(inputBuffer2, Serial2);
        inputBuffer2 = "";
      }
    } else if (c >= 32 && c < 127) {
      // Accumulate printable characters
      inputBuffer2 += c;
    }
  }

  // Handle pulse timers - turn off outputs when time expires
  unsigned long now = millis();
  for (int i = 0; i < NUM_OUTPUTS; i++) {
    if (active_until[i] != 0 && now >= active_until[i]) {
      active_until[i] = 0;
      if (outputs_state[i]) {
        outputs_state[i] = false;
        setOutput(i, false);
      }
    }
  }
}

// ============================================================================
// OUTPUT CONTROL
// ============================================================================

void setOutput(int idx, bool on) {
  if (idx < 0 || idx >= NUM_OUTPUTS) return;

  // Determine which multiplexer and channel
  int mux_num = idx / MOTORS_PER_MUX;      // 0-3
  int channel = idx % MOTORS_PER_MUX;      // 0-15

  // Update state
  outputs_state[idx] = on;

  // Control the appropriate multiplexer
  switch (mux_num) {
    case 0:
      mux1.channel(channel);
      digitalWrite(MUX1_SIG, on ? HIGH : LOW);
      break;
    case 1:
      mux2.channel(channel);
      digitalWrite(MUX2_SIG, on ? HIGH : LOW);
      break;
    case 2:
      mux3.channel(channel);
      digitalWrite(MUX3_SIG, on ? HIGH : LOW);
      break;
    case 3:
      mux4.channel(channel);
      digitalWrite(MUX4_SIG, on ? HIGH : LOW);
      break;
  }
}

// ============================================================================
// COMMAND PROCESSING
// ============================================================================

void processCommand(String cmd, Stream &out) {
  cmd.trim();
  if (cmd.length() == 0) return;

  // Parse command (whitespace-separated)
  String parts[10];
  int partCount = 0;
  int start = 0;

  for (int i = 0; i <= cmd.length(); i++) {
    if (i == cmd.length() || isspace(cmd.charAt(i))) {
      if (i - start > 0 && partCount < 10) {
        parts[partCount] = cmd.substring(start, i);
        partCount++;
      }
      start = i + 1;
    }
  }

  if (partCount == 0) return;

  String command = parts[0];
  command.toUpperCase();

  // PULSE <slot> <ms> - pulse for specified milliseconds
  if (command == "PULSE") {
    if (partCount >= 3) {
      int slot = parts[1].toInt();
      unsigned long ms = (unsigned long)parts[2].toInt();
      if (slot >= 1 && slot <= NUM_OUTPUTS) {
        int idx = slot - 1;
        active_until[idx] = millis() + ms;
        outputs_state[idx] = true;
        setOutput(idx, true);
        out.println("OK");
      } else {
        out.print("ERR invalid slot ");
        out.println(slot);
      }
    } else {
      out.println("ERR PULSE requires: PULSE <slot> <ms>");
    }
  }
  // OPEN <slot> - turn on
  else if (command == "OPEN") {
    if (partCount >= 2) {
      int slot = parts[1].toInt();
      if (slot >= 1 && slot <= NUM_OUTPUTS) {
        setOutput(slot - 1, true);
        out.println("OK");
      } else {
        out.print("ERR invalid slot ");
        out.println(slot);
      }
    } else {
      out.println("ERR OPEN requires: OPEN <slot>");
    }
  }
  // CLOSE <slot> - turn off
  else if (command == "CLOSE") {
    if (partCount >= 2) {
      int slot = parts[1].toInt();
      if (slot >= 1 && slot <= NUM_OUTPUTS) {
        setOutput(slot - 1, false);
        out.println("OK");
      } else {
        out.print("ERR invalid slot ");
        out.println(slot);
      }
    } else {
      out.println("ERR CLOSE requires: CLOSE <slot>");
    }
  }
  // OPENALL - turn all on
  else if (command == "OPENALL") {
    for (int i = 0; i < NUM_OUTPUTS; i++) {
      setOutput(i, true);
    }
    out.println("OK");
  }
  // CLOSEALL - turn all off
  else if (command == "CLOSEALL") {
    for (int i = 0; i < NUM_OUTPUTS; i++) {
      setOutput(i, false);
    }
    out.println("OK");
  }
  // STATUS - return list of ON slots
  else if (command == "STATUS") {
    String csv = "";
    for (int i = 0; i < NUM_OUTPUTS; i++) {
      if (outputs_state[i]) {
        if (csv.length() > 0) csv += ",";
        csv += String(i + 1);  // 1-based slot numbers
      }
    }
    out.println(csv.length() > 0 ? csv : "NONE");
  }
  // Unknown command
  else {
    out.print("ERR unknown command: ");
    out.println(command);
  }
}
