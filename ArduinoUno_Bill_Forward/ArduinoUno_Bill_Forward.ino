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
    IR CALIBRATION:
    - IR_READ
    - IR_STATUS
    - IR_SET <sensor> <blocked_enter> <clear_exit>
    - IR_POLARITY <sensor> HIGHER|LOWER
    - IR_CAL_EMPTY [seconds]
    - IR_CAL_ITEM [seconds]
    - IR_SUGGEST
    - IR_APPLY
    - IR_RESET_CAL

  Adjust `ONE_MOTOR_PIN`, `FIVE_MOTOR_PIN`, `ONE_SENSOR_PIN`, `FIVE_SENSOR_PIN`,
  and `pulsePin` to match wiring. This build uses USB Serial only (no RX/TX Serial2).

  Added shared Arduino Uno sensor bridge:
  - Coin acceptor on D3
  - DHT22 on D4/D5
  - IR sensors (Sharp GP2Y0A21YK0F analog) on A0/A1
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
const unsigned long coinDebounceMs = 180;      // debounce between recognized coin events
const unsigned long coinPulseDebounceUs = 12000; // debounce per pulse edge (12ms) for noise rejection
const unsigned long coinGroupGapMs = 220;     // gap that ends a pulse train for one coin
float coin_total = 0.0;

// --- Shared Sensor Bridge Pins ---
const int DHT1_PIN = 4; // D4
const int DHT2_PIN = 5; // D5
const int IR1_PIN = A0;  // Analog input
const int IR2_PIN = A1;  // Analog input
// Sharp GP2Y0A21YK0F outputs higher voltage when an object is closer.
// Calibrate thresholds for your chute geometry (max distance ~26cm).
// Use a little hysteresis to avoid flicker.
const int IR_DEFAULT_BLOCKED_THRESHOLD = 350; // 0-1023 (5V ADC), enter BLOCKED
const int IR_DEFAULT_CLEAR_THRESHOLD   = 300; // 0-1023 (5V ADC), return to CLEAR
const int IR_SAMPLE_COUNT = 5;
const int IR_SAMPLE_DELAY_MS = 2;
const int TEC_RELAY_PIN = 8; // D8

#define DHTTYPE DHT22
DHT dht1(DHT1_PIN, DHTTYPE);
DHT dht2(DHT2_PIN, DHTTYPE);
unsigned long lastDhtMs = 0;
const unsigned long DHT_INTERVAL_MS = 2000;
int last_ir1_state = -1; // 1 = BLOCKED, 0 = CLEAR
int last_ir2_state = -1; // 1 = BLOCKED, 0 = CLEAR
unsigned long last_motor_active_ms = 0;
const unsigned long IR_ARM_DELAY_MS = 800; // wait after motors stop before reporting IR
int ir_blocked_threshold[2] = {IR_DEFAULT_BLOCKED_THRESHOLD, IR_DEFAULT_BLOCKED_THRESHOLD};
int ir_clear_threshold[2] = {IR_DEFAULT_CLEAR_THRESHOLD, IR_DEFAULT_CLEAR_THRESHOLD};
bool ir_blocked_is_higher[2] = {true, true};

struct IrCaptureStats {
  long sum[2];
  int count[2];
  int min_v[2];
  int max_v[2];
};

IrCaptureStats ir_empty_stats;
IrCaptureStats ir_item_stats;
bool ir_has_empty_stats = false;
bool ir_has_item_stats = false;

// --- Coin Hopper Pin Configuration ---
// The dispenser wiring uses digital pins 9/10 for the 1p/5p motors and 11/12 for
// the corresponding sensors, so we hardcode those lines for consistency.
const int ONE_MOTOR_PIN = 9;   // 1-peso motor control
const int FIVE_MOTOR_PIN = 10; // 5-peso motor control

const int ONE_SENSOR_PIN = 11;  // 1-peso sensor input
const int FIVE_SENSOR_PIN = 12; // 5-peso sensor input
const unsigned long HOPPER_SENSOR_DEBOUNCE_MS = 25;

const unsigned long BAUD_RATE = 115200;

// --- Coin Hopper State Variables ---
unsigned int one_count = 0;
unsigned int five_count = 0;
int last_one_state = HIGH;  // Track previous state for edge detection
int last_five_state = HIGH;
int one_sensor_active_level = LOW;
int five_sensor_active_level = LOW;
unsigned long last_one_edge_ms = 0;
unsigned long last_five_edge_ms = 0;

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
const int RELAY_ACTIVE_LEVEL = LOW;
const int RELAY_INACTIVE_LEVEL = (RELAY_ACTIVE_LEVEL == HIGH) ? LOW : HIGH;

