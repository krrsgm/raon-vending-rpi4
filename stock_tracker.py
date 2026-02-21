"""
Stock Tracker - Integration between kiosk and web_app for inventory management
Automatically records sales and monitors low stock alerts
"""

import requests
import json
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class StockTracker:
    """Track inventory stock and communicate with web_app database."""
    
    def __init__(self, web_app_host='localhost', web_app_port=5000, machine_id='RAON-001'):
        """
        Initialize stock tracker.
        
        Args:
            web_app_host (str): Host where web_app is running
            web_app_port (int): Port where web_app is running
            machine_id (str): Machine identifier
        """
        self.machine_id = machine_id
        self.base_url = f'http://{web_app_host}:{web_app_port}'
        self.timeout = 5.0  # seconds
        
    def record_sale(self, item_name, quantity=1, coin_amount=0.0, bill_amount=0.0, 
                   change_dispensed=0.0):
        """
        Record a sale transaction and update inventory.
        
        Args:
            item_name (str): Name of item sold
            quantity (int): Quantity sold
            coin_amount (float): Amount paid in coins
            bill_amount (float): Amount paid in bills
            change_dispensed (float): Change given to customer
            
        Returns:
            dict: Response from web_app with sale details and alerts
        """
        try:
            amount_received = coin_amount + bill_amount
            
            payload = {
                'machine_id': self.machine_id,
                'item_name': item_name,
                'quantity': quantity,
                'amount_received': amount_received,
                'coin_amount': coin_amount,
                'bill_amount': bill_amount,
                'change_dispensed': change_dispensed
            }
            
            url = f'{self.base_url}/api/sales/record'
            response = requests.post(url, json=payload, timeout=self.timeout)
            
            if response.status_code == 200:
                data = response.json()
                
                # Log alert if created
                if data.get('low_stock_alert', {}).get('created'):
                    alert_msg = data['low_stock_alert'].get('message', 'Stock low')
                    logger.warning(f"[StockTracker] LOW STOCK ALERT: {alert_msg}")
                    return {
                        'success': True,
                        'message': f"Sale recorded: {item_name} x{quantity}",
                        'alert': data['low_stock_alert']
                    }
                
                logger.info(f"[StockTracker] Sale recorded: {item_name} x{quantity}, new stock: {data.get('new_quantity', '?')}")
                return {
                    'success': True,
                    'message': f"Sale recorded: {item_name} x{quantity}",
                    'alert': None
                }
            else:
                error_msg = response.json().get('error', 'Unknown error')
                logger.error(f"[StockTracker] Failed to record sale: {error_msg}")
                return {
                    'success': False,
                    'message': f"Error recording sale: {error_msg}",
                    'alert': None
                }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"[StockTracker] Network error recording sale: {e}")
            return {
                'success': False,
                'message': f"Network error: {e}",
                'alert': None
            }
        except Exception as e:
            logger.error(f"[StockTracker] Error recording sale: {e}")
            return {
                'success': False,
                'message': f"Error: {e}",
                'alert': None
            }
    
    def get_active_alerts(self):
        """
        Get all active low stock alerts.
        
        Returns:
            list: List of alert dictionaries
        """
        try:
            url = f'{self.base_url}/api/low-stock-alerts?machine_id={self.machine_id}'
            response = requests.get(url, timeout=self.timeout)
            
            if response.status_code == 200:
                data = response.json()
                alerts = data.get('alerts', [])
                logger.info(f"[StockTracker] Retrieved {len(alerts)} active alerts")
                return alerts
            else:
                logger.warning(f"[StockTracker] Failed to get alerts: {response.status_code}")
                return []
                
        except requests.exceptions.RequestException as e:
            logger.error(f"[StockTracker] Network error getting alerts: {e}")
            return []
        except Exception as e:
            logger.error(f"[StockTracker] Error getting alerts: {e}")
            return []
    
    def acknowledge_alert(self, alert_id):
        """
        Acknowledge (dismiss) a low stock alert.
        
        Args:
            alert_id (int): Alert ID to acknowledge
            
        Returns:
            bool: True if successful
        """
        try:
            url = f'{self.base_url}/api/low-stock-alerts/{alert_id}/acknowledge'
            response = requests.post(url, timeout=self.timeout)
            
            if response.status_code == 200:
                logger.info(f"[StockTracker] Alert {alert_id} acknowledged")
                return True
            else:
                logger.warning(f"[StockTracker] Failed to acknowledge alert: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"[StockTracker] Network error acknowledging alert: {e}")
            return False
        except Exception as e:
            logger.error(f"[StockTracker] Error acknowledging alert: {e}")
            return False
    
    def restock_item(self, item_name, new_quantity):
        """
        Manually restock an item.
        
        Args:
            item_name (str): Item to restock
            new_quantity (int): New stock quantity
            
        Returns:
            bool: True if successful
        """
        try:
            payload = {'quantity': new_quantity}
            url = f'{self.base_url}/api/machines/{self.machine_id}/items/{item_name}/restock'
            response = requests.post(url, json=payload, timeout=self.timeout)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"[StockTracker] Restocked {item_name} to {new_quantity} units")
                return True
            else:
                logger.warning(f"[StockTracker] Failed to restock: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"[StockTracker] Network error restocking: {e}")
            return False
        except Exception as e:
            logger.error(f"[StockTracker] Error restocking: {e}")
            return False


# Create a default instance for easy import and use
def get_tracker(host='localhost', port=5000, machine_id='RAON-001'):
    """Get a StockTracker instance."""
    return StockTracker(web_app_host=host, web_app_port=port, machine_id=machine_id)
