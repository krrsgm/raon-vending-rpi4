/*
  arduino_bill_forward.ino
  Simplified coin hopper sketch: supports DISPENSE_AMOUNT, DISPENSE_DENOM,
  OPEN <denom>, CLOSE <denom>, STATUS, STOP over USB Serial.
  Motors (relays) on pins 9 (1-peso) and 10 (5-peso).
  Sensors on pins 11 (1-peso) and 12 (5-peso) - simple LOW-edge coin detection.
*/

#include <Arduino.h>

const unsigned long BAUD_RATE = 115200;

// Pin definitions (matches requested mapping)
const int ONE_MOTOR_PIN = 9;   // Relay/motor for 1-peso
const int FIVE_MOTOR_PIN = 10; // Relay/motor for 5-peso
const int ONE_SENSOR_PIN = 11; // Sensor that detects 1-peso coin passage
const int FIVE_SENSOR_PIN = 12; // Sensor that detects 5-peso coin passage

// --- Bill acceptor pulse input (optional)
const int pulsePin = 2;         // pulse input from bill acceptor
volatile int pulseCount = 0;
volatile unsigned long lastPulseTime = 0;
const unsigned long pulseDebounceMs = 5;
const unsigned long timeout = 1000; // ms to consider pulse sequence ended
volatile bool pulseEvent = false;
bool waitingForBill = false;
bool billProcessed = true;

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
void start_motor(int pin) { digitalWrite(pin, HIGH); }
void stop_motor(int pin) { digitalWrite(pin, LOW); }