void start_motor(int pin) { digitalWrite(pin, RELAY_ACTIVE_LEVEL); }
void stop_motor(int pin) { digitalWrite(pin, RELAY_INACTIVE_LEVEL); }

void enforce_hopper_output_safety() {
  // Hard failsafe: hopper outputs are only energized while a dispense job is active.
  // This prevents latched HIGH outputs from manual/stray commands.
  digitalWrite(ONE_MOTOR_PIN, job_one.active ? RELAY_ACTIVE_LEVEL : RELAY_INACTIVE_LEVEL);
  digitalWrite(FIVE_MOTOR_PIN, job_five.active ? RELAY_ACTIVE_LEVEL : RELAY_INACTIVE_LEVEL);
}

// Configure TEC relay active level:
// - Active-low relay modules (common): set to LOW
// - Active-high relay modules: set to HIGH
const int TEC_RELAY_ACTIVE_LEVEL = HIGH;
const int TEC_RELAY_INACTIVE_LEVEL = (TEC_RELAY_ACTIVE_LEVEL == HIGH) ? LOW : HIGH;

void tec_on() { digitalWrite(TEC_RELAY_PIN, TEC_RELAY_ACTIVE_LEVEL); }
void tec_off() { digitalWrite(TEC_RELAY_PIN, TEC_RELAY_INACTIVE_LEVEL); }

