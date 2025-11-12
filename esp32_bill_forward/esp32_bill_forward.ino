volatile int pulseCount = 0;
unsigned long lastPulseTime = 0;
const int pulsePin = 2;
const unsigned long timeout = 700; // 700 ms

bool waitingForBill = false;
bool billProcessed = false;

void setup() {
  Serial.begin(115200);
  pinMode(pulsePin, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(pulsePin), countPulse, FALLING);
}

void loop() {
if (waitingForBill && !billProcessed && millis() - lastPulseTime > timeout) {
  int pesoValue = mapPulsesToPesos(pulseCount);
  // Always emit a machine-friendly pulses line for diagnostics
  Serial.print("PULSES:");
  Serial.println(pulseCount);

  if (pesoValue > 0) {
    // Emit both human-friendly and machine-friendly bill lines
    Serial.print("Bill inserted: ₱");
    Serial.println(pesoValue);
    Serial.print("BILL:");
    Serial.println(pesoValue);
    pulseCount = 0;
    waitingForBill = false;
    billProcessed = true;
  } else {
    // Unknown pulse pattern — report and reset after extended timeout
    Serial.print("Unknown pulse count: ");
    Serial.println(pulseCount);
    if (millis() - lastPulseTime > timeout + 5000) {
      pulseCount = 0;
      waitingForBill = false;
      billProcessed = true;
    }
}


}

void countPulse() {
  pulseCount++;
  lastPulseTime = millis();
  waitingForBill = true;
  billProcessed = false; // reset lock when new pulse comes in
  Serial.print("Pulse detected. Total: ");
  Serial.println(pulseCount);
}

int mapPulsesToPesos(int pulses) {
  switch (pulses) {
    case 5: return 20;
    case 10: return 100;
    case 20: return 200;
    case 50: return 500;
    case 100: return 1000;
    default: return 0;
  }
}
