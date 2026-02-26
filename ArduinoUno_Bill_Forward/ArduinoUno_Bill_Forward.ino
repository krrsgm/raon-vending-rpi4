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

  Added shared Arduino Uno sensor bridge:
  - Coin acceptor on D3
  - DHT22 on D4/D5
  - IR sensors on D6/D7
  - TEC relay on D8
*/

// Include Arduino and C++ helpers
#include <Arduino.h>
#include <DHT.h>

// --- Bill Acceptor Pin Configuration ---
volatile int pulseCount = 0;
volatile unsigned long lastPulseTime = 0;
volatile bool pulseEvent = false; // flag for main loop printing/processing
const int pulsePin = 2; // use pin 2 (commonly supports external interrupt)
const unsigned long timeout = 2000; // 2 seconds (increased to allow complete bill insertion)

volatile bool waitingForBill = false;
volatile bool billProcessed = false;
const unsigned long pulseDebounceMs = 60; // debounce interval in ms (INCREASED from 20ms to filter noise)

// --- Coin Acceptor (Allan 123A-Pro) ---
const int COIN_ACCEPTOR_PIN = 3; // D3 (external interrupt)
volatile unsigned int coinPulseCount = 0;
volatile unsigned long coinLastPulseMs = 0;
volatile unsigned long coinLastEdgeUs = 0;
volatile bool coinCountActive = false;
unsigned long lastCoinValidMs = 0;
const unsigned long coinDebounceMs = 80;      // debounce between recognized coin events
const unsigned long coinPulseDebounceUs = 5000; // debounce per pulse edge (5ms)
const unsigned long coinGroupGapMs = 180;     // gap that ends a pulse train for one coin
float coin_total = 0.0;

// --- Shared Sensor Bridge Pins ---
const int DHT1_PIN = 4; // D4
const int DHT2_PIN = 5; // D5
const int IR1_PIN = 6;  // D6
const int IR2_PIN = 7;  // D7
const int TEC_RELAY_PIN = 8; // D8

#define DHTTYPE DHT22
DHT dht1(DHT1_PIN, DHTTYPE);
DHT dht2(DHT2_PIN, DHTTYPE);
unsigned long lastDhtMs = 0;
const unsigned long DHT_INTERVAL_MS = 2000;
int last_ir1_state = HIGH;
int last_ir2_state = HIGH;
unsigned long last_motor_active_ms = 0;
const unsigned long IR_ARM_DELAY_MS = 800; // wait after motors stop before reporting IR

// --- Coin Hopper Pin Configuration ---
// The dispenser wiring uses digital pins 9/10 for the 1p/5p motors and 11/12 for
// the corresponding sensors, so we hardcode those lines for consistency.
const int ONE_MOTOR_PIN = 9;   // 1-peso motor control
const int FIVE_MOTOR_PIN = 10; // 5-peso motor control

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
  unsigned long last_coin_ms;
};

DispenseJob job_one = {false, 0, 0, 30000, 0};
DispenseJob job_five = {false, 0, 0, 30000, 0};

bool sequence_active = false;
unsigned long sequence_timeout_ms = 30000;

String inputBuffer = "";

// --- Motor Control Functions ---
// Configure the relay/motor active level:
// - If your relay driver is active-high (energized when pin is HIGH),
//   set RELAY_ACTIVE_LEVEL to HIGH.
// - If your relay driver is active-low (energized when pin is LOW),
//   set RELAY_ACTIVE_LEVEL to LOW.
const int RELAY_ACTIVE_LEVEL = HIGH;
const int RELAY_INACTIVE_LEVEL = (RELAY_ACTIVE_LEVEL == HIGH) ? LOW : HIGH;

void start_motor(int pin) { digitalWrite(pin, RELAY_ACTIVE_LEVEL); }
void stop_motor(int pin) { digitalWrite(pin, RELAY_INACTIVE_LEVEL); }

void tec_on() { digitalWrite(TEC_RELAY_PIN, HIGH); }
void tec_off() { digitalWrite(TEC_RELAY_PIN, LOW); }

void report_tec_state(Stream &out) {
  out.print("TEC: ");
  out.println(digitalRead(TEC_RELAY_PIN) == HIGH ? "ON" : "OFF");
}

// --- Coin Hopper Functions ---
void start_dispense_denon(int denom, unsigned int count, unsigned long timeout_ms);