// --- Coin Hopper Functions (Simple) ---
void start_dispense_denom(int denom, unsigned int count, unsigned long timeout_ms, Stream &out) {
  if (denom == 5) {
    five_count = 0; // start counting fresh for this job
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

void start_dispense_denom(int denom, unsigned int count, unsigned long timeout_ms) {
  start_dispense_denom(denom, count, timeout_ms, Serial);
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
  s += "one_count:" + String(one_count) + " five_count:" + String(five_count) + " job_one:" + (job_one.active?"RUN":"IDLE") + " job_five:" + (job_five.active?"RUN":"IDLE");
  out.println(s);
}

void report_status() {
  report_status(Serial);
}

void processLine(String line, Stream &out) {
  line.trim();
  if (line.length() == 0) return;
  String parts[6];
  int partCount = 0;
  int start = 0;
  for (int i=0;i<=line.length();i++){
    if (i==line.length() || isspace(line.charAt(i))){
      if (i-start>0 && partCount < 6) {
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
      // start with 5-peso coins first
      if (five_needed > 0){
        job_one.target = one_needed; // queued for later
        start_dispense_denom(5, five_needed, tmo, out);
      } else if (one_needed > 0) {
        start_dispense_denom(1, one_needed, tmo, out);
      } else {
        out.println("OK NOTHING_TO_DO");
      }
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
      start_dispense_denom(denom, count, tmo, out);
      out.println("OK DISPENSE_DENOM STARTED");
    }
  } else if (cmd == "OPEN"){
    if (partCount >= 2){ int denom = parts[1].toInt(); if (denom == 1){ start_motor(ONE_MOTOR_PIN); out.println("OK OPEN ONE"); } else if (denom == 5){ start_motor(FIVE_MOTOR_PIN); out.println("OK OPEN FIVE"); } else out.println("ERR bad denom"); }
  } else if (cmd == "CLOSE"){
    if (partCount >= 2){ int denom = parts[1].toInt(); if (denom == 1){ stop_motor(ONE_MOTOR_PIN); out.println("OK CLOSE ONE"); } else if (denom == 5){ stop_motor(FIVE_MOTOR_PIN); out.println("OK CLOSE FIVE"); } else out.println("ERR bad denom"); }
  } else if (cmd == "STATUS"){
    report_status(out);
  } else if (cmd == "STOP"){
    stop_all_jobs("user", out);
  } else {
    out.println("ERR unknown command");
  }
}

// Backward-compatible wrapper that outputs to USB Serial
void processLine(String line) { processLine(line, Serial); }

// We keep the bill acceptor pulse counting behavior (optional) but the
// main focus here is the coin hopper simple counting and dispensing.
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
  switch (pulses) {
    case 2: return 20;    // 20 peso bill
    case 5: return 50;    // 50 peso bill
    case 10: return 100;  // 100 peso bill
    case 50: return 500;  // 500 peso bill
    default: return 0;    // Only accept 20, 50, 100, and 500 peso bills
  }
}

void setup(){
  // Initialize coin hopper pins
  pinMode(ONE_MOTOR_PIN, OUTPUT);
  pinMode(FIVE_MOTOR_PIN, OUTPUT);
  digitalWrite(ONE_MOTOR_PIN, LOW);
  digitalWrite(FIVE_MOTOR_PIN, LOW);
  pinMode(ONE_SENSOR_PIN, INPUT);
  pinMode(FIVE_SENSOR_PIN, INPUT);
  
  // Initialize bill acceptor pins
  pinMode(pulsePin, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(pulsePin), countPulse, FALLING);
  
  Serial.begin(BAUD_RATE);
  
  // Diagnostics
  Serial.println("Simple Coin Hopper & Bill Acceptor ready");
}

void loop(){
  // Report pulse events for diagnostics
  if (pulseEvent) {
    int pulses;
    noInterrupts();
    pulses = pulseCount;
    pulseEvent = false;
    interrupts();
    Serial.print("Pulse detected. Total: ");
    Serial.println(pulses);
  }

  // Bill acceptor settle handling (unchanged)
  static int lastReportedPulseCount = -1;
  if (waitingForBill && !billProcessed && millis() - (unsigned long)lastPulseTime > timeout) {
    int pulses;
    noInterrupts();
    pulses = pulseCount;
    interrupts();
    int pesoValue = mapPulsesToPesos(pulses);
    if (pesoValue > 0) {
      Serial.print("Bill inserted: ");
      Serial.println(pesoValue);
      noInterrupts();
      pulseCount = 0;
      interrupts();
      waitingForBill = false;
      billProcessed = true;
      lastReportedPulseCount = -1;
    } else {
      if (pulses != lastReportedPulseCount) {
        Serial.print("Unknown pulse count: ");
        Serial.println(pulses);
        lastReportedPulseCount = pulses;
      }
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

  // --- Sensor polling: count LOW edges (coin passes)
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
      if (inputBuffer.length() > 0){ processLine(inputBuffer); inputBuffer = ""; }
    } else if (c != '\r'){
      inputBuffer += c;
      if (inputBuffer.length() > 256) inputBuffer = inputBuffer.substring(inputBuffer.length()-256);
    }
  }

  // --- Job management: check for completion and sequencing ---
  unsigned long now = millis();
  if (job_five.active){
    if (five_count >= job_five.target){
      stop_motor(FIVE_MOTOR_PIN);
      job_five.active = false;
      Serial.print("DONE FIVE "); Serial.println(five_count);
      // If sequence queued (one coins), start one job
      if (sequence_active && job_one.target > 0 && !job_one.active){
        start_dispense_denom(1, job_one.target, sequence_timeout_ms, Serial);
      } else {
        sequence_active = false;
      }
    } else if (now - job_five.start_ms > job_five.timeout_ms){
      stop_motor(FIVE_MOTOR_PIN);
      job_five.active = false;
      Serial.print("ERR TIMEOUT FIVE dispensed:"); Serial.println(five_count);
    }
  }

  if (job_one.active){
    if (one_count >= job_one.target){
      stop_motor(ONE_MOTOR_PIN);
      job_one.active = false;
      Serial.print("DONE ONE "); Serial.println(one_count);
      sequence_active = false;
    } else if (now - job_one.start_ms > job_one.timeout_ms){
      stop_motor(ONE_MOTOR_PIN);
      job_one.active = false;
      Serial.print("ERR TIMEOUT ONE dispensed:"); Serial.println(one_count);
      sequence_active = false;
    }
  }
}
