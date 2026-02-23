Raspberry Pi deployment notes — RAON Vending
===========================================

This repository contains the Raspberry Pi touchscreen kiosk and supporting code for the RAON vending project.

Quick USB-Serial setup (Arduino Uno as TB74 forwarder)
---------------------------------------------------

- Connect the Arduino Uno to the Raspberry Pi using a USB A-to-B cable.
- The Uno will appear as `/dev/ttyACM0` (or `/dev/ttyUSB0` on some clones).
- Edit `config.json` (copy `config.example.json`) and set:

  "hardware": {
    "bill_acceptor": {
      "enabled": true,
      "serial_port": "/dev/ttyACM0",
      "baudrate": 115200,
      "proxy_via_esp32": true
    }
  }

- The Pi application will read lines like `BILL:100` from the Uno and update the touchscreen in real time.

Wiring notes (USB method)
-------------------------
- USB provides data + ground; you don't need to wire grounds separately when using USB.
- If you also power the Uno from an external supply, tie the grounds together before connecting any TX/RX lines.

Wiring notes (GPIO UART method)
-------------------------------
- If you prefer to use the Pi's hardware UART pins (GPIO14 TX, GPIO15 RX), disable the Linux serial console and set `serial_port` to `/dev/serial0` in the config.
- Use a level shifter for any 5V MCU TX -> Pi RX connections.

Testing
-------
1. Plug in the Uno and run `dmesg | tail -n 20` to check device node (e.g., `/dev/ttyACM0`).
2. Start the kiosk app (follow your usual run instructions). When the payment window is open and a bill is accepted, the touchscreen will update.
3. To manually test the serial input, run:

```bash
python3 tools/serial_test.py --port /dev/ttyACM0 --baud 115200
```

This script will send test `BILL:` lines to exercise the UI.

Security and safety
-------------------
- Do NOT connect TB74 12V signals directly to MCU GPIO pins. Use an optocoupler or transistor level shifter.
- Use a buck converter to power devices from 12V; do not use a buck to translate signals.

Support
-------
If you need help getting the Pi to see the device, run `ls -l /dev/tty*` and `dmesg | grep -i tty` and provide the output.

EOF
