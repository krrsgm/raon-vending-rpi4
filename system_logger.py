"""
System Logger - Image-based Logging Module for RAON Vending Machine

This module provides centralized logging functionality similar to how images
are configured in config.json. It supports:
- Transaction logging
- Error logging
- Dispense/item logging
- Sensor logging
- Rotating file handlers
- Multiple log levels

Configuration is read from config.json under the 'logging' key.
"""

import logging
import logging.handlers
import os
import json
from pathlib import Path
from datetime import datetime


class SystemLogger:
    """
    Centralized logging system with image-like configuration structure.
    
    Configuration example (from config.json):
    {
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
    }
    """
    
    _instance = None  # Singleton pattern
    
    def __new__(cls, config=None):
        """Ensure only one logger instance exists."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, config=None):
        """Initialize the logging system."""
        if self._initialized:
            return
        
        self._initialized = True
        self.config = config or {}
        self.loggers = {}
        self.log_dir = None
        
        # Extract logging config
        self.logging_config = self.config.get('logging', {})
        
        # If logging is disabled, create dummy loggers
        if not self.logging_config.get('enabled', True):
            self._setup_dummy_loggers()
            return
        
        # Set up logging directory
        self._setup_log_directory()
        
        # Initialize each logger type (like configuring different image paths)
        self._setup_transaction_logger()
        self._setup_error_logger()
        self._setup_dispense_logger()
        self._setup_sensor_logger()
    
    def _setup_log_directory(self):
        """Create and configure the logging directory."""
        log_dir = self.logging_config.get('log_directory', './logs')
        self.log_dir = Path(log_dir)
        
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            print(f"✓ Logging directory ready: {self.log_dir.absolute()}")
        except Exception as e:
            print(f"✗ Error creating log directory: {e}")
            self.log_dir = Path('./logs')
            try:
                self.log_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e2:
                print(f"✗ Failed to create backup log directory: {e2}")
    
    def _get_log_level(self):
        """Get logging level from config."""
        level_str = self.logging_config.get('log_level', 'INFO').upper()
        return getattr(logging, level_str, logging.INFO)
    
    def _create_logger(self, logger_name, log_filename, max_mb=10, backup_count=5):
        """
        Create a logger with rotating file handler.
        
        Args:
            logger_name: Name of the logger
            log_filename: Filename for this log
            max_mb: Maximum file size in MB before rotation
            backup_count: Number of backup files to keep
        
        Returns:
            Configured logger instance
        """
        if not self.log_dir:
            return None
        
        logger = logging.getLogger(logger_name)
        logger.setLevel(self._get_log_level())
        
        # Remove existing handlers
        logger.handlers = []
        
        try:
            log_path = self.log_dir / log_filename
            
            # Rotating file handler (like image sizing - auto-manages files)
            handler = logging.handlers.RotatingFileHandler(
                str(log_path),
                maxBytes=max_mb * 1024 * 1024,
                backupCount=backup_count
            )
            
            # Format: timestamp | level | message
            formatter = logging.Formatter(
                '%(asctime)s | %(levelname)-8s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
            print(f"✓ Logger '{logger_name}' configured: {log_path}")
            return logger
            
        except Exception as e:
            print(f"✗ Error setting up logger '{logger_name}': {e}")
            return None
    
    def _setup_dummy_loggers(self):
        """Create dummy loggers that don't write to disk."""
        print("⚠ Logging disabled in configuration - using dummy loggers")
        
        for logger_name in ['transaction', 'error', 'dispense', 'sensor']:
            logger = logging.getLogger(f'dummy_{logger_name}')
            logger.setLevel(logging.CRITICAL)  # Effectively disabled
            self.loggers[logger_name] = logger
    
    def _setup_transaction_logger(self):
        """Set up transaction logger (payment, purchases)."""
        cfg = self.logging_config.get('transaction_log', {})
        if not cfg.get('enabled', True):
            self.loggers['transaction'] = None
            return
        
        filename = cfg.get('log_filename', 'transactions.log')
        max_mb = self.logging_config.get('max_log_size_mb', 10)
        backups = self.logging_config.get('backup_count', 5)
        
        self.loggers['transaction'] = self._create_logger(
            'transaction_logger', filename, max_mb, backups
        )
    
    def _setup_error_logger(self):
        """Set up error logger (exceptions, warnings)."""
        cfg = self.logging_config.get('error_log', {})
        if not cfg.get('enabled', True):
            self.loggers['error'] = None
            return
        
        filename = cfg.get('log_filename', 'errors.log')
        max_mb = self.logging_config.get('max_log_size_mb', 10)
        backups = self.logging_config.get('backup_count', 5)
        
        self.loggers['error'] = self._create_logger(
            'error_logger', filename, max_mb, backups
        )
    
    def _setup_dispense_logger(self):
        """Set up dispense logger (item dispensing, bin detection)."""
        cfg = self.logging_config.get('dispense_log', {})
        if not cfg.get('enabled', True):
            self.loggers['dispense'] = None
            return
        
        filename = cfg.get('log_filename', 'dispense.log')
        max_mb = self.logging_config.get('max_log_size_mb', 10)
        backups = self.logging_config.get('backup_count', 5)
        
        self.loggers['dispense'] = self._create_logger(
            'dispense_logger', filename, max_mb, backups
        )
    
    def _setup_sensor_logger(self):
        """Set up sensor logger (temperature, IR sensors)."""
        cfg = self.logging_config.get('sensor_log', {})
        if not cfg.get('enabled', True):
            self.loggers['sensor'] = None
            return
        
        filename = cfg.get('log_filename', 'sensors.log')
        max_mb = self.logging_config.get('max_log_size_mb', 10)
        backups = self.logging_config.get('backup_count', 5)
        
        self.loggers['sensor'] = self._create_logger(
            'sensor_logger', filename, max_mb, backups
        )
    
    # --- Public API Methods ---
    
    def log_transaction(self, message, level='INFO'):
        """Log a transaction event."""
        if self.loggers.get('transaction'):
            getattr(self.loggers['transaction'], level.lower(), self.loggers['transaction'].info)(message)
    
    def log_error(self, message, exc_info=False):
        """Log an error with optional exception info."""
        if self.loggers.get('error'):
            self.loggers['error'].error(message, exc_info=exc_info)
    
    def log_warning(self, message):
        """Log a warning."""
        if self.loggers.get('error'):
            self.loggers['error'].warning(message)
    
    def log_dispense(self, message, level='INFO'):
        """Log a dispense event."""
        if self.loggers.get('dispense'):
            getattr(self.loggers['dispense'], level.lower(), self.loggers['dispense'].info)(message)
    
    def log_sensor(self, message, level='INFO'):
        """Log a sensor reading."""
        if self.loggers.get('sensor'):
            getattr(self.loggers['sensor'], level.lower(), self.loggers['sensor'].info)(message)
    
    # --- Convenience Methods ---
    
    def log_payment_received(self, amount, payment_type='coins', item_name=None):
        """Log a payment transaction."""
        msg = f"Payment received: {payment_type} = PHP{amount:.2f}"
        if item_name:
            msg += f" (for {item_name})"
        self.log_transaction(msg)
    
    def log_item_dispensed(self, item_name, quantity, status='SUCCESS'):
        """Log item dispensing."""
        msg = f"[{status}] Dispensed {quantity}x {item_name}"
        self.log_dispense(msg)
    
    def log_dispense_timeout(self, item_name, timeout_sec):
        """Log a dispense timeout alert."""
        msg = f"[TIMEOUT] Dispense timeout for {item_name} after {timeout_sec}s"
        self.log_dispense(msg, 'warning')
    
    def log_item_detected_in_bin(self, sensor_info=''):
        """Log item detected in bin by IR sensor."""
        msg = f"[IR DETECT] Item detected in bin. {sensor_info}"
        self.log_dispense(msg)
    
    def log_temperature_reading(self, sensor_num, temp, humidity):
        """Log temperature and humidity reading."""
        msg = f"DHT22[{sensor_num}] T={temp:.1f}°C H={humidity:.1f}%"
        self.log_sensor(msg)
    
    def log_tec_status(self, enabled, active, target, current):
        """Log TEC cooling status."""
        status = "ACTIVE" if active else ("ENABLED" if enabled else "DISABLED")
        msg = f"TEC [{status}] Target={target:.1f}°C Current={current:.1f}°C"
        self.log_sensor(msg)
    
    def log_system_error(self, error_msg, error_type='ERROR'):
        """Log a system error."""
        msg = f"[{error_type}] {error_msg}"
        self.log_error(msg)
    
    def get_log_directory(self):
        """Get the current log directory path."""
        return str(self.log_dir.absolute()) if self.log_dir else None
    
    def get_log_files(self):
        """Get list of all log files."""
        if not self.log_dir:
            return []
        return [str(f) for f in self.log_dir.glob('*.log')]
    
    def get_log_summary(self):
        """Get summary of logging setup."""
        if not self.logging_config.get('enabled', True):
            return "Logging is DISABLED"
        
        summary = {
            'status': 'ENABLED',
            'directory': self.get_log_directory(),
            'level': self.logging_config.get('log_level', 'INFO'),
            'max_file_size': f"{self.logging_config.get('max_log_size_mb', 10)} MB",
            'backup_count': self.logging_config.get('backup_count', 5),
            'loggers': {}
        }
        
        for logger_name, logger_obj in self.loggers.items():
            summary['loggers'][logger_name] = logger_obj is not None and 'configured' or 'disabled'
        
        return summary


