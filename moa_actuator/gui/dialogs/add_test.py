"""Dialog for adding a new test (Force, Stroke, Current) to the design."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)

from ...models import DesignModel, TestModel


class AddTestDialog(QDialog):
    """Dialog to add a Force, Stroke, or Current test."""

    def __init__(self, kind: str, design: DesignModel, parent=None):
        super().__init__(parent)
        self._kind = kind
        self._design = design
        self.setWindowTitle(f"Add {kind}")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)

        # --- Name ---
        name_group = QGroupBox("Test Identity")
        name_form = QFormLayout(name_group)

        existing_names = {t.name for t in design.tests}
        default_name = self._generate_name(kind, existing_names)
        self._name_edit = QLineEdit(default_name)
        name_form.addRow("Name:", self._name_edit)
        layout.addWidget(name_group)

        # --- Parameters ---
        params_group = QGroupBox("Parameters")
        params_form = QFormLayout(params_group)

        if kind == "ForceTest":
            self._setup_force_fields(params_form)
        elif kind == "StrokeTest":
            self._setup_stroke_fields(params_form)
        elif kind == "CurrentTest":
            self._setup_current_fields(params_form)

        layout.addWidget(params_group)

        # --- Buttons ---
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _generate_name(self, kind: str, existing: set[str]) -> str:
        for i in range(1, 100):
            name = f"{kind}_{i:02d}"
            if name not in existing:
                return name
        return f"{kind}_new"

    def _setup_force_fields(self, form: QFormLayout):
        self._current_spin = QDoubleSpinBox()
        self._current_spin.setRange(0.0, 100000.0)
        self._current_spin.setValue(1000.0)
        self._current_spin.setSuffix(" AT")
        form.addRow("Current:", self._current_spin)

        self._stroke_spin = QDoubleSpinBox()
        self._stroke_spin.setRange(-100.0, 100.0)
        self._stroke_spin.setValue(0.0)
        self._stroke_spin.setSuffix(" mm")
        form.addRow("Stroke Position:", self._stroke_spin)

    def _setup_stroke_fields(self, form: QFormLayout):
        self._current_spin = QDoubleSpinBox()
        self._current_spin.setRange(0.0, 100000.0)
        self._current_spin.setValue(1000.0)
        self._current_spin.setSuffix(" AT")
        form.addRow("Fixed Current:", self._current_spin)

        self._stroke_start = QDoubleSpinBox()
        self._stroke_start.setRange(-100.0, 100.0)
        self._stroke_start.setValue(0.0)
        self._stroke_start.setSuffix(" mm")
        form.addRow("Stroke Start:", self._stroke_start)

        self._stroke_end = QDoubleSpinBox()
        self._stroke_end.setRange(-100.0, 100.0)
        self._stroke_end.setValue(5.0)
        self._stroke_end.setSuffix(" mm")
        form.addRow("Stroke End:", self._stroke_end)

        self._stroke_step = QDoubleSpinBox()
        self._stroke_step.setRange(0.1, 50.0)
        self._stroke_step.setValue(1.0)
        self._stroke_step.setSuffix(" mm")
        form.addRow("Stroke Step:", self._stroke_step)

    def _setup_current_fields(self, form: QFormLayout):
        self._stroke_spin = QDoubleSpinBox()
        self._stroke_spin.setRange(-100.0, 100.0)
        self._stroke_spin.setValue(0.0)
        self._stroke_spin.setSuffix(" mm")
        form.addRow("Fixed Stroke:", self._stroke_spin)

        self._current_start = QDoubleSpinBox()
        self._current_start.setRange(0.0, 100000.0)
        self._current_start.setValue(200.0)
        self._current_start.setSuffix(" AT")
        form.addRow("Current Start:", self._current_start)

        self._current_end = QDoubleSpinBox()
        self._current_end.setRange(0.0, 100000.0)
        self._current_end.setValue(1000.0)
        self._current_end.setSuffix(" AT")
        form.addRow("Current End:", self._current_end)

        self._current_step = QDoubleSpinBox()
        self._current_step.setRange(1.0, 10000.0)
        self._current_step.setValue(200.0)
        self._current_step.setSuffix(" AT")
        form.addRow("Current Step:", self._current_step)

    def get_test(self) -> TestModel:
        """Build a TestModel from dialog inputs."""
        props: dict = {}

        if self._kind == "ForceTest":
            props["Current"] = self._current_spin.value()
            props["Stroke"] = self._stroke_spin.value()

        elif self._kind == "StrokeTest":
            props["Current"] = self._current_spin.value()
            props["StrokeStart"] = self._stroke_start.value()
            props["StrokeEnd"] = self._stroke_end.value()
            props["StrokeStep"] = self._stroke_step.value()

        elif self._kind == "CurrentTest":
            props["Stroke"] = self._stroke_spin.value()
            props["CurrentStart"] = self._current_start.value()
            props["CurrentEnd"] = self._current_end.value()
            props["CurrentStep"] = self._current_step.value()

        return TestModel(
            name=self._name_edit.text().strip(),
            kind=self._kind,
            properties=props,
        )
