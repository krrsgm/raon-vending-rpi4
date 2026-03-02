# Sharp IR Calibration Guide (A0/A1)

This guide is for `Sharp_GP2Y0A21YK0F` style analog IR sensors connected to:
- `IR1 -> A0`
- `IR2 -> A1`

Use sketch: `arduino_tests/Sharp_IR_Calibration/Sharp_IR_Calibration.ino`

## 1. Upload and Open Serial Monitor

1. Upload the sketch to Arduino Uno.
2. Open Serial Monitor at `115200` baud.
3. Set line ending to `Newline`.

You should see live lines like:
`ms=1234 IR1 raw=290 ema=287 CLEAR | IR2 raw=305 ema=300 CLEAR`

## 2. Capture Baseline for Empty Bin

With no item in the detection zone, run:
`CAL_EMPTY 8`

This captures 8 seconds of values and prints mean/min/max for each sensor.

## 3. Capture Item-Detected Zone

Place a sample item in the exact area where you want to confirm successful dispense.
Keep the item steady and run:
`CAL_ITEM 8`

This captures the "detected" population.

## 4. Get Suggested Thresholds

Run:
`SUGGEST`

The sketch prints per-sensor suggestions:
- `blocked_enter`
- `clear_exit`
- detection polarity (`HIGHER` or `LOWER`)

Apply directly in the test sketch with:
`APPLY`

## 5. How to Pick Final Production Values

Use this rule:
1. `empty_mean` = average value from `CAL_EMPTY`
2. `item_mean` = average value from `CAL_ITEM`
3. `delta = item_mean - empty_mean`
4. `blocked_enter = empty_mean + 0.65 * delta`
5. `clear_exit = empty_mean + 0.45 * delta`

This creates hysteresis so readings do not flicker near the threshold.

Notes:
- If `delta > 0`: item detection means ADC goes higher.
- If `delta < 0`: item detection means ADC goes lower.
- If `abs(delta) < 40`: separation is weak; improve sensor angle/distance first.

## 6. Validate with Real Dispense Motion

Run 20-30 dispense tests and verify:
- At rest (bin empty), both sensors stay `CLEAR`.
- During item pass, at least one sensor transitions to `BLOCKED`.
- No random `BLOCKED` spikes when idle.

If you see false triggers:
- Increase separation by repositioning sensor.
- Increase hysteresis gap (`blocked_enter` farther from `clear_exit`).
- Use EMA/averaging (already included in the test sketch).

## 7. Apply to `ArduinoUno_Bill_Forward.ino`

Update thresholds in your production sketch based on calibration results:

```cpp
const int IR_BLOCKED_THRESHOLD = 350;
const int IR_CLEAR_THRESHOLD   = 300;
```

If IR1 and IR2 need different thresholds, split these into per-sensor constants.

