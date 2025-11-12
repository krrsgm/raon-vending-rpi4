// esp32_bill_forward.ino
// Simple ESP32 sketch to read TB74 (or MAX232-connected) bytes from a serial
// interface and forward bill accept events to the Raspberry Pi in the form:
//   BILL:<amount>\n
// Depending on your wiring, you may read TB74 on Serial2 (UART2) and forward
// via Serial (USB) or via TCP on WiFi. This sketch provides both methods.

#include <WiFi.h>

// === CONFIG ===
const char* ssid = "your-ssid";
const char* password = "your-password";

// If forwarding over TCP, connect to the Pi's host and port
const char* pi_host = "192.168.4.1"; // change to your Pi IP
const uint16_t pi_port = 5000;

bool use_tcp_forward = false; // set true to forward to Pi over TCP
bool use_usb_serial = true;   // set true to forward over USB Serial (Serial)

// TB74 connected to Serial2 (change pins/uart as needed)
HardwareSerial tbSerial(2);
const int TB_RX_PIN = 16; // ESP32 RX2 pin (input from TB74 TX)
const int TB_TX_PIN = 17; // ESP32 TX2 pin (output to TB74 RX)

WiFiClient piClient;

void setup() {
  // Serial (USB) to host
  Serial.begin(115200);
  delay(1000);
  Serial.println("ESP32 Bill Forwarder starting...");

  // TB74 serial (match TB74 baud/format)
  tbSerial.begin(9600, SERIAL_8N2, TB_RX_PIN, TB_TX_PIN);

  // Optional WiFi connect for TCP forwarding
  if (use_tcp_forward) {
    WiFi.begin(ssid, password);
    Serial.print("Connecting to WiFi");
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 20) {
      delay(500);
      Serial.print('.');
      attempts++;
    }
    Serial.println();
    if (WiFi.status() == WL_CONNECTED) {
      Serial.print("Connected, IP: ");
      Serial.println(WiFi.localIP());
    } else {
      Serial.println("WiFi connect failed");
    }
  }
}

String buffer = "";

void forward_line(const String &line) {
  // Normalize and forward
  if (use_usb_serial) {
    Serial.println(line);
  }
  if (use_tcp_forward) {
    if (!piClient.connected()) {
      if (!piClient.connect(pi_host, pi_port)) {
        Serial.println("Failed to connect to Pi TCP");
        return;
      }
    }
    piClient.println(line);
  }
}

void loop() {
  // Read from TB74 serial
  while (tbSerial.available()) {
    int b = tbSerial.read();
    if (b < 0) break;
    // If TB74 sends ASCII or single bytes, parse accordingly
    // This example assumes TB74 sends status bytes; you may need to adapt
    // mapping from byte values to amounts here.
    
    // Example: TB74 sends 0x41..0x45 mapping to 20..1000
    if (b == 0x41) {
      forward_line("BILL:20");
    } else if (b == 0x42) {
      forward_line("BILL:50");
    } else if (b == 0x43) {
      forward_line("BILL:100");
    } else if (b == 0x44) {
      forward_line("BILL:500");
    } else if (b == 0x45) {
      forward_line("BILL:1000");
    } else {
      // If TB74 sends ASCII text, accumulate and forward lines
      if (b == '\n' || b == '\r') {
        if (buffer.length() > 0) {
          forward_line(buffer);
          buffer = "";
        }
      } else {
        buffer += (char)b;
        if (buffer.length() > 256) buffer = buffer.substring(buffer.length()-256);
      }
    }
  }

  // Also forward any incoming Serial (USB) commands to Serial2 if needed
  // (optional bridging)
  while (Serial.available()) {
    int c = Serial.read();
    // echo for debug
    //Serial.write(c);
  }

  delay(10);
}
