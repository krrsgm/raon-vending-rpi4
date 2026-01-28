/*
  vending_controller.ino
  ESP32 Arduino sketch to control 60 outputs using 4 x CD74HC4067 16-channel multiplexers.

  Protocol (Serial communication with Raspberry Pi):
    - PULSE <slot> <ms>   : pulse output for <ms> milliseconds (slot numbers 1..60)
    - OPEN <slot>         : set output on (continuous)
    - CLOSE <slot>        : set output off
    - OPENALL             : set all outputs on
    - CLOSEALL            : set all outputs off
    - STATUS              : returns ON slots as comma-separated

  Wiring:
    - 4 x CD74HC4067 multiplexers with individual control pins
    - Serial Communication with Raspberry Pi:
      - ESP32 TX (GPIO 1) -> Raspberry Pi RX
      - ESP32 RX (GPIO 3) -> Raspberry Pi TX
      - Connect GND between ESP32 and Raspberry Pi

  Usage:
    - Connect ESP32 to Raspberry Pi via UART (TX/RX)
    - Send commands through serial at 115200 baud rate
    - Each command should end with a newline character
    - Example: "PULSE 12 800\n"

  Notes:
    - This sketch uses non-blocking timers for pulses, so multiple outputs can be active concurrently.
    - Each multiplexer controls 15 motors (using channels 0-14).
*/

#include <Arduino.h>
#include <CD74HC4067.h>

// Serial Communication Settings
const unsigned long BAUD_RATE = 115200;

// Optional: explicitly bind Serial2 (UART2) to specific RX/TX pins.
// Set to -1 to use the ESP32 default Serial2 pins for your board.
// If you wired the Pi's TX/RX to specific ESP32 GPIOs, change these
// to match your wiring (example: 16, 17).
const int SERIAL2_RX_PIN = 3; // change to your wiring RX pin (ESP32 GPIO)
const int SERIAL2_TX_PIN = 1; // change to your wiring TX pin (ESP32 GPIO)

// Multiplexer 1 pins (Slots 1-15)
const int MUX1_S0 = 13;
const int MUX1_S1 = 12;
const int MUX1_S2 = 14; 
const int MUX1_S3 = 27;
const int MUX1_SIG = 23;

// Multiplexer 2 pins (Slots 16-30)
const int MUX2_S0 = 26;
const int MUX2_S1 = 25;
const int MUX2_S2 = 33;
const int MUX2_S3 = 32;
const int MUX2_SIG = 22;

// Multiplexer 3 pins (Slots 31-45)
const int MUX3_S0 = 15;
const int MUX3_S1 = 2;
const int MUX3_S2 = 4;
const int MUX3_S3 = 16;
const int MUX3_SIG = 21;

// Multiplexer 4 pins (Slots 46-60)
const int MUX4_S0 = 17;
const int MUX4_S1 = 5;
const int MUX4_S2 = 18;
const int MUX4_S3 = 19;
const int MUX4_SIG = 35;

// Constants
const int NUM_OUTPUTS = 60;  // Total number of motors
const int MOTORS_PER_MUX = 15;  // We use 15 channels per multiplexer

// Array to track active until (millis). 0 means off.
unsigned long active_until[NUM_OUTPUTS];
bool outputs_state[NUM_OUTPUTS]; // State tracking for each output
String inputBuffer = "";         // Buffer for incoming serial data (USB / Serial)
String inputBuffer2 = "";        // Buffer for incoming Serial2 (RX/TX)

// Create multiplexer objects
// The CD74HC4067 library constructor takes the selector pins (s0..s3).
// The SIG pin (common I/O) is controlled separately (we write it high/low).
CD74HC4067 mux1(MUX1_S0, MUX1_S1, MUX1_S2, MUX1_S3);
CD74HC4067 mux2(MUX2_S0, MUX2_S1, MUX2_S2, MUX2_S3);
CD74HC4067 mux3(MUX3_S0, MUX3_S1, MUX3_S2, MUX3_S3);
CD74HC4067 mux4(MUX4_S0, MUX4_S1, MUX4_S2, MUX4_S3);

// --- forward declarations ---
void setOutput(int idx, bool on);
void processLine(String line, Stream &out);

void setup(){

  // Initialize multiplexer 1 pins
  pinMode(MUX1_S0, OUTPUT);
  pinMode(MUX1_S1, OUTPUT);
  pinMode(MUX1_S2, OUTPUT);
  pinMode(MUX1_S3, OUTPUT);
  pinMode(MUX1_SIG, OUTPUT);

  // Initialize multiplexer 2 pins
  pinMode(MUX2_S0, OUTPUT);
  pinMode(MUX2_S1, OUTPUT);
  pinMode(MUX2_S2, OUTPUT);
  pinMode(MUX2_S3, OUTPUT);
  pinMode(MUX2_SIG, OUTPUT);

  // Initialize multiplexer 3 pins
  pinMode(MUX3_S0, OUTPUT);
  pinMode(MUX3_S1, OUTPUT);
  pinMode(MUX3_S2, OUTPUT);
  pinMode(MUX3_S3, OUTPUT);
  pinMode(MUX3_SIG, OUTPUT);

  // Initialize multiplexer 4 pins
  pinMode(MUX4_S0, OUTPUT);
  pinMode(MUX4_S1, OUTPUT);
  pinMode(MUX4_S2, OUTPUT);
  pinMode(MUX4_S3, OUTPUT);
  pinMode(MUX4_SIG, OUTPUT);

  // init outputs off
  for(int i=0; i<NUM_OUTPUTS; i++){
    active_until[i] = 0;
    outputs_state[i] = false;
    setOutput(i, false);
  }

  // Initialize serial communication for both USB (Serial) and hardware UART (Serial2)
  // This allows using USB CDC (Serial) or RX/TX wiring (Serial2) to connect to the Pi.
  Serial.begin(BAUD_RATE);
  // Start Serial2 (UART): use explicit pins if configured, otherwise use defaults.
  #ifdef HAVE_HWSERIAL2
  if (SERIAL2_RX_PIN >= 0 && SERIAL2_TX_PIN >= 0) {
    Serial2.begin(BAUD_RATE, SERIAL_8N1, SERIAL2_RX_PIN, SERIAL2_TX_PIN);
    Serial.print("Serial2 started on RX="); Serial.print(SERIAL2_RX_PIN);
    Serial.print(" TX="); Serial.println(SERIAL2_TX_PIN);
  } else {
    Serial2.begin(BAUD_RATE);
    Serial.println("Serial2 started on default pins");
  }
  #else
  Serial.println("Serial2 not available on this board");
  #endif
  delay(100);
  Serial.println("ESP32 Vending Controller starting...");
  Serial.println("Listening on Serial (USB) and Serial2 (RX/TX)");
}