void report_tec_state(Stream &out) {
  out.print("TEC: ");
  out.println(digitalRead(TEC_RELAY_PIN) == TEC_RELAY_ACTIVE_LEVEL ? "ON" : "OFF");
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

int read_ir_avg(int pin) {
  long sum = 0;
  for (int i = 0; i < IR_SAMPLE_COUNT; i++) {
    sum += analogRead(pin);
    delay(IR_SAMPLE_DELAY_MS);
  }
  return (int)(sum / IR_SAMPLE_COUNT);
}

int clamp_adc(int value) {
  if (value < 0) return 0;
  if (value > 1023) return 1023;
  return value;
}

void reset_ir_capture_stats(IrCaptureStats &stats) {
  for (int i = 0; i < 2; i++) {
    stats.sum[i] = 0;
    stats.count[i] = 0;
    stats.min_v[i] = 1023;
    stats.max_v[i] = 0;
  }
}

void add_ir_capture_sample(IrCaptureStats &stats, int idx, int value) {
  int v = clamp_adc(value);
  stats.sum[idx] += v;
  stats.count[idx]++;
  if (v < stats.min_v[idx]) stats.min_v[idx] = v;
  if (v > stats.max_v[idx]) stats.max_v[idx] = v;
}

int ir_capture_mean(const IrCaptureStats &stats, int idx) {
  if (stats.count[idx] <= 0) return 0;
  return (int)(stats.sum[idx] / stats.count[idx]);
}

void print_ir_capture_stats(Stream &out, const char *label, const IrCaptureStats &stats) {
  out.print(label);
  out.println(":");
  for (int i = 0; i < 2; i++) {
    out.print("IR");
    out.print(i + 1);
    out.print(" mean=");
    out.print(ir_capture_mean(stats, i));
    out.print(" min=");
    out.print(stats.min_v[i]);
    out.print(" max=");
    out.print(stats.max_v[i]);
    out.print(" samples=");
    out.println(stats.count[i]);
  }
}

void print_ir_config(Stream &out) {
  for (int i = 0; i < 2; i++) {
    out.print("IR");
    out.print(i + 1);
    out.print(" cfg blocked_enter=");
    out.print(ir_blocked_threshold[i]);
    out.print(" clear_exit=");
    out.print(ir_clear_threshold[i]);
    out.print(" polarity=");
    out.println(ir_blocked_is_higher[i] ? "HIGHER" : "LOWER");
  }
}

int read_ir_sensor_by_index(int sensor_idx) {
  int pin = (sensor_idx == 0) ? IR1_PIN : IR2_PIN;
  return read_ir_avg(pin);
}

bool ir_blocked_from_adc(int sensor_idx, int last_state, int *reading_out) {
  int reading = read_ir_sensor_by_index(sensor_idx);
  if (reading_out != nullptr) {
    *reading_out = reading;
  }

  if (ir_blocked_is_higher[sensor_idx]) {
    if (last_state == 1) {
      return reading >= ir_clear_threshold[sensor_idx];
    }
    return reading >= ir_blocked_threshold[sensor_idx];
  }

  if (last_state == 1) {
    return reading <= ir_clear_threshold[sensor_idx];
  }
  return reading <= ir_blocked_threshold[sensor_idx];
}

bool ir_blocked_from_adc(int sensor_idx, int last_state) {
  return ir_blocked_from_adc(sensor_idx, last_state, nullptr);
}

bool can_run_ir_calibration() {
  return !job_one.active && !job_five.active && !sequence_active;
}

void capture_ir_window(const char *label, int seconds, IrCaptureStats &stats, Stream &out) {
  if (seconds < 1) seconds = 1;
  if (seconds > 60) seconds = 60;

  reset_ir_capture_stats(stats);

  out.print("IR capture start: ");
  out.print(label);
  out.print(" for ");
  out.print(seconds);
  out.println("s");
  out.println("Keep the scene stable during capture.");

  unsigned long start_ms = millis();
  unsigned long last_progress_ms = 0;
  unsigned long duration_ms = (unsigned long)seconds * 1000UL;

  while (millis() - start_ms < duration_ms) {
    int ir1 = read_ir_sensor_by_index(0);
    int ir2 = read_ir_sensor_by_index(1);
    add_ir_capture_sample(stats, 0, ir1);
    add_ir_capture_sample(stats, 1, ir2);

    unsigned long now = millis();
    if (now - last_progress_ms >= 500) {
      last_progress_ms = now;
      out.print("t=");
      out.print((now - start_ms) / 1000.0, 1);
      out.print("s IR1=");
      out.print(ir1);
      out.print(" IR2=");
      out.println(ir2);
    }
    delay(40);
  }

  out.print("IR capture done: ");
  out.println(label);
  print_ir_capture_stats(out, label, stats);
}

void compute_ir_suggestion(int sensor_idx, int &blocked_enter, int &clear_exit, bool &blocked_is_higher) {
  int empty_mean = ir_capture_mean(ir_empty_stats, sensor_idx);
  int item_mean = ir_capture_mean(ir_item_stats, sensor_idx);
  long delta = (long)item_mean - (long)empty_mean;

  blocked_is_higher = (delta >= 0);
  blocked_enter = clamp_adc((int)(empty_mean + ((delta * 65L) / 100L)));
  clear_exit = clamp_adc((int)(empty_mean + ((delta * 45L) / 100L)));
}

void report_ir_suggestion(Stream &out, bool apply_now) {
  if (!ir_has_empty_stats || !ir_has_item_stats) {
    out.println("ERR run IR_CAL_EMPTY and IR_CAL_ITEM first");
    return;
  }

  out.println("IR threshold suggestion:");
  for (int i = 0; i < 2; i++) {
    int empty_mean = ir_capture_mean(ir_empty_stats, i);
    int item_mean = ir_capture_mean(ir_item_stats, i);
    long delta = (long)item_mean - (long)empty_mean;
    long sep = (delta >= 0) ? delta : -delta;

    int blocked_enter = 0;
    int clear_exit = 0;
    bool blocked_is_higher = true;
    compute_ir_suggestion(i, blocked_enter, clear_exit, blocked_is_higher);

    out.print("IR");
    out.print(i + 1);
    out.print(": empty_mean=");
    out.print(empty_mean);
    out.print(" item_mean=");
    out.print(item_mean);
    out.print(" delta=");
    out.println(delta);
    out.print("  blocked_enter=");
    out.print(blocked_enter);
    out.print(" clear_exit=");
    out.print(clear_exit);
    out.print(" polarity=");
    out.println(blocked_is_higher ? "HIGHER" : "LOWER");

    if (sep < 40) {
      out.println("  warning: low separation (<40 ADC), adjust sensor position.");
    }

    if (apply_now) {
      ir_blocked_threshold[i] = blocked_enter;
      ir_clear_threshold[i] = clear_exit;
      ir_blocked_is_higher[i] = blocked_is_higher;
    }
  }

  if (apply_now) {
    out.println("OK IR thresholds updated");
    last_ir1_state = -1;
    last_ir2_state = -1;
  }
}

void report_ir_live(Stream &out) {
  int ir1_reading = 0;
  int ir2_reading = 0;
  bool ir1_blocked = ir_blocked_from_adc(0, last_ir1_state, &ir1_reading);
  bool ir2_blocked = ir_blocked_from_adc(1, last_ir2_state, &ir2_reading);
  out.print("IR1: ");
  out.print(ir1_blocked ? "BLOCKED" : "CLEAR");
  out.print(" ADC=");
  out.print(ir1_reading);
  out.print(" | IR2: ");
  out.print(ir2_blocked ? "BLOCKED" : "CLEAR");
  out.print(" ADC=");
  out.println(ir2_reading);
}

void report_ir_state(Stream &out) {
  bool ir1_blocked = ir_blocked_from_adc(0, last_ir1_state);
  bool ir2_blocked = ir_blocked_from_adc(1, last_ir2_state);
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
      // Reset sequence/job state before starting a new amount request.
      sequence_active = (one_needed > 0);
      sequence_timeout_ms = tmo;
      five_count = 0; one_count = 0;
      job_five.target = 0;
      job_one.target = 0;
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
      // Exact denomination dispense should never chain into sequence logic.
      sequence_active = false;
      job_one.target = 0;
      job_five.target = 0;
      one_count = 0;
      five_count = 0;
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
  } else if (cmd == "IR_READ") {
    report_ir_live(out);
  } else if (cmd == "IR_STATUS") {
    print_ir_config(out);
    if (ir_has_empty_stats) {
      print_ir_capture_stats(out, "empty", ir_empty_stats);
    }
    if (ir_has_item_stats) {
      print_ir_capture_stats(out, "item", ir_item_stats);
    }
  } else if (cmd == "IR_SET") {
    if (partCount >= 4) {
      int sensor = parts[1].toInt();
      int blocked_enter = parts[2].toInt();
      int clear_exit = parts[3].toInt();
      if (sensor < 1 || sensor > 2) {
        out.println("ERR sensor must be 1 or 2");
        return;
      }
      if (blocked_enter < 0 || blocked_enter > 1023 || clear_exit < 0 || clear_exit > 1023) {
        out.println("ERR thresholds must be 0..1023");
        return;
      }
      int idx = sensor - 1;
      ir_blocked_threshold[idx] = blocked_enter;
      ir_clear_threshold[idx] = clear_exit;
      last_ir1_state = -1;
      last_ir2_state = -1;
      out.println("OK IR_SET");
      print_ir_config(out);
    } else {
      out.println("ERR usage: IR_SET <sensor> <blocked_enter> <clear_exit>");
    }
  } else if (cmd == "IR_POLARITY") {
    if (partCount >= 3) {
      int sensor = parts[1].toInt();
      String mode = parts[2];
      mode.toUpperCase();
      if (sensor < 1 || sensor > 2) {
        out.println("ERR sensor must be 1 or 2");
        return;
      }
      int idx = sensor - 1;
      if (mode == "HIGHER") {
        ir_blocked_is_higher[idx] = true;
      } else if (mode == "LOWER") {
        ir_blocked_is_higher[idx] = false;
      } else {
        out.println("ERR mode must be HIGHER or LOWER");
        return;
      }
      last_ir1_state = -1;
      last_ir2_state = -1;
      out.println("OK IR_POLARITY");
      print_ir_config(out);
    } else {
      out.println("ERR usage: IR_POLARITY <sensor> HIGHER|LOWER");
    }
  } else if (cmd == "IR_CAL_EMPTY") {
    if (!can_run_ir_calibration()) {
      out.println("ERR machine busy, stop dispensing before IR calibration");
      return;
    }
    int seconds = 8;
    if (partCount >= 2) {
      int parsed = parts[1].toInt();
      if (parsed > 0) seconds = parsed;
    }
    capture_ir_window("empty", seconds, ir_empty_stats, out);
    ir_has_empty_stats = true;
  } else if (cmd == "IR_CAL_ITEM") {
    if (!can_run_ir_calibration()) {
      out.println("ERR machine busy, stop dispensing before IR calibration");
      return;
    }
    int seconds = 8;
    if (partCount >= 2) {
      int parsed = parts[1].toInt();
      if (parsed > 0) seconds = parsed;
    }
    capture_ir_window("item", seconds, ir_item_stats, out);
    ir_has_item_stats = true;
  } else if (cmd == "IR_SUGGEST") {
    report_ir_suggestion(out, false);
  } else if (cmd == "IR_APPLY") {
    report_ir_suggestion(out, true);
  } else if (cmd == "IR_RESET_CAL") {
    reset_ir_capture_stats(ir_empty_stats);
    reset_ir_capture_stats(ir_item_stats);
    ir_has_empty_stats = false;
    ir_has_item_stats = false;
    out.println("OK IR calibration capture reset");
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

  bool temp_in_off_band = (avg_temp >= TARGET_TEMP_MIN && avg_temp <= TARGET_TEMP_MAX);
  bool humidity_below_threshold = (!isnan(avg_humid) && avg_humid < HUMIDITY_THRESHOLD);

  // Priority OFF rule:
  // - Turn OFF when temp is in 20-25C band, OR humidity is below 60%.
  if (temp_in_off_band || humidity_below_threshold) {
    tec_off();
    return;
  }

  // Otherwise turn ON only when above thresholds.
  if (avg_temp > TARGET_TEMP_MAX || (!isnan(avg_humid) && avg_humid > HUMIDITY_THRESHOLD)) {
    tec_on();
  }
}

void setup(){
  // Initialize coin hopper pins
  pinMode(ONE_MOTOR_PIN, OUTPUT);
  pinMode(FIVE_MOTOR_PIN, OUTPUT);
  digitalWrite(ONE_MOTOR_PIN, RELAY_INACTIVE_LEVEL);
  digitalWrite(FIVE_MOTOR_PIN, RELAY_INACTIVE_LEVEL);
  pinMode(ONE_SENSOR_PIN, INPUT_PULLUP);
  pinMode(FIVE_SENSOR_PIN, INPUT_PULLUP);
  last_one_state = digitalRead(ONE_SENSOR_PIN);
  last_five_state = digitalRead(FIVE_SENSOR_PIN);
  // Auto-polarity: count coins on transition to opposite of idle level.
  one_sensor_active_level = (last_one_state == HIGH) ? LOW : HIGH;
  five_sensor_active_level = (last_five_state == HIGH) ? LOW : HIGH;
  
  // Initialize bill acceptor pins
  pinMode(pulsePin, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(pulsePin), countPulse, FALLING);

  // Initialize coin acceptor
  pinMode(COIN_ACCEPTOR_PIN, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(COIN_ACCEPTOR_PIN), countCoinPulse, FALLING);

  // Initialize shared sensor pins
  pinMode(IR1_PIN, INPUT);
  pinMode(IR2_PIN, INPUT);
  reset_ir_capture_stats(ir_empty_stats);
  reset_ir_capture_stats(ir_item_stats);
  pinMode(TEC_RELAY_PIN, OUTPUT);
  digitalWrite(TEC_RELAY_PIN, TEC_RELAY_INACTIVE_LEVEL);
  dht1.begin();
  dht2.begin();
  
  Serial.begin(BAUD_RATE);
  
  // This build uses USB Serial only; Serial2 (RX/TX) disabled
  Serial.println("Using USB Serial only; RX/TX Serial2 disabled");
  
  delay(50);
  Serial.println("Arduino Bill Acceptor & Coin Hopper ready");
  Serial.println("IR calibration cmds: IR_STATUS, IR_READ, IR_CAL_EMPTY, IR_CAL_ITEM, IR_SUGGEST, IR_APPLY");
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
  
  unsigned long sensor_now_ms = millis();
  if (one_state != last_one_state && one_state == one_sensor_active_level) {
    if (sensor_now_ms - last_one_edge_ms >= HOPPER_SENSOR_DEBOUNCE_MS) {
      one_count++;
      job_one.last_coin_ms = sensor_now_ms;
      last_one_edge_ms = sensor_now_ms;
      Serial.print("PULSE ONE ");
      Serial.println(one_count);
    }
  }
  
  if (five_state != last_five_state && five_state == five_sensor_active_level) {
    if (sensor_now_ms - last_five_edge_ms >= HOPPER_SENSOR_DEBOUNCE_MS) {
      five_count++;
      job_five.last_coin_ms = sensor_now_ms;
      last_five_edge_ms = sensor_now_ms;
      Serial.print("PULSE FIVE ");
      Serial.println(five_count);
    }
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

  if (sequence_active && !job_five.active && !job_one.active){
    if (job_one.target > 0 && one_count < job_one.target){
      start_dispense_denon(1, job_one.target, sequence_timeout_ms);
    } else {
      sequence_active = false;
    }
  }

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
    int ir1_state = ir_blocked_from_adc(0, last_ir1_state) ? 1 : 0;
    int ir2_state = ir_blocked_from_adc(1, last_ir2_state) ? 1 : 0;
    if (ir1_state != last_ir1_state) {
      Serial.print("IR1: ");
      Serial.println(ir1_state == 1 ? "BLOCKED" : "CLEAR");
      last_ir1_state = ir1_state;
    }
    if (ir2_state != last_ir2_state) {
      Serial.print("IR2: ");
      Serial.println(ir2_state == 1 ? "BLOCKED" : "CLEAR");
      last_ir2_state = ir2_state;
    }
  }

  // Always enforce safe hopper output state each loop.
  enforce_hopper_output_safety();
}
