import tkinter as tk
import importlib.util
import os

# Load assign_items_screen module from project root path
proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
module_path = os.path.join(proj_root, 'assign_items_screen.py')
spec = importlib.util.spec_from_file_location('assign_items_screen', module_path)
import sys, types
# Inject a lightweight mock for esp32_client so module import succeeds in test
mock_esp = types.ModuleType('esp32_client')
def pulse_slot(host, slot_num, duration, timeout=1.0):
    return 'OK'
def send_command(host, cmd, timeout=1.0):
    return 'OK'
mock_esp.pulse_slot = pulse_slot
mock_esp.send_command = send_command
sys.modules['esp32_client'] = mock_esp
# Ensure fix_paths is available (some environments may not have it importable)
mock_fix = types.ModuleType('fix_paths')
def get_absolute_path(p):
    return p
mock_fix.get_absolute_path = get_absolute_path
sys.modules['fix_paths'] = mock_fix

assign_items_screen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assign_items_screen)

# Mock dialog to simulate user selecting the first term preset
class MockDialog:
    def __init__(self, parent, slot_idx=0, term_options=None, current_term_idx=0):
        # pick the first non-None term option or a sample
        self.result = None
        if term_options and term_options[0]:
            # return a shallow copy to simulate selection
            self.result = dict(term_options[0])
        else:
            # fallback sample
            self.result = {'code':'MOCK','name':'MOCK ITEM','category':'','price':0,'quantity':1,'image':'','description':''}

# Replace the real dialog with mock
assign_items_screen.EditSlotDialog = MockDialog

root = tk.Tk()
root.withdraw()

# Mock controller with minimal required attributes
class Controller:
    def __init__(self):
        self.items = []
        self.frames = {}

ctrl = Controller()

screen = assign_items_screen.AssignItemsScreen(root, ctrl)
# Ensure current term is 0
screen.current_term = 0

# Ensure slot 0 is empty
screen.slots[0] = {'terms':[None, None, None]}

# Simulate selecting the first term preset by assigning directly (since dialogs require a display)
sample = {'code':'SS1','name':'SS1 - Sensor: IR Sensor, Photodiode, PIR Sensor','category':'','price':185.0,'quantity':1,'image':'images/SS1.png','description':'P185'}
screen.slots[0]['terms'][0] = sample
screen.refresh_slot(0)

print('Slot 1 Term 1 after simulated edit:', screen.slots[0]['terms'][0])

root.destroy()
