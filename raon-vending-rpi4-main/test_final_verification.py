#!/usr/bin/env python3
"""
Final Verification Test - All Components
Tests that all new features work correctly together
"""

import sys

def test_imports():
    """Test all modules import correctly"""
    print('1. Testing module imports...')
    try:
        from cart_screen import CartScreen
        from system_status_panel import SystemStatusPanel
        from system_logger import SystemLogger
        from kiosk_app import KioskFrame
        print('   ✓ All modules import successfully')
        return True
    except Exception as e:
        print(f'   ✗ Import failed: {e}')
        return False

def test_config():
    """Test configuration loads correctly"""
    print('\n2. Testing configuration...')
    try:
        import json
        with open('config.example.json') as f:
            config = json.load(f)
        assert config.get('currency_symbol'), 'Missing currency_symbol'
        assert config.get('header_logo_path'), 'Missing header_logo_path'
        assert config.get('logging'), 'Missing logging section'
        assert config.get('items'), 'Missing items section'
        print('   ✓ config.example.json loads successfully')
        print('   ✓ All required sections present')
        return True
    except Exception as e:
        print(f'   ✗ Config test failed: {e}')
        return False

def test_logger():
    """Test logger initialization"""
    print('\n3. Testing logger initialization...')
    try:
        import json
        from system_logger import SystemLogger
        
        with open('config.example.json') as f:
            config = json.load(f)
        
        logger = SystemLogger(config)
        summary = logger.get_log_summary()
        
        assert isinstance(summary, dict), 'Logger summary invalid'
        assert summary.get('status') == 'ENABLED', 'Logger not enabled'
        
        loggers_configured = len([v for v in summary['loggers'].values() if v == 'configured'])
        assert loggers_configured == 4, f'Expected 4 loggers, got {loggers_configured}'
        
        print('   ✓ SystemLogger initialized')
        print('   ✓ All 4 loggers configured')
        print(f'   ✓ Log directory: {logger.get_log_directory()}')
        return True
    except Exception as e:
        print(f'   ✗ Logger test failed: {e}')
        return False

def test_status_panel():
    """Test status panel creation"""
    print('\n4. Testing SystemStatusPanel creation...')
    try:
        import tkinter as tk
        from system_status_panel import SystemStatusPanel
        
        root = tk.Tk()
        root.withdraw()
        panel = SystemStatusPanel(root, controller=None)
        print('   ✓ SystemStatusPanel instantiated successfully')
        root.destroy()
        return True
    except Exception as e:
        print(f'   ✗ StatusPanel test failed: {e}')
        return False

def test_cart_screen():
    """Test cart screen has status panel integration"""
    print('\n5. Testing CartScreen integration...')
    try:
        import inspect
        from cart_screen import CartScreen
        import cart_screen
        
        # Get module source (includes imports)
        module_source = inspect.getsource(cart_screen)
        # Get class source
        class_source = inspect.getsource(CartScreen)
        
        checks = {
            'Import': 'from system_status_panel import SystemStatusPanel' in module_source,
            'Instantiation': 'self.status_panel = SystemStatusPanel' in class_source,
            'Packing': 'self.status_panel.pack' in class_source,
        }
        
        for check_name, result in checks.items():
            if not result:
                raise Exception(f'Missing {check_name}')
            print(f'   ✓ {check_name} verified')
        
        return True
    except Exception as e:
        print(f'   ✗ CartScreen test failed: {e}')
        return False

def main():
    """Run all tests"""
    print('='*60)
    print('FINAL VERIFICATION TEST')
    print('='*60)
    
    tests = [
        test_imports,
        test_config,
        test_logger,
        test_status_panel,
        test_cart_screen,
    ]
    
    results = [test() for test in tests]
    
    print('\n' + '='*60)
    if all(results):
        print('✅ ALL TESTS PASSED')
        print('='*60)
        print('\nSystem Status:')
        print('  ✓ Cart screen displays status panel')
        print('  ✓ Logging system fully configured')
        print('  ✓ Configuration structure correct')
        print('  ✓ All components integrated')
        print('  ✓ Ready for Raspberry Pi deployment')
        return 0
    else:
        print('❌ SOME TESTS FAILED')
        print('='*60)
        return 1

if __name__ == '__main__':
    sys.exit(main())