void loop(){
  // Read from Serial (USB/CDC)
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      if (inputBuffer.length() > 0) {
        Serial.print("CMD(Serial): "); Serial.println(inputBuffer);
        processLine(inputBuffer, Serial);
        inputBuffer = "";
      }
    } else {
      inputBuffer += c;
    }
  }

  // Read from Serial2 (hardware RX/TX wiring to Pi)
  #ifdef HAVE_HWSERIAL2
  while (Serial2.available()) {
    char c = Serial2.read();
    if (c == '\n') {
      if (inputBuffer2.length() > 0) {
        Serial.print("CMD(Serial2): "); Serial.println(inputBuffer2); // debug on USB
        processLine(inputBuffer2, Serial2);
        inputBuffer2 = "";
      }
    } else {
      inputBuffer2 += c;
    }
  }
  #endif

  // Manage timers: clear outputs when their time expires
  unsigned long now = millis();
  bool changed = false;
  for(int i=0;i<NUM_OUTPUTS;i++){
    if (active_until[i] != 0 && now >= active_until[i]){
      active_until[i] = 0;
      // clear state for this index and turn the output off
      if (outputs_state[i]) {
        outputs_state[i] = false;
        setOutput(i, false);
        changed = true;
      }
    }
  }
  (void)changed; // changed is kept for future use / debugging
}

void setOutput(int idx, bool on) {
  if (idx < 0 || idx >= NUM_OUTPUTS) return;
  
  // Calculate which multiplexer and channel to use
  int mux_num = idx / MOTORS_PER_MUX;  // 0-3 for the four multiplexers
  int channel = idx % MOTORS_PER_MUX;   // 0-14 for the channels within each mux
  
  // Update state tracking
  outputs_state[idx] = on;
  
  // Select the right multiplexer and set its channel
  switch(mux_num) {
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

void processLine(String line, Stream &out){
  // Simple whitespace-separated parsing
  // Commands: PULSE <slot> <ms>, OPEN <slot>, CLOSE <slot>, OPENALL, CLOSEALL, STATUS
  line.trim();
  if (line.length()==0) return;
  // split
  String parts[10];  // Fixed-size array for command parts (max 10 parts)
  int partCount = 0;
  int start = 0;
  for (int i=0;i<=line.length();i++){
    if (i==line.length() || isspace(line.charAt(i))) {
      if (i-start>0 && partCount < 10) {
        parts[partCount] = line.substring(start,i);
        partCount++;
      }
      start = i+1;
    }
  }
  if (partCount==0) return;
  String cmd = parts[0];
  cmd.toUpperCase();

  if (cmd == "PULSE"){
    if (partCount >= 3){
      int slot = parts[1].toInt();
      unsigned long ms = (unsigned long) parts[2].toInt();
      if (slot >=1 && slot <= 60){
        int idx = slot - 1; // mapping
        // set active until and set bit
        active_until[idx] = millis() + ms;
        outputs_state[idx] = true;
        setOutput(idx, true);
        out.println("OK");
      } else {
        out.println("ERR slot range 1..60");
      }
    }
  } else if (cmd == "OPEN"){
    if (partCount >= 2){
      int slot = parts[1].toInt();
      if (slot >=1 && slot <= NUM_OUTPUTS){
        setOutput(slot-1, true);
        out.println("OK");
      }
    }
  } else if (cmd == "CLOSE"){
    if (partCount >= 2){
      int slot = parts[1].toInt();
      if (slot >=1 && slot <= NUM_OUTPUTS){
        setOutput(slot-1, false);
        out.println("OK");
      }
    }
  } else if (cmd == "OPENALL"){
    for(int i=0; i<NUM_OUTPUTS; i++) {
      setOutput(i, true);
      outputs_state[i] = true;
    }
    out.println("OK");
  } else if (cmd == "CLOSEALL"){
    for(int i=0; i<NUM_OUTPUTS; i++) {
      setOutput(i, false);
      outputs_state[i] = false;
    }
    out.println("OK");
  } else if (cmd == "STATUS"){
    // return CSV of ON slots (1-based)
    String csv = "";
    for (int i=0; i<NUM_OUTPUTS; i++){
      if (outputs_state[i]){
        if (csv.length()>0) csv += ",";
        csv += String(i+1);
      }
    }
    out.println(csv);
  } else {
    out.println("ERR unknown command");
  }
}