def get_logger():
    """Get the singleton logger instance."""
    return SystemLogger()


# --- Global convenience functions ---

def log_transaction(message):
    """Quick access to transaction logger."""
    get_logger().log_transaction(message)


def log_error(message, exc_info=False):
    """Quick access to error logger."""
    get_logger().log_error(message, exc_info)


def log_dispense(message):
    """Quick access to dispense logger."""
    get_logger().log_dispense(message)


def log_sensor(message):
    """Quick access to sensor logger."""
    get_logger().log_sensor(message)


if __name__ == '__main__':
    # Test the logging system
    print("Testing SystemLogger...\n")
    
    # Create test config
    test_config = {
        'logging': {
            'enabled': True,
            'log_directory': './test_logs',
            'log_level': 'INFO',
            'max_log_size_mb': 10,
            'backup_count': 3,
            'transaction_log': {'enabled': True, 'log_filename': 'transactions.log'},
            'error_log': {'enabled': True, 'log_filename': 'errors.log'},
            'dispense_log': {'enabled': True, 'log_filename': 'dispense.log'},
            'sensor_log': {'enabled': True, 'log_filename': 'sensors.log'}
        }
    }
    
    # Initialize logger
    logger = SystemLogger(test_config)
    
    print("\n--- Testing Log Functions ---\n")
    
    # Test transaction logging
    logger.log_payment_received(100.00, 'coins', 'Coca Cola')
    logger.log_payment_received(500.00, 'bills')
    
    # Test dispense logging
    logger.log_item_dispensed('Coca Cola', 1, 'SUCCESS')
    logger.log_item_detected_in_bin('Sensor 1+2 detected')
    logger.log_dispense_timeout('Sprite', 10)
    
    # Test sensor logging
    logger.log_temperature_reading(1, 24.5, 65.2)
    logger.log_tec_status(True, True, 10.0, 12.3)
    
    # Test error logging
    logger.log_error('Test error message')
    logger.log_system_error('Connection timeout', 'WARNING')
    
    print("\n--- Logger Summary ---")
    summary = logger.get_log_summary()
    if isinstance(summary, dict):
        import pprint
        pprint.pprint(summary)
    else:
        print(summary)
    
    print("\n--- Log Files Created ---")
    for log_file in logger.get_log_files():
        print(f"  • {log_file}")
    
    print("\n✓ Testing complete!")
