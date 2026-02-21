## ✅ Stock Monitoring & Low Stock Alerts System

### 📋 Overview

The vending machine now has a **comprehensive stock monitoring system** that:

1. **Tracks every sale** - Records items purchased with payment details
2. **Decrements stock** - Automatically updates inventory after each sale
3. **Detects low stock** - Monitors threshold levels and flags when items run low
4. **Creates alerts** - Generates warnings visible on the web dashboard
5. **Persistent storage** - Stores alerts in database for later reference

---

## 🎯 Features

### Real-time Stock Management

- **Automatic stock decrement** when items are sold
- **Configurable thresholds** per item (default: 3 units)
- **Out-of-stock detection** when quantity reaches 0
- **Daily alert tracking** - prevents duplicate alerts for same item

### Low Stock Alerts

The dashboard displays alerts with:
- **🟡 Warning Level:** When stock ≤ threshold (e.g., ≤ 3 units)
- **🔴 Critical Level:** When stock = 0 (out of stock)
- **Timestamp:** When alert was triggered
- **Acknowledge button:** To dismiss alerts after restocking

### Web Dashboard Features

```
Top bar shows: "Low Stock Alerts: 3" (red counter)
Alerts section displays:
├── ⚠️ LOW STOCK: Resistor
│   ├── Quantity: 2 (Threshold: 3)
│   ├── Detected: 2/21/2026 2:45 PM
│   └── [Acknowledge button]
├── ❌ OUT OF STOCK: Capacitor
│   ├── Quantity: 0 (Threshold: 3)
│   ├── Detected: 2/21/2026 1:30 PM
│   └── [Acknowledge button]
└── ⚠️ LOW STOCK: IC Chip
    └── ...
```

---

## 🔧 Integration with Kiosk

### Using StockTracker in cart_screen.py

```python
from stock_tracker import get_tracker

class CartScreen(tk.Frame):
    def __init__(self, parent, controller):
        # ...
        self.stock_tracker = get_tracker(
            host='localhost',  # or IP of web_app server
            port=5000,
            machine_id='RAON-001'
        )
    
    def complete_payment(self):
        # After vending items, record sale:
        result = self.stock_tracker.record_sale(
            item_name='Resistor 10K',
            quantity=1,
            coin_amount=5.00,
            bill_amount=0.0,
            change_dispensed=0.00
        )
        
        if result['alert']:
            # Display alert to user
            print(f"⚠️ {result['alert']['message']}")
            messagebox.showwarning('Stock Alert', result['alert']['message'])
```

### API Endpoints

#### Record Sale & Update Stock
```
POST /api/sales/record

Request:
{
  "machine_id": "RAON-001",
  "item_name": "Resistor 10K",
  "quantity": 1,
  "amount_received": 5.00,
  "coin_amount": 5.00,
  "bill_amount": 0.0,
  "change_dispensed": 0.00
}

Response:
{
  "success": true,
  "sale_id": 42,
  "item_name": "Resistor 10K",
  "new_quantity": 2,
  "low_stock_alert": {
    "created": true,
    "type": "low_stock",
    "message": "⚠️ Resistor 10K is now LOW STOCK! Only 2 left!"
  }
}
```

#### Get Active Alerts
```
GET /api/low-stock-alerts?machine_id=RAON-001

Response:
{
  "alerts": [
    {
      "id": 1,
      "item_name": "Resistor 10K",
      "current_quantity": 2,
      "threshold": 3,
      "alert_type": "low_stock",
      "timestamp": "2026-02-21T14:45:00",
      "severity": "warning"
    },
    {
      "id": 2,
      "item_name": "Capacitor",
      "current_quantity": 0,
      "threshold": 3,
      "alert_type": "out_of_stock",
      "timestamp": "2026-02-21T13:30:00",
      "severity": "critical"
    }
  ],
  "total_active_alerts": 2
}
```

#### Acknowledge Alert
```
POST /api/low-stock-alerts/42/acknowledge

Response:
{
  "success": true,
  "message": "Alert for Resistor 10K acknowledged"
}
```

---

## 📊 Database Models

### LowStockAlert Table

