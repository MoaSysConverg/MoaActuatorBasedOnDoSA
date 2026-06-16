"""Solver configuration panel."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QComboBox,
    QCheckBox,
    QGroupBox,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from ...runner import RunConfig


class SolverPanel(QWidget):
    """Panel for configuring solver settings."""

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        # Mode & Solver group
        group = QGroupBox("Solver Configuration")
        form = QFormLayout(group)

        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["2d", "3d"])
        form.addRow("Mode:", self._mode_combo)

        self._solver_combo = QComboBox()
        self._solver_combo.addItems(["maxwell", "femm", "getdp"])
        form.addRow("Solver:", self._solver_combo)

        self._profile_combo = QComboBox()
        self._profile_combo.addItems(["default", "ws01_2020r1", "le01_2020r1", "coupling_1114_2014", "tpc_1210_2014"])
        form.addRow("Profile:", self._profile_combo)

        self._out_dir = QLineEdit("./output")
        form.addRow("Output Dir:", self._out_dir)

        self._dry_run = QCheckBox("Dry Run (no AEDT)")
        form.addRow(self._dry_run)

        self._non_graphical = QCheckBox("Non-graphical")
        self._non_graphical.setChecked(True)
        form.addRow(self._non_graphical)

        layout.addWidget(group)
        layout.addStretch()

    def set_mode(self, mode: str):
        """Set the mode combo to match the loaded file type."""
        idx = self._mode_combo.findText(mode)
        if idx >= 0:
            self._mode_combo.setCurrentIndex(idx)

    def get_run_config(self) -> RunConfig:
        """Build a RunConfig from current panel state."""
        return RunConfig(
            mode=self._mode_combo.currentText(),
            solver=self._solver_combo.currentText(),
            profile=self._profile_combo.currentText(),
            out_dir=self._out_dir.text(),
            dry_run=self._dry_run.isChecked(),
            non_graphical=self._non_graphical.isChecked(),
        )
