import importlib.util, os, types, sys
proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
module_path = os.path.join(proj_root, 'assign_items_screen.py')
spec = importlib.util.spec_from_file_location('assign_items_screen', module_path)
# inject mocks
mock_esp = types.ModuleType('esp32_client')
mock_esp.pulse_slot = lambda *a, **k: 'OK'
mock_esp.send_command = lambda *a, **k: 'OK'
sys.modules['esp32_client'] = mock_esp
mock_fix = types.ModuleType('fix_paths')
mock_fix.get_absolute_path = lambda p: os.path.join(proj_root, p)
sys.modules['fix_paths'] = mock_fix
assign_items_screen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assign_items_screen)

# create controller
class Ctrl:
    def __init__(self):
        self.config_path = os.path.join(proj_root, 'config.json')
        self.frames = {}
ctrl = Ctrl()

root = None
# instantiate without Tk root by creating a dummy tk.Tk if possible
try:
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    screen = assign_items_screen.AssignItemsScreen(root, ctrl)
    # inspect slot 0 terms
    print('Slot 1 terms:')
    for i, t in enumerate(screen.slots[0]['terms']):
        print(i, bool(t), t.get('name') if t else None)
    root.destroy()
except Exception as e:
    print('Failed to create Tk UI:', e)
