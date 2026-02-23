import sys
from pathlib import Path
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from payment_handler import PaymentHandler

# Minimal config for PaymentHandler
config = {}

if __name__ == '__main__':
    ph = PaymentHandler(config, coin_port=None, bill_port='/dev/ttyACM0', bill_esp32_mode=True)
    ba = ph.bill_acceptor
    if not ba:
        print('PaymentHandler.bill_acceptor is None (not connected)')
    else:
        print('PaymentHandler.bill_acceptor object exists')
        ser = getattr(ba, 'serial_conn', None)
        print('serial_conn:', ser)
        try:
            print('received_amount:', ba.get_received_amount())
        except Exception as e:
            print('Error reading received_amount:', e)
    ph.cleanup()
