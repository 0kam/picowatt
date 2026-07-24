# Calibration

## SHUNT_CAL register

The INA228 computes CURRENT from VSHUNT using the SHUNT_CAL register (0x02):

```
CURRENT_LSB = full-scale current / 2^19
SHUNT_CAL   = 13107.2e6 × CURRENT_LSB × R_SHUNT      (ADCRANGE = 0)
SHUNT_CAL   = 4 × 13107.2e6 × CURRENT_LSB × R_SHUNT  (ADCRANGE = 1)
```

`R_SHUNT = 0.015 Ω` (Adafruit INA228 board, 0.1%).

### picowatt operating points

| Mode | ADCRANGE | Shunt range | CURRENT_LSB | Full scale | SHUNT_CAL |
|---|---|---|---|---|---|
| Default | 0 | ±163.84 mV | 8 µA | ≈4.19 A | 1573 |
| Low current | 1 | ±40.96 mV | 2 µA | ≈1.05 A | 1573 |

The register value is identical in both modes: the ×4 factor for ADCRANGE=1
cancels against the 4× smaller CURRENT_LSB. **The PC must always convert
`curr_raw` with the CURRENT_LSB matching the range the device actually has** —
GET_CONFIG is the source of truth.

Other fixed LSBs (range-independent unless noted):

| Quantity | LSB |
|---|---|
| VBUS | 195.3125 µV |
| VSHUNT | 312.5 nV (range 0) / 78.125 nV (range 1) |

## Zero-offset calibration (PC-side)

With no load connected, residual current readings (ADC offset, board leakage)
are averaged over ~1 s and stored per `board_id` in the PC profile. The offset
(in raw counts) is subtracted from every sample on the PC. No firmware state.

## One-point gain calibration

Shunt resistors are within a few % of nominal; a one-point calibration against
a known current removes most of the error:

1. Drive a known current `I_ref` through the channel (e.g. ET5410A+ in CC mode
   at 1.000 A, cross-checked on its readout).
2. Read the measured current `I_meas` (zero-offset already applied).
3. `SHUNT_CAL_new = round(SHUNT_CAL_current × I_ref / I_meas)`
4. Write it via SET_SHUNT_CAL and store it in the PC profile for this board_id.

Gain correction lives in the device register (so the OLED also shows calibrated
values); it is re-pushed by the PC on every connect.
