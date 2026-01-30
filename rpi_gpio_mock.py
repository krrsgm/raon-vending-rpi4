"""Lightweight mock of RPi.GPIO API for non-Raspberry-Pi environments.

This mock provides a minimal subset of the API used by the project so
the UI can run on Windows or desktop Linux without hardware.

It also exposes simulate_pulse(pin) to manually trigger registered
callbacks (useful for testing).
"""
import time
from threading import Thread
import sys

# Basic constants
BCM = 'BCM'
IN = 'IN'
PUD_UP = 'PUD_UP'
FALLING = 'FALLING'
OUT = 'OUT'
BOTH = 'BOTH'
HIGH = 1
LOW = 0

# Internal pin state storage for input/output simulation
_pin_state = {}

_callbacks = {}

def setmode(mode):
    # no-op for mock
    return

def setup(pin, mode, pull_up_down=None):
    # no-op for mock
    # initialize pin state based on pull_up_down
    if pull_up_down == PUD_UP:
        _pin_state.setdefault(pin, HIGH)
    else:
        _pin_state.setdefault(pin, LOW)
    return

def add_event_detect(pin, edge, callback=None, bouncetime=0):
    # Store callback for the pin
    _callbacks[pin] = callback

def remove_event_detect(pin):
    _callbacks.pop(pin, None)

def cleanup(pin=None):
    if pin is None:
        _callbacks.clear()
    else:
        _callbacks.pop(pin, None)

def simulate_pulse(pin, delay=0):
    """Simulate a pulse on the given pin after optional delay (seconds).

    If a callback was registered with add_event_detect, it will be called
    on a separate thread to mimic asynchronous hardware interrupts.
    """
    def _run():
        if delay:
            time.sleep(delay)
        cb = _callbacks.get(pin)
        if cb:
            try:
                # Toggle the input state to simulate a pulse
                _pin_state[pin] = HIGH
                cb(pin)
                # small delay to emulate pulse width
                time.sleep(0.01)
                _pin_state[pin] = LOW
            except Exception as e:
                print(f"Mock GPIO callback error: {e}")

    Thread(target=_run, daemon=True).start()


def input(pin):
    """Return simulated input state for a pin."""
    return _pin_state.get(pin, LOW)


def output(pin, value):
    """Set simulated output state for a pin."""
    _pin_state[pin] = value


# Expose a module-like GPIO symbol so callers that do
# `from rpi_gpio_mock import GPIO` get an object with
# the same attributes as this module.
GPIO = sys.modules[__name__]
