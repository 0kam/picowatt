# Hardware verification log

Bench: PS30V5A10 supply, ET5410A+ electronic load, Adafruit INA228 ×2
(15 mΩ), Pico 2, macOS host. 2026-07-24.

## M2 — single-channel accuracy (uncalibrated)

5.00 V supply, 0.500 A CC load:

| Quantity | Reading | Note |
|---|---|---|
| VBUS | 4.9457 V (sd 1.4 mV) | −54 mV vs supply setpoint = lead drop at 0.5 A |
| Current | 0.49981 A (sd 1.6 mA) | −0.04 % vs load setpoint |

Settings: ADCRANGE=0, 540 µs CT, AVG=16.

## M4 — streaming rates (1 MHz I2C)

| Preset | Theory | Measured | Gaps / drops |
|---|---|---|---|
| fast (single) | 3333 Hz | 3193 Hz (−4.2 %) | 0 / 0 |
| fast-dual (dual) | 1786 Hz/ch | 1714 Hz/ch | 0 / 0 |
| normal | 926 Hz | 907 Hz | 0 / 0 |

10-minute soak at fast: 1,916,273 samples, 0 frame gaps, 0 ring drops.
Δt: median 1093 µs vs 1080 µs theoretical; p99 1.8 ms; max 3.1 ms
(OLED page-write interleave; device timestamps make this harmless).

## M6 — energy integration

GUI region (19.627 s): 13.4911 mWh → P_avg 2.4747 W.
Offline CSV re-integration (separate 9.9 s log, same load): P_avg 2.4738 W.
Agreement 0.04 %.

## M7 — dual-channel efficiency

Null test (both shunts in series, same current): **η = 99.84 %**
(uncalibrated; criterion 100 ± 2 %).

DC-DC test: 秋月 M78AR05-1 (5 V / 1 A), 12 V input, load sweep:

| I_out | η (GUI) |
|---|---|
| 0.01 A | 51.81 % |
| 0.05 A | 81.95 % |
| 0.10 A | 87.42 % |
| 0.20 A | 91.45 % |
| 0.30 A | 91.78 % |
| 0.40 A | 91.71 % |

Plateau agrees with the datasheet typical (~92 % at 12 V in) within ~1 %;
light-load rolloff consistent with quiescent-current loss.
