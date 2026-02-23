# Quick Reference: Cart Status + Logging Configuration

## What Changed?

### 1️⃣ Cart Screen Now Shows Status Panel
When customers are paying, they see real-time system status at the bottom:
- 🌡️ Temperature and humidity
- ❄️ TEC cooling status
- 📡 Item bin detection
- ⚙️ System health

**File:** `cart_screen.py` (added 3 lines)

### 2️⃣ Logging Configuration Like Images
Logging is now configured in `config.json` just like image paths.

**Files:** 
- `config.example.json` (added logging + items sections)
- `system_logger.py` (new module, 350+ lines)

---

## File Changes at a Glance

```
cart_screen.py
├─ + from system_status_panel import SystemStatusPanel
└─ + self.status_panel = SystemStatusPanel(...)

config.example.json
├─ + "header_logo_path": "./logo.png"
├─ + "items": { "image_directory": "./images", ... }
└─ + "logging": { "transaction_log", "error_log", ... }

system_logger.py  [NEW FILE - 350+ lines]
├─ SystemLogger class (singleton)
├─ Auto-rotating logs
├─ 4 log types (transaction, error, dispense, sensor)
└─ Easy configuration from config.json
```

---

## How to Use

### Option 1: Use Now (Immediate)
```python
from system_logger import SystemLogger

# Initialize with your config
logger = SystemLogger(your_config_dict)

# Start logging
logger.log_transaction("Payment received: 100 PHP")
logger.log_item_dispensed("Coca Cola", 1, "SUCCESS")
logger.log_temperature_reading(1, 24.5, 65.2)
```

### Option 2: Use Later (Optional)
- Logger is ready but doesn't need to be used immediately
- Can integrate into main.py incrementally
- system_logger.py works standalone

### Option 3: Copy Config
```bash
# Update your config.json with logging section from config.example.json
```

---

## Log Files Created Automatically

```
logs/
├─ transactions.log    ← payments
├─ errors.log         ← system errors
├─ dispense.log       ← item dispensing
└─ sensors.log        ← temperature readings
```

Each log:
- Max 10 MB (configurable)
- Keeps 5 backups (configurable)
- Auto-rotates

---

## Configuration Analogy

### Images (Existing)
```json
{
  "header_logo_path": "./logo.png",
  "items": {
    "image_directory": "./images"
  }
}
```
Items reference images: `"image": "./images/coke.png"`

### Logging (New)
```json
{
  "logging": {
    "log_directory": "./logs",
    "transaction_log": {"log_filename": "transactions.log"},
    "error_log": {"log_filename": "errors.log"},
    ...
  }
}
```
Pre-defined log files for different purposes

---

## Verification Commands

```bash
# Check compilation
python3 -m py_compile cart_screen.py system_logger.py

# Check config
python3 -c "import json; json.load(open('config.example.json'))"

# Check imports
python3 -c "from system_logger import SystemLogger; from cart_screen import CartScreen; print('OK')"

# Test logger
python3 system_logger.py
```

---

## What Gets Logged?

| Log File | Examples |
|----------|----------|
| **transactions.log** | Payment received: coins = PHP100<br>Transaction completed |
| **errors.log** | Connection timeout<br>Sensor reading invalid |
| **dispense.log** | Dispensed 1x Coca Cola<br>Item detected in bin<br>Dispense timeout |
| **sensors.log** | DHT22[1] T=24.5°C<br>TEC [ACTIVE] Target=10°C |

---

## Integration with main.py (Optional)

```python
from system_logger import SystemLogger

class VendingController:
    def __init__(self, config):
        self.logger = SystemLogger(config)
    
    # Log payment events
    def _handle_payment(self, amount):
        self.logger.log_payment_received(amount)
    
    # Log sensor readings
    def _on_dht22_update(self, sensor_num, temp, humidity):
        self.logger.log_temperature_reading(sensor_num, temp, humidity)
    
    # Log errors
    def _handle_error(self, error_msg):
        self.logger.log_error(error_msg)
```

---

## Features

✅ **Cart Screen Status Display**
- Visible during checkout
- Real-time hardware monitoring
- Builds customer trust

✅ **Structured Logging**
- Similar to image configuration
- 4 log types (transaction, error, dispense, sensor)
- Auto-rotating files

✅ **Zero Maintenance**
- Auto-creates log directory
- Auto-rotates logs at 10 MB
- Keeps 5 backups max
- Old files auto-deleted

✅ **Easy Configuration**
- All in config.json
- Can enable/disable per log type
- Flexible log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)

---

## Troubleshooting

**Q: Logs not created?**
A: Check `logging.enabled` is `true` in config.json

**Q: Logs filling disk?**
A: Auto-rotation works - max 60 MB total (5 files × 10 MB each)

**Q: Unicode errors in console?**
A: Windows console issue - logs still written correctly

**Q: How to disable logging?**
A: Set `"enabled": false` in logging config

---

## Documentation

- **CART_STATUS_AND_LOGGING.md** - Complete detailed guide
- **IMPLEMENTATION_COMPLETE.md** - Implementation summary
- **system_logger.py** - Code comments and docstrings
- **config.example.json** - Configuration reference

---

## Quick Start (Copy-Paste)

### 1. Update config.json
Copy this section:
```json
"logging": {
  "enabled": true,
  "log_directory": "./logs",
  "log_level": "INFO",
  "max_log_size_mb": 10,
  "backup_count": 5,
  "transaction_log": {"enabled": true, "log_filename": "transactions.log"},
  "error_log": {"enabled": true, "log_filename": "errors.log"},
  "dispense_log": {"enabled": true, "log_filename": "dispense.log"},
  "sensor_log": {"enabled": true, "log_filename": "sensors.log"}
}
```

### 2. Use Logger in Code
```python
from system_logger import SystemLogger
logger = SystemLogger(config)
logger.log_transaction("Your event")
```

### 3. Find Logs
```
./logs/transactions.log
./logs/errors.log
./logs/dispense.log
./logs/sensors.log
```

---

## Testing

```bash
# Test logger directly
python3 system_logger.py

# Output:
✓ Logging directory ready: ./logs
✓ Logger 'transaction_logger' configured
✓ Logger 'error_logger' configured
✓ Logger 'dispense_logger' configured
✓ Logger 'sensor_logger' configured
✓ Testing complete!
```

---

## Status

| Feature | Status | Notes |
|---------|--------|-------|
| Cart status display | ✅ Complete | Shows in payment screen |
| Logging config | ✅ Complete | In config.example.json |
| system_logger.py | ✅ Complete | Tested and working |
| Documentation | ✅ Complete | 3 detailed guides |
| Integration | ⏳ Optional | Can add to main.py |
| Testing | ✅ Complete | All tests pass |

---

## Next Steps

1. **Review** - Check `CART_STATUS_AND_LOGGING.md` for details
2. **Configure** - Copy logging section to your `config.json`
3. **Deploy** - Ready for Raspberry Pi deployment
4. **Monitor** - Check `./logs/` directory for events
5. **Integrate** - Optional: add logging to main.py for more detail

---

**Everything is ready to use! 🚀**

For detailed information, see: **CART_STATUS_AND_LOGGING.md**
