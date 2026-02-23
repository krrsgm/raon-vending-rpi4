/*
  vending_controller.ino
  ESP32 Vending Controller for 64-output vending machine using 4 x CD74HC4067 multiplexers.
  Integrated with Allan 123A-Pro Coin Acceptor.
  
  RXTX Communication (Raspberry Pi ↔ ESP32):
    - Baud rate: 115200
    - ESP32 RX on GPIO 3  (receives from Raspberry Pi TX on GPIO 14)
    - ESP32 TX on GPIO 1  (sends to Raspberry Pi RX on GPIO 15)
    - GND connected between both boards
    
  USB Serial Communication (Coin Acceptor):
    - Baud rate: 115200
    - GET_BALANCE, RESET_BALANCE, SET_COIN_VALUE, SET_OUTPUT, STATUS
    
  Protocol (RXTX text-based commands, terminated with newline):
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
const int NUM_OUTPUTS = 48;          // 3 multiplexers × 16 channels
const int MOTORS_PER_MUX = 16;       // channels per multiplexer
const int NUM_MUXES = 3;             // number of multiplexers

// RXTX Serial pins for communication with Raspberry Pi
const int SERIAL2_RX_PIN = 3;        // ESP32 receives from Pi TX (GPIO 14)
const int SERIAL2_TX_PIN = 1;        // ESP32 sends to Pi RX (GPIO 15)

// ============================================================================
// PWM global motor speed control (shared for all motors on external parallel wiring)
const int PWM_PIN = 19;              // GPIO19 - PWM output to control motor speed
const int PWM_DEFAULT_DUTY = 230;    // default speed (~200 of 255)

// ============================================================================
// MOTOR PULSE CONFIGURATION
// ============================================================================
const unsigned long DEFAULT_PULSE_MS = 4000;  // Default pulse duration (4000ms = 4 seconds)
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

// Note: This firmware is for a 48-output machine (3 × CD74HC4067 multiplexers).
// Multiplexer 4 (slots 49-64) is not used in this configuration.

// ============================================================================
// COIN ACCEPTOR PIN CONFIGURATION (ESP32)
// ============================================================================
const int COIN_PIN = 5;        // GPIO 5 - coin detect input (from Allan 123A-Pro)
const int COUNTER_PIN = 18;    // GPIO 18 - optional counter feedback

// ============================================================================
// STATE TRACKING
// ============================================================================

unsigned long active_until[NUM_OUTPUTS];  // when each pulse expires
bool outputs_state[NUM_OUTPUTS];          // current ON/OFF state
String inputBuffer2 = "";                 // RXTX command buffer
String inputBuffer = "";                  // USB Serial command buffer

// --- Coin Acceptor State ---
volatile float received_amount = 0.0;
volatile unsigned long last_trigger_time = 0;
volatile bool coin_detected = false;
volatile int current_output = 1;  // Current active output (1-6 from Allan 123A-Pro)
unsigned long debounce_time_ms = 50;  // 50ms debounce for Allan 123A-Pro

// Allan 123A-Pro coin values - customizable per output
float COIN_VALUES[6] = {
  1.0,   // Output A1: Old 1 Peso Coin
  1.0,   // Output A2: New 1 Peso Coin
  5.0,   // Output A3: Old 5 Peso Coin
  5.0,   // Output A4: New 5 Peso Coin
  10.0,  // Output A5: Old 10 Peso Coin
  10.0   // Output A6: New 10 Peso Coin
};

// Multiplexer objects
CD74HC4067 mux1(MUX1_S0, MUX1_S1, MUX1_S2, MUX1_S3);
CD74HC4067 mux2(MUX2_S0, MUX2_S1, MUX2_S2, MUX2_S3);
CD74HC4067 mux3(MUX3_S0, MUX3_S1, MUX3_S2, MUX3_S3);
// MUX4 handled by Raspberry Pi; ESP32 does not instantiate a mux4 object

// ============================================================================
// FORWARD DECLARATIONS
// ============================================================================

void setOutput(int idx, bool on);
void processCommand(String cmd, Stream &out);
void processCoinCommand(String command);

// ============================================================================
// COIN ACCEPTOR INTERRUPT HANDLER
// ============================================================================
void IRAM_ATTR coin_interrupt() {
  unsigned long current_time = millis();
  
  // Debounce check
  if ((current_time - last_trigger_time) < debounce_time_ms) {
    return;
  }
  
  last_trigger_time = current_time;
  coin_detected = true;
  
  // Add coin value (current_output is 1-based, array is 0-based)
  if (current_output >= 1 && current_output <= 6) {
    received_amount += COIN_VALUES[current_output - 1];
  }
}

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

  // Multiplexer 4 not present — no ESP32 pin configuration required

  // Initialize coin acceptor pin
  pinMode(COIN_PIN, INPUT_PULLUP);
  if (COUNTER_PIN >= 0) {
    pinMode(COUNTER_PIN, INPUT_PULLUP);
  }
  attachInterrupt(digitalPinToInterrupt(COIN_PIN), coin_interrupt, FALLING);

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
  
  // Initialize PWM pin for global motor speed control using analogWrite
  pinMode(PWM_PIN, OUTPUT);
  analogWrite(PWM_PIN, PWM_DEFAULT_DUTY);
  
  Serial.println("==============================================================");
  Serial.println("ESP32 Vending Controller - RXTX + Coin Acceptor");
  Serial.println("==============================================================");
  Serial.print("Serial2 (RXTX) initialized:");
  Serial.print(" RX=GPIO"); Serial.print(SERIAL2_RX_PIN);
  Serial.print(" TX=GPIO"); Serial.println(SERIAL2_TX_PIN);
  Serial.print("Coin Acceptor on GPIO");
  Serial.print(COIN_PIN);
  Serial.print(" (Debounce: ");
  Serial.print(debounce_time_ms);
  Serial.println("ms)");
  Serial.print("Baud rate: "); Serial.println(BAUD_RATE);
  Serial.println("Waiting for commands...");
  Serial.println("==============================================================");
}

// ============================================================================
// MAIN LOOP
// ============================================================================

void loop() {
  // Check for coin detection event (USB Serial feedback)
  if (coin_detected) {
    coin_detected = false;
    
    if (current_output >= 1 && current_output <= 6) {
      float coin_value = COIN_VALUES[current_output - 1];
      Serial.print("[COIN] Output A");
      Serial.print(current_output);
      Serial.print(" - Value: ₱");
      Serial.print(coin_value, 1);
      Serial.print(" | Total: ₱");
      Serial.println(received_amount, 2);
    }
  }
  
  // Process USB Serial commands (coin acceptor)
  while (Serial.available()) {
    char c = (char)Serial.read();
    
    if (c == '\n') {
      if (inputBuffer.length() > 0) {
        Serial.print("CMD: ");
        Serial.println(inputBuffer);
        processCoinCommand(inputBuffer);
        inputBuffer = "";
      }
    } else if (c != '\r') {
      inputBuffer += c;
      if (inputBuffer.length() > 256) {
        inputBuffer = inputBuffer.substring(inputBuffer.length() - 256);
      }
    }
  }
  
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
    default:
      // Out of range for this firmware (supports 0..47 indices)
      break;
  }
}

// ============================================================================
// COIN ACCEPTOR COMMAND PROCESSING
// ============================================================================

void processCoinCommand(String command) {
  command.trim();
  command.toUpperCase();
  
  // Parse command
  int spaceIndex = command.indexOf(' ');
  String cmd = (spaceIndex > 0) ? command.substring(0, spaceIndex) : command;
  String param = (spaceIndex > 0) ? command.substring(spaceIndex + 1) : "";
  
  // GET_BALANCE
  if (cmd == "GET_BALANCE") {
    Serial.print("BALANCE: ₱");
    Serial.println(received_amount, 2);
  }
  // RESET_BALANCE
  else if (cmd == "RESET_BALANCE") {
    received_amount = 0.0;
    Serial.println("OK BALANCE_RESET");
  }
  // SET_COIN_VALUE
  else if (cmd == "SET_COIN_VALUE") {
    int output = 0;
    float value = 0.0;
    int firstSpace = param.indexOf(' ');
    if (firstSpace > 0) {
      output = param.substring(0, firstSpace).toInt();
      value = param.substring(firstSpace + 1).toFloat();
      
      if (output >= 1 && output <= 6 && value > 0) {
        COIN_VALUES[output - 1] = value;
        Serial.print("OK SET_COIN_VALUE A");
        Serial.print(output);
        Serial.print(" = ₱");
        Serial.println(value, 2);
      } else {
        Serial.println("ERR invalid output or value");
      }
    } else {
      Serial.println("ERR usage: SET_COIN_VALUE <output(1-6)> <value>");
    }
  }
  // SET_DEBOUNCE
  else if (cmd == "SET_DEBOUNCE") {
    unsigned long ms = param.toInt();
    if (ms >= 10 && ms <= 1000) {
      debounce_time_ms = ms;
      Serial.print("OK DEBOUNCE_SET: ");
      Serial.print(ms);
      Serial.println("ms");
    } else {
      Serial.println("ERR debounce must be 10-1000ms");
    }
  }
  // SET_OUTPUT
  else if (cmd == "SET_OUTPUT") {
    int output = param.toInt();
    if (output >= 1 && output <= 6) {
      current_output = output;
      Serial.print("OK OUTPUT_SET: A");
      Serial.print(output);
      Serial.print(" (₱");
      Serial.print(COIN_VALUES[output - 1], 1);
      Serial.println(")");
    } else {
      Serial.println("ERR output must be 1-6");
    }
  }
  // STATUS
  else if (cmd == "STATUS") {
    Serial.println("=== Coin Acceptor Status ===");
    Serial.print("Current Output: A");
    Serial.println(current_output);
    Serial.print("Current Balance: ₱");
    Serial.println(received_amount, 2);
    Serial.print("Debounce Time: ");
    Serial.print(debounce_time_ms);
    Serial.println("ms");
  }
  else {
    Serial.println("ERR unknown command");
  }
}


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

  // PULSE <slot> <ms> - pulse for specified milliseconds (uses DEFAULT_PULSE_MS from ESP32 config)
  if (command == "PULSE") {
    if (partCount >= 2) {
      int slot = parts[1].toInt();
      if (slot >= 1 && slot <= NUM_OUTPUTS) {
        int idx = slot - 1;
        active_until[idx] = millis() + DEFAULT_PULSE_MS;  // Use DEFAULT_PULSE_MS from ESP32 config
        outputs_state[idx] = true;
        setOutput(idx, true);
        out.println("OK");
      } else {
        out.print("ERR invalid slot ");
        out.println(slot);
      }
    } else {
      out.println("ERR PULSE requires: PULSE <slot>");
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
