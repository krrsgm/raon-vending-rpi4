# Motor Test Troubleshooting Guide

## Overview

The motor test feature allows you to verify that individual vending slots are properly connected and responsive. When you click the **"Test"** button next to a slot in the Assign Items screen, it sends a pulse command to the ESP32 vending controller.

## Testing Motor

### From the Admin Screen

1. **Open Admin Screen** → **Assign Items to Slots**
2. **Find the slot** you want to test
3. **Click the "Test" button** next to the slot
4. **Listen for the motor** to pulse (should hear a click/buzz)
5. **Check the result** in the message box

### Expected Behavior

✓ **Success**: Motor makes a brief buzzing/clicking sound, message says "Motor Test Success"

✗ **Failure**: No sound, error message about connection issues

---

## Common Issues & Solutions

### Issue 1: "Connection Failed" Error

**Symptoms:**
- Error message: "Cannot reach ESP32 at [host]"
- No motor pulse sound
- Connection error shows in the message

**Causes:**
- ESP32 not powered on
- Wrong USB port or serial configuration
- USB cable not properly connected
- Permissions issue on Linux/Mac

**Solutions:**

#### For Serial Connection (e.g., `serial:/dev/ttyUSB0`):

1. **Check USB cable connection:**
   - Verify cable is properly plugged into both Raspberry Pi and ESP32
   - Try a different USB cable
   - Try a different USB port on the Raspberry Pi

2. **Verify serial port exists:**
   ```bash
   # On Raspberry Pi (Linux)
   ls /dev/ttyUSB*
   ls /dev/ttyACM*
   
   # Should show /dev/ttyUSB0 or similar
   ```

3. **Check permissions (Linux/Mac only):**
   ```bash
   # Check current user
   whoami
   
   # Add user to dialout group (may need restart)
   sudo usermod -a -G dialout $USER
   
   # Or run kiosk app with sudo
   sudo python main.py
   ```

4. **Test serial connection directly:**
   ```bash
   cd tools
   python test_esp32_connection.py serial:/dev/ttyUSB0
   ```

#### For TCP Connection (e.g., `192.168.4.1`):

1. **Check ESP32 is powered on**
2. **Verify network connection:**
   ```bash
   ping 192.168.4.1
   ```

3. **Check firewall:**
   - Port 5000 should be open on ESP32
   - Check if router is blocking the connection

4. **Test connection directly:**
   ```bash
   cd tools
   python test_esp32_connection.py 192.168.4.1
   ```

---

### Issue 2: "Connection Timeout" Error

**Symptoms:**
- Error message mentions "timeout"
- Motor doesn't respond after a few seconds
- ESP32 might be responding slowly

**Solutions:**

1. **ESP32 might be busy:**
   - Wait a moment and try again
   - Restart ESP32

2. **Check serial connection quality:**
   - Use a shorter USB cable
   - Avoid USB hubs (connect directly to Raspberry Pi)
   - Try different USB port

3. **Increase timeout in config.json:**
   ```json
   {
     "esp32_host": "serial:/dev/ttyUSB0",
     "esp32_timeout_ms": 3000
   }
   ```

---

### Issue 3: Motor Doesn't Pulse (No Sound)

**Symptoms:**
- Message says "Motor Test Success"
- BUT: No sound from motor
- Motor might not be connected

**Causes:**
- Motor not connected to ESP32 multiplexer
- Wrong GPIO pin configured
- Motor power issue
- Multiplexer issue

**Solutions:**

1. **Verify motor is connected:**
   - Check all wiring connections
   - Check motor power supply
   - Verify multiplexer is powered

2. **Check slot number:**
   - Slots are numbered 1-64
   - Verify motor is wired to the correct slot

3. **Test all slots:**
   - Try pulsing different slots
   - If SOME slots work, others might have wiring issues

4. **Check multiplexer channels:**
   - Vending machine has 4 multiplexers (CD74HC4067)
   - Each controls 16 slots
   - Verify correct multiplexer is wired

---

## Diagnostic Tools

### Quick Test from Command Line

```bash
cd tools

# Test connection only
python test_esp32_connection.py serial:/dev/ttyUSB0

# Test connection with verbose output
python test_esp32_connection.py serial:/dev/ttyUSB0 --verbose

# Test specific slot (pulse slot 5)
python test_esp32_connection.py serial:/dev/ttyUSB0 --slot 5

# For TCP connection
python test_esp32_connection.py 192.168.4.1
```

### Example Output (Success)

```
======================================================================
ESP32 VENDING CONTROLLER CONNECTION TEST
======================================================================

Target Host: serial:/dev/ttyUSB0
Connection Type: Serial (UART)
Serial Port: /dev/ttyUSB0
Baud Rate: 115200

----------------------------------------------------------------------
Test 1: STATUS Command
----------------------------------------------------------------------
Sending: STATUS
✓ Response received: OK
✓ Connection test PASSED

----------------------------------------------------------------------
Test 2: PULSE Slot 1
----------------------------------------------------------------------
Sending: PULSE 1 100
✓ Pulse sent successfully

======================================================================
SUMMARY
======================================================================
✓ ESP32 is reachable
✓ Connection working properly

You can now use motor test in the admin screen.
ESP32 Status: OK
```

