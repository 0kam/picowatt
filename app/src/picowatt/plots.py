"""Stacked V/I/P realtime plots with min/max decimation."""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg

from .buffer import ChannelBuffer
from .decimate import minmax_decimate

CH_COLORS = ("#4fc3f7", "#ffb74d")  # ch0 input, ch1 output
CH_NAMES = ("in", "out")
MAX_PLOT_POINTS = 2000


class LivePlots(pg.GraphicsLayoutWidget):
    """Three stacked plots (V / I / P), linked X axes, per-channel curves."""

    def __init__(self) -> None:
        super().__init__()
        pg.setConfigOptions(antialias=False)
        self.plots: list[pg.PlotItem] = []
        labels = [("Voltage", "V"), ("Current", "A"), ("Power", "W")]
        for row, (name, unit) in enumerate(labels):
            p = self.addPlot(row=row, col=0)
            p.setLabel("left", name, units=unit)
            p.showGrid(x=True, y=True, alpha=0.2)
            p.setClipToView(True)
            if row > 0:
                p.setXLink(self.plots[0])
            if row < 2:
                p.getAxis("bottom").setStyle(showValues=False)
            self.plots.append(p)
        self.plots[2].setLabel("bottom", "Time", units="s")

        # curves[plot_row][ch]
        self.curves = [
            [p.plot(pen=pg.mkPen(CH_COLORS[c], width=1), name=CH_NAMES[c]) for c in (0, 1)]
            for p in self.plots
        ]

    def update_channel(self, ch: int, buf: ChannelBuffer, t0: float, t1: float) -> None:
        t, v, i = buf.window(t0, t1)
        if len(t) == 0:
            for row in range(3):
                self.curves[row][ch].setData([], [])
            return
        p = v * i
        for row, y in enumerate((v, i, p)):
            td, yd = minmax_decimate(t, y.astype(np.float64), MAX_PLOT_POINTS)
            self.curves[row][ch].setData(td, yd)

    def set_x_range(self, t0: float, t1: float) -> None:
        self.plots[0].setXRange(t0, t1, padding=0)
