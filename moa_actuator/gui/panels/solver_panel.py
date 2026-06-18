"""Solver configuration panel with inline profile details."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QCheckBox,
    QGroupBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...profiles import MaxwellProfile, get_profile, list_profiles
from ...runner import RunConfig

SOLUTION_TYPES = [
    "MagnetostaticZ",
    "TransientZ",
    "Magnetostatic",
    "Transient",
    "EddyCurrent",
]


class SolverPanel(QWidget):
    """Panel for configuring solver settings with full profile details."""

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        # --- Solver group ---
        solver_group = QGroupBox("Solver")
        solver_form = QFormLayout(solver_group)

        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["2d", "3d"])
        solver_form.addRow("Mode:", self._mode_combo)

        self._solver_combo = QComboBox()
        self._solver_combo.addItems(["maxwell", "femm", "getdp"])
        solver_form.addRow("Solver:", self._solver_combo)

        self._out_dir = QLineEdit("./output")
        solver_form.addRow("Output Dir:", self._out_dir)

        self._dry_run = QCheckBox("Dry Run (no AEDT)")
        solver_form.addRow(self._dry_run)

        self._non_graphical = QCheckBox("Non-graphical")
        self._non_graphical.setChecked(True)
        solver_form.addRow(self._non_graphical)

        self._new_desktop = QCheckBox("New Desktop (uncheck to use running AEDT)")
        self._new_desktop.setChecked(True)
        solver_form.addRow(self._new_desktop)

        layout.addWidget(solver_group)

        # --- Profile group ---
        profile_group = QGroupBox("Profile Settings")
        profile_layout = QVBoxLayout(profile_group)

        # Profile selector row
        profile_row = QHBoxLayout()
        self._profile_combo = QComboBox()
        self._profile_combo.currentTextChanged.connect(self._on_profile_changed)
        profile_row.addWidget(QLabel("Preset:"))
        profile_row.addWidget(self._profile_combo, stretch=1)
        profile_layout.addLayout(profile_row)

        # Profile detail fields (editable)
        detail_form = QFormLayout()

        self._solution_type_combo = QComboBox()
        self._solution_type_combo.addItems(SOLUTION_TYPES)
        self._solution_type_combo.setEditable(True)
        self._solution_type_combo.currentTextChanged.connect(self._on_solution_type_changed)
        detail_form.addRow("Solution Type:", self._solution_type_combo)

        self._time_step_label = QLabel("Time Step:")
        self._time_step_edit = QLineEdit("0.2ms")
        detail_form.addRow(self._time_step_label, self._time_step_edit)

        self._stop_time_label = QLabel("Stop Time:")
        self._stop_time_edit = QLineEdit("20ms")
        detail_form.addRow(self._stop_time_label, self._stop_time_edit)

        self._mesh_hint_combo = QComboBox()
        self._mesh_hint_combo.addItems(["balanced", "medium_fine", "fine", "coarse"])
        self._mesh_hint_combo.setEditable(True)
        detail_form.addRow("Mesh Hint:", self._mesh_hint_combo)

        self._notes_label = QLabel("")
        self._notes_label.setWordWrap(True)
        self._notes_label.setStyleSheet("color: #666; font-style: italic;")
        detail_form.addRow("Notes:", self._notes_label)

        self._source_label = QLabel("")
        self._source_label.setStyleSheet("color: #888; font-size: 10px;")
        detail_form.addRow("Source:", self._source_label)

        profile_layout.addLayout(detail_form)
        layout.addWidget(profile_group)

        layout.addStretch()

        # Load profiles into combo
        self._load_profile_list()

    def _load_profile_list(self):
        """Populate the profile combo from config."""
        self._profile_combo.blockSignals(True)
        self._profile_combo.clear()
        profiles = list_profiles()
        for p in profiles:
            self._profile_combo.addItem(p["name"])
        self._profile_combo.blockSignals(False)
        if self._profile_combo.count() > 0:
            self._on_profile_changed(self._profile_combo.currentText())

    def _on_profile_changed(self, name: str):
        """Load selected profile's details into the editable fields."""
        if not name:
            return
        try:
            p = get_profile(name)
        except ValueError:
            return

        self._solution_type_combo.setCurrentText(p.solution_type)
        self._time_step_edit.setText(p.time_step)
        self._stop_time_edit.setText(p.stop_time)
        self._mesh_hint_combo.setCurrentText(p.mesh_hint)
        self._notes_label.setText(p.notes)
        self._source_label.setText(p.source_pdf)
        self._on_solution_type_changed(p.solution_type)

    def _on_solution_type_changed(self, solution_type: str):
        """Show/hide transient fields based on solution type."""
        is_transient = "transient" in solution_type.lower() or "eddy" in solution_type.lower()
        self._time_step_label.setVisible(is_transient)
        self._time_step_edit.setVisible(is_transient)
        self._stop_time_label.setVisible(is_transient)
        self._stop_time_edit.setVisible(is_transient)

    def set_mode(self, mode: str):
        """Set the mode combo to match the loaded file type."""
        idx = self._mode_combo.findText(mode)
        if idx >= 0:
            self._mode_combo.setCurrentIndex(idx)

    def set_solver(self, solver: str):
        """Set the solver combo."""
        idx = self._solver_combo.findText(solver)
        if idx >= 0:
            self._solver_combo.setCurrentIndex(idx)

    def get_run_config(self) -> RunConfig:
        """Build a RunConfig from current panel state, using edited profile values."""
        solution_type = self._solution_type_combo.currentText()
        is_transient = "transient" in solution_type.lower() or "eddy" in solution_type.lower()
        return RunConfig(
            mode=self._mode_combo.currentText(),
            solver=self._solver_combo.currentText(),
            profile=self._profile_combo.currentText(),
            out_dir=self._out_dir.text(),
            dry_run=self._dry_run.isChecked(),
            non_graphical=self._non_graphical.isChecked(),
            new_desktop=self._new_desktop.isChecked(),
            solution_type=solution_type,
            time_step=self._time_step_edit.text() if is_transient else "",
            stop_time=self._stop_time_edit.text() if is_transient else "",
            mesh_hint=self._mesh_hint_combo.currentText(),
        )
