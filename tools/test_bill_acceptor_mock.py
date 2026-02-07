import sys
from pathlib import Path

# Ensure repository root is on sys.path so top-level modules can be imported
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from bill_acceptor import MockBillAcceptor


def ui_callback(amount):
    print(f"UI callback invoked: total amount = {amount}")


if __name__ == '__main__':
    m = MockBillAcceptor()
    m.set_callback(ui_callback)
    m.connect()
    m.start_reading()
    print("Simulating a ₱50 bill...")
    m.simulate_bill_accepted(50)
    print("Simulating a ₱20 bill...")
    m.simulate_bill_accepted(20)
    print("Final total:", m.get_received_amount())
