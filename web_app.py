"""
web_app.py - Flask web application replacing Tkinter UI for RAON Vending Machine.
Provides:
  - Kiosk UI (item selection, payment, vending)
  - Multi-machine inventory dashboard
  - API for payment/vending control integration
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
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
    item_name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    amount_received = db.Column(db.Float, nullable=False)
    coin_amount = db.Column(db.Float, default=0.0)
    bill_amount = db.Column(db.Float, default=0.0)
    change_dispensed = db.Column(db.Float, default=0.0)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


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


def init_payment_handler(config):
    """Initialize the payment handler with config."""
    global payment_handler
    try:
        if PaymentHandler:
            payment_handler = PaymentHandler(
                config=config,
                use_gpio_coin=True,
                coin_gpio_pin=config.get('hardware', {}).get('coin_acceptor', {}).get('gpio_pin', 17)
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





                    coin_amount=coin_amt / len(current_payment_session['items']),
                    bill_amount=bill_amt / len(current_payment_session['items']),
                    change_dispensed=change / len(current_payment_session['items'])
                )
                db.session.add(sale)
            
            db.session.commit()
            
            # Reset session
            current_payment_session['in_progress'] = False
            current_payment_session['items'] = []
        
        return jsonify({
            'success': True,
            'received': received,
            'change': change,
            'vend_results': vend_results
        }), 200
    except Exception as e:
        logger.error(f"Error confirming payment: {e}")
        return jsonify({'error': str(e)}), 500


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
        
        total_sales_today = db.session.query(db.func.sum(Sale.amount_received))\
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
                logs = f.readlines()
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
        init_payment_handler(config)
        logger.info("Web app initialized")
    return app


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    create_app_with_db()
    app.run(host='0.0.0.0', port=5000, debug=False)
