"""picowatt GUI: realtime V/I/P plots with device control."""

from __future__ import annotations

import sys

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDockWidget,
    QDoubleSpinBox,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QToolBar,
)

from . import protocol as proto
from .buffer import ChannelBuffer
from .calibration import CalibrationStore
from .csv_logger import CsvLogger
from .device import find_ports
from .dialogs import AdvancedSettingsDialog, CalibrationDialog
from .measure import check_vbus, integrate_region
from .plots import CH_NAMES, LivePlots
from .serial_link import SerialWorker

BUFFER_CAPACITY = 9_000_000  # ~45 min at 3.3 kHz, ~144 MB


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("picowatt")
        self.resize(1100, 750)

        self.worker: SerialWorker | None = None
        self.buffers = [ChannelBuffer(BUFFER_CAPACITY) for _ in range(2)]
        self.streaming = False
        self.mode = 0
        self.logger: CsvLogger | None = None
        self.cal_store = CalibrationStore()
        self.config: proto.Config | None = None
        # After a calibration is applied, buffered samples older than this
        # were converted with the previous calibration — never reuse them.
        self._cal_markers: list[float | None] = [None, None]
        self._disp_t1: float | None = None  # smoothed right edge for follow mode

        self.plots = LivePlots()
        self.setCentralWidget(self.plots)
        self._build_toolbar()
        self._build_statusbar()
        self._build_region_dock()

        self.region_timer = QTimer(self)
        self.region_timer.setInterval(150)
        self.region_timer.setSingleShot(True)
        self.region_timer.timeout.connect(self._update_region_panel)
        self.plots.region.sigRegionChanged.connect(
            lambda: self.region_timer.start()
        )

        self.plot_timer = QTimer(self)
        self.plot_timer.setInterval(33)  # ~30 Hz
        self.plot_timer.timeout.connect(self._refresh_plots)
        self.plot_timer.start()

        # Bus-voltage plausibility check (floating GND / open VBus jumper).
        self.health_timer = QTimer(self)
        self.health_timer.setInterval(500)
        self.health_timer.timeout.connect(self._check_bus_health)
        self.health_timer.start()

        # Manual pan/zoom on the time axis takes over from follow mode.
        self.plots.plots[0].getViewBox().sigRangeChangedManually.connect(
            lambda *_: self.follow_check.setChecked(False)
        )

    # -- UI scaffolding ----------------------------------------------------

    def _build_toolbar(self) -> None:
        tb = QToolBar("Controls")
        tb.setMovable(False)
        self.addToolBar(tb)

        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(220)
        self._refresh_ports()
        tb.addWidget(QLabel(" Port: "))
        tb.addWidget(self.port_combo)

        refresh = QPushButton("⟳")
        refresh.setFixedWidth(28)
        refresh.clicked.connect(self._refresh_ports)
        tb.addWidget(refresh)

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self._toggle_connect)
        tb.addWidget(self.connect_btn)

        self.start_btn = QPushButton("Start")
        self.start_btn.setEnabled(False)
        self.start_btn.clicked.connect(self._toggle_stream)
        tb.addWidget(self.start_btn)

        tb.addSeparator()
        tb.addWidget(QLabel(" Mode: "))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["single", "dual"])
        self.mode_combo.currentIndexChanged.connect(self._mode_changed)
        tb.addWidget(self.mode_combo)

        tb.addWidget(QLabel(" Preset: "))
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(list(proto.PRESETS))
        self.preset_combo.setCurrentText("fast-dual")
        self.preset_combo.currentTextChanged.connect(self._preset_changed)
        tb.addWidget(self.preset_combo)

        tb.addWidget(QLabel(" Range: "))
        self.range_combo = QComboBox()
        self.range_combo.addItems(["±163.84 mV (8 µA)", "±40.96 mV (2 µA)"])
        self.range_combo.currentIndexChanged.connect(self._preset_changed)
        tb.addWidget(self.range_combo)

        tb.addSeparator()
        tb.addWidget(QLabel(" Window: "))
        self.window_spin = QDoubleSpinBox()
        self.window_spin.setRange(0.1, 2700.0)
        self.window_spin.setValue(10.0)
        self.window_spin.setSuffix(" s")
        tb.addWidget(self.window_spin)

        self.follow_check = QCheckBox("Follow")
        self.follow_check.setChecked(True)
        tb.addWidget(self.follow_check)

        reset_view_btn = QPushButton("Reset view")
        reset_view_btn.clicked.connect(self._reset_view)
        tb.addWidget(reset_view_btn)

        tb.addSeparator()
        self.measure_check = QCheckBox("Measure")
        self.measure_check.toggled.connect(self._toggle_measure)
        tb.addWidget(self.measure_check)

        self.log_btn = QPushButton("Log CSV…")
        self.log_btn.setCheckable(True)
        self.log_btn.toggled.connect(self._toggle_logging)
        tb.addWidget(self.log_btn)

        tb.addSeparator()
        self.cal_btn = QPushButton("Calibrate…")
        self.cal_btn.setEnabled(False)
        self.cal_btn.clicked.connect(self._open_calibration)
        tb.addWidget(self.cal_btn)

        self.adv_btn = QPushButton("Advanced…")
        self.adv_btn.setEnabled(False)
        self.adv_btn.clicked.connect(self._open_advanced)
        tb.addWidget(self.adv_btn)

    def _build_statusbar(self) -> None:
        self.status_conn = QLabel("disconnected")
        self.status_rate = QLabel("")
        self.status_drops = QLabel("")
        self.status_log = QLabel("")
        for w in (self.status_conn, self.status_rate, self.status_drops, self.status_log):
            self.statusBar().addWidget(w)
            w.setMargin(4)
        # Right-aligned, red; only visible while a channel's VBUS looks wrong.
        self.status_warn = QLabel("")
        self.status_warn.setMargin(4)
        self.status_warn.setStyleSheet("color: #c62828; font-weight: bold;")
        self.status_warn.setToolTip(
            "The bus voltage cannot be a real DC supply. Usual causes: the supply "
            "'-' is not connected to the GND terminal (J5), or the VBus jumper on "
            "the INA228 is open. See docs/troubleshooting.md")
        self.statusBar().addPermanentWidget(self.status_warn)

    def _build_region_dock(self) -> None:
        self.region_dock = QDockWidget("Region", self)
        self.region_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetClosable)
        self.region_label = QLabel("enable Measure and drag the region")
        self.region_label.setTextFormat(Qt.TextFormat.RichText)
        self.region_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.region_label.setMargin(8)
        self.region_dock.setWidget(self.region_label)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.region_dock)
        self.region_dock.hide()

    # -- connection lifecycle ------------------------------------------------

    def _refresh_ports(self) -> None:
        self.port_combo.clear()
        self.port_combo.addItems(find_ports())

    def _toggle_connect(self) -> None:
        if self.worker is not None:
            self.worker.shutdown()
            return
        # Each session restarts device time at 0 — stale samples from the
        # previous session would break the buffers' time monotonicity.
        self.buffers = [ChannelBuffer(BUFFER_CAPACITY) for _ in range(2)]
        self._disp_t1 = None
        self._cal_markers = [None, None]
        port = self.port_combo.currentText() or None
        self.worker = SerialWorker(port, cal_store=self.cal_store)
        self.worker.connected.connect(self._on_connected)
        self.worker.config_updated.connect(self._on_config)
        self.worker.samples.connect(self._on_samples)
        self.worker.stats.connect(self._on_stats)
        self.worker.error.connect(self._on_error)
        self.worker.finished_session.connect(self._on_session_end)
        self.worker.start()
        self.connect_btn.setText("Disconnect")

    def _on_connected(self, hello: proto.HelloAck) -> None:
        fw = ".".join(map(str, hello.fw_version))
        self.status_conn.setText(
            f"fw {fw}  board {hello.board_id}  ch 0x{hello.ch_present:02X}"
        )
        self.start_btn.setEnabled(True)
        self.mode_combo.setEnabled(bool(hello.ch_present & 2))
        self.cal_btn.setEnabled(True)
        self.adv_btn.setEnabled(True)

    def _on_config(self, cfg: proto.Config) -> None:
        self.mode = cfg.mode
        self.config = cfg
        self.status_drops.setText(f"ring drops: {cfg.drops}")

    def _on_session_end(self) -> None:
        if self.worker is not None:
            self.worker.wait(2000)
            self.worker = None
        self.streaming = False
        self.connect_btn.setText("Connect")
        self.start_btn.setText("Start")
        self.start_btn.setEnabled(False)
        self.cal_btn.setEnabled(False)
        self.adv_btn.setEnabled(False)
        self.status_conn.setText("disconnected")
        self.status_warn.setText("")

    def _on_error(self, msg: str) -> None:
        QMessageBox.warning(self, "picowatt", msg)

    # -- device commands -----------------------------------------------------

    def _toggle_stream(self) -> None:
        if self.worker is None:
            return
        if self.streaming:
            self.worker.submit(lambda d: d.stop())
            self.streaming = False
            self.start_btn.setText("Start")
        else:
            self.worker.submit(lambda d: d.start())
            self.streaming = True
            self.start_btn.setText("Stop")

    def _mode_changed(self, idx: int) -> None:
        if self.worker is not None:
            self.worker.submit(lambda d: d.set_mode(idx))

    def _preset_changed(self) -> None:
        if self.worker is None:
            return
        preset = self.preset_combo.currentText()
        adcrange = self.range_combo.currentIndex()
        self.worker.submit(lambda d: d.set_preset(preset, adcrange=adcrange))

    # -- region measurement ----------------------------------------------------

    def _toggle_measure(self, on: bool) -> None:
        self.plots.show_region(on)
        self.region_dock.setVisible(on)
        if on:
            self._update_region_panel()

    @staticmethod
    def _fmt(val: float, unit: str) -> str:
        for factor, prefix in ((1.0, ""), (1e3, "m"), (1e6, "µ")):
            if abs(val) * factor >= 1.0 or prefix == "µ":
                return f"{val * factor:.4f} {prefix}{unit}"
        return f"{val:.4f} {unit}"

    def _update_region_panel(self) -> None:
        if not self.measure_check.isChecked():
            return
        t0, t1 = self.plots.region_bounds()
        nch = 2 if self.mode == 1 else 1
        parts = [f"<b>Δt</b> {t1 - t0:.3f} s"]
        results = {}
        for c in range(nch):
            r = integrate_region(self.buffers[c], t0, t1)
            results[c] = r
            if r is None:
                parts.append(f"<br><b>ch{c}</b>: no data")
                continue
            parts.append(
                f"<br><b>ch{c} ({CH_NAMES[c]})</b>  n={r.n}"
                f"<br>&nbsp;&nbsp;V<sub>avg</sub> {self._fmt(r.avg_v, 'V')}"
                f"<br>&nbsp;&nbsp;I<sub>avg</sub> {self._fmt(r.avg_i, 'A')}"
                f"<br>&nbsp;&nbsp;P<sub>avg</sub> {self._fmt(r.avg_w, 'W')}"
                f"<br>&nbsp;&nbsp;<b>E {self._fmt(r.wh, 'Wh')}</b>"
                f"<br>&nbsp;&nbsp;Q {self._fmt(r.ah, 'Ah')}"
            )
        if nch == 2 and results.get(0) and results.get(1) and results[0].wh > 0:
            eff = 100.0 * results[1].wh / results[0].wh
            parts.append(f"<br><b>η</b> {eff:.2f} %")
        self.region_label.setText("".join(parts))

    # -- calibration / advanced settings ---------------------------------------

    def _mean_current(self, ch: int) -> tuple[float, int]:
        """Mean displayed current over the last second of post-calibration data."""
        buf = self.buffers[ch]
        t_last = buf.latest_t()
        if t_last is None:
            return 0.0, 0
        t_lo = t_last - 1.0
        marker = self._cal_markers[ch]
        if marker is not None:
            # 0.3 s margin covers the config round-trip on the worker thread
            t_lo = max(t_lo, marker + 0.3)
        if t_last - t_lo < 0.4:
            return 0.0, 0  # not enough fresh data yet
        t, _v, i = buf.window(t_lo, t_last)
        if len(i) == 0:
            return 0.0, 0
        return float(np.mean(i.astype(np.float64))), len(t)

    def _mark_calibration(self, ch: int) -> None:
        self._cal_markers[ch] = self.buffers[ch].latest_t()

    def _open_calibration(self) -> None:
        if self.worker is None or self.worker.board_id is None or self.config is None:
            return
        board = self.worker.board_id

        def get_shunt_cal(ch: int) -> int:
            assert self.config is not None
            return self.config.ch[ch].shunt_cal

        def apply_zero(ch: int, delta_a: float) -> None:
            assert self.config is not None and self.worker is not None
            adcrange = self.config.ch[ch].adcrange
            old = self.cal_store.get(board, ch).offset_for(adcrange)
            self.cal_store.set_zero_offset(board, ch, adcrange, old + delta_a)
            # No-op command forces a config round-trip -> worker reloads offsets
            self.worker.submit(lambda d: None)
            self._mark_calibration(ch)

        def apply_gain(ch: int, new_cal: int) -> None:
            assert self.worker is not None
            self.cal_store.set_shunt_cal(board, ch, new_cal)
            self.worker.submit(lambda d: d.set_shunt_cal(ch, new_cal))
            self._mark_calibration(ch)

        def apply_reset(ch: int) -> None:
            assert self.config is not None and self.worker is not None
            from .calibration import DEFAULT_SHUNT_CAL, ChannelCal
            self.cal_store.set(board, ch, ChannelCal())
            self.worker.submit(lambda d: d.set_shunt_cal(ch, DEFAULT_SHUNT_CAL))
            self._mark_calibration(ch)

        CalibrationDialog(
            self, self._mean_current, get_shunt_cal, apply_zero, apply_gain, apply_reset
        ).exec()

    def _open_advanced(self) -> None:
        if self.worker is None or self.config is None:
            return

        def apply_fn(ch: int, adcrange: int, vbusct: int, vshct: int, avg: int) -> None:
            assert self.worker is not None
            self.worker.submit(lambda d: d.set_adc(ch, adcrange, vbusct, vshct, avg))

        AdvancedSettingsDialog(self, self.config, apply_fn).exec()

    # -- CSV logging -----------------------------------------------------------

    def _toggle_logging(self, on: bool) -> None:
        if on:
            path, _ = QFileDialog.getSaveFileName(
                self, "Log to CSV", "picowatt.csv", "CSV files (*.csv)"
            )
            if not path:
                self.log_btn.setChecked(False)
                return
            meta = {"device": self.status_conn.text()}
            if self.worker is not None and self.worker.isRunning():
                meta["mode"] = "dual" if self.mode == 1 else "single"
            self.logger = CsvLogger(path, meta)
            self.log_btn.setText("Stop log")
            self.status_log.setText(f"logging → {path}")
        else:
            if self.logger is not None:
                self.logger.stop()
                self.status_log.setText(
                    f"logged {self.logger.rows_written} rows"
                    + (f" ({self.logger.dropped_batches} batches dropped)"
                       if self.logger.dropped_batches else "")
                )
                self.logger = None
            self.log_btn.setText("Log CSV…")

    # -- data path -----------------------------------------------------------

    def _on_samples(self, ch: int, t: np.ndarray, v: np.ndarray, i: np.ndarray) -> None:
        self.buffers[ch].append(t, v, i)
        if self.logger is not None:
            self.logger.log(ch, t, v, i)

    def _on_stats(self, gaps: int, _drops: int) -> None:
        self.status_rate.setText(f"frame gaps: {gaps}")

    def _check_bus_health(self) -> None:
        """Warn in the status bar when VBUS over the last second is implausible."""
        if not self.streaming:
            return
        nch = 2 if self.mode == 1 else 1
        msgs = []
        for c in range(nch):
            buf = self.buffers[c]
            t_last = buf.latest_t()
            if t_last is None:
                continue
            _t, v, _i = buf.window(t_last - 1.0, t_last)
            if len(v) < 10:
                continue
            h = check_vbus(v)
            if h.problem:
                msgs.append(f"ch{c}: {h.problem}")
        if msgs:
            self.status_warn.setText("\u26a0 " + "   ".join(msgs)
                                     + " \u2014 check GND link to J5 / VBus jumper")
        else:
            self.status_warn.setText("")

    def _reset_view(self) -> None:
        self.plots.reset_view()
        self._disp_t1 = None
        self.follow_check.setChecked(True)

    def _refresh_plots(self) -> None:
        latest = [b.latest_t() for b in self.buffers]
        t_last = max((t for t in latest if t is not None), default=None)
        if t_last is None:
            return
        if self.follow_check.isChecked():
            # Exponential approach to the newest sample: data arrives in USB
            # bursts, and snapping the range to each burst looks jerky.
            if self._disp_t1 is None or t_last < self._disp_t1:
                self._disp_t1 = t_last
            else:
                self._disp_t1 += 0.35 * (t_last - self._disp_t1)
            t1 = self._disp_t1
            t0 = t1 - self.window_spin.value()
        else:
            # Feed whatever time range the user has panned/zoomed to.
            x0, x1 = self.plots.plots[0].viewRange()[0]
            pad = (x1 - x0) * 0.1
            t0, t1 = x0 - pad, x1 + pad
        nch = 2 if self.mode == 1 else 1
        for c in range(2):
            if c < nch and self.buffers[c].count:
                self.plots.update_channel(c, self.buffers[c], t0, t1)
            else:
                self.plots.update_channel(c, ChannelBuffer(1), 0, 0)
        if self.follow_check.isChecked():
            self.plots.set_x_range(t0, t1)

    def closeEvent(self, event) -> None:
        if self.logger is not None:
            self.logger.stop()
        if self.worker is not None:
            self.worker.shutdown()
            self.worker.wait(2000)
        event.accept()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("picowatt")
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
