"""Calibration and advanced-settings dialogs."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from . import protocol as proto

CT_LABELS = [f"{us} µs" for us in proto.CT_US]
AVG_LABELS = [str(n) for n in proto.AVG_COUNT]


class CalibrationDialog(QDialog):
    """Guided zero-offset and one-point gain calibration.

    get_mean_current(ch) -> (mean_amps, n_samples) over the last ~1 s
    (as displayed, i.e. zero-corrected).
    get_shunt_cal(ch) -> current SHUNT_CAL register value.
    apply_zero(ch, delta_amps) / apply_gain(ch, new_shunt_cal) do the work.
    """

    def __init__(
        self,
        parent,
        get_mean_current: Callable[[int], tuple[float, int]],
        get_shunt_cal: Callable[[int], int],
        apply_zero: Callable[[int, float], None],
        apply_gain: Callable[[int, int], None],
        apply_reset: Callable[[int], None],
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Calibration")
        self._get_mean = get_mean_current
        self._get_shunt_cal = get_shunt_cal
        self._apply_zero = apply_zero
        self._apply_gain = apply_gain
        self._apply_reset = apply_reset

        layout = QVBoxLayout(self)

        ch_row = QHBoxLayout()
        ch_row.addWidget(QLabel("Channel:"))
        self.ch_combo = QComboBox()
        self.ch_combo.addItems(["ch0 (in)", "ch1 (out)"])
        ch_row.addWidget(self.ch_combo)
        ch_row.addStretch()
        layout.addLayout(ch_row)

        zero_box = QGroupBox("Zero offset")
        zl = QVBoxLayout(zero_box)
        zl.addWidget(QLabel(
            "1. Remove the load so that NO current flows.\n"
            "2. Keep streaming for at least 2 seconds.\n"
            "3. Click Zero — the mean of the last second becomes the offset."
        ))
        zero_btn = QPushButton("Zero")
        zero_btn.clicked.connect(self._do_zero)
        zl.addWidget(zero_btn)
        layout.addWidget(zero_box)

        gain_box = QGroupBox("One-point gain")
        gl = QFormLayout(gain_box)
        gl.addRow(QLabel(
            "1. Zero first (above).\n"
            "2. Drive a known, stable current (e.g. electronic load CC mode).\n"
            "3. Enter that current and click Calibrate gain."
        ))
        self.iref_spin = QDoubleSpinBox()
        self.iref_spin.setDecimals(4)
        self.iref_spin.setRange(0.001, 10.0)
        self.iref_spin.setValue(1.0)
        self.iref_spin.setSuffix(" A")
        gl.addRow("Reference current:", self.iref_spin)
        gain_btn = QPushButton("Calibrate gain")
        gain_btn.clicked.connect(self._do_gain)
        gl.addRow(gain_btn)
        layout.addWidget(gain_box)

        self.result_label = QLabel("")
        layout.addWidget(self.result_label)

        reset_btn = QPushButton("Reset channel to defaults")
        reset_btn.clicked.connect(self._do_reset)
        layout.addWidget(reset_btn)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _ch(self) -> int:
        return self.ch_combo.currentIndex()

    def _do_zero(self) -> None:
        ch = self._ch()
        mean, n = self._get_mean(ch)
        if n < 50:
            QMessageBox.warning(
                self, "Calibration",
                f"only {n} fresh samples available — make sure streaming is on, "
                "and wait ~2 s after a previous calibration step")
            return
        self._apply_zero(ch, mean)
        self.result_label.setText(f"ch{ch}: zero offset updated by {mean * 1e6:.1f} µA (n={n})")

    def _do_reset(self) -> None:
        ch = self._ch()
        self._apply_reset(ch)
        self.result_label.setText(f"ch{ch}: restored SHUNT_CAL 1573, zero offsets cleared")

    def _do_gain(self) -> None:
        ch = self._ch()
        mean, n = self._get_mean(ch)
        if n < 50:
            QMessageBox.warning(
                self, "Calibration",
                f"only {n} fresh samples available — make sure streaming is on, "
                "and wait ~2 s after a previous calibration step")
            return
        if mean <= 0:
            QMessageBox.warning(self, "Calibration", "measured current is not positive")
            return
        i_ref = self.iref_spin.value()
        old = self._get_shunt_cal(ch)
        new = round(old * i_ref / mean)
        if not (100 <= new <= 32767):
            QMessageBox.warning(self, "Calibration",
                                f"computed SHUNT_CAL {new} out of range — check setup")
            return
        self._apply_gain(ch, new)
        self.result_label.setText(
            f"ch{ch}: SHUNT_CAL {old} → {new} "
            f"(measured {mean:.5f} A vs ref {i_ref:.4f} A, n={n})"
        )


class AdvancedSettingsDialog(QDialog):
    """Raw INA228 ADC settings (conversion times, averaging, range)."""

    def __init__(self, parent, cfg: proto.Config,
                 apply_fn: Callable[[int, int, int, int, int], None]) -> None:
        super().__init__(parent)
        self.setWindowTitle("Advanced ADC settings")
        self._apply_fn = apply_fn

        form = QFormLayout(self)

        self.ch_combo = QComboBox()
        self.ch_combo.addItems(["both", "ch0 (in)", "ch1 (out)"])
        form.addRow("Channel:", self.ch_combo)

        self.range_combo = QComboBox()
        self.range_combo.addItems(["0: ±163.84 mV (8 µA/LSB)", "1: ±40.96 mV (2 µA/LSB)"])
        self.range_combo.setCurrentIndex(cfg.ch[0].adcrange)
        form.addRow("ADC range:", self.range_combo)

        self.vbusct_combo = QComboBox()
        self.vbusct_combo.addItems(CT_LABELS)
        self.vbusct_combo.setCurrentIndex(cfg.ch[0].vbusct)
        form.addRow("VBUS conversion:", self.vbusct_combo)

        self.vshct_combo = QComboBox()
        self.vshct_combo.addItems(CT_LABELS)
        self.vshct_combo.setCurrentIndex(cfg.ch[0].vshct)
        form.addRow("Shunt conversion:", self.vshct_combo)

        self.avg_combo = QComboBox()
        self.avg_combo.addItems(AVG_LABELS)
        self.avg_combo.setCurrentIndex(cfg.ch[0].avg)
        form.addRow("Averaging:", self.avg_combo)

        self.rate_label = QLabel("")
        form.addRow("Resulting rate:", self.rate_label)
        for w in (self.vbusct_combo, self.vshct_combo, self.avg_combo):
            w.currentIndexChanged.connect(self._update_rate)
        self._update_rate()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Close
        )
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self._apply)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _update_rate(self) -> None:
        period = (
            proto.CT_US[self.vbusct_combo.currentIndex()]
            + proto.CT_US[self.vshct_combo.currentIndex()]
        ) * proto.AVG_COUNT[self.avg_combo.currentIndex()]
        self.rate_label.setText(f"~{1e6 / period:.1f} Hz per channel (device-side)")

    def _apply(self) -> None:
        ch = {0: 0xFF, 1: 0, 2: 1}[self.ch_combo.currentIndex()]
        self._apply_fn(
            ch,
            self.range_combo.currentIndex(),
            self.vbusct_combo.currentIndex(),
            self.vshct_combo.currentIndex(),
            self.avg_combo.currentIndex(),
        )