### Example Output (Failure)

```
======================================================================
ESP32 VENDING CONTROLLER CONNECTION TEST
======================================================================

Target Host: serial:/dev/ttyUSB0
Connection Type: Serial (UART)
Serial Port: /dev/ttyUSB0
Baud Rate: 115200

----------------------------------------------------------------------
Test 1: STATUS Command
----------------------------------------------------------------------
Sending: STATUS
✗ Connection failed: [Errno 2] No such file or directory: '/dev/ttyUSB0'
✗ Connection test FAILED

======================================================================
TROUBLESHOOTING
======================================================================

Serial Connection Issues:
1. Check USB cable is properly connected
2. Verify serial port exists: /dev/ttyUSB0
3. Check USB permissions (may need sudo on Linux/Mac)
4. Try different USB port
5. Verify ESP32 firmware is loaded

On Linux, list available ports:
  ls /dev/ttyUSB* /dev/ttyACM*

Error: [Errno 2] No such file or directory: '/dev/ttyUSB0'
```

---

## Configuration

### In config.json

```json
{
  "esp32_host": "serial:/dev/ttyUSB0",
  "esp32_pulse_ms": 800,
  "esp32_timeout_ms": 2000
}
```

**Options:**

| Setting | Default | Description |
|---------|---------|-------------|
| `esp32_host` | `192.168.4.1` | ESP32 connection: TCP IP, or `serial:/dev/ttyXXX` for serial |
| `esp32_pulse_ms` | `800` | Default pulse duration in milliseconds (motor on time) |
| `esp32_timeout_ms` | `2000` | How long to wait for ESP32 response (milliseconds) |

---

## Serial vs TCP Connection

### Serial Connection (Recommended for Raspberry Pi)

**Pros:**
- More reliable on Raspberry Pi
- Direct connection via USB
- No network dependency
- Lower latency

**Cons:**
- Requires USB cable
- Limited to one ESP32 per serial port

**Config:**
```json
{
  "esp32_host": "serial:/dev/ttyUSB0"
}
```

**Finding your serial port:**
```bash
# List all USB devices
ls /dev/ttyUSB* /dev/ttyACM*

# If multiple, try each one:
ls -la /dev/ttyUSB*
```

### TCP Connection (Network)

**Pros:**
- No cable needed (wireless possible)
- Multiple devices on network
- Good for testing

**Cons:**
- Network dependency
- Less reliable than direct connection
- Requires network to be configured

**Config:**
```json
{
  "esp32_host": "192.168.4.1"
}
```

**Finding ESP32 IP:**
```bash
# If ESP32 is in AP mode, connect to "RAON" WiFi
# Then access at: 192.168.4.1

# Or scan network
arp-scan -l
nmap -p 5000 192.168.4.0/24
```

---

## Testing Steps

### Complete Test Procedure

1. **Test Connection:**
   ```bash
   cd tools
   python test_esp32_connection.py serial:/dev/ttyUSB0
   ```

2. **If connection works, test from Admin Screen:**
   - Go to Assign Items → Slots
   - Click "Test" on Slot 1
   - Verify motor pulses

3. **If motor doesn't pulse:**
   - Check wiring: Motor → Multiplexer → ESP32
   - Check motor power supply
   - Test different slots

4. **If multiple slots don't work:**
   - Check multiplexer connections
   - Verify ESP32 GPIO pins match config

---

## Error Messages Reference

| Error | Likely Cause | Solution |
|-------|-------------|----------|
| "No such file or directory: /dev/ttyUSB0" | Serial port not found | Check USB cable, use correct port name |
| "Permission denied" | User doesn't have serial permission | `sudo usermod -a -G dialout $USER` |
| "Connection refused" | ESP32 not listening | Power cycle ESP32, check TCP config |
| "Timeout" | No response from ESP32 | Check connection, restart ESP32 |
| "Motor Test Error: [error]" | Command failed | Check ESP32 logs, verify slot number |

---

## Next Steps

✓ If motor test works: You're ready to sell items!

✗ If motor test still fails:
1. Check the detailed error message carefully
2. Use `test_esp32_connection.py` to diagnose
3. Review the wiring diagram in the docs
4. Check ESP32 firmware is correct version
5. Consider trying TCP connection instead

---

## Additional Resources

- **SYSTEM_ARCHITECTURE.md** - Hardware pinout and system diagram
- **tools/esp32_probe.py** - Advanced ESP32 diagnostics
- **esp32_client.py** - Python client for ESP32 communication
- **vending_controller/vending_controller.ino** - ESP32 firmware source

