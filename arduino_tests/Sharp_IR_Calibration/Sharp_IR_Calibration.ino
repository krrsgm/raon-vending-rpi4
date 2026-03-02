/*
  Sharp_IR_Calibration.ino

  Purpose:
  - Test Sharp GP2Y0A21YK0F analog IR sensors on Arduino Uno (A0/A1)
  - Capture "empty bin" and "item detected zone" values
  - Suggest hysteresis thresholds for stable BLOCKED/CLEAR detection

  Serial monitor:
  - Baud: 115200
  - Line ending: Newline
*/

#include <Arduino.h>

const unsigned long BAUD_RATE = 115200;
const int IR_PINS[2] = {A0, A1};

const int IR_SAMPLE_COUNT = 8;
const int IR_SAMPLE_DELAY_MS = 2;
const unsigned long STREAM_INTERVAL_MS = 150;

struct SensorConfig {
  int blocked_enter;
  int clear_exit;
  bool blocked_is_higher;
  bool last_blocked;
  int ema;
  bool ema_initialized;
};

SensorConfig sensor_cfg[2] = {
  {350, 300, true, false, 0, false},
  {350, 300, true, false, 0, false}
};

struct CaptureStats {
  long sum;
  int count;
  int min_v;
  int max_v;
};

CaptureStats empty_stats[2];
CaptureStats item_stats[2];
bool has_empty_stats = false;
bool has_item_stats = false;

bool stream_enabled = true;
unsigned long last_stream_ms = 0;
String input_buffer = "";

int clamp_adc(int value) {
  if (value < 0) return 0;
  if (value > 1023) return 1023;
  return value;
}

void reset_stats(CaptureStats &stats) {
  stats.sum = 0;
  stats.count = 0;
  stats.min_v = 1023;
  stats.max_v = 0;
}

void add_sample(CaptureStats &stats, int value) {
  int v = clamp_adc(value);
  stats.sum += v;
  stats.count++;
  if (v < stats.min_v) stats.min_v = v;
  if (v > stats.max_v) stats.max_v = v;
}

int mean_from_stats(const CaptureStats &stats) {
  if (stats.count <= 0) return 0;
  return (int)(stats.sum / stats.count);
}

int read_ir_avg(int pin) {
  long sum = 0;
  for (int i = 0; i < IR_SAMPLE_COUNT; i++) {
    sum += analogRead(pin);
    delay(IR_SAMPLE_DELAY_MS);
  }
  return (int)(sum / IR_SAMPLE_COUNT);
}

int update_ema(int idx, int sample) {
  if (!sensor_cfg[idx].ema_initialized) {
    sensor_cfg[idx].ema = sample;
    sensor_cfg[idx].ema_initialized = true;
  } else {
    sensor_cfg[idx].ema = ((sensor_cfg[idx].ema * 3) + sample) / 4;
  }
  return sensor_cfg[idx].ema;
}

bool is_blocked(int idx, int reading) {
  SensorConfig &cfg = sensor_cfg[idx];
  bool blocked = false;

  if (cfg.blocked_is_higher) {
    if (cfg.last_blocked) {
      blocked = (reading >= cfg.clear_exit);
    } else {
      blocked = (reading >= cfg.blocked_enter);
    }
  } else {
    if (cfg.last_blocked) {
      blocked = (reading <= cfg.clear_exit);
    } else {
      blocked = (reading <= cfg.blocked_enter);
    }
  }

  return blocked;
}

void print_help() {
  Serial.println();
  Serial.println("Commands:");
  Serial.println("  HELP");
  Serial.println("  STATUS");
  Serial.println("  READ");
  Serial.println("  STREAM ON|OFF");
  Serial.println("  SET <sensor> <blocked_enter> <clear_exit>    (sensor: 1 or 2)");
  Serial.println("  POLARITY <sensor> HIGHER|LOWER               (blocked when value goes higher/lower)");
  Serial.println("  CAL_EMPTY [seconds]                          (default 8)");
  Serial.println("  CAL_ITEM [seconds]                           (default 8)");
  Serial.println("  SUGGEST                                      (print suggested thresholds)");
  Serial.println("  APPLY                                        (apply suggested thresholds)");
  Serial.println("  RESET_CAL");
  Serial.println();
}

void print_sensor_config(int idx) {
  const SensorConfig &cfg = sensor_cfg[idx];
  Serial.print("IR");
  Serial.print(idx + 1);
  Serial.print(" config: blocked_enter=");
  Serial.print(cfg.blocked_enter);
  Serial.print(" clear_exit=");
  Serial.print(cfg.clear_exit);
  Serial.print(" polarity=");
  Serial.println(cfg.blocked_is_higher ? "HIGHER" : "LOWER");
}

void print_capture_stats(const char *label, CaptureStats stats_arr[2]) {
  Serial.print(label);
  Serial.println(":");
  for (int i = 0; i < 2; i++) {
    Serial.print("  IR");
    Serial.print(i + 1);
    Serial.print(" mean=");
    Serial.print(mean_from_stats(stats_arr[i]));
    Serial.print(" min=");
    Serial.print(stats_arr[i].min_v);
    Serial.print(" max=");
    Serial.print(stats_arr[i].max_v);
    Serial.print(" samples=");
    Serial.println(stats_arr[i].count);
  }
}

