# Cart Screen Status Display + Logging Configuration

## Summary

Two major enhancements have been implemented:

1. **System Status Panel in Cart Screen** - Real-time hardware monitoring now displayed during checkout
2. **Image-Based Logging Configuration** - Structured logging similar to how images are configured

---

## 1. System Status Panel in Cart Screen

### What's New

The system status display (temperature, TEC, IR sensors) is now visible while customers are checking out and paying.

### Files Modified

- **cart_screen.py**
  - Added import: `from system_status_panel import SystemStatusPanel`
  - Added status panel at bottom: `self.status_panel = SystemStatusPanel(self, controller=self.controller)`

### What Customers See

While in the cart/payment screen, customers see at the bottom:

```
🌡️  ENV: T1=24.5°C H=65% | T2=23.8°C H=66%
❄️  TEC: OFF (Target: 10°C) | Current: 24.2°C
📡 IR: Sensor 1 (EMPTY) | Sensor 2 (EMPTY)
⚙️  SYSTEM: ✓ OPERATIONAL
```

### Benefits

- **Transparency**: Customers see the machine is working properly during payment
- **Trust**: Real-time monitoring builds confidence
- **Monitoring**: Operators can see hardware status from any screen

---

## 2. Image-Based Logging Configuration

### What's New

Logging is now configured in `config.json` just like images. Create logs for:
- Transactions (payment history)
- Errors (system issues)
- Dispense events (item dispensing)
- Sensor readings (temperature, IR)

### Configuration Structure

The logging config in `config.example.json` now looks like this:

```json
{
  "items": {
    "image_directory": "./images",
    "image_format": "png"
  },
  
  "logging": {
    "enabled": true,
    "log_directory": "./logs",
    "log_level": "INFO",
    "max_log_size_mb": 10,
    "backup_count": 5,
    "transaction_log": {
      "enabled": true,
      "log_filename": "transactions.log"
    },
    "error_log": {
      "enabled": true,
      "log_filename": "errors.log"
    },
    "dispense_log": {
      "enabled": true,
      "log_filename": "dispense.log"
    },
    "sensor_log": {
      "enabled": true,
      "log_filename": "sensors.log"
    }
  }
}
```

### How It Works

**Similar to Image Configuration:**

| Aspect | Images | Logging |
|--------|--------|---------|
| **Configured in** | config.json | config.json |
| **Path structure** | `image_directory` + `image` field | `log_directory` + multiple log files |
| **Enablement** | per-item in item_list.json | per-logger in config.json |
| **Auto-management** | PIL handles scaling | RotatingFileHandler auto-rotates files |
| **Directory** | Creates `./images` automatically | Creates `./logs` automatically |

---

## 3. New Module: system_logger.py

### What It Does

Provides centralized logging using a **singleton pattern** (like a global resource).

### Key Features

✅ **Multiple Log Types**
- Transaction logging (payments)
- Error logging (exceptions, warnings)
- Dispense logging (item dispensing, IR detection)
- Sensor logging (temperature readings, TEC status)

✅ **Auto-Rotating Logs**
- Automatically rotates when file reaches max size (default: 10 MB)
- Keeps backup copies (default: 5)

✅ **Configurable**
- Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
- Log directory: default `./logs`
- Can disable individual loggers

✅ **Easy to Use**
```python
from system_logger import get_logger

logger = get_logger()
logger.log_payment_received(100.00, 'coins', 'Coca Cola')
logger.log_item_dispensed('Coca Cola', 1, 'SUCCESS')
logger.log_temperature_reading(1, 24.5, 65.2)
```

### Usage Examples

```python
from system_logger import SystemLogger

# Initialize with config
config = {
    'logging': {
        'enabled': True,
        'log_directory': './logs',
        'log_level': 'INFO',
        'max_log_size_mb': 10,
        'backup_count': 5,
        'transaction_log': {'enabled': True, 'log_filename': 'transactions.log'},
        'error_log': {'enabled': True, 'log_filename': 'errors.log'},
        'dispense_log': {'enabled': True, 'log_filename': 'dispense.log'},
        'sensor_log': {'enabled': True, 'log_filename': 'sensors.log'}
    }
}

logger = SystemLogger(config)

# Log different events
logger.log_transaction("User inserted 100 PHP")
logger.log_error("Connection timeout", exc_info=False)
logger.log_dispense("Item Coca Cola dispensed successfully")
logger.log_sensor("Temperature reading: 24.5°C")

# Get info
print(logger.get_log_directory())
print(logger.get_log_summary())
print(logger.get_log_files())
```

