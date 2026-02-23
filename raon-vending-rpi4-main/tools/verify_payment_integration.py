import sys
from pathlib import Path
import time

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from payment_handler import PaymentHandler


def on_payment_update(amount):
    print(f"Payment update callback: total amount = {amount}")

if __name__ == '__main__':
    # Adjust the port if needed (use COM5 detected earlier)
    bill_port = 'COM5'
    print('Starting PaymentHandler with bill_port=', bill_port)
    ph = PaymentHandler({}, coin_port=None, bill_port=bill_port, bill_esp32_mode=True)
    if not ph.bill_acceptor:
        print('Bill acceptor not connected. Exiting.')
        ph.cleanup()
        sys.exit(1)

    # Show some diagnostic info about the connected serial device
    try:
        conn = ph.bill_acceptor.serial_conn
        print(f"Bill acceptor object present. serial_conn={getattr(conn, 'port', None)}, baud={getattr(conn, 'baudrate', None)}")
    except Exception:
        print("Bill acceptor object present but serial_conn not introspectable")

    # Preserve existing callback (registered by PaymentHandler) and wrap it so
    # we also print a direct diagnostic without replacing the UI callback.
    try:
        existing_cb = getattr(ph.bill_acceptor, '_callback', None)

        def _wrapped(amt):
            print(f"Direct bill_acceptor callback (diagnostic): bill total now {amt}")
            try:
                if existing_cb:
                    existing_cb(amt)
            except Exception:
                pass

        ph.bill_acceptor.set_callback(_wrapped)
    except Exception:
        pass

    print('Starting payment session and registering UI callback...')
    ph.start_payment_session(required_amount=100.0, on_payment_update=on_payment_update)

    print('Listening for bills for 30 seconds. Insert a bill now...')
    try:
        for i in range(30):
            time.sleep(1)
    except KeyboardInterrupt:
        pass

    ph.cleanup()
    print('Done.')
