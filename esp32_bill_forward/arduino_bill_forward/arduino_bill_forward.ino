/*
  arduino_bill_forward.ino

  Combined Arduino sketch for:
  1. Bill Acceptor - detects pulses and maps them to peso values
  2. Coin Hopper Control - controls two coin hoppers (1-peso and 5-peso) over USB serial
  
  The sketch listens on Serial for simple text commands and controls motor outputs 
  while counting coins via sensor inputs. Also detects bill insertions via pulse input.

  Protocol (Serial, 115200 baud):
    COIN HOPPER:
    - DISPENSE_AMOUNT <amount> [timeout_ms]
    - DISPENSE_DENOM <denom> <count> [timeout_ms]
    - OPEN <denom>
    - CLOSE <denom>
    - STATUS
    - STOP

  Adjust `ONE_MOTOR_PIN`, `FIVE_MOTOR_PIN`, `ONE_SENSOR_PIN`, `FIVE_SENSOR_PIN`, 
  and `pulsePin` to match wiring.
*/

// Include Arduino and C++ helpers
#include <Arduino.h>

// --- Bill Acceptor Pin Configuration ---
volatile int pulseCount = 0;
unsigned long lastPulseTime = 0;
const int pulsePin = 2;
const unsigned long timeout = 1000; // 1 second

bool waitingForBill = false;
bool billProcessed = false;

// --- Coin Hopper Pin Configuration ---
const int ONE_MOTOR_PIN = 9;    // 1-peso motor control
const int FIVE_MOTOR_PIN = 10;  // 5-peso motor control

const int ONE_SENSOR_PIN = 11;  // 1-peso sensor input
const int FIVE_SENSOR_PIN = 12; // 5-peso sensor input

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
String inputBuffer2 = ""; // for Serial2 (RX/TX) data

// Optional: configure Serial2 RX/TX pins; set to -1 to use defaults
const int SERIAL2_RX_PIN = 3;
const int SERIAL2_TX_PIN = 1;

// --- Motor Control Functions ---
void start_motor(int pin) { digitalWrite(pin, HIGH); }
void stop_motor(int pin) { digitalWrite(pin, LOW); }

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
  for (int i=0;i<=line.length();i++){
    if (i==line.length() || isspace(line.charAt(i))){
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

// --- Bill Acceptor Functions ---
void countPulse() {
  pulseCount++;
  lastPulseTime = millis();
  waitingForBill = true;
  billProcessed = false; // allow new bill to be processed
  Serial.print("Pulse detected. Total: ");
  Serial.println(pulseCount);
}

int mapPulsesToPesos(int pulses) {
  switch (pulses) {
    case 2: return 20;
    case 5: return 50;
    case 10: return 100;
    case 20: return 200;
    case 50: return 500;
    case 100: return 1000;
    default: return 0;
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
  
  // Start Serial2 for UART RX/TX communication with Pi; use default pins when -1
  #ifdef HAVE_HWSERIAL2
  if (SERIAL2_RX_PIN >= 0 && SERIAL2_TX_PIN >= 0) {
    Serial2.begin(BAUD_RATE, SERIAL_8N1, SERIAL2_RX_PIN, SERIAL2_TX_PIN);
    Serial.print("Serial2 started on RX="); Serial.print(SERIAL2_RX_PIN);
    Serial.print(" TX="); Serial.println(SERIAL2_TX_PIN);
  } else {
    Serial2.begin(BAUD_RATE);
    Serial.println("Serial2 ready on default pins");
  }
  #else
  Serial.println("Serial2 not available on this board");
  #endif
  
  delay(50);
  Serial.println("Arduino Bill Acceptor & Coin Hopper ready");
}

void loop(){
  // --- Bill Acceptor Processing ---
  if (waitingForBill && !billProcessed && millis() - lastPulseTime > timeout) {
    int pesoValue = mapPulsesToPesos(pulseCount);
    if (pesoValue > 0) {
      Serial.print("Bill inserted: ₱");
      Serial.println(pesoValue);
      pulseCount = 0;
      waitingForBill = false;
      billProcessed = true;
    } else {
      // Don't reset yet — wait for more pulses
      Serial.print("Unknown pulse count: ");
      Serial.println(pulseCount);
      // Optional: add a longer timeout before resetting unknowns
      if (millis() - lastPulseTime > timeout + 5000) {
        pulseCount = 0;
        waitingForBill = false;
        billProcessed = true;
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

  // Read commands from Serial2 (hardware RX/TX connection to Raspberry Pi)
  #ifdef HAVE_HWSERIAL2
  while (Serial2.available()){
    char c = (char) Serial2.read();
    if (c == '\n'){
      if (inputBuffer2.length() > 0){ Serial.print("CMD(Serial2): "); Serial.println(inputBuffer2); processLine(inputBuffer2, Serial2); inputBuffer2 = ""; }
    } else if (c != '\r'){
      inputBuffer2 += c;
      if (inputBuffer2.length() > 256) inputBuffer2 = inputBuffer2.substring(inputBuffer2.length()-256);
    }
  }
  #endif

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
