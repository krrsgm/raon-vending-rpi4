/*
  coin_sensor_test.ino

  ESP32 sketch to test coin sensors.
  Simple detection: Sensor is normally HIGH, goes LOW when coin passes through.
  
  Wiring:
    - 1-peso sensor (optical/mechanical) → GPIO 34
    - 5-peso sensor (optical/mechanical) → GPIO 35
  
  Detection: Counts coin when sensor goes from HIGH → LOW
*/

// Pin configuration
const int ONE_SENSOR_PIN = 34;  // 1-peso sensor input
const int FIVE_SENSOR_PIN = 35; // 5-peso sensor input

const unsigned long BAUD_RATE = 115200;

// Counters and state tracking
unsigned int one_count = 0;
unsigned int five_count = 0;
int last_one_state = HIGH;  // Track previous state for edge detection
int last_five_state = HIGH;

const unsigned long DEBOUNCE_MS = 10;  // Very short debounce for fast detection
unsigned long last_display_time = 0;
const unsigned long DISPLAY_INTERVAL = 1000;  // Display status every 1 second

void setup() {
  Serial.begin(BAUD_RATE);
  delay(500);
  
  // Configure sensor pins as inputs
  pinMode(ONE_SENSOR_PIN, INPUT);
  pinMode(FIVE_SENSOR_PIN, INPUT);
  
  Serial.println("\n========================================");
  Serial.println("ESP32 COIN SENSOR TEST");
  Serial.println("========================================");
  Serial.println("GPIO 34: 1-peso sensor");
  Serial.println("GPIO 35: 5-peso sensor");
  Serial.println("Sensor state: HIGH (normal) → LOW (coin)");
  Serial.println("Drop coins into hoppers to test...");
  Serial.println("========================================\n");
}

void loop() {
  // Read current pin states - run as fast as possible
  int one_state = digitalRead(ONE_SENSOR_PIN);
  int five_state = digitalRead(FIVE_SENSOR_PIN);
  
  // Detect HIGH → LOW transition (coin passing through)
  if (last_one_state == HIGH && one_state == LOW) {
    one_count++;
    Serial.println("✓ 1-PESO COIN DETECTED!");
  }
  
  if (last_five_state == HIGH && five_state == LOW) {
    five_count++;
    Serial.println("✓ 5-PESO COIN DETECTED!");
  }
  
  // Update state tracking
  last_one_state = one_state;
  last_five_state = five_state;
  
  // Display status periodically (not on every loop iteration)
  unsigned long now = millis();
  if (now - last_display_time >= DISPLAY_INTERVAL) {
    last_display_time = now;
    Serial.println("\n--- STATUS ---");
    Serial.print("1-PESO: ");
    Serial.print(one_count);
    Serial.print(" coins | State: ");
    Serial.println(one_state == HIGH ? "HIGH" : "LOW");
    
    Serial.print("5-PESO: ");
    Serial.print(five_count);
    Serial.print(" coins | State: ");
    Serial.println(five_state == HIGH ? "HIGH" : "LOW");
    Serial.println();
  }
}
