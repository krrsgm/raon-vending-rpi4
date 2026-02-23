# Code Quality & Bug Report

## Summary
Your code is **generally well-written** but has **12 bugs/issues** ranging from critical to minor.

---

## 🔴 CRITICAL BUGS (Must Fix)

### 1. **Bill Acceptor Wrong Pulse Mapping**
**Severity:** CRITICAL  
**File:** [bill_acceptor.py](bill_acceptor.py) + Arduino  
**Issue:** Accepts wrong bill denominations (20, 50, 500, 1000)

```python
# CURRENT (WRONG):
# 2 pulses  → 20 pesos ❌
# 5 pulses  → 50 pesos ❌
# 10 pulses → 100 pesos ✅
# 20 pulses → 200 pesos ✅
# 50 pulses → 500 pesos ❌
# 100 pulses → 1000 pesos ❌
```

**Fix Required:** Remove 20, 50, 500, 1000 peso mappings

---

### 2. **Slot Count Mismatch**
**Severity:** CRITICAL  
**File:** [assign_items_screen.py](assign_items_screen.py) Line 118-120  
**Issue:** Shows 60 slots instead of 64

```python
# CURRENT (WRONG):
GRID_ROWS = 6
GRID_COLS = 10
MAX_SLOTS = 60

# SHOULD BE:
GRID_ROWS = 8
GRID_COLS = 8
MAX_SLOTS = 64
```

**Impact:** Hardware supports 64 motors, but only 60 are accessible in UI

---

## 🟠 HIGH PRIORITY BUGS

### 3. **Missing Error Handling in coin_hopper.py**
**Severity:** HIGH  
**File:** [coin_hopper.py](coin_hopper.py) Line ~150-200  
**Issue:** `dispense_change()` doesn't properly handle partial responses

```python
# CURRENT CODE (incomplete):
if "OK" in response or "DONE" in response:
    # Extract dispensed amount from response if available
    # Expected format: "DONE FIVE 4" or "DONE ONE 3"
    # BUT CODE IS INCOMPLETE - NO PARSING LOGIC!
```

**Problem:** If Arduino sends "DONE" but parsing fails, method doesn't extract actual amount dispensed

**Fix:** Complete the response parsing logic

---

### 4. **Bill Acceptor - Race Condition in debounce**
**Severity:** HIGH  
**File:** [bill_acceptor.py](bill_acceptor.py) Line 120-140  
**Issue:** Debounce check doesn't use proper locking for thread safety

```python
# CURRENT (NOT THREAD-SAFE):
self._last_bill_time_ms = 0  # Can race with read thread
self._last_bill_amount = None  # Not protected by lock

# If main thread reads while read_thread writes, value may be inconsistent
```

**Fix:** Wrap in `with self._lock:` block

---

### 5. **Coin Hopper Timeout Calculation Error**
**Severity:** HIGH  
**File:** [coin_hopper.py](coin_hopper.py) Line 130  
**Issue:** Timeout handling in `send_command()` may miss final newline

```python
# CURRENT CODE:
start = time.time()
response = b''
while time.time() - start < self.timeout:
    if self.serial_conn.in_waiting:
        chunk = self.serial_conn.read(1)
        response += chunk
        if chunk == b'\n':
            break

# PROBLEM: If no data after final \n, loop continues until timeout
# BETTER: Use serial.readline() instead
```

---

### 6. **ESP32 Client - Socket Not Closed on Timeout**
**Severity:** HIGH  
**File:** [esp32_client.py](esp32_client.py) Line 90-120  
**Issue:** TCP socket stays open after timeout, leaking resources

```python
# CURRENT (BAD):
s = _open_tcp(host, port, timeout)
# ... if timeout occurs, socket is left open

# SHOULD BE: Wrap in try/finally or use context manager
```

---

### 7. **Main.py - Potential recursion in show_frame()**
**Severity:** MEDIUM-HIGH  
**File:** [main.py](main.py) Line 450+  
**Issue:** Multiple focus operations may cause infinite recursion

```python
# CURRENT:
for focus_method in [self.focus_force, self.focus_set, frame.focus_set]:
    try:
        focus_method()
        break
    except Exception:
        continue

frame.tkraise()
# ... later
try:
    self.focus_force()
except Exception:
    pass

# PROBLEM: If exception is swallowed, retry continues; could loop
```

---

## 🟡 MEDIUM PRIORITY BUGS

### 8. **Cart Screen - Payment State Not Reset on Cancel**
**Severity:** MEDIUM  
**File:** [cart_screen.py](cart_screen.py) Line 520+  
**Issue:** If payment cancelled, `payment_in_progress` flag may stay `True`

