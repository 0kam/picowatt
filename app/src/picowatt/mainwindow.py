"""picowatt GUI: realtime V/I/P plots with device control."""

from __future__ import annotations

import sys

import numpy as np
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QToolBar,
)

from . import protocol as proto
from .buffer import ChannelBuffer
from .device import find_ports
from .plots import LivePlots
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

        self.plots = LivePlots()
        self.setCentralWidget(self.plots)
        self._build_toolbar()
        self._build_statusbar()

        self.plot_timer = QTimer(self)
        self.plot_timer.setInterval(33)  # ~30 Hz
        self.plot_timer.timeout.connect(self._refresh_plots)
        self.plot_timer.start()

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

    def _build_statusbar(self) -> None:
        self.status_conn = QLabel("disconnected")
        self.status_rate = QLabel("")
        self.status_drops = QLabel("")
        for w in (self.status_conn, self.status_rate, self.status_drops):
            self.statusBar().addWidget(w)
            w.setMargin(4)

    # -- connection lifecycle ------------------------------------------------

    def _refresh_ports(self) -> None:
        self.port_combo.clear()
        self.port_combo.addItems(find_ports())

    def _toggle_connect(self) -> None:
        if self.worker is not None:
            self.worker.shutdown()
            return
        port = self.port_combo.currentText() or None
        self.worker = SerialWorker(port)
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

    def _on_config(self, cfg: proto.Config) -> None:
        self.mode = cfg.mode
        self.status_drops.setText(f"ring drops: {cfg.drops}")

    def _on_session_end(self) -> None:
        if self.worker is not None:
            self.worker.wait(2000)
            self.worker = None
        self.streaming = False
        self.connect_btn.setText("Connect")
        self.start_btn.setText("Start")
        self.start_btn.setEnabled(False)
        self.status_conn.setText("disconnected")

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

    # -- data path -----------------------------------------------------------

    def _on_samples(self, ch: int, t: np.ndarray, v: np.ndarray, i: np.ndarray) -> None:
        self.buffers[ch].append(t, v, i)

    def _on_stats(self, gaps: int, _drops: int) -> None:
        self.status_rate.setText(f"frame gaps: {gaps}")

    def _refresh_plots(self) -> None:
        latest = [b.latest_t() for b in self.buffers]
        t_last = max((t for t in latest if t is not None), default=None)
        if t_last is None:
            return
        win = self.window_spin.value()
        t0, t1 = t_last - win, t_last
        nch = 2 if self.mode == 1 else 1
        for c in range(2):
            if c < nch and self.buffers[c].count:
                self.plots.update_channel(c, self.buffers[c], t0, t1)
            else:
                self.plots.update_channel(c, ChannelBuffer(1), 0, 0)
        if self.follow_check.isChecked():
            self.plots.set_x_range(t0, t1)

    def closeEvent(self, event) -> None:
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