void start_dispense_denon(int denom, unsigned int count, unsigned long timeout_ms, Stream &out) {
  if (denom == 5) {
    five_count = 0;
    job_five.active = true;
    job_five.target = count;
    job_five.start_ms = millis();
    job_five.timeout_ms = timeout_ms;
    job_five.last_coin_ms = millis();
    start_motor(FIVE_MOTOR_PIN);
    out.println("OK START FIVE");
  } else {
    one_count = 0;
    job_one.active = true;
    job_one.target = count;
    job_one.start_ms = millis();
    job_one.timeout_ms = timeout_ms;
    job_one.last_coin_ms = millis();
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

void report_balance(Stream &out) {
  out.print("BALANCE: ");
  out.println(coin_total, 2);
}

void report_balance() {
  report_balance(Serial);
}

void report_ir_state(Stream &out) {
  bool ir1_blocked = (digitalRead(IR1_PIN) == LOW);
  bool ir2_blocked = (digitalRead(IR2_PIN) == LOW);
  out.print("IR1: ");
  out.println(ir1_blocked ? "BLOCKED" : "CLEAR");
  out.print("IR2: ");
  out.println(ir2_blocked ? "BLOCKED" : "CLEAR");
}

void report_dht_readings(Stream &out, float t1, float h1, float t2, float h2) {
  if (!isnan(t1) && !isnan(h1)) {
    out.print("DHT1: ");
    out.print(t1, 1);
    out.print("C ");
    out.print(h1, 1);
    out.println("%");
  }
  if (!isnan(t2) && !isnan(h2)) {
    out.print("DHT2: ");
    out.print(t2, 1);
    out.print("C ");
    out.print(h2, 1);
    out.println("%");
  }
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
    report_balance(out);
    report_tec_state(out);
    report_ir_state(out);
  } else if (cmd == "STOP"){
    stop_all_jobs("user", out);
  } else if (cmd == "TEC"){
    if (partCount >= 2) {
      String state = parts[1];
      state.toUpperCase();
      if (state == "ON") {
        tec_on();
        out.println("OK TEC ON");
      } else if (state == "OFF") {
        tec_off();
        out.println("OK TEC OFF");
      } else {
        out.println("ERR bad TEC state");
      }
    } else {
      out.println("ERR missing TEC state");
    }
  } else if (cmd == "GET_BALANCE"){
    report_balance(out);
  } else if (cmd == "RESET_BALANCE"){
    coin_total = 0.0;
    out.println("OK RESET_BALANCE");
  } else {
    out.println("ERR unknown command");
  }
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

int mapCoinPulseCountToValue(int pulses) {
  // Pulse-count mode mapping:
  // 1 pulse = 1 peso, 5 pulses = 5 peso, 10 pulses = 10 peso.
  if (pulses == 1) return 1;
  if (pulses == 5) return 5;
  if (pulses == 10) return 10;
  return 0;
}

void countCoinPulse() {
  // Count pulses on falling edges.
  unsigned long nowUs = micros();
  if ((nowUs - coinLastEdgeUs) < coinPulseDebounceUs) return;
  coinLastEdgeUs = nowUs;
  coinPulseCount++;
  coinLastPulseMs = millis();
  coinCountActive = true;
}

// --- TEC Control (simple range + humidity trigger) ---
const float TARGET_TEMP_MIN = 20.0;
const float TARGET_TEMP_MAX = 25.0;
const float HUMIDITY_THRESHOLD = 60.0;

void update_tec_control(float t1, float h1, float t2, float h2) {
  float temp_sum = 0.0;
  float humid_sum = 0.0;
  int temp_count = 0;
  int humid_count = 0;

  if (!isnan(t1)) { temp_sum += t1; temp_count++; }
  if (!isnan(t2)) { temp_sum += t2; temp_count++; }
  if (!isnan(h1)) { humid_sum += h1; humid_count++; }
  if (!isnan(h2)) { humid_sum += h2; humid_count++; }

  if (temp_count == 0) return;
  float avg_temp = temp_sum / temp_count;
  float avg_humid = (humid_count > 0) ? (humid_sum / humid_count) : NAN;

  bool need_on = false;
  if (avg_temp > TARGET_TEMP_MAX) need_on = true;
  if (!isnan(avg_humid) && avg_humid > HUMIDITY_THRESHOLD) need_on = true;

  if (need_on) {
    tec_on();
  } else if (avg_temp < TARGET_TEMP_MIN && (isnan(avg_humid) || avg_humid <= HUMIDITY_THRESHOLD)) {
    tec_off();
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

  // Initialize coin acceptor
  pinMode(COIN_ACCEPTOR_PIN, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(COIN_ACCEPTOR_PIN), countCoinPulse, FALLING);

  // Initialize shared sensor pins
  pinMode(IR1_PIN, INPUT_PULLUP);
  pinMode(IR2_PIN, INPUT_PULLUP);
  pinMode(TEC_RELAY_PIN, OUTPUT);
  digitalWrite(TEC_RELAY_PIN, LOW);
  dht1.begin();
  dht2.begin();
  
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
    job_one.last_coin_ms = millis();
  }
  
  if (last_five_state == HIGH && five_state == LOW) {
    five_count++;
    job_five.last_coin_ms = millis();
  }
  
  last_one_state = one_state;
  last_five_state = five_state;

  // --- Coin Acceptor Processing (pulse count mode) ---
  bool finalizeCoin = false;
  unsigned int pulses = 0;
  noInterrupts();
  if (coinCountActive && (millis() - coinLastPulseMs > coinGroupGapMs)) {
    pulses = coinPulseCount;
    coinPulseCount = 0;
    coinCountActive = false;
    finalizeCoin = true;
  }
  interrupts();

  if (finalizeCoin && pulses > 0) {
    unsigned long nowMs = millis();
    if (nowMs - lastCoinValidMs >= coinDebounceMs) {
      int value = mapCoinPulseCountToValue((int)pulses);
      if (value > 0) {
        coin_total += (float)value;
        lastCoinValidMs = nowMs;
        Serial.print("[COIN] Value: ");
        Serial.print(value);
        Serial.print(" Total: ");
        Serial.println(coin_total, 2);
      } else {
        Serial.print("[COIN] Unknown pulse count: ");
        Serial.println(pulses);
      }
    }
  }

  // --- Serial Command Processing ---
  while (Serial.available()){
    char c = (char) Serial.read();
    if (c == '\n'){
    if (inputBuffer.length() > 0){ Serial.print("CMD: "); Serial.println(inputBuffer); processLine(inputBuffer, Serial); inputBuffer = ""; }
    } else if (c != '\r'){
      inputBuffer += c;
      if (inputBuffer.length() > 256) inputBuffer = inputBuffer.substring(inputBuffer.length()-256);
    }
  }

  // Serial2 (RX/TX) disabled — commands are accepted over USB Serial only

  // --- Coin Hopper Job Management ---
  unsigned long now = millis();
  const unsigned long COIN_TIMEOUT_MS = 5000;
  if (job_five.active){
    if (five_count >= job_five.target){ stop_motor(FIVE_MOTOR_PIN); job_five.active = false; Serial.print("DONE FIVE "); Serial.println(five_count); if (sequence_active && job_one.target > 0 && !job_one.active){ if (job_one.target > 0){ start_dispense_denon(1, job_one.target, sequence_timeout_ms); } } }
    else if (now - job_five.start_ms > job_five.timeout_ms){ stop_motor(FIVE_MOTOR_PIN); job_five.active = false; Serial.print("ERR TIMEOUT FIVE dispensed:"); Serial.println(five_count); }
    else if (now - job_five.last_coin_ms > COIN_TIMEOUT_MS){ stop_motor(FIVE_MOTOR_PIN); job_five.active = false; Serial.print("ERR NO COIN FIVE timeout"); Serial.println(five_count); }
  }

  if (job_one.active){
    if (one_count >= job_one.target){ stop_motor(ONE_MOTOR_PIN); job_one.active = false; Serial.print("DONE ONE "); Serial.println(one_count); sequence_active = false; }
    else if (now - job_one.start_ms > job_one.timeout_ms){ stop_motor(ONE_MOTOR_PIN); job_one.active = false; Serial.print("ERR TIMEOUT ONE dispensed:"); Serial.println(one_count); sequence_active = false; }
    else if (now - job_one.last_coin_ms > COIN_TIMEOUT_MS){ stop_motor(ONE_MOTOR_PIN); job_one.active = false; Serial.print("ERR NO COIN ONE timeout"); Serial.println(one_count); sequence_active = false; }
  }

  if (sequence_active && !job_five.active && !job_one.active){ if (job_one.target > 0 && one_count < job_one.target){ start_dispense_denon(1, job_one.target, sequence_timeout_ms); } }

  // Track motor activity for IR suppression
  if (job_one.active || job_five.active) {
    last_motor_active_ms = millis();
  }

  // --- DHT22 / IR Status Reporting ---
  unsigned long now_ms = millis();
  if (now_ms - lastDhtMs >= DHT_INTERVAL_MS) {
    lastDhtMs = now_ms;
    float h1 = dht1.readHumidity();
    float t1 = dht1.readTemperature();
    float h2 = dht2.readHumidity();
    float t2 = dht2.readTemperature();
    report_dht_readings(Serial, t1, h1, t2, h2);
    update_tec_control(t1, h1, t2, h2);
    report_tec_state(Serial);
  }

  // Suppress IR reporting while motors are active and for a short settle period after
  if (now_ms - last_motor_active_ms >= IR_ARM_DELAY_MS) {
    int ir1_state = digitalRead(IR1_PIN);
    int ir2_state = digitalRead(IR2_PIN);
    if (ir1_state != last_ir1_state) {
      Serial.print("IR1: ");
      Serial.println(ir1_state == LOW ? "BLOCKED" : "CLEAR");
      last_ir1_state = ir1_state;
    }
    if (ir2_state != last_ir2_state) {
      Serial.print("IR2: ");
      Serial.println(ir2_state == LOW ? "BLOCKED" : "CLEAR");
      last_ir2_state = ir2_state;
    }
  }
}
