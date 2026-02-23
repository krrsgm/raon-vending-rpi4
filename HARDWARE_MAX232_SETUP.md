# MAX232 Level Converter Setup Guide

## Overview

The TB74 bill acceptor communicates using RS-232 serial protocol, which requires voltage levels between -12V to +12V. The Raspberry Pi UART operates at TTL levels (0V to 3.3V). The MAX232 IC is a level converter that bridges this gap.

---

## Hardware Connection Diagram

```
TB74 Bill Acceptor          MAX232 IC              Raspberry Pi 4
(RS-232)                    (Level Converter)       (TTL/UART)

TX (Pin 2) ──────────────► RX (Pin 13) ─────► GPIO 15 (RXD/UART0-RX)
RX (Pin 3) ◄──────────────── TX (Pin 14) ◄───── GPIO 14 (TXD/UART0-TX)
GND ───────────────────► GND (Pin 15)
+5V ───────────────────► VCC (Pin 16)
                        GND (Pins 11,12)
                        VCC (Pins 4,5)

Note: Pin numbers refer to MAX232 DIP-16 package pinout
```

---

## MAX232 Pinout (DIP-16 Package)

```
        ┌─────────────────┐
      1 │ C1+ ────────── 16│ VCC (+5V)
      2 │ C1- ────────── 15│ GND
      3 │ C2+ ────────── 14│ TX → RPi GPIO 14 (TXD)
      4 │ C2- ────────── 13│ RX from RPi GPIO 15 (RXD)
      5 │ GND ────────── 12│ GND
      6 │ R1OUT ──────── 11│ GND
      7 │ R1IN  ──────── 10│ R2IN (leave unconnected)
      8 │ T1IN  ─────────  9│ T2OUT (leave unconnected)
        └─────────────────┘
        
        ↑
    MAX232 IC
```

---

## Detailed Wiring

### MAX232 Power Supply Connections
```
Pin 16 (VCC)    → +5V (from RPi or external)
Pin 5, 11, 12, 15 (GND) → Ground
```

### Capacitor Connections (Required for Level Shifting)
```
Pin 1 (C1+) → 10µF capacitor → +5V
Pin 2 (C1-) → 10µF capacitor → GND

Pin 3 (C2+) → 10µF capacitor → +5V  
Pin 4 (C2-) → 10µF capacitor → GND

(Four 10µF capacitors total, or use 100nF if 10µF unavailable)
```

### TB74 to MAX232 Connection
```
TB74 TX (Pin 2) → MAX232 Pin 13 (RX Input)
TB74 RX (Pin 3) → MAX232 Pin 14 (TX Output)
TB74 GND        → MAX232 GND (Pin 5, 11, 12, 15)
TB74 +5V        → MAX232 VCC (Pin 16)
```

### MAX232 to Raspberry Pi Connection
```
MAX232 Pin 13 (RX)  → RPi GPIO 15 (UART RXD)
MAX232 Pin 14 (TX)  → RPi GPIO 14 (UART TXD)
MAX232 GND          → RPi GND
```

---

## Raspberry Pi GPIO Assignment

```
GPIO 14 (TXD/UART0-TX) → TX to MAX232 (Pin 14)
GPIO 15 (RXD/UART0-RX) → RX from MAX232 (Pin 13)
```

---

## Step-by-Step Assembly

### 1. Prepare the Breadboard Layout
- Place MAX232 IC in center of breadboard
- Reserve rows for TB74 connector, RPi header, and capacitors

### 2. Add Capacitors
- Install 4× 10µF (or 100nF) capacitors on breadboard
- Connect C1+/C1- to power/ground (pins 1-2)
- Connect C2+/C2- to power/ground (pins 3-4)

### 3. Connect Power
- VCC (pin 16) → +5V supply
- All GND pins (5, 11, 12, 15) → Ground

### 4. Connect TB74 Lines
- TB74 TX → MAX232 RX Input (Pin 13)
- TB74 RX → MAX232 TX Output (Pin 14)
- TB74 GND → Breadboard Ground
- TB74 +5V → +5V Supply (if powered externally)

### 5. Connect to Raspberry Pi
- MAX232 Pin 13 (RX) → RPi GPIO 15
- MAX232 Pin 14 (TX) → RPi GPIO 14
- Ground → RPi GND (use same power supply!)

### 6. Enable UART on Raspberry Pi
```bash
sudo raspi-config
# Navigate to: Interface Options → Serial Port
# Disable serial login shell: YES
# Enable serial port hardware: YES
# Exit and reboot
```

---

## Configuration in Python Code

### Default Port (No Configuration Needed)

