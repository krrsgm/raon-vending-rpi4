import sys
sys.path.insert(0, r'c:\Users\SILO\Downloads\TUP\THESIS')
from coin_hopper import CoinHopper
print('import OK')
c = CoinHopper(17, 27, 22, 23)
print('instantiated OK')
from rpi_gpio_mock import simulate_pulse
simulate_pulse(22)
simulate_pulse(23)
print('simulate pulses sent')