Stores all low stock alerts with:
- `id` - Primary key
- `machine_id` - Machine reference
- `item_id` - Item reference
- `item_name` - Item name (denormalized for quick access)
- `current_quantity` - Stock level when alert triggered
- `threshold` - Low stock threshold
- `alert_type` - "low_stock" or "out_of_stock"
- `timestamp` - When alert was created
- `acknowledged` - Boolean flag for dismissal

### Sale Table (Enhanced)

Now tracks complete transaction with:
- `id` - Primary key
- `machine_id` - Machine reference
- `item_name` - Item sold
- `quantity` - How many sold
- `amount_received` - Total payment
- `coin_amount` - Cash from coins
- `bill_amount` - Cash from bills
- `change_dispensed` - Change given
- `timestamp` - Transaction time

### Item Table (Enhanced)

Now has low stock tracking:
- `quantity` - Current stock
- `low_stock_threshold` - Alert threshold (default: 3)

---

## ⚙️ Configuration

### Set Low Stock Threshold

Via web dashboard (future feature) or direct database:

```python
from web_app import Item, db

item = Item.query.filter_by(name='Resistor 10K').first()
item.low_stock_threshold = 5  # Alert when <= 5 units
db.session.commit()
```

### Machine Configuration

In `config.json`:
```json
{
  "esp32_host": "192.168.4.1",
  "web_app_host": "localhost",
  "web_app_port": 5000,
  "machine_id": "RAON-001",
  "default_low_stock_threshold": 3
}
```

---

## 🎨 Dashboard Display

### Alert Section (New)
- Shows at top of dashboard
- Red background with alert icons
- Lists all unacknowledged alerts
- One-click acknowledge buttons
- Updates every 5 seconds

### Stats Card
- "Low Stock Alerts" counter shows total active
- Updates in real-time
- Color changes when alerts present

### Machine Cards
- Still show low stock items list
- Now linked to detailed alert info
- Click item name to see alert history

---

## 📝 Example Flow

### Scenario: Customer buys last Resistor

1. **KioskFrame**: Customer selects "Resistor - Qty: 3"
2. **CartScreen**: Shows cart with resistor
3. **Payment**: Coins/bills accepted, motor vends item
4. **Complete**: Calls `stock_tracker.record_sale(...)`
5. **Web API**: 
   - Creates Sale record
   - Updates Item: quantity 3 → 2
   - Detects: 2 ≤ 3 (threshold)
   - Creates LowStockAlert
   - Returns alert message
6. **Kiosk**: Shows popup: "⚠️ Resistor is now LOW STOCK! Only 2 left!"
7. **Dashboard**: 
   - Refreshes alert (5-sec interval)
   - Shows "Low Stock Alerts: 1" badge
   - Displays alert: "⚠️ LOW STOCK: Resistor - Qty: 2"
   - Manager can click "Acknowledge" to dismiss

---

## 🚀 Getting Started

### 1. Install Dependencies

```bash
pip install requests  # For stock_tracker.py
```

### 2. Database Migration

```python
from web_app import db, create_app_with_db
app = create_app_with_db()  # Creates LowStockAlert table
```

### 3. Initialize Stock Levels

```python
from web_app import db, Item, Machine

# Set thresholds and quantities
machine = Machine.query.first()
for item in machine.items:
    item.quantity = 10  # Starting stock
    item.low_stock_threshold = 3  # Alert at 3 or less
db.session.commit()
```

### 4. Use in Kiosk

```python
from stock_tracker import get_tracker

tracker = get_tracker()
result = tracker.record_sale('Item Name', quantity=1, coin_amount=5.0)
if result['alert']:
    show_alert(result['alert']['message'])
```

---

## 🔍 Troubleshooting

### Alerts Not Showing
- Check web_app is running: `curl http://localhost:5000/api/machines`
- Verify machine_id matches config
- Check database: `SELECT * FROM low_stock_alert;`

### Stock Not Updating
- Verify record_sale() is being called
- Check API response for errors
- Ensure web_app database has write access

### Duplicate Alerts
- System prevents duplicates within 24 hours
- Clear acknowledge flag to re-alert: `UPDATE low_stock_alert SET acknowledged=0`

---

## 📚 Related Files

- `web_app.py` - Main API server with alert endpoints
- `stock_tracker.py` - Kiosk-side integration client
- `templates/dashboard.html` - Alert display UI
- `daily_sales_logger.py` - Transaction logging

---

**Last Updated:** Feb 21, 2026  
**Version:** 1.0
