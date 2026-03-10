# RAON Vending System Operator and Admin Manual

Version: 1.1 (2026-03-10)  
Audience: New Operators and Admins  
Scope: Daily operation of the kiosk, admin maintenance, dashboard monitoring, system status visibility, and basic troubleshooting.

## 1. System Overview

The system has two main applications:

1. `main.py`  
   Purpose: Touchscreen kiosk UI, payments, dispensing, local admin screens.
2. `web_app.py`  
   Purpose: Web dashboard for sales, stock alerts, and sensor monitoring.

Operator-visible system features:

1. System Status Panel: Real-time temperature, cooling, IR sensors, and uptime shown at the bottom of the kiosk UI.
2. Stock Monitoring: Low-stock and out-of-stock alerts shown on the dashboard.
3. Dispense Monitoring: IR-based dispense timeout alerts and dispense logging.

Important data files:

1. `config.json` - machine settings and hardware configuration.
2. `assigned_items.json` - slot-to-item assignments and stock values.
3. `logs/transactions.log` - transaction log (rotating file).
4. `logs/errors.log` - errors and warnings (rotating file).
5. `logs/dispense.log` - dispense events and IR detection (rotating file).
6. `logs/sensors.log` - temperature and TEC status (rotating file).
7. `logs/sales_YYYY-MM-DD.log` - daily sales and temperature summary log.
8. `logs/sensor_data_YYYY-MM-DD.csv` - timestamped sensor data for charts.

## 2. Roles

Operator:

1. Start and monitor the machine.
2. Assist customers if needed.
3. Refill stock and verify assigned slots.
4. Check dashboard alerts.

Admin:

1. Update item details (name, price, quantity, category, image, threshold).
2. Assign items to slots.
3. Adjust kiosk config.
4. Review and export logs.

## 3. Startup Procedure

### Option A: Service mode on Raspberry Pi (recommended)

1. Check service status:
```bash
sudo systemctl status raon-vending.service
```
2. If not running, start it:
```bash
sudo systemctl start raon-vending.service
```
3. Confirm kiosk appears on display.

### Option B: Manual start

1. Open terminal in project folder.
2. Start kiosk app:
```bash
python3 main.py
```
3. Start dashboard app (optional but recommended) in another terminal:
```bash
python3 web_app.py
```

### Dashboard access

1. Open browser.
2. Go to:
```text
http://<machine-ip>:5000/dashboard
```
3. If local:
```text
http://localhost:5000/dashboard
```

## 4. Daily Operator Flow

## 4.1 Beginning of shift checklist

1. Confirm kiosk opens to "Select Operating Mode".
2. Tap `Kiosk`.
3. Confirm "Start Order" screen appears.
4. Verify System Status Panel shows:
   1. Temperature and humidity for both sensors.
   2. TEC status (ON/OFF) and target temperature if enabled.
   3. IR sensor status (EMPTY/PRESENT).
   4. System status is "Operational."
5. Run one test vend (optional but recommended).
6. Open dashboard and confirm:
   1. Stock alerts section loads.
   2. Sales logs load.
   3. Sensor charts load for today.

## 4.2 Customer transaction flow

1. Customer taps `Start Order`.
2. Customer selects products and quantity.
3. Customer taps `Pay`.
4. Customer inserts coins/bills.
5. System dispenses item and change as needed.
6. If dispense fails, alert appears; assist customer and retry safely.

## 4.3 End of shift checklist

1. Review dashboard sales logs for today.
2. Review stock alerts and refill as needed.
3. Export logs if required by your process.
4. If shutdown is needed, follow Section 10.

## 5. Admin Screen Operations

From the first screen, tap `Admin`.

Main Admin functions:

1. `Edit` item: Update name, category, description, price, quantity, image.
   1. Update low-stock threshold (if enabled in your build).
2. `Remove` item: Delete item from catalog.
3. `Assign Slots`: Map products to vending slots and update per-slot details.
4. `Kiosk Config`: Update machine name, subtitle, logo, categories, and display settings.
5. `View Logs`: Open local log viewer and export daily logs.

Navigation:

1. Press `Esc` to return to Selection Screen.

## 6. System Status Panel (Kiosk UI)

The System Status Panel appears at the bottom of the kiosk screen and updates continuously.

What it shows:

