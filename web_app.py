"""
web_app.py - Flask web application replacing Tkinter UI for RAON Vending Machine.
Provides:
  - Kiosk UI (item selection, payment, vending)
  - Multi-machine inventory dashboard
  - API for payment/vending control integration
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from datetime import datetime, timedelta
import json
import os
import sys
import time
from threading import Thread, Lock
import logging

# Add parent directory to path so we can import existing modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import existing vending modules (unchanged)
try:
    from esp32_client import pulse_slot
    from payment_handler import PaymentHandler
    from fix_paths import get_absolute_path
    from daily_sales_logger import get_logger
except ImportError as e:
    print(f"Warning: Could not import vending modules: {e}")
    pulse_slot = None
    PaymentHandler = None
    get_logger = None

# Flask setup
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'dev-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///vending_machine.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
logger = logging.getLogger(__name__)

# ============================================================================
# DATABASE MODELS
# ============================================================================

class Machine(db.Model):
    """Represents a vending machine."""
    id = db.Column(db.Integer, primary_key=True)
    machine_id = db.Column(db.String(50), unique=True, nullable=False)  # e.g., 'RAON-001'
    name = db.Column(db.String(100), nullable=False)
    esp32_host = db.Column(db.String(100), nullable=False)  # IP or serial://...
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    items = db.relationship('Item', backref='machine', lazy=True, cascade='all, delete-orphan')
    sales = db.relationship('Sale', backref='machine', lazy=True, cascade='all, delete-orphan')


class Item(db.Model):
    """Represents an item in a vending machine."""
    id = db.Column(db.Integer, primary_key=True)
    machine_id = db.Column(db.Integer, db.ForeignKey('machine.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, default=0)  # Current stock
    slots = db.Column(db.String(255), default='')  # Comma-separated slot numbers
    image_url = db.Column(db.String(255), default='')
    category = db.Column(db.String(50), default='')
    description = db.Column(db.String(255), default='')
    low_stock_threshold = db.Column(db.Integer, default=3)


class Sale(db.Model):
    """Represents a sale transaction."""
    id = db.Column(db.Integer, primary_key=True)
    machine_id = db.Column(db.Integer, db.ForeignKey('machine.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=True)
    item_name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    amount_received = db.Column(db.Float, nullable=False)
    coin_amount = db.Column(db.Float, default=0.0)
    bill_amount = db.Column(db.Float, default=0.0)
    change_dispensed = db.Column(db.Float, default=0.0)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class LowStockAlert(db.Model):
    """Represents a low stock warning alert."""
    id = db.Column(db.Integer, primary_key=True)
    machine_id = db.Column(db.Integer, db.ForeignKey('machine.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    item_name = db.Column(db.String(100), nullable=False)
    current_quantity = db.Column(db.Integer, nullable=False)
    threshold = db.Column(db.Integer, nullable=False)
    alert_type = db.Column(db.String(50), default='low_stock')  # 'low_stock', 'out_of_stock'
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    acknowledged = db.Column(db.Boolean, default=False)


# ============================================================================
# GLOBAL STATE & PAYMENT HANDLER
# ============================================================================

payment_handler = None
payment_lock = Lock()
current_payment_session = {
    'in_progress': False,
    'required_amount': 0.0,
    'received_amount': 0.0,
    'items': []
}


def should_init_payment_handler(config):
    """Web app must never own payment hardware; main.py is the hardware owner."""
    return False


def init_payment_handler(config):
    """Initialize the payment handler with config."""
    global payment_handler
    try:
        if PaymentHandler:
            coin_cfg = config.get('hardware', {}).get('coin_acceptor', {}) if isinstance(config, dict) else {}
            payment_handler = PaymentHandler(
                config=config,
                use_gpio_coin=bool(coin_cfg.get('use_gpio', False)),
                coin_gpio_pin=coin_cfg.get('gpio_pin', 17)
            )
            logger.info("Payment handler initialized")
            return True
    except Exception as e:
        logger.error(f"Failed to initialize payment handler: {e}")
    return False


# ============================================================================
# ROUTES - KIOSK UI
# ============================================================================

@app.route('/')
def home():
    """Redirect to dashboard."""
    return redirect(url_for('inventory_dashboard'))


# ============================================================================
# ROUTES - DASHBOARD & MONITORING
# ============================================================================

def _filter_dashboard_sales_logs(raw_lines):
    """Keep only sales/payment log entries for dashboard logs view."""
    if not raw_lines:
        return []

    excluded_markers = (
        'temperature',
        'dht',
        'tec',
        'relay',
        'ir sensor',
        'ir1',
        'ir2',
        'sensor',
    )
    included_markers = (
        'sale',
        'sold',
        'payment',
        'coin',
        'bill',
        'change',
        'transaction',
    )

    filtered = []
    for line in raw_lines:
        text = str(line).strip()
        if not text:
            continue

        lower = text.lower()
        if any(marker in lower for marker in excluded_markers):
            continue
        if any(marker in lower for marker in included_markers):
            filtered.append(line)

    return filtered


def _resolve_sale_item_name(sale):
    """Resolve display name for a sale row, preferring persisted sale.item_name."""
    placeholder_names = {
        'unknown',
        'unknown item',
        'n/a',
        'na',
        'none',
        'null',
        '-',
        '--',
    }

    try:
        if getattr(sale, 'item_name', None):
            name = str(sale.item_name).strip()
            if name and name.lower() not in placeholder_names:
                return name
    except Exception:
        pass

    try:
        if getattr(sale, 'item_id', None):
            item = Item.query.get(sale.item_id)
            if item and item.name:
                return item.name
    except Exception:
        pass

    return "Unknown Item"


# ============================================================================
# ROUTES - INVENTORY DASHBOARD (Multi-Machine)
# ============================================================================

@app.route('/dashboard')
def inventory_dashboard():
    """Inventory dashboard for all machines."""
    machines = Machine.query.filter_by(is_active=True).all()
    
    dashboard_data = []
    for machine in machines:
        items = Item.query.filter_by(machine_id=machine.id).all()
        low_stock_items = [i for i in items if i.quantity <= i.low_stock_threshold]
        
        recent_sales = Sale.query.filter_by(machine_id=machine.id)\
            .order_by(Sale.timestamp.desc()).limit(10).all()
        
        total_sales_today = db.session.query(func.sum(Sale.coin_amount + Sale.bill_amount))\
            .filter_by(machine_id=machine.id)\
            .filter(Sale.timestamp > datetime.utcnow() - timedelta(hours=24)).scalar() or 0.0
        
        dashboard_data.append({
            'machine': machine,
            'items': items,
            'low_stock': low_stock_items,
            'recent_sales': recent_sales,
            'total_sales_today': total_sales_today
        })
    
    return render_template('dashboard.html', machines_data=dashboard_data, currency='₱')


@app.route('/api/sales/today')
def api_sales_today():
    """API: Get today's sales summary from logs."""
    try:
        logger_inst = get_logger() if get_logger else None
        if not logger_inst:
            return jsonify({'error': 'Logger not available'}), 500
        
        summary = logger_inst.get_today_summary()
        items_sold = logger_inst.get_items_sold_summary()
        
        return jsonify({
            'date': summary['date'],
            'total_transactions': summary['total_transactions'],
            'total_sales': summary['total_sales'],
            'total_coins': summary['total_coins'],
            'total_bills': summary['total_bills'],
            'total_change': summary['total_change'],
            'items_sold': items_sold
        }), 200
    except Exception as e:
        logger.error(f"Sales today error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/sales/logs')
def api_sales_logs():
    """API: Get sales logs for a specific date (default today)."""
    try:
        logger_inst = get_logger() if get_logger else None
        if not logger_inst:
            return jsonify({'error': 'Logger not available'}), 500
        
        from datetime import datetime as dt
        date_str = request.args.get('date', dt.now().strftime("%Y-%m-%d"))
        logs_dir = logger_inst.logs_dir
        log_file = os.path.join(logs_dir, f"sales_{date_str}.log")
        
        if not os.path.exists(log_file):
            return jsonify({'logs': [], 'date': date_str}), 200
        
        logs = []
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                logs = _filter_dashboard_sales_logs(f.readlines())
        except Exception as e:
            logger.error(f"Error reading log file: {e}")
        
        return jsonify({
            'logs': logs,
            'date': date_str,
            'count': len(logs)
        }), 200
    except Exception as e:
        logger.error(f"Sales logs error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/sales/previous-day')
def api_sales_previous_day():
    """API: Get sales logs from the previous day."""
    try:
        logger_inst = get_logger() if get_logger else None
        if not logger_inst:
            return jsonify({'error': 'Logger not available'}), 500
        
        from datetime import datetime as dt
        yesterday = (dt.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        logs_dir = logger_inst.logs_dir
        log_file = os.path.join(logs_dir, f"sales_{yesterday}.log")
        
        if not os.path.exists(log_file):
            return jsonify({'logs': [], 'date': yesterday, 'summary': {
                'total_transactions': 0,
                'total_sales': 0.0,
                'total_coins': 0.0,
                'total_bills': 0.0,
                'items_sold': {}
            }}), 200
        
        logs = []
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                logs = _filter_dashboard_sales_logs(f.readlines())
        except Exception as e:
            logger.error(f"Error reading log file: {e}")
        
        # Try to get summary for previous day
        summary = {
            'total_transactions': len(logs),
            'total_sales': 0.0,
            'total_coins': 0.0,
            'total_bills': 0.0,
            'items_sold': {}
        }
        
        return jsonify({
            'logs': logs,
            'date': yesterday,
            'count': len(logs),
            'summary': summary
        }), 200
    except Exception as e:
        logger.error(f"Previous day sales error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/sensor-readings')
def api_sensor_readings():
    """API: Get sensor readings for a specific date (default today)."""
    try:
        from datetime import datetime as dt
        date_str = request.args.get('date', dt.now().strftime("%Y-%m-%d"))
        
        # Try to find sensor data logger
        sensor_log_dir = 'logs'  # Default logs directory
        sensor_log_file = os.path.join(sensor_log_dir, f"sensor_data_{date_str}.csv")
        
        if not os.path.exists(sensor_log_file):
            return jsonify({
                'readings': [],
                'date': date_str,
                'stats': {
                    'avg_temp1': 0,
                    'avg_temp2': 0,
                    'avg_humidity1': 0,
                    'avg_humidity2': 0
                }
            }), 200
        
        readings = []
        temps1, temps2, humidity1, humidity2 = [], [], [], []
        
        try:
            import csv
            with open(sensor_log_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    reading = {
                        'timestamp': row.get('DateTime', row.get('Timestamp', '')),
                        'temp1': float(row.get('Sensor1_Temp_C', 0)) if row.get('Sensor1_Temp_C') else None,
                        'humidity1': float(row.get('Sensor1_Humidity_Pct', 0)) if row.get('Sensor1_Humidity_Pct') else None,
                        'temp2': float(row.get('Sensor2_Temp_C', 0)) if row.get('Sensor2_Temp_C') else None,
                        'humidity2': float(row.get('Sensor2_Humidity_Pct', 0)) if row.get('Sensor2_Humidity_Pct') else None,
                        'ir1': row.get('IR_Sensor1_Detection', ''),
                        'ir2': row.get('IR_Sensor2_Detection', ''),
                        'relay': row.get('Relay_Status', ''),
                        'target_temp': float(row.get('Target_Temp_C', 0)) if row.get('Target_Temp_C') else None
                    }
                    readings.append(reading)
                    
                    # Collect stats
                    if reading['temp1'] is not None:
                        temps1.append(reading['temp1'])
                    if reading['temp2'] is not None:
                        temps2.append(reading['temp2'])
                    if reading['humidity1'] is not None:
                        humidity1.append(reading['humidity1'])
                    if reading['humidity2'] is not None:
                        humidity2.append(reading['humidity2'])
        except Exception as e:
            logger.error(f"Error reading sensor log file: {e}")
        
        # Calculate averages
        stats = {
            'avg_temp1': sum(temps1) / len(temps1) if temps1 else 0,
            'avg_temp2': sum(temps2) / len(temps2) if temps2 else 0,
            'avg_humidity1': sum(humidity1) / len(humidity1) if humidity1 else 0,
            'avg_humidity2': sum(humidity2) / len(humidity2) if humidity2 else 0,
            'readings_count': len(readings)
        }
        
        return jsonify({
            'readings': readings,
            'date': date_str,
            'stats': stats
        }), 200
    except Exception as e:
        logger.error(f"Sensor readings error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/sensor-readings/previous-day')
def api_sensor_readings_previous_day():
    """API: Get sensor readings from the previous day."""
    try:
        from datetime import datetime as dt
        yesterday = (dt.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        
        # Try to find sensor data logger
        sensor_log_dir = 'logs'  # Default logs directory
        sensor_log_file = os.path.join(sensor_log_dir, f"sensor_data_{yesterday}.csv")
        
        if not os.path.exists(sensor_log_file):
            return jsonify({
                'readings': [],
                'date': yesterday,
                'stats': {
                    'avg_temp1': 0,
                    'avg_temp2': 0,
                    'avg_humidity1': 0,
                    'avg_humidity2': 0
                }
            }), 200
        
        readings = []
        temps1, temps2, humidity1, humidity2 = [], [], [], []
        
        try:
            import csv
            with open(sensor_log_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    reading = {
                        'timestamp': row.get('DateTime', row.get('Timestamp', '')),
                        'temp1': float(row.get('Sensor1_Temp_C', 0)) if row.get('Sensor1_Temp_C') else None,
                        'humidity1': float(row.get('Sensor1_Humidity_Pct', 0)) if row.get('Sensor1_Humidity_Pct') else None,
                        'temp2': float(row.get('Sensor2_Temp_C', 0)) if row.get('Sensor2_Temp_C') else None,
                        'humidity2': float(row.get('Sensor2_Humidity_Pct', 0)) if row.get('Sensor2_Humidity_Pct') else None,
                        'ir1': row.get('IR_Sensor1_Detection', ''),
                        'ir2': row.get('IR_Sensor2_Detection', ''),
                        'relay': row.get('Relay_Status', ''),
                        'target_temp': float(row.get('Target_Temp_C', 0)) if row.get('Target_Temp_C') else None
                    }
                    readings.append(reading)
                    
                    # Collect stats
                    if reading['temp1'] is not None:
                        temps1.append(reading['temp1'])
                    if reading['temp2'] is not None:
                        temps2.append(reading['temp2'])
                    if reading['humidity1'] is not None:
                        humidity1.append(reading['humidity1'])
                    if reading['humidity2'] is not None:
                        humidity2.append(reading['humidity2'])
        except Exception as e:
            logger.error(f"Error reading sensor log file: {e}")
        
        # Calculate averages
        stats = {
            'avg_temp1': sum(temps1) / len(temps1) if temps1 else 0,
            'avg_temp2': sum(temps2) / len(temps2) if temps2 else 0,
            'avg_humidity1': sum(humidity1) / len(humidity1) if humidity1 else 0,
            'avg_humidity2': sum(humidity2) / len(humidity2) if humidity2 else 0,
            'readings_count': len(readings)
        }
        
        return jsonify({
            'readings': readings,
            'date': yesterday,
            'stats': stats
        }), 200
    except Exception as e:
        logger.error(f"Previous day sensor readings error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/stock-alerts')
def api_stock_alerts():
    """API: Get active stock alerts (low stock and out of stock items)."""
    try:
        alerts = []
        machines = Machine.query.filter_by(is_active=True).all()
        assigned_items = aggregate_assigned_inventory()

        for machine in machines:
            for item in assigned_items:
                qty = item.get('quantity', 0)
                threshold = item.get('threshold', 0)
                alert_type = None

                if qty <= 0:
                    alert_type = 'out_of_stock'
                elif threshold and qty <= threshold:
                    alert_type = 'low_stock'
                
                if not alert_type:
                    continue

                alerts.append({
                    'machine_id': machine.machine_id,
                    'machine_name': machine.name,
                    'item_id': None,
                    'item_name': item.get('name'),
                    'category': item.get('category', ''),
                    'current_quantity': qty,
                    'threshold': threshold,
                    'price': item.get('price', 0.0),
                    'slots': ','.join(str(s) for s in item.get('slots', [])),
                    'alert_type': alert_type,
                    'timestamp': datetime.utcnow().isoformat()
                })
        
        # Sort by alert type (out_of_stock first) then by machine and item name
        alerts.sort(key=lambda x: (0 if x['alert_type'] == 'out_of_stock' else 1, x['machine_id'], x['item_name']))
        
        return jsonify({
            'alerts': alerts,
            'total_critical': sum(1 for a in alerts if a['alert_type'] == 'out_of_stock'),
            'total_warning': sum(1 for a in alerts if a['alert_type'] == 'low_stock'),
            'timestamp': datetime.utcnow().isoformat()
        }), 200
    except Exception as e:
        logger.error(f"Stock alerts error: {e}")
        return jsonify({'error': str(e), 'alerts': []}), 200


@app.route('/api/status/realtime')
def api_realtime_status():
    """API: Get real-time machine status (stock, sales, connectivity)."""
    try:
        machines = Machine.query.filter_by(is_active=True).all()
        status_data = []
        
        logger_inst = get_logger() if get_logger else None
        today_summary = logger_inst.get_today_summary() if logger_inst else {}
        today_items = logger_inst.get_items_sold_summary() if logger_inst else {}
        
        for m in machines:
            items = Item.query.filter_by(machine_id=m.id).all()
            low_stock = [i for i in items if i.quantity <= i.low_stock_threshold]
            
            status_data.append({
                'machine_id': m.machine_id,
                'name': m.name,
                'is_active': m.is_active,
                'total_items': len(items),
                'low_stock_count': len(low_stock),
                'low_stock_items': [i.name for i in low_stock],
                'today_transactions': today_summary.get('total_transactions', 0),
                'today_sales': today_summary.get('total_sales', 0.0),
                'items_sold_today': today_items
            })
        
        return jsonify(status_data), 200
    except Exception as e:
        logger.error(f"Realtime status error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/machines')
def api_machines():
    """API: List all machines with status."""
    machines = Machine.query.filter_by(is_active=True).all()
    data = []
    for m in machines:
        items = Item.query.filter_by(machine_id=m.id).all()
        low_stock = sum(1 for i in items if i.quantity <= i.low_stock_threshold)
        data.append({
            'id': m.machine_id,
            'name': m.name,
            'last_seen': m.last_seen.isoformat(),
            'items_count': len(items),
            'low_stock_count': low_stock,
            'esp32_host': m.esp32_host
        })
    return jsonify(data), 200


@app.route('/api/machines/<machine_id>/items')
def api_machine_items(machine_id):
    """API: Get items for a specific machine."""
    machine = Machine.query.filter_by(machine_id=machine_id).first()
    if not machine:
        return jsonify({'error': 'Not found'}), 404
    
    items = Item.query.filter_by(machine_id=machine.id).all()
    data = [{
        'name': i.name,
        'price': i.price,
        'quantity': i.quantity,
        'category': i.category,
        'image_url': i.image_url,
        'low_stock_threshold': i.low_stock_threshold
    } for i in items]
    
    return jsonify(data), 200


@app.route('/api/machines/<machine_id>/items/<item_name>/restock', methods=['POST'])
def api_restock_item(machine_id, item_name):
    """API: Update item quantity (for restocking)."""
    try:
        data = request.get_json()
        quantity = data.get('quantity', 0)
        
        machine = Machine.query.filter_by(machine_id=machine_id).first()
        item = Item.query.filter_by(machine_id=machine.id, name=item_name).first()
        
        if not item:
            return jsonify({'error': 'Item not found'}), 404
        
        item.quantity = quantity
        machine.last_seen = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'success': True, 'new_quantity': item.quantity}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/sales/record', methods=['POST'])
def api_record_sale():
    """API: Record a sale, decrement stock, and check for low stock."""
    try:
        data = request.get_json()
        machine_id = data.get('machine_id', 'RAON-001')
        item_name = data.get('item_name')
        quantity = data.get('quantity', 1)
        amount_received = data.get('amount_received', 0.0)
        coin_amount = data.get('coin_amount', 0.0)
        bill_amount = data.get('bill_amount', 0.0)
        change_dispensed = data.get('change_dispensed', 0.0)
        
        machine = Machine.query.filter_by(machine_id=machine_id).first()
        if not machine:
            return jsonify({'error': 'Machine not found'}), 404
        
        item = Item.query.filter_by(machine_id=machine.id, name=item_name).first()
        if not item:
            return jsonify({'error': 'Item not found'}), 404
        
        # Create sale record
        sale = Sale(
            machine_id=machine.id,
            item_id=item.id,
            item_name=item_name,
            quantity=quantity,
            amount_received=amount_received,
            coin_amount=coin_amount,
            bill_amount=bill_amount,
            change_dispensed=change_dispensed,
            timestamp=datetime.utcnow()
        )
        db.session.add(sale)
        
        # Decrement stock
        item.quantity = max(0, item.quantity - quantity)
        machine.last_seen = datetime.utcnow()
        db.session.commit()
        
        # Check for low stock and create alert if needed
        alert_created = False
        alert_type = 'low_stock'
        
        if item.quantity == 0:
            alert_type = 'out_of_stock'
        
        if item.quantity <= item.low_stock_threshold:
            # Check if alert already exists for this item today
            existing_alert = LowStockAlert.query.filter_by(
                machine_id=machine.id,
                item_id=item.id,
                alert_type=alert_type,
                acknowledged=False
            ).filter(
                LowStockAlert.timestamp > datetime.utcnow() - timedelta(hours=24)
            ).first()
            
            if not existing_alert:
                alert = LowStockAlert(
                    machine_id=machine.id,
                    item_id=item.id,
                    item_name=item_name,
                    current_quantity=item.quantity,
                    threshold=item.low_stock_threshold,
                    alert_type=alert_type,
                    timestamp=datetime.utcnow(),
                    acknowledged=False
                )
                db.session.add(alert)
                db.session.commit()
                alert_created = True
        
        return jsonify({
            'success': True,
            'sale_id': sale.id,
            'item_name': item_name,
            'new_quantity': item.quantity,
            'low_stock_alert': {
                'created': alert_created,
                'type': alert_type if alert_created else None,
                'message': f'⚠️ {item_name} is now LOW STOCK! Only {item.quantity} left!' if item.quantity > 0 and alert_created else f'❌ {item_name} is OUT OF STOCK!' if alert_created else None
            }
        }), 200
    except Exception as e:
        logger.error(f"Record sale error: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/api/low-stock-alerts')
def api_low_stock_alerts():
    """API: Get all unacknowledged low stock alerts."""
    try:
        machine_id = request.args.get('machine_id', 'RAON-001')
        
        machine = Machine.query.filter_by(machine_id=machine_id).first()
        if not machine:
            return jsonify({'alerts': []}), 200

        # Ensure alerts exist for any currently low/out-of-stock items
        try:
            items = Item.query.filter_by(machine_id=machine.id).all()
            for item in items:
                if item.quantity <= 0:
                    alert_type = 'out_of_stock'
                elif item.quantity <= item.low_stock_threshold:
                    alert_type = 'low_stock'
                else:
                    continue

                existing_alert = LowStockAlert.query.filter_by(
                    machine_id=machine.id,
                    item_id=item.id,
                    alert_type=alert_type,
                    acknowledged=False
                ).filter(
                    LowStockAlert.timestamp > datetime.utcnow() - timedelta(days=7)
                ).first()

                if not existing_alert:
                    alert = LowStockAlert(
                        machine_id=machine.id,
                        item_id=item.id,
                        item_name=item.name,
                        current_quantity=item.quantity,
                        threshold=item.low_stock_threshold,
                        alert_type=alert_type,
                        timestamp=datetime.utcnow(),
                        acknowledged=False
                    )
                    db.session.add(alert)
            db.session.commit()
        except Exception as e:
            logger.error(f"Low stock alert sync error: {e}")
            db.session.rollback()
        
        # Get unacknowledged alerts from last 7 days
        alerts = LowStockAlert.query.filter_by(
            machine_id=machine.id,
            acknowledged=False
        ).filter(
            LowStockAlert.timestamp > datetime.utcnow() - timedelta(days=7)
        ).order_by(LowStockAlert.timestamp.desc()).all()
        
        alert_list = []
        for alert in alerts:
            alert_list.append({
                'id': alert.id,
                'item_name': alert.item_name,
                'current_quantity': alert.current_quantity,
                'threshold': alert.threshold,
                'alert_type': alert.alert_type,
                'timestamp': alert.timestamp.isoformat(),
                'severity': 'critical' if alert.alert_type == 'out_of_stock' else 'warning'
            })
        
        return jsonify({
            'alerts': alert_list,
            'total_active_alerts': len(alert_list)
        }), 200
    except Exception as e:
        logger.error(f"Low stock alerts error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/low-stock-alerts/<int:alert_id>/acknowledge', methods=['POST'])
def api_acknowledge_alert(alert_id):
    """API: Mark a low stock alert as acknowledged."""
    try:
        alert = LowStockAlert.query.filter_by(id=alert_id).first()
        if not alert:
            return jsonify({'error': 'Alert not found'}), 404
        
        alert.acknowledged = True
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Alert for {alert.item_name} acknowledged'
        }), 200
    except Exception as e:
        logger.error(f"Acknowledge alert error: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# DASHBOARD API ENDPOINTS
# ============================================================================

@app.route('/api/status/realtime')
def get_realtime_status():
    """Get real-time status for all machines"""
    try:
        machines = Machine.query.all()
        result = []
        assigned_inventory = aggregate_assigned_inventory()
        total_items_available = sum(item.get('quantity', 0) for item in assigned_inventory)
        low_stock_entries = []
        for item in assigned_inventory:
            qty = item.get('quantity', 0)
            threshold = item.get('threshold', 0)
            if qty <= 0:
                low_stock_entries.append(item.get('name'))
            elif threshold and qty <= threshold:
                low_stock_entries.append(item.get('name'))
        
        for machine in machines:
            items = Item.query.filter_by(machine_id=machine.id).all()
            
            # Calculate low stock items
            # Calculate today's sales
            today = datetime.date.today()
            today_sales_sum = db.session.query(func.sum(Sale.coin_amount + Sale.bill_amount)).filter(
                Sale.item_id.in_([i.id for i in items]),
                func.date(Sale.timestamp) == today
            ).scalar() or 0.0
            
            # Count items sold today
            items_sold_today = {}
            sales = Sale.query.filter(
                Sale.machine_id == machine.id,
                func.date(Sale.timestamp) == today
            ).all()
            
            for sale in sales:
                item_name = _resolve_sale_item_name(sale)
                qty = sale.quantity if getattr(sale, 'quantity', None) and sale.quantity > 0 else 1
                items_sold_today[item_name] = items_sold_today.get(item_name, 0) + qty
            
            result.append({
                "id": machine.id,
                "name": machine.name,
                "is_active": True,
                "total_items": total_items_available,
                "today_sales": today_sales_sum,
                "low_stock_count": len(low_stock_entries),
                "low_stock_items": low_stock_entries,
                "items_sold_today": items_sold_today
            })
        
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Error getting realtime status: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/sales/today')
def get_today_sales():
    """Get today's sales summary"""
    try:
        today = datetime.date.today()
        sales = Sale.query.filter(func.date(Sale.timestamp) == today).all()
        
        total_sales = sum(s.coin_amount + s.bill_amount for s in sales)
        total_transactions = len(sales)
        items_sold = {}
        
        for sale in sales:
            item_name = _resolve_sale_item_name(sale)
            qty = sale.quantity if getattr(sale, 'quantity', None) and sale.quantity > 0 else 1
            items_sold[item_name] = items_sold.get(item_name, 0) + qty
        
        return jsonify({
            "total_sales": total_sales,
            "total_transactions": total_transactions,
            "items_sold": items_sold
        }), 200
    except Exception as e:
        logger.error(f"Error getting today's sales: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/sales/logs')
def get_sales_logs():
    """Get today's sales logs"""
    try:
        today = datetime.date.today()
        sales = Sale.query.filter(func.date(Sale.timestamp) == today).order_by(Sale.timestamp.desc()).limit(100).all()
        
        logs = []
        for sale in sales:
            # Use item_name directly, or fallback to database lookup if item_id exists
            item_name = sale.item_name
            if not item_name and sale.item_id:
                item = Item.query.get(sale.item_id)
                if item:
                    item_name = item.name
            
            if item_name:
                amount = sale.coin_amount + sale.bill_amount
                qty = sale.quantity if sale.quantity > 1 else ''
                qty_text = f" x{qty}" if qty else ''
                logs.append(f"[{sale.timestamp.strftime('%H:%M:%S')}] {item_name}{qty_text} - ₱{amount:.2f}")
        
        return jsonify({"logs": logs}), 200
    except Exception as e:
        logger.error(f"Error getting sales logs: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================================================
# ADMIN INITIALIZATION
# ============================================================================

def load_config():
    """Load config from config.json."""
    try:
        config_path = get_absolute_path('config.json') if get_absolute_path else 'config.json'
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load config: {e}")
        return {'esp32_host': '192.168.4.1'}


def load_assigned_items():
    """Load items from assigned_items.json."""
    try:
        path = get_absolute_path('assigned_items.json') if get_absolute_path else 'assigned_items.json'
        with open(path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load assigned items: {e}")
        return {}


def _safe_int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _extract_slots_from_assigned(assigned_data):
    if isinstance(assigned_data, list):
        return assigned_data
    if not isinstance(assigned_data, dict):
        return []

    for key in ('slots', 'data', 'items', 'assigned'):
        maybe = assigned_data.get(key)
        if isinstance(maybe, list):
            return maybe

    if 'terms' in assigned_data:
        return [assigned_data]

    return []


def _select_term_entry(slot_data, term_idx=0):
    if not isinstance(slot_data, dict):
        return None

    terms = slot_data.get('terms')
    if isinstance(terms, list):
        if 0 <= term_idx < len(terms):
            entry = terms[term_idx]
            if isinstance(entry, dict) and entry.get('name'):
                return entry
        # fallback to first non-empty term
        for entry in terms:
            if isinstance(entry, dict) and entry.get('name'):
                return entry

    if isinstance(terms, dict):
        for key in (str(term_idx + 1), str(term_idx), term_idx):
            entry = terms.get(key)
            if isinstance(entry, dict) and entry.get('name'):
                return entry

    if slot_data.get('name'):
        return slot_data

    return None


def aggregate_assigned_inventory(term_idx=0, machine_id=None):
    assigned = load_assigned_items()
    if isinstance(assigned, dict):
        assigned_machine = assigned.get('machine_id')
        if machine_id and assigned_machine and assigned_machine != machine_id:
            return []

    slots = _extract_slots_from_assigned(assigned)
    summary = {}

    for slot_idx, slot in enumerate(slots):
        term_entry = _select_term_entry(slot, term_idx)
        if not term_entry:
            continue

        name = term_entry.get('name') or slot.get('name')
        if not name:
            continue

        quantity = _safe_int(term_entry.get('quantity', slot.get('quantity')))
        threshold = _safe_int(term_entry.get('low_stock_threshold', slot.get('low_stock_threshold')), 0)
        price = _safe_float(term_entry.get('price', slot.get('price')))
        category = term_entry.get('category') or slot.get('category') or ''
        image_url = term_entry.get('image') or slot.get('image') or ''
        key = name.strip()

        entry = summary.setdefault(key, {
            'name': name,
            'quantity': 0,
            'threshold': threshold,
            'price': price,
            'category': category,
            'image_url': image_url,
            'slots': []
        })

        entry['quantity'] += quantity
        if threshold > entry.get('threshold', 0):
            entry['threshold'] = threshold
        if price:
            entry['price'] = price
        if category:
            entry['category'] = category
        if image_url:
            entry['image_url'] = image_url

        slot_number = slot_idx + 1
        if slot_number not in entry['slots']:
            entry['slots'].append(slot_number)

    return list(summary.values())


@app.route('/admin/init', methods=['POST'])
def admin_init():
    """Initialize machines and items from config (admin only)."""
    try:
        # Load config and assigned items
        config = load_config()
        assigned = load_assigned_items()
        
        machine_id = 'RAON-001'
        esp32_host = config.get('esp32_host', '192.168.4.1')
        
        # Create or update machine
        machine = Machine.query.filter_by(machine_id=machine_id).first()
        if not machine:
            machine = Machine(machine_id=machine_id, name='RAON Vending', esp32_host=esp32_host)
            db.session.add(machine)
        else:
            machine.esp32_host = esp32_host
            machine.last_seen = datetime.utcnow()
        
        db.session.commit()
        
        # Load items
        for slot_idx, slot_data in enumerate(assigned.get('slots', []), 1):
            if isinstance(slot_data, dict) and 'terms' in slot_data:
                term_data = slot_data.get('terms', {}).get('1', {})  # Term 1
                if term_data:
                    item_name = slot_data.get('name', f'Item {slot_idx}')
                    price = float(term_data.get('price', 1.0))
                    qty = int(term_data.get('quantity', 0))
                    
                    item = Item.query.filter_by(machine_id=machine.id, name=item_name).first()
                    if not item:
                        item = Item(
                            machine_id=machine.id,
                            name=item_name,
                            price=price,
                            quantity=qty,
                            slots=str(slot_idx),
                            category=term_data.get('category', ''),
                            image_url=term_data.get('image', '')
                        )
                        db.session.add(item)
                    else:
                        item.price = price
                        item.quantity = qty
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Initialization complete'}), 200
    except Exception as e:
        logger.error(f"Init error: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# STARTUP
# ============================================================================

def create_app_with_db():
    """Initialize app and database."""
    with app.app_context():
        db.create_all()
        config = load_config()
        
        # Ensure default machine exists
        machine_id = config.get('machine_id', 'RAON-001')
        machine_name = config.get('machine_name', 'RAON Vending Machine')
        esp32_host = config.get('esp32_host', '192.168.4.1')
        
        machine = Machine.query.filter_by(machine_id=machine_id).first()
        if not machine:
            machine = Machine(
                machine_id=machine_id,
                name=machine_name,
                esp32_host=esp32_host,
                is_active=True
            )
            db.session.add(machine)
            db.session.commit()
            logger.info(f"Created default machine: {machine_id}")
        
        if should_init_payment_handler(config):
            init_payment_handler(config)
        else:
            logger.info("Skipping PaymentHandler in web_app (hard-disabled; use main.py for hardware).")
        logger.info("Web app initialized")
    return app


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    create_app_with_db()
    app.run(host='0.0.0.0', port=5000, debug=False)
