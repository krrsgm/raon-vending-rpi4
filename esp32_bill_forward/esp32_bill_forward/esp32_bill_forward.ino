/*
  arduino_bill_forward.ino

  Combined Arduino sketch for:
  1. Bill Acceptor - detects pulses and maps them to peso values
  2. Coin Hopper Control - controls two coin hoppers (1-peso and 5-peso) over USB serial
  
  The sketch listens on USB Serial for simple text commands and controls motor outputs
  while counting coins via sensor inputs. Also detects bill insertions via pulse input.

  Protocol (USB Serial, 115200 baud):
    COIN HOPPER:
    - DISPENSE_AMOUNT <amount> [timeout_ms]
    - DISPENSE_DENOM <denom> <count> [timeout_ms]
    - OPEN <denom>
    - CLOSE <denom>
    - STATUS
    - STOP

  Adjust `ONE_MOTOR_PIN`, `FIVE_MOTOR_PIN`, `ONE_SENSOR_PIN`, `FIVE_SENSOR_PIN`,
  and `pulsePin` to match wiring. This build uses USB Serial only (no RX/TX Serial2).
*/

// Include Arduino and C++ helpers
#include <Arduino.h>

// --- Bill Acceptor Pin Configuration ---
volatile int pulseCount = 0;
volatile unsigned long lastPulseTime = 0;
volatile bool pulseEvent = false; // flag for main loop printing/processing
const int pulsePin = 2; // use pin 2 (commonly supports external interrupt)
const unsigned long timeout = 2000; // 2 seconds (increased to allow complete bill insertion)

volatile bool waitingForBill = false;
volatile bool billProcessed = false;
const unsigned long pulseDebounceMs = 60; // debounce interval in ms (INCREASED from 20ms to filter noise)

// --- Coin Hopper Pin Configuration ---
// Default pins are for ESP32. For Arduino Uno/Nano, an AVR macro will switch to
// safer Uno-compatible pins (motor outputs on 9/10, sensors on 11/12).
const int ONE_MOTOR_PIN = 9;   // 1-peso motor control (Uno digital pin 9)
const int FIVE_MOTOR_PIN = 10; // 5-peso motor control (Uno digital pin 10)

const int ONE_SENSOR_PIN = 11; // 1-peso sensor input (Uno digital pin 11)
const int FIVE_SENSOR_PIN = 12; // 5-peso sensor input (Uno digital pin 12)

const unsigned long BAUD_RATE = 115200;

// --- Coin Hopper State Variables ---
unsigned int one_count = 0;
unsigned int five_count = 0;
int last_one_state = HIGH;  // Track previous state for edge detection
int last_five_state = HIGH;

struct DispenseJob {
  bool active;
  unsigned int target;
  unsigned long start_ms;
  unsigned long timeout_ms;
};

DispenseJob job_one = {false, 0, 0, 30000};
DispenseJob job_five = {false, 0, 0, 30000};

bool sequence_active = false;
unsigned long sequence_timeout_ms = 30000;

String inputBuffer = "";

// --- Motor Control Functions ---
// Configure the relay/motor active level.
// This project uses normally-open relays (active when pin is LOW), so
// set the active level to LOW and inactive to HIGH.
const int RELAY_ACTIVE_LEVEL = LOW;      // energized / motor ON for normally-open wiring
const int RELAY_INACTIVE_LEVEL = HIGH;  // de-energized / motor OFF

void start_motor(int pin) { digitalWrite(pin, RELAY_ACTIVE_LEVEL); }
void stop_motor(int pin) { digitalWrite(pin, RELAY_INACTIVE_LEVEL); }

// --- Coin Hopper Functions ---
void start_dispense_denon(int denom, unsigned int count, unsigned long timeout_ms);

void start_dispense_denon(int denom, unsigned int count, unsigned long timeout_ms, Stream &out) {
  if (denom == 5) {
    five_count = 0;
    job_five.active = true;
    job_five.target = count;
    job_five.start_ms = millis();
    job_five.timeout_ms = timeout_ms;
    start_motor(FIVE_MOTOR_PIN);
    out.println("OK START FIVE");
  } else {
    one_count = 0;
    job_one.active = true;
    job_one.target = count;
    job_one.start_ms = millis();
    job_one.timeout_ms = timeout_ms;
    start_motor(ONE_MOTOR_PIN);
    out.println("OK START ONE");
  }
}

// Ensure file-level braces are balanced
}

// Backwards-compatible wrapper which uses USB Serial
void start_dispense_denon(int denom, unsigned int count, unsigned long timeout_ms) {
  start_dispense_denon(denom, count, timeout_ms, Serial);
}

void stop_all_jobs(const char *reason, Stream &out) {
  job_one.active = false;
  job_five.active = false;
  stop_motor(ONE_MOTOR_PIN);
  stop_motor(FIVE_MOTOR_PIN);
  sequence_active = false;
  out.print("STOPPED "); out.println(reason);
}