1. Environment: DHT22 temperature and humidity readings for Sensor 1 and Sensor 2.
2. TEC Cooler: Cooling status (ON/OFF), target temperature, current temperature.
3. IR Sensors: Bin detection status for Sensor 1 and Sensor 2.
4. System: Overall status (Operational/Warning/Error) and uptime.

Common meanings:

1. Operational: All sensors responding and system running normally.
2. Warning: Minor issue (for example, high temperature but still cooling).
3. Error: Sensor failure or system fault; investigate before continued operation.

## 7. Dashboard Guide

Dashboard sections:

1. Stock Alerts
   1. `Out of Stock` and `Low Stock` counters.
   2. Audible alert plays when new/increased stock alerts appear.
   3. Alerts can be acknowledged after restocking.
2. Sales Logs
   1. Main transaction log for operation review.
   2. Includes transaction time and IR status in each entry.
3. Temperature and Humidity Logs
   1. Text summaries every 15 minutes.
   2. Shows T1/H1, T2/H2, and TEC status.
   3. IR is not shown in this section.
4. Sensor Charts
   1. Temperature and humidity chart.
   2. IR chart (from transaction-linked IR snapshots).

### Sales log format (current)

Each sales line is shown as:

```text
[HH:MM:SS] Transaction Time: MM:SS.xx | Item: <item name/qty> | Coins: <amount> | Bills: <amount> | Total: <amount> | Change: <amount> | IR Status: <status>
```

Possible IR Status values include:

1. `IR1 DETECTED, IR2 CLEAR` (sensor snapshot matched).
2. `SUCCESS` or `FAILED` (dispense result matched).
3. `N/A` (no close match found).

## 8. Sensor and IR Logging Rules

Current behavior:

1. Temperature/Humidity/TEC snapshots are logged every 15 minutes.
2. IR snapshots are logged only when a dispense transaction callback occurs.
3. Random IR changes without a transaction are ignored for transaction logs.

Operational implication:

1. IR status should be interpreted together with sales entries, not as standalone ambient events.

## 9. Troubleshooting

## 9.1 Dashboard not updating

1. Confirm `web_app.py` is running.
2. Check browser URL is correct (`:5000/dashboard`).
3. Restart web app:
```bash
python3 web_app.py
```
4. Refresh browser.

## 9.2 Serial port errors (`permission denied` or `could not open port`)

1. Ensure only one hardware owner process is running (`main.py` should own serial).
2. Stop test scripts that access the same serial port.
3. If on Linux, check user group permissions (`dialout`/`gpio`).
4. Reboot if serial lock persists.

## 9.3 No sensor data in dashboard

1. Confirm kiosk app (`main.py`) is running and receiving DHT data in terminal logs.
2. Confirm `logs/sensor_data_<today>.csv` exists.
3. Wait for the next 15-minute snapshot or perform a transaction for IR-linked entries.

## 9.4 Dispense did not complete

1. Check sales log `IR Status` and any `DISPENSE_RESULT` events in local logs.
2. Verify stock was assigned to the correct slot.
3. Run a controlled test vend from admin/test procedure.
4. Check motor/ESP32 and sensor wiring.

## 9.5 Dispense timeout popup appears

1. Confirm the item is not stuck in the slot.
2. If needed, retry a controlled vend.
3. Check IR sensors are clean and aligned.
4. Review `logs/dispense.log` for TIMEOUT entries.

## 9.6 Low stock alerts do not clear

1. After restocking, confirm the item quantity was updated in Admin.
2. Refresh the dashboard.
3. If still present, acknowledge the alert and recheck stock values.

## 10. Restart and Shutdown

Service mode:

1. Restart:
```bash
sudo systemctl restart raon-vending.service
```
2. Stop:
```bash
sudo systemctl stop raon-vending.service
```

Manual mode:

1. Stop app with `Ctrl+C` in terminal.
2. Start again with:
```bash
python3 main.py
```

System shutdown:

```bash
sudo shutdown -h now
```

## 11. Daily Recordkeeping Recommendation

At the end of each shift:

1. Save/export sales log for the date.
2. Record:
   1. Total sales.
   2. Total transactions.
   3. Out-of-stock items.
   4. Any failed dispenses.
3. Confirm refill actions were completed in Admin and reflected on dashboard.

## 12. Handover Notes for New Staff

1. Never run hardware test scripts while kiosk is actively serving customers.
2. Use `Admin` only for controlled updates.
3. Use dashboard as the main monitoring screen during operation.
4. If behavior is unusual, collect logs first before restarting.