void print_status() {
  Serial.println();
  print_sensor_config(0);
  print_sensor_config(1);
  Serial.print("stream=");
  Serial.println(stream_enabled ? "ON" : "OFF");
  if (has_empty_stats) {
    print_capture_stats("empty", empty_stats);
  }
  if (has_item_stats) {
    print_capture_stats("item", item_stats);
  }
  Serial.println();
}

void print_live_line() {
  int raw1 = read_ir_avg(IR_PINS[0]);
  int raw2 = read_ir_avg(IR_PINS[1]);
  int ema1 = update_ema(0, raw1);
  int ema2 = update_ema(1, raw2);

  bool blocked1 = is_blocked(0, ema1);
  bool blocked2 = is_blocked(1, ema2);
  sensor_cfg[0].last_blocked = blocked1;
  sensor_cfg[1].last_blocked = blocked2;

  Serial.print("ms=");
  Serial.print(millis());
  Serial.print(" IR1 raw=");
  Serial.print(raw1);
  Serial.print(" ema=");
  Serial.print(ema1);
  Serial.print(" ");
  Serial.print(blocked1 ? "BLOCKED" : "CLEAR");
  Serial.print(" | IR2 raw=");
  Serial.print(raw2);
  Serial.print(" ema=");
  Serial.print(ema2);
  Serial.print(" ");
  Serial.println(blocked2 ? "BLOCKED" : "CLEAR");
}

int parse_seconds_arg(const String &cmd, int default_seconds) {
  int space_pos = cmd.indexOf(' ');
  if (space_pos < 0) return default_seconds;

  String arg = cmd.substring(space_pos + 1);
  arg.trim();
  if (arg.length() == 0) return default_seconds;

  int value = arg.toInt();
  if (value <= 0) return default_seconds;
  if (value > 60) return 60;
  return value;
}

void capture_window(const char *label, int seconds, CaptureStats out_stats[2]) {
  for (int i = 0; i < 2; i++) {
    reset_stats(out_stats[i]);
  }

  Serial.println();
  Serial.print("Capture start: ");
  Serial.print(label);
  Serial.print(" for ");
  Serial.print(seconds);
  Serial.println("s");
  Serial.println("Hold scene stable during capture...");

  unsigned long start_ms = millis();
  unsigned long end_ms = start_ms + (unsigned long)seconds * 1000UL;
  unsigned long last_progress_ms = 0;

  while (millis() < end_ms) {
    int r1 = read_ir_avg(IR_PINS[0]);
    int r2 = read_ir_avg(IR_PINS[1]);
    add_sample(out_stats[0], r1);
    add_sample(out_stats[1], r2);

    unsigned long now = millis();
    if (now - last_progress_ms >= 500) {
      last_progress_ms = now;
      Serial.print("  t=");
      Serial.print((now - start_ms) / 1000.0, 1);
      Serial.print("s IR1=");
      Serial.print(r1);
      Serial.print(" IR2=");
      Serial.println(r2);
    }
    delay(40);
  }

  Serial.print("Capture done: ");
  Serial.println(label);
  print_capture_stats(label, out_stats);
  Serial.println();
}

void compute_suggestion_for_sensor(int idx, int &blocked_enter, int &clear_exit, bool &blocked_is_higher) {
  int e_mean = mean_from_stats(empty_stats[idx]);
  int i_mean = mean_from_stats(item_stats[idx]);
  long delta = (long)i_mean - (long)e_mean;

  blocked_is_higher = (delta >= 0);
  blocked_enter = clamp_adc((int)(e_mean + ((delta * 65L) / 100L)));
  clear_exit = clamp_adc((int)(e_mean + ((delta * 45L) / 100L)));
}

void suggest_thresholds(bool apply_now) {
  if (!has_empty_stats || !has_item_stats) {
    Serial.println("Need both captures first: run CAL_EMPTY and CAL_ITEM.");
    return;
  }

  Serial.println();
  Serial.println("Suggested thresholds:");

  for (int i = 0; i < 2; i++) {
    int e_mean = mean_from_stats(empty_stats[i]);
    int i_mean = mean_from_stats(item_stats[i]);
    long delta = (long)i_mean - (long)e_mean;
    long separation = (delta >= 0) ? delta : -delta;

    int blocked_enter = 0;
    int clear_exit = 0;
    bool blocked_is_higher = true;
    compute_suggestion_for_sensor(i, blocked_enter, clear_exit, blocked_is_higher);

    Serial.print("IR");
    Serial.print(i + 1);
    Serial.print(": empty_mean=");
    Serial.print(e_mean);
    Serial.print(" item_mean=");
    Serial.print(i_mean);
    Serial.print(" delta=");
    Serial.println(delta);
    Serial.print("  blocked condition: reading goes ");
    Serial.println(blocked_is_higher ? "HIGHER" : "LOWER");
    Serial.print("  blocked_enter=");
    Serial.print(blocked_enter);
    Serial.print(" clear_exit=");
    Serial.println(clear_exit);

    if (separation < 40) {
      Serial.println("  warning: low separation (<40 ADC). Adjust sensor angle/distance.");
    }

    if (apply_now) {
      sensor_cfg[i].blocked_enter = blocked_enter;
      sensor_cfg[i].clear_exit = clear_exit;
      sensor_cfg[i].blocked_is_higher = blocked_is_higher;
      sensor_cfg[i].last_blocked = false;
      sensor_cfg[i].ema_initialized = false;
    }
  }

  if (apply_now) {
    Serial.println("Applied suggested thresholds.");
  } else {
    Serial.println("Use APPLY to set these thresholds in this test sketch.");
  }
  Serial.println();
}

