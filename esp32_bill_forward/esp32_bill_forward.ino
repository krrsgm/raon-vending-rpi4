volatile int pulseCount = 0;
unsigned long lastPulseTime = 0;
const int pulsePin = 2;
const unsigned long timeout = 1000; // 5 seconds

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

}

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
    case 5: return 20;
    case 10: return 100;
    case 20: return 200;
    case 50: return 500;
    case 100: return 1000;
    default: return 0;
  }
}