void stop_all_jobs(const char *reason) {
  stop_all_jobs(reason, Serial);
}

void report_status(Stream &out) {
  String s = "STATUS ";
  s += "ONE:" + String(one_count) + ",JOBONE:" + (job_one.active?"RUN":"IDLE") + ",FIVE:" + String(five_count) + ",JOBFIVE:" + (job_five.active?"RUN":"IDLE");
  out.println(s);
}

void report_status() {
  report_status(Serial);
}

void processLine(String line, Stream &out) {
  line.trim();
  if (line.length() == 0) return;
  String parts[10];  // Fixed-size array for command parts (max 10 parts)
  int partCount = 0;
  int start = 0;
  int len = (int) line.length();
  for (int i = 0; i <= len; i++){
    if (i == len || isspace(line.charAt(i))){
      if (i-start>0 && partCount < 10) {
        parts[partCount] = line.substring(start,i);
        partCount++;
      }
      start = i+1;
    }
  }
  if (partCount == 0) return;
  String cmd = parts[0]; cmd.toUpperCase();

  if (cmd == "DISPENSE_AMOUNT"){
    if (partCount >= 2){
      int amount = parts[1].toInt();
      unsigned long tmo = 30000;
      if (partCount >= 3) tmo = (unsigned long) parts[2].toInt();
      if (amount <= 0){ out.println("ERR bad amount"); return; }
      int five_needed = amount / 5;
      int one_needed = amount % 5;
      sequence_active = true;
      sequence_timeout_ms = tmo;
      five_count = 0; one_count = 0;
      if (five_needed > 0){ start_dispense_denon(5, five_needed, tmo); }
      else if (one_needed > 0) { start_dispense_denon(1, one_needed, tmo); }
      else { out.println("OK NOTHING_TO_DO"); }
      out.println("OK DISPENSE_AMOUNT QUEUED");
    }
  } else if (cmd == "DISPENSE_DENOM"){
    if (partCount >= 3){
      int denom = parts[1].toInt();
      int count = parts[2].toInt();
      unsigned long tmo = 30000;
      if (partCount >= 4) tmo = (unsigned long) parts[3].toInt();
      if (denom != 1 && denom != 5){ out.println("ERR bad denom"); return; }
      if (count <= 0){ out.println("ERR bad count"); return; }
      start_dispense_denon(denom, count, tmo, out);
      out.println("OK DISPENSE_DENOM STARTED");
    }
  } else if (cmd == "OPEN"){
    if (partCount >= 2) {
      int denom = parts[1].toInt();
      if (denom == 1) {
        start_motor(ONE_MOTOR_PIN);
        out.println("OK OPEN ONE");
      } else if (denom == 5) {
        start_motor(FIVE_MOTOR_PIN);
        out.println("OK OPEN FIVE");
      } else {
        out.println("ERR bad denom");
      }
    }
  } else if (cmd == "CLOSE"){
    if (partCount >= 2) {
      int denom = parts[1].toInt();
      if (denom == 1) {
        stop_motor(ONE_MOTOR_PIN);
        out.println("OK CLOSE ONE");
      } else if (denom == 5) {
        stop_motor(FIVE_MOTOR_PIN);
        out.println("OK CLOSE FIVE");
      } else {
        out.println("ERR bad denom");
      }
    }
  } else if (cmd == "STATUS"){
    report_status(out);
  } else if (cmd == "STOP"){
    stop_all_jobs("user", out);
  } else {
    out.println("ERR unknown command");
  }

// --- Bill Acceptor Functions ---
void countPulse() {
  unsigned long now = millis();
  if (now - lastPulseTime < pulseDebounceMs) return; // simple ISR debounce
  pulseCount++;
  lastPulseTime = now;
  waitingForBill = true;
  billProcessed = false; // allow new bill to be processed
  pulseEvent = true; // set flag; do NOT call Serial from ISR
}

int mapPulsesToPesos(int pulses) {
  // Allow tolerance range for hardware variability
  if (pulses >= 4 && pulses <= 6) return 50;    // 50 peso bill (accepts 4-6 pulses)
  switch (pulses) {
    case 2: return 20;    // 20 peso bill
    case 10: return 100;  // 100 peso bill

    default: return 0;    // Only accept 20, 50, and 100 peso bills
  }
}

void setup(){
  // Initialize coin hopper pins
  pinMode(ONE_MOTOR_PIN, OUTPUT);
  pinMode(FIVE_MOTOR_PIN, OUTPUT);
  // Initialize motors to INACTIVE (de-energized) for normally-open relays
  digitalWrite(ONE_MOTOR_PIN, RELAY_INACTIVE_LEVEL);
  digitalWrite(FIVE_MOTOR_PIN, RELAY_INACTIVE_LEVEL);
  pinMode(ONE_SENSOR_PIN, INPUT);
  pinMode(FIVE_SENSOR_PIN, INPUT);
  
  // Initialize bill acceptor pins
  pinMode(pulsePin, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(pulsePin), countPulse, FALLING);
  
  Serial.begin(BAUD_RATE);
  
  // This build uses USB Serial only; Serial2 (RX/TX) disabled
  Serial.println("Using USB Serial only; RX/TX Serial2 disabled");
  
  delay(50);
  Serial.println("Arduino Bill Acceptor & Coin Hopper ready");
}

void loop(){
  // --- Bill Acceptor Processing ---
  // Immediate report of pulse events (set by ISR) to help diagnostics
  if (pulseEvent) {
    int pulses;
    noInterrupts();
    pulses = pulseCount;
    pulseEvent = false;
    interrupts();
    Serial.print("Pulse detected. Total: ");
    Serial.println(pulses);
  }

  // Handle settled pulses (debounced via ISR and using volatile state)
  static int lastReportedPulseCount = -1;
  if (waitingForBill && !billProcessed && millis() - (unsigned long)lastPulseTime > timeout) {
    int pulses;
    noInterrupts(); // copy shared variables atomically
    pulses = pulseCount;
    interrupts();

    int pesoValue = mapPulsesToPesos(pulses);
    if (pesoValue > 0) {
      Serial.print("Bill inserted: ₱");
      Serial.print(pesoValue);
      Serial.print(" (pulses: ");
      Serial.print(pulses);
      Serial.println(")");
      noInterrupts();
      pulseCount = 0;
      interrupts();
      waitingForBill = false;
      billProcessed = true;
      lastReportedPulseCount = -1;
    } else {
      // report unknown counts only when they change
      if (pulses != lastReportedPulseCount) {
        Serial.print("[DEBUG] Unknown pulse count: ");
        Serial.print(pulses);
        Serial.println(" - Try adjusting pulseDebounceMs or check bill acceptor calibration");
        lastReportedPulseCount = pulses;
      }
      // long idle reset for unknown counts
      if (millis() - (unsigned long)lastPulseTime > timeout + 5000) {
        noInterrupts();
        pulseCount = 0;
        interrupts();
        waitingForBill = false;
        billProcessed = true;
        lastReportedPulseCount = -1;
      }
    }
  }

  // --- Coin Hopper Sensor Polling ---
  // Fast sensor polling - detect HIGH → LOW transition (coins passing through)
  int one_state = digitalRead(ONE_SENSOR_PIN);
  int five_state = digitalRead(FIVE_SENSOR_PIN);
  
  if (last_one_state == HIGH && one_state == LOW) {
    one_count++;
  }
  
  if (last_five_state == HIGH && five_state == LOW) {
    five_count++;
  }
  
  last_one_state = one_state;
  last_five_state = five_state;

  // --- Serial Command Processing ---
  while (Serial.available()){
    char c = (char) Serial.read();
    if (c == '\n'){
      if (inputBuffer.length() > 0){ Serial.print("CMD: "); Serial.println(inputBuffer); processLine(inputBuffer); inputBuffer = ""; }
    } else if (c != '\r'){
      inputBuffer += c;
      if (inputBuffer.length() > 256) inputBuffer = inputBuffer.substring(inputBuffer.length()-256);
    }
  }

  // Serial2 (RX/TX) disabled — commands are accepted over USB Serial only

  // --- Coin Hopper Job Management ---
  unsigned long now = millis();
  if (job_five.active){
    if (five_count >= job_five.target){ stop_motor(FIVE_MOTOR_PIN); job_five.active = false; Serial.print("DONE FIVE "); Serial.println(five_count); if (sequence_active && job_one.target > 0 && !job_one.active){ if (job_one.target > 0){ start_dispense_denon(1, job_one.target, sequence_timeout_ms); } } }
    else if (now - job_five.start_ms > job_five.timeout_ms){ stop_motor(FIVE_MOTOR_PIN); job_five.active = false; Serial.print("ERR TIMEOUT FIVE dispensed:"); Serial.println(five_count); }
  }

  if (job_one.active){
    if (one_count >= job_one.target){ stop_motor(ONE_MOTOR_PIN); job_one.active = false; Serial.print("DONE ONE "); Serial.println(one_count); sequence_active = false; }
    else if (now - job_one.start_ms > job_one.timeout_ms){ stop_motor(ONE_MOTOR_PIN); job_one.active = false; Serial.print("ERR TIMEOUT ONE dispensed:"); Serial.println(one_count); sequence_active = false; }
  }

  if (sequence_active && !job_five.active && !job_one.active){ if (job_one.target > 0 && one_count < job_one.target){ start_dispense_denon(1, job_one.target, sequence_timeout_ms); } }
}