void process_command(String cmd) {
  cmd.trim();
  if (cmd.length() == 0) return;

  String upper = cmd;
  upper.toUpperCase();

  if (upper == "HELP") {
    print_help();
    return;
  }

  if (upper == "STATUS") {
    print_status();
    return;
  }

  if (upper == "READ") {
    print_live_line();
    return;
  }

  if (upper == "STREAM ON") {
    stream_enabled = true;
    Serial.println("stream=ON");
    return;
  }

  if (upper == "STREAM OFF") {
    stream_enabled = false;
    Serial.println("stream=OFF");
    return;
  }

  if (upper.startsWith("SET ")) {
    int sensor = 0;
    int blocked_enter = 0;
    int clear_exit = 0;
    if (sscanf(upper.c_str(), "SET %d %d %d", &sensor, &blocked_enter, &clear_exit) == 3) {
      if (sensor < 1 || sensor > 2) {
        Serial.println("ERR sensor must be 1 or 2");
        return;
      }
      if (blocked_enter < 0 || blocked_enter > 1023 || clear_exit < 0 || clear_exit > 1023) {
        Serial.println("ERR thresholds must be 0..1023");
        return;
      }
      int idx = sensor - 1;
      sensor_cfg[idx].blocked_enter = blocked_enter;
      sensor_cfg[idx].clear_exit = clear_exit;
      sensor_cfg[idx].last_blocked = false;
      sensor_cfg[idx].ema_initialized = false;
      print_sensor_config(idx);
      return;
    }
    Serial.println("ERR usage: SET <sensor> <blocked_enter> <clear_exit>");
    return;
  }

  if (upper.startsWith("POLARITY ")) {
    int sensor = 0;
    char mode[12];
    if (sscanf(upper.c_str(), "POLARITY %d %11s", &sensor, mode) == 2) {
      if (sensor < 1 || sensor > 2) {
        Serial.println("ERR sensor must be 1 or 2");
        return;
      }
      int idx = sensor - 1;
      if (strcmp(mode, "HIGHER") == 0) {
        sensor_cfg[idx].blocked_is_higher = true;
      } else if (strcmp(mode, "LOWER") == 0) {
        sensor_cfg[idx].blocked_is_higher = false;
      } else {
        Serial.println("ERR mode must be HIGHER or LOWER");
        return;
      }
      sensor_cfg[idx].last_blocked = false;
      print_sensor_config(idx);
      return;
    }
    Serial.println("ERR usage: POLARITY <sensor> HIGHER|LOWER");
    return;
  }

  if (upper.startsWith("CAL_EMPTY")) {
    int seconds = parse_seconds_arg(upper, 8);
    capture_window("empty", seconds, empty_stats);
    has_empty_stats = true;
    return;
  }

  if (upper.startsWith("CAL_ITEM")) {
    int seconds = parse_seconds_arg(upper, 8);
    capture_window("item", seconds, item_stats);
    has_item_stats = true;
    return;
  }

  if (upper == "SUGGEST") {
    suggest_thresholds(false);
    return;
  }

  if (upper == "APPLY") {
    suggest_thresholds(true);
    return;
  }

  if (upper == "RESET_CAL") {
    for (int i = 0; i < 2; i++) {
      reset_stats(empty_stats[i]);
      reset_stats(item_stats[i]);
    }
    has_empty_stats = false;
    has_item_stats = false;
    Serial.println("Calibration captures reset.");
    return;
  }

  Serial.println("ERR unknown command. Type HELP.");
}

void setup() {
  for (int i = 0; i < 2; i++) {
    pinMode(IR_PINS[i], INPUT);
    reset_stats(empty_stats[i]);
    reset_stats(item_stats[i]);
  }

  Serial.begin(BAUD_RATE);
  delay(100);

  Serial.println("Sharp IR calibration test ready.");
  Serial.println("Pins: IR1=A0, IR2=A1");
  Serial.println("Type HELP for commands.");
  Serial.println();
}

void loop() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n') {
      process_command(input_buffer);
      input_buffer = "";
    } else if (c != '\r') {
      input_buffer += c;
      if (input_buffer.length() > 96) {
        input_buffer = input_buffer.substring(input_buffer.length() - 96);
      }
    }
  }

  unsigned long now = millis();
  if (stream_enabled && (now - last_stream_ms >= STREAM_INTERVAL_MS)) {
    last_stream_ms = now;
    print_live_line();
  }
}

