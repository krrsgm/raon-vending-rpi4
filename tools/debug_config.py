#!/usr/bin/env python3
"""
debug_config.py
Debug script to check what config is being loaded by main.py
"""
import json
import os
import sys

print("\n" + "="*60)
print("DEBUGGING CONFIG LOADING")
print("="*60)

# Check current directory
cwd = os.getcwd()
print(f"\nCurrent working directory: {cwd}")

# Check if config.json exists
config_path = "config.json"
abs_config_path = os.path.abspath(config_path)
print(f"\nLooking for config.json at: {abs_config_path}")

if os.path.exists(abs_config_path):
    print(f"✓ config.json EXISTS")
    try:
        with open(abs_config_path, 'r') as f:
            config = json.load(f)
        print(f"✓ Successfully loaded config.json")
        print(f"\nConfig contents:")
        print(json.dumps(config, indent=2))
        
        esp32_host = config.get('esp32_host', 'NOT SET')
        print(f"\n✓ esp32_host = {esp32_host}")
    except Exception as e:
        print(f"✗ Error reading config.json: {e}")
else:
    print(f"✗ config.json NOT FOUND")
    print(f"\nLooking for config.example.json...")
    if os.path.exists("config.example.json"):
        print(f"✓ config.example.json EXISTS")
        print(f"\nTo create config.json, run:")
        print(f"  cp config.example.json config.json")
        print(f"  Edit config.json and set esp32_host to 'serial:/dev/ttyS0'")

# Also check where main.py would look for it
print(f"\n" + "="*60)
print("MAIN.PY PATH RESOLUTION")
print("="*60)

# Mimic what main.py does
def get_absolute_path(relative_path):
    """Get absolute path relative to the script location (mimics main.py)"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, relative_path)

main_config_path = get_absolute_path("config.json")
print(f"\nIf running from main.py, it would look for:")
print(f"  {main_config_path}")
print(f"  Exists: {os.path.exists(main_config_path)}")

# List all files in current directory
print(f"\n" + "="*60)
print("FILES IN CURRENT DIRECTORY")
print("="*60)
files = os.listdir('.')
json_files = [f for f in files if f.endswith('.json')]
print(f"\nJSON files found:")
for f in json_files:
    print(f"  - {f}")

if not json_files:
    print(f"  (no JSON files found)")
