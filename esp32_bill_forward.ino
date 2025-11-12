// Arduino Uno TB74 pulse-forwarder
// Reworked to run on an Arduino Uno (ATmega328P). This sketch listens for
// pulses on a single input (TB74 blue wire via an optocoupler or transistor)
// and forwards bill events to the host Pi over USB Serial in the format:
//   BILL:<amount>
//
// IMPORTANT: do NOT connect the TB74 blue/12V signals directly to the Uno.
// Use an optocoupler or transistor level shifter (see wiring notes below).

#include <Arduino.h>

// --- CONFIG ---
const unsigned long PULSE_GAP_MS = 300; // ms to consider pulse-burst finished

// TB74 blue-wire (after safe level-shifting/opto) should be connected to this pin.
// Use an external optocoupler or transistor; DO NOT connect 12V directly.
const uint8_t TB_SIGNAL_PIN = 2; // INT0 on UNO (digital pin 2)

volatile unsigned int pulse_count = 0;
volatile unsigned long last_pulse_time_ms = 0;

// Interrupt Service Routine: count rising edges
void tb_pulse_isr() {
  pulse_count++;
  last_pulse_time_ms = millis();
}

// Map pulse counts to bill amounts — update to match your TB74 behaviour
struct CountMap { uint8_t pulses; unsigned int amount; };
CountMap count_map[] = {
  { 1, 20 },
  { 2, 50 },
  { 3, 100 },
  { 4, 500 },
  { 5, 1000 },
};

unsigned int map_count_to_amount(unsigned int cnt) {
  for (unsigned i = 0; i < (sizeof(count_map)/sizeof(count_map[0])); ++i) {
    if (count_map[i].pulses == cnt) return count_map[i].amount;
  }
  return 0;
}

void setup() {
  Serial.begin(115200);
  while (!Serial) { ; } // wait for serial on Leonardo/Micro; harmless on UNO
  Serial.println(F("Arduino Uno TB74 pulse forwarder starting"));

  // Configure pulse input pin and attach interrupt on RISING edge
  pinMode(TB_SIGNAL_PIN, INPUT_PULLUP); // use pullup; actual wiring depends on level shifter/opto
  attachInterrupt(digitalPinToInterrupt(TB_SIGNAL_PIN), tb_pulse_isr, RISING);
  Serial.print(F("Listening for pulses on pin "));
  Serial.println(TB_SIGNAL_PIN);
}

void loop() {
  unsigned long now = millis();

  // Read and clear the current counter atomically
  noInterrupts();
  unsigned int cnt = pulse_count;
  unsigned long last_ms = last_pulse_time_ms;
  interrupts();

  if (cnt > 0 && (now - last_ms) > PULSE_GAP_MS) {
    unsigned int amount = map_count_to_amount(cnt);
    if (amount > 0) {
      Serial.print(F("BILL:"));
      Serial.println(amount);
    } else {
      // Unknown mapping — forward raw count for tuning
      Serial.print(F("BILL:PULSE_COUNT:"));
      Serial.println(cnt);
    }

    // reset counter
    noInterrupts();
    pulse_count = 0;
    interrupts();
  }

  delay(10);
}

/*
Wiring notes (summary):

Power:
- TB74 Red: +12V (TB74 power input) — keep separate from Arduino 5V!
- TB74 Orange & Purple: GND
- Use a buck converter to step 12V down to 5V if you want the Arduino
  powered from the same 12V source. Feed the buck output to the UNO VIN or
  5V pin (if you know what you're doing). When feeding VIN, set buck to 7-9V
  or feed barrel jack; if feeding 5V to the 5V pin, set buck to 5.0V.

Signal (blue wire):
- Do NOT connect blue directly to Arduino.
- Recommended: optocoupler circuit (isolated):
    TB74 blue -> series resistor (~5.6k for ~2mA) -> opto LED -> TB74 GND
    opto transistor side: collector -> 5V via 10k pull-up -> collector to Arduino pin
                       emitter -> Arduino GND
- Simpler (no isolation): NPN level-shifter
    TB74 blue -> 10k resistor -> base of NPN (e.g., 2N3904)
    emitter -> TB74 GND (and tie to Arduino GND)
    collector -> Arduino input pin with pull-up to 5V (10k)

Testing:
- Open Serial Monitor at 115200.
- Insert a bill and observe lines like: BILL:100 or BILL:PULSE_COUNT:3

*/