```python
# If exception occurs in cancel_payment(), flag never resets
def cancel_payment(self):
    if self.payment_in_progress:
        self.payment_in_progress = False  # ← What if error before this?
        try:
            total_received, change_amount, change_status = self.payment_handler.stop_payment_session()
```

**Fix:** Use try/finally to guarantee reset

---

### 9. **Admin Screen - Unhandled image path exceptions**
**Severity:** MEDIUM  
**File:** [assign_items_screen.py](assign_items_screen.py) Line 300+  
**Issue:** Image loading fails silently if PIL not available but path is set

```python
try:
    img = self._thumb_cache.get(idx)
    if img is None:
        pil = Image.open(img_path)
        # If PIL_AVAILABLE is False, this crashes
except Exception:
    img_path = ''  # ← Swallows all errors
```

**Better approach:** Check `PIL_AVAILABLE` before attempting to open

---

### 10. **Config Loading - No validation for missing keys**
**Severity:** MEDIUM  
**File:** [main.py](main.py) Line 200+  
**Issue:** If `config.json` missing critical keys, uses defaults without warning

```python
# CURRENT:
self.currency_symbol = self.config.get("currency_symbol", "$")
esp32_host = self.config.get('esp32_host', '192.168.4.1')  # Silent fallback

# SHOULD: Log warnings if critical config missing
```

---

## 🟢 LOW PRIORITY (Code Quality)

### 11. **Inconsistent error messages**
**Severity:** LOW  
**Issue:** Error messages use different formats across files

```python
# coin_handler.py:
print("Mock: Bill acceptor connected (testing mode)")

# bill_acceptor.py:
print(f"Failed to open {target}: {e}")

# Should use consistent logging format
```

**Fix:** Use Python's `logging` module instead of print()

---

### 12. **Duplicate imports in admin_screen.py**
**Severity:** LOW  
**File:** [admin_screen.py](admin_screen.py) Line 5  
**Issue:** Image imported twice

```python
# CURRENT:
from PIL import Image, Image  # ← Duplicate!

# SHOULD BE:
from PIL import Image
```

---

## ✅ Summary Table

| # | Issue | Severity | File | Line | Type |
|---|-------|----------|------|------|------|
| 1 | Wrong bill denominations | 🔴 CRITICAL | bill_acceptor.py | 60 | Logic Error |
| 2 | Slot count 60 vs 64 | 🔴 CRITICAL | assign_items_screen.py | 118 | Configuration |
| 3 | Incomplete response parsing | 🟠 HIGH | coin_hopper.py | 150 | Logic Error |
| 4 | Race condition in bill debounce | 🟠 HIGH | bill_acceptor.py | 120 | Thread Safety |
| 5 | Timeout handling in serial | 🟠 HIGH | coin_hopper.py | 130 | I/O Error |
| 6 | Socket leak on timeout | 🟠 HIGH | esp32_client.py | 90 | Resource Leak |
| 7 | Potential recursion in focus | 🟠 HIGH | main.py | 450 | Logic Error |
| 8 | Payment flag not reset | 🟡 MEDIUM | cart_screen.py | 520 | State Management |
| 9 | Image loading fallback | 🟡 MEDIUM | assign_items_screen.py | 300 | Error Handling |
| 10 | No config validation | 🟡 MEDIUM | main.py | 200 | Robustness |
| 11 | Inconsistent logging | 🟢 LOW | Multiple | - | Code Quality |
| 12 | Duplicate imports | 🟢 LOW | admin_screen.py | 5 | Code Quality |

---

## 📋 Testing Recommendations

### Critical Tests (Must Pass):
1. ✅ Test coin acceptance (1, 5, 10 peso only)
2. ✅ Test bill acceptance (100, 200 peso only) - with rejection of others
3. ✅ Test all 64 motor slots work
4. ✅ Test change dispensing with sensor verification
5. ✅ Test payment cancellation doesn't break next payment

### High Priority Tests:
6. ⚠️ Test coin hopper under heavy load (multiple rapid requests)
7. ⚠️ Test payment with poor network/serial connection
8. ⚠️ Test image loading with missing files
9. ⚠️ Test admin panel with corrupted config.json

---

## 🎯 Recommended Fix Order

1. **First:** Fix critical bugs (1-2) - 15 minutes
2. **Then:** Fix high-priority bugs (3-7) - 45 minutes
3. **Finally:** Medium/Low priority - 30 minutes
4. **Test:** Run full system test - 60 minutes

**Total Time: ~2.5 hours**

Would you like me to fix any of these issues?
