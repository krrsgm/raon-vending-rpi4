#!/usr/bin/env python3
"""
Test MUX4 selector mapping and SIG pulse for channels 0..15.
Usage: run on the Raspberry Pi where MUX4 is wired.
"""
import time
from mux4_controller import MUX4Controller

m = MUX4Controller()
print(f"MUX4 initialized. pins: S0={m.s0_pin}, S1={m.s1_pin}, S2={m.s2_pin}, S3={m.s3_pin}, SIG={m.sig_pin}")

print("\nCycling channels 0..15")
for ch in range(16):
    bits = [(ch >> i) & 1 for i in range(4)]
    print(f"Channel {ch:2d}: bits S3 S2 S1 S0 = {bits[3]} {bits[2]} {bits[1]} {bits[0]}")
    try:
        m.select_channel(ch)
        time.sleep(0.05)
        # Optional: read SIG before pulse
        sig_before = m.read_sig()
        print(f"  SIG before: {sig_before}")
        m.pulse(200)
        # read after
        sig_after = m.read_sig()
        print(f"  SIG after: {sig_after}")
    except Exception as e:
        print(f"  ERROR on channel {ch}: {e}")
    time.sleep(0.2)

print('\nDone. If only the last channels activate motors, check selector wiring order (S0-S3 mapping) and that setmode is BCM.')
