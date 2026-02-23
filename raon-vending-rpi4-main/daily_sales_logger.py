"""
Daily Sales and Temperature Logger

Logs vending transactions and temperature sensor readings to a daily log file.
Creates one log file per day in the 'logs/' directory.

Log entries include:
- Sales: items sold, amounts paid, change dispensed, timestamp
- Temperature: sensor readings, relay status, target temp
"""

import os
import json
from datetime import datetime
from threading import Lock


class DailySalesLogger:
    """Log vending transactions and temperature data to daily files."""
    
    def __init__(self, logs_dir="logs"):
        """Initialize logger.
        
        Args:
            logs_dir (str): Directory to store log files (default: 'logs/')
        """
        self.logs_dir = logs_dir
        self._lock = Lock()
        
        # Create logs directory if it doesn't exist
        try:
            os.makedirs(logs_dir, exist_ok=True)
            print(f"[Logger] Logs directory: {os.path.abspath(logs_dir)}")
        except Exception as e:
            print(f"[Logger] ERROR creating logs directory: {e}")
    
    def _get_log_filename(self):
        """Get today's log filename (YYYY-MM-DD format)."""
        today = datetime.now().strftime("%Y-%m-%d")
        return os.path.join(self.logs_dir, f"sales_{today}.log")
    
    def log_transaction(self, items_list, coin_amount, bill_amount, change_dispensed):
        """Log a completed vending transaction.
        
        Args:
            items_list (list): List of item dicts with 'name' and 'quantity'
            coin_amount (float): Amount paid in coins (₱)
            bill_amount (float): Amount paid in bills (₱)
            change_dispensed (float): Change dispensed (₱)
        """
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            total_paid = coin_amount + bill_amount
            
            # Format items
            items_str = ", ".join([
                f"{item.get('name', 'Unknown')} x{item.get('quantity', 1)}"
                for item in items_list
            ])
            
            # Build log entry
            log_entry = (
                f"[{timestamp}] TRANSACTION | "
                f"Items: {items_str} | "
                f"Coins: ₱{coin_amount:.2f} | "
                f"Bills: ₱{bill_amount:.2f} | "
                f"Total: ₱{total_paid:.2f} | "
                f"Change: ₱{change_dispensed:.2f}"
            )
            
            # Write to log file (thread-safe)
            with self._lock:
                log_file = self._get_log_filename()
                try:
                    with open(log_file, "a", encoding="utf-8") as f:
                        f.write(log_entry + "\n")
                    print(f"[Logger] Transaction logged: {items_str}")
                except Exception as e:
                    print(f"[Logger] ERROR writing transaction log: {e}")
        except Exception as e:
            print(f"[Logger] ERROR logging transaction: {e}")
    
    def log_temperature(self, sensor_1_temp=None, sensor_2_temp=None, relay_status=None, target_temp=None):
        """Log temperature sensor readings from TEC controller.
        
        Args:
            sensor_1_temp (float): DHT22 sensor 1 temperature (°C)
            sensor_2_temp (float): DHT22 sensor 2 temperature (°C)
            relay_status (bool): TEC relay on/off status
            target_temp (float): Target temperature setpoint (°C)
        """
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Build temperature log entry
            parts = [f"[{timestamp}] TEMPERATURE"]
            
            if sensor_1_temp is not None:
                parts.append(f"Sensor 1: {sensor_1_temp:.1f}°C")
            
            if sensor_2_temp is not None:
                parts.append(f"Sensor 2: {sensor_2_temp:.1f}°C")
            
            if relay_status is not None:
                parts.append(f"Relay: {'ON' if relay_status else 'OFF'}")
            
            if target_temp is not None:
                parts.append(f"Target: {target_temp:.1f}°C")
            
            log_entry = " | ".join(parts)
            
            # Write to log file (thread-safe)
            with self._lock:
                log_file = self._get_log_filename()
                try:
                    with open(log_file, "a", encoding="utf-8") as f:
                        f.write(log_entry + "\n")
                    # Don't spam console with every temp reading
                except Exception as e:
                    print(f"[Logger] ERROR writing temperature log: {e}")
        except Exception as e:
            print(f"[Logger] ERROR logging temperature: {e}")
    
    def log_event(self, event_type, message):
        """Log a generic event (warnings, errors, system events).
        
        Args:
            event_type (str): Type of event ('WARNING', 'ERROR', 'INFO', 'SYSTEM')
            message (str): Event message
        """
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            log_entry = f"[{timestamp}] {event_type:8s} | {message}"
            
            # Write to log file (thread-safe)
            with self._lock:
                log_file = self._get_log_filename()
                try:
                    with open(log_file, "a", encoding="utf-8") as f:
                        f.write(log_entry + "\n")
                    print(f"[Logger] Event logged: {event_type}: {message}")
                except Exception as e:
                    print(f"[Logger] ERROR writing event log: {e}")
        except Exception as e:
            print(f"[Logger] ERROR logging event: {e}")
    
    def get_today_summary(self):
        """Get summary of today's sales.
        
        Returns:
            dict: Summary with total_transactions, total_sales, total_coins, total_bills, total_change
        """
        try:
            log_file = self._get_log_filename()
            if not os.path.exists(log_file):
                return {
                    'date': datetime.now().strftime("%Y-%m-%d"),
                    'total_transactions': 0,
                    'total_sales': 0.0,
                    'total_coins': 0.0,
                    'total_bills': 0.0,
                    'total_change': 0.0
                }
            
            summary = {
                'date': datetime.now().strftime("%Y-%m-%d"),
                'total_transactions': 0,
                'total_sales': 0.0,
                'total_coins': 0.0,
                'total_bills': 0.0,
                'total_change': 0.0
            }
            
            with self._lock:
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if "TRANSACTION |" in line:
                            summary['total_transactions'] += 1
                            # Parse amounts from log line
                            try:
                                if "Coins: ₱" in line:
                                    coin_str = line.split("Coins: ₱")[1].split(" |")[0]
                                    summary['total_coins'] += float(coin_str)
                                if "Bills: ₱" in line:
                                    bill_str = line.split("Bills: ₱")[1].split(" |")[0]
                                    summary['total_bills'] += float(bill_str)
                                if "Change: ₱" in line:
                                    change_str = line.split("Change: ₱")[1].split("\n")[0]
                                    summary['total_change'] += float(change_str)
                            except Exception:
                                pass
            
            summary['total_sales'] = summary['total_coins'] + summary['total_bills']
            return summary
        
        except Exception as e:
            print(f"[Logger] ERROR reading summary: {e}")
            return None
    
    def get_items_sold_summary(self):
        """Get summary of items sold today with quantities.
        
        Returns:
            dict: Item names mapped to total quantities sold
        """
        try:
            log_file = self._get_log_filename()
            if not os.path.exists(log_file):
                return {}
            
            items_sold = {}
            
            with self._lock:
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if "TRANSACTION |" in line and "Items:" in line:
                            # Extract items section between "Items:" and "|"
                            try:
                                items_section = line.split("Items: ")[1].split(" | ")[0]
                                # Parse "Item1 x2, Item2 x1" format
                                item_entries = items_section.split(", ")
                                for entry in item_entries:
                                    if " x" in entry:
                                        name, qty_str = entry.rsplit(" x", 1)
                                        qty = int(qty_str)
                                        if name in items_sold:
                                            items_sold[name] += qty
                                        else:
                                            items_sold[name] = qty
                            except Exception:
                                pass
            
            return items_sold
        except Exception as e:
            print(f"[Logger] ERROR reading items sold: {e}")
            return {}


# Global logger instance
_logger_instance = None

def get_logger(logs_dir="logs"):
    """Get or create the global logger instance."""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = DailySalesLogger(logs_dir=logs_dir)
    return _logger_instance