---

## 4. Log File Examples

### transactions.log
```
2025-01-25 14:32:15 | INFO     | Payment received: coins = PHP100.00 (for Coca Cola)
2025-01-25 14:32:20 | INFO     | Payment received: bills = PHP500.00
2025-01-25 14:32:45 | INFO     | Transaction completed: Total = PHP600.00
```

### dispense.log
```
2025-01-25 14:32:50 | INFO     | [SUCCESS] Dispensed 1x Coca Cola
2025-01-25 14:33:10 | INFO     | [IR DETECT] Item detected in bin. Sensor 1+2 detected
2025-01-25 14:35:22 | WARNING  | [TIMEOUT] Dispense timeout for Sprite after 10s
```

### sensor.log
```
2025-01-25 14:30:00 | INFO     | DHT22[1] T=24.5°C H=65.1%
2025-01-25 14:30:05 | INFO     | TEC [ACTIVE] Target=10.0°C Current=12.3°C
2025-01-25 14:30:10 | INFO     | DHT22[2] T=23.8°C H=66.2%
```

### errors.log
```
2025-01-25 14:22:15 | ERROR    | Connection timeout to ESP32
2025-01-25 14:25:33 | WARNING  | Sensor reading invalid
2025-01-25 14:28:44 | ERROR    | Bill acceptor disconnected
```

---

## 5. Integration with main.py (Next Step)

To use the logging in main.py:

```python
from system_logger import SystemLogger

class VendingController:
    def __init__(self, config):
        self.config = config
        self.logger = SystemLogger(config)
    
    def _on_tec_status_update(self, enabled, active, target_temp, current_temp):
        # Log status
        self.logger.log_tec_status(enabled, active, target_temp, current_temp)
        # ... existing code ...
    
    def _on_dht22_update(self, sensor_num, temp, humidity):
        # Log sensor reading
        self.logger.log_temperature_reading(sensor_num, temp, humidity)
        # ... existing code ...
    
    def handle_payment_complete(self, amount):
        # Log transaction
        self.logger.log_transaction(f"Payment completed: PHP{amount:.2f}")
        # ... existing code ...
```

---

## 6. Configuration: How to Set Up

### Step 1: Update Your config.json

Copy the logging section from `config.example.json`:

```json
{
  "currency_symbol": "₱",
  "header_logo_path": "./logo.png",
  
  "items": {
    "image_directory": "./images",
    "image_format": "png"
  },
  
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
  },
  
  "hardware": { ... }
}
```

### Step 2: Create Logs Directory

The system creates `./logs` automatically on first run.

### Step 3: Start Using

```python
from system_logger import SystemLogger

# Will read from config
logger = SystemLogger(your_config)
logger.log_transaction("First transaction!")
```

---

## 7. File Changes Summary

| File | Change | Type |
|------|--------|------|
| `cart_screen.py` | Added SystemStatusPanel import and instantiation | Modified |
| `config.example.json` | Added `header_logo_path`, `items`, and `logging` sections | Enhanced |
| `system_logger.py` | New logging module (350+ lines) | Created |

---

## 8. Testing the Changes

### Test 1: Verify Cart Screen Compiles
```bash
python3 -m py_compile cart_screen.py
```

### Test 2: Verify Logger Works
```bash
python3 system_logger.py
```

### Test 3: Check Config Is Valid
```bash
python3 -c "import json; json.load(open('config.example.json')); print('OK')"
```

### Test 4: Verify Imports
```bash
python3 -c "from system_logger import SystemLogger; from cart_screen import CartScreen; print('✓ All imports OK')"
```

---

## 9. Benefits

✅ **Transparency**: Customers see real-time system status during payment
✅ **Debugging**: Detailed logs help diagnose issues
✅ **Auditing**: Transaction history for accounting
✅ **Configuration**: Logging setup similar to image configuration
✅ **Auto-Management**: Logs auto-rotate and don't fill disk
✅ **Scalable**: Easy to add new log types

---

## 10. Next Steps

1. ✅ Cart screen now shows status panel
2. ✅ Logging configuration structure added
3. ✅ system_logger.py module created and tested
4. ⏳ Integration with main.py (optional - can be done incrementally)
5. ⏳ Deploy to Raspberry Pi
6. ⏳ Monitor logs during operation

---

## Questions?

- For status panel help: See `SYSTEM_STATUS_PANEL_README.md`
- For image configuration: See `QUICK_IMAGE_GUIDE.md`
- For logger details: See `system_logger.py` docstrings
