# Sharp IR Calibration on ESP32 (GPIO34/GPIO35)

Use sketch: `arduino_tests/Sharp_IR_Calibration_ESP32/Sharp_IR_Calibration_ESP32.ino`

Default wiring:
- `Sharp IR 1 OUT -> GPIO34`
- `Sharp IR 2 OUT -> GPIO35`
- `VCC -> 5V`
- `GND -> GND` (shared ground with ESP32)

Notes:
- ESP32 ADC is `12-bit` (`0..4095`).
- GPIO34/35 are input-only and good for analog reads.

## 1. Upload and Open Serial Monitor

1. Select your ESP32 board in Arduino IDE.
2. Upload the sketch.
3. Open Serial Monitor:
- Baud: `115200`
- Line ending: `Newline`

## 2. Calibrate Empty Bin

With no item in the detection zone:
`CAL_EMPTY 8`

## 3. Calibrate Item-Detected Zone

Hold a real product/sample in the desired dispense-detection area:
`CAL_ITEM 8`

## 4. Compute and Apply Suggested Thresholds

`SUGGEST`

Then:
`APPLY`

The sketch will switch to suggested values with hysteresis for stable detection.

## 5. Validate with Real Dispense

Run repeated dispense tests (20+):
- Idle: sensors should stay mostly `CLEAR`.
- Item pass/fall: at least one sensor should move to `BLOCKED`.
- No random flicker when idle.

If unstable:
- Re-angle sensor and target zone.
- Increase spacing from reflective surfaces.
- Re-run `CAL_EMPTY` + `CAL_ITEM`.

## 6. Threshold Formula Used

Per sensor:
1. `delta = item_mean - empty_mean`
2. `blocked_enter = empty_mean + 0.65 * delta`
3. `clear_exit = empty_mean + 0.45 * delta`

This supports both behaviors:
- blocked value going higher, or
- blocked value going lower.

## 7. Command Quick List

- `HELP`
- `STATUS`
- `READ`
- `STREAM ON` / `STREAM OFF`
- `CAL_EMPTY [seconds]`
- `CAL_ITEM [seconds]`
- `SUGGEST`
- `APPLY`
- `SET <sensor> <blocked_enter> <clear_exit>`
- `POLARITY <sensor> HIGHER|LOWER`
- `RESET_CAL`

