# Motor Test Improvements - Summary

## What Changed

The motor test functionality has been significantly improved to help diagnose and fix connection issues. The changes focus on providing better error messages and diagnostic tools.

## Key Improvements

### 1. Enhanced Error Handling in `assign_items_screen.py`

**Before:**
- Generic error message: "Failed to test motor 5: [error]"
- No context about what went wrong
- No suggestions for fixing the issue

**After:**
- Pre-test ESP32 connection with STATUS command
- Specific error types with targeted solutions:
  - Connection timeout → Check ESP32 power and USB cable
  - Connection refused → Check ESP32 is running
  - Configuration error → Check config.json settings
- Detailed error dialogs with troubleshooting hints

**Code:**
```python
def test_motor(self, idx):
    # ... checks esp32_host from config
    # ... validates configuration
    # ... checks ESP32 connection first
    # ... provides specific error messages
```

### 2. Improved `esp32_client.py`

**Changes:**
- Better serial port error handling (distinguishes between timeout and port not found)
- Added `logging.error()` for serial port specific errors
- Prevents unnecessary retries for permanent errors

```python
except serial.SerialException as e:
    # Serial port error (port not found, permission denied, etc.)
    logging.error(f"Serial port error on {port_name}: {e}")
    raise  # Don't retry, error is permanent
```

### 3. New Diagnostic Tools

#### `tools/test_esp32_connection.py`

Quick command-line tool to test ESP32 connectivity:

```bash
# Test serial connection
python tools/test_esp32_connection.py serial:/dev/ttyUSB0

# Test TCP connection
python tools/test_esp32_connection.py 192.168.4.1

# With verbose output
python tools/test_esp32_connection.py serial:/dev/ttyUSB0 --verbose
```

**Features:**
- Tests both STATUS command and actual pulse
- Shows detailed connection info
- Provides troubleshooting steps on failure
- Works with both serial and TCP connections

#### `tools/quick_motor_test.py`

Simplest way to test a specific motor:

```bash
# Test slot 1
python tools/quick_motor_test.py 1

# Test slot 5
python tools/quick_motor_test.py 5
```

**Features:**
- Load config automatically
- Simple pass/fail output
- Includes error troubleshooting

### 4. Comprehensive Documentation

#### `MOTOR_TEST_TROUBLESHOOTING.md`

Complete guide covering:
- How to use motor test feature
- Common issues and solutions
- Diagnostic tools usage
- Configuration options
- Serial vs TCP connections
- Error message reference
- Complete test procedures

## How to Use

### From the Admin Screen (Easiest)

1. Go to **Admin** → **Assign Items to Slots**
2. Click **Test** button next to any slot
3. Motor should buzz/click
4. If error occurs, read the error message for instructions

### From Command Line (Debugging)

```bash
# Quick test - fastest way
python tools/quick_motor_test.py 1

# Detailed diagnostic
python tools/test_esp32_connection.py serial:/dev/ttyUSB0 --verbose
```

### From Python (Programmatic)

```python
from esp32_client import pulse_slot

# Pulse slot 5 for 800ms
result = pulse_slot('serial:/dev/ttyUSB0', 5, 800)
print(f"Response: {result}")
```

## Common Issue Solutions

### Motor test shows error "Connection failed"

**Quick fix:**
```bash
python tools/test_esp32_connection.py serial:/dev/ttyUSB0
```

This will tell you exactly what's wrong:
- Port not found → Wrong USB port or cable
- Permission denied → Need sudo or user permissions
- Timeout → ESP32 not responding

### Motor test succeeds but no sound

Check:
1. Motor is connected to ESP32 multiplexer
2. Motor has power
3. Test a different slot to verify multiplexer works
4. Check wiring diagram in docs

### Timeout errors occur sometimes

Try:
1. Use shorter USB cable (for serial)
2. Avoid USB hubs (connect directly)
3. Increase timeout in config.json:
   ```json
   {
     "esp32_timeout_ms": 3000
   }
   ```

## Files Modified

```
assign_items_screen.py      - Enhanced test_motor() with better error handling
esp32_client.py             - Improved serial port error detection
tools/test_esp32_connection.py  - NEW: Diagnostic tool
tools/quick_motor_test.py       - NEW: Quick motor test
MOTOR_TEST_TROUBLESHOOTING.md   - NEW: Complete troubleshooting guide
```

## Testing the Changes

### Test 1: Verify error handling
```bash
# Change config to invalid port
python tools/quick_motor_test.py 1

# Should show clear error about invalid port
```

### Test 2: Verify working setup
```bash
# With correct config
python tools/test_esp32_connection.py serial:/dev/ttyUSB0

# Should show connection OK and pulse works
```

### Test 3: From admin screen
1. Open admin screen
2. Go to Assign Items
3. Click Test button
4. Verify error messages are helpful

## Configuration

Make sure your `config.json` has the correct ESP32 host:

```json
{
  "esp32_host": "serial:/dev/ttyUSB0",
  "esp32_pulse_ms": 800
}
```

Valid formats:
- `"serial:/dev/ttyUSB0"` - USB serial (Linux/RPi)
- `"serial:COM3"` - COM port (Windows)
- `"192.168.4.1"` - TCP network connection

## Benefits

✓ **Better User Experience:** Clear, actionable error messages

✓ **Faster Debugging:** Diagnostic tools identify issues quickly

✓ **Comprehensive Docs:** Troubleshooting guide covers all scenarios

✓ **Multiple Access Points:** Test from admin screen, CLI, or Python

✓ **Robust Error Handling:** Distinguishes different failure types

## What Works Now

1. ✓ Motor test shows specific error types
2. ✓ Pre-test connection validation
3. ✓ Diagnostic tools for troubleshooting
4. ✓ Clear error messages with solutions
5. ✓ Works with both serial and TCP connections
6. ✓ Comprehensive troubleshooting documentation

## Next Steps

1. Test motor functionality with `python tools/quick_motor_test.py 1`
2. If errors, run full diagnostic: `python tools/test_esp32_connection.py [host]`
3. Check MOTOR_TEST_TROUBLESHOOTING.md for solutions
4. Use admin screen Test buttons once working