The code now defaults to `/dev/ttyAMA0` (RPi hardware UART):

```python
from bill_acceptor import BillAcceptor

# Uses /dev/ttyAMA0 by default
bill_acceptor = BillAcceptor()
bill_acceptor.connect()
bill_acceptor.start_reading()
```

### Custom Port (If Needed)

For USB adapter or other port:

```python
from bill_acceptor import BillAcceptor

# Custom port
bill_acceptor = BillAcceptor(port='/dev/ttyUSB0')
bill_acceptor.connect()
bill_acceptor.start_reading()
```

### In PaymentHandler

```python
from payment_handler import PaymentHandler

# Uses /dev/ttyAMA0 by default
handler = PaymentHandler(config)

# Or custom port
handler = PaymentHandler(config, bill_port='/dev/ttyUSB0')
```

---

## Testing the Connection

### 1. Check Serial Port
```bash
# List available serial ports
ls -la /dev/tty*

# You should see /dev/ttyAMA0 (hardware UART)
```

### 2. Enable UART and Check
```bash
# Check if UART is enabled
sudo raspi-config nonint get_serial_hw

# Output: 0 = enabled, 1 = disabled
```

### 3. Test with Python
```python
import serial

# Test connection
try:
    ser = serial.Serial('/dev/ttyAMA0', 9600, timeout=1)
    print("✓ Serial connection successful")
    
    # Read incoming data
    if ser.in_waiting:
        data = ser.read(ser.in_waiting)
        print(f"Received: {data.hex()}")
    
    ser.close()
except Exception as e:
    print(f"✗ Error: {e}")
```

### 4. Test Bill Acceptor
```python
from bill_acceptor import BillAcceptor

bill = BillAcceptor()
if bill.connect():
    bill.start_reading()
    print("✓ Bill acceptor connected")
    
    # Manually feed a bill and check
    import time
    time.sleep(5)
    
    amount = bill.get_received_amount()
    print(f"Amount received: ₱{amount}")
    
    bill.stop_reading()
    bill.disconnect()
else:
    print("✗ Failed to connect")
```

---

## Troubleshooting

### "Permission to krrsgm/raon-vending-rpi4.git denied"
- This is a GitHub authentication issue, not related to MAX232

### Serial Connection Fails: "Permission denied"
```bash
# Fix permissions
sudo usermod -a -G dialout $USER

# Log out and back in for changes to take effect
```

### No Data Received
1. Check MAX232 capacitors are installed
2. Verify all GND connections
3. Test with oscilloscope if available
4. Try 115200 baud rate instead

### Data Corruption
1. Ensure good ground connection between RPi and MAX232
2. Use shielded cable for serial lines if possible
3. Check for EMI (electromagnetic interference)

### TB74 Not Responding
1. Verify TB74 is powered (+5V and GND)
2. Check TB74 is in accept mode (consult TB74 manual)
3. Ensure baud rate is set to 9600
4. Verify start/stop bits match TB74 spec (8-N-2)

---

## Hardware Bill of Materials (BOM)

| Component | Qty | Notes |
|-----------|-----|-------|
| MAX232 IC | 1 | DIP-16 package |
| 10µF Capacitor | 4 | Electrolytic, 16V or higher |
| Breadboard | 1 | Standard size |
| Jumper Wires | ~15 | 22 AWG recommended |
| +5V Power Supply | 1 | For MAX232 and TB74 |

---

## Pinout Quick Reference

### Raspberry Pi UART Pins
```
GPIO 14 (Pin 8)  → TXD (transmit)
GPIO 15 (Pin 10) → RXD (receive)
GND (Pin 6)      → Ground
```

### MAX232 Serial Lines
```
Pin 13 (RX)  ← TB74 TX ← Serial Input
Pin 14 (TX)  → TB74 RX → Serial Output
```

### TB74 Serial Connector
```
Pin 1: GND
Pin 2: TX (to MAX232 RX)
Pin 3: RX (from MAX232 TX)
Pin 4: +5V
```

---

## Notes

1. **Voltage Levels**: MAX232 converts between +12V/-12V (RS-232) and 0V/+5V (TTL)
2. **Capacitors**: Essential for level shifting - don't skip!
3. **Baud Rate**: TB74 defaults to 9600 - verify in your unit
4. **Ground**: Common ground between RPi, MAX232, and TB74 is critical
5. **Power Supply**: Use stable 5V source; noise can cause transmission errors

---

## Further Reading

- MAX232 Datasheet: https://www.ti.com/lit/ds/symlink/max232.pdf
- RPi UART Documentation: https://www.raspberrypi.org/documentation/
- TB74 Bill Acceptor Manual: Consult your device documentation

