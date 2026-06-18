"""Dialog for adding a new part (Coil, Magnet, Steel) to the design."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from ...models import DesignModel, NodeModel


# Material lists matching DoSA-2D's FEMM built-in materials
STEEL_MATERIALS = [
    "Pure Iron", "SUS_430", "S20C", "S45C",
    "1006 Steel", "1010 Steel", "1018 Steel", "1020 Steel", "1117 Steel",
    "M-19 Steel", "M-27 Steel", "M-36 Steel", "M-43 Steel", "M-45 Steel",
    "416 Stainless Steel", "430FR Stainless Steel",
    "Hiperco-50",
]

MAGNET_MATERIALS = [
    "N30", "N33", "N35", "N38", "N40", "N42", "N45", "N48", "N50", "N52",
    "N30H", "N33H", "N35H", "N38H", "N40H", "N42H", "N45H",
    "N30SH", "N33SH", "N35SH", "N38SH", "N40SH", "N42SH",
    "SmCo24", "SmCo26", "SmCo28", "SmCo30", "SmCo32",
    "Alnico5", "Alnico8",
    "Ceramic5", "Ceramic8",
]

MAGNET_DIRECTIONS = ["UP", "DOWN", "LEFT", "RIGHT"]

CONDUCTOR_MATERIALS = ["Copper", "Aluminum"]


class AddPartDialog(QDialog):
    """Dialog to add a Coil, Magnet, or Steel part."""

    def __init__(self, kind: str, design: DesignModel, parent=None):
        super().__init__(parent)
        self._kind = kind
        self._design = design
        self.setWindowTitle(f"Add {kind}")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        # --- Name ---
        name_group = QGroupBox("Part Identity")
        name_form = QFormLayout(name_group)

        existing_names = {p.name for p in design.parts}
        default_name = self._generate_name(kind, existing_names)
        self._name_edit = QLineEdit(default_name)
        name_form.addRow("Name:", self._name_edit)

        layout.addWidget(name_group)

        # --- Kind-specific properties ---
        props_group = QGroupBox(f"{kind} Properties")
        props_form = QFormLayout(props_group)

        if kind == "Coil":
            self._setup_coil_fields(props_form)
        elif kind == "Magnet":
            self._setup_magnet_fields(props_form)
        elif kind == "Steel":
            self._setup_steel_fields(props_form)

        layout.addWidget(props_group)

        # --- Geometry ---
        geom_group = QGroupBox("Geometry (Rectangle Cross-Section)")
        geom_form = QFormLayout(geom_group)
        self._setup_geometry_fields(geom_form)
        layout.addWidget(geom_group)

        # --- Buttons ---
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _generate_name(self, kind: str, existing: set[str]) -> str:
        """Generate a unique default name."""
        for i in range(1, 100):
            name = f"{kind}_{i:02d}"
            if name not in existing:
                return name
        return f"{kind}_new"

    def _setup_coil_fields(self, form: QFormLayout):
        self._material_combo = QComboBox()
        self._material_combo.addItems(CONDUCTOR_MATERIALS)
        form.addRow("Wire Material:", self._material_combo)

        self._turns_spin = QDoubleSpinBox()
        self._turns_spin.setRange(1, 100000)
        self._turns_spin.setValue(1000)
        self._turns_spin.setDecimals(0)
        form.addRow("Turns:", self._turns_spin)

        self._resistance_spin = QDoubleSpinBox()
        self._resistance_spin.setRange(0.0, 10000.0)
        self._resistance_spin.setValue(1.0)
        self._resistance_spin.setDecimals(3)
        self._resistance_spin.setSuffix(" Ω")
        form.addRow("Resistance:", self._resistance_spin)

        self._current_spin = QDoubleSpinBox()
        self._current_spin.setRange(0.0, 100000.0)
        self._current_spin.setValue(1000.0)
        self._current_spin.setDecimals(1)
        self._current_spin.setSuffix(" AT")
        form.addRow("Current (Amp-Turns):", self._current_spin)

        self._direction_combo = QComboBox()
        self._direction_combo.addItems(["IN", "OUT"])
        form.addRow("Current Direction:", self._direction_combo)

    def _setup_magnet_fields(self, form: QFormLayout):
        self._material_combo = QComboBox()
        self._material_combo.addItems(MAGNET_MATERIALS)
        self._material_combo.setCurrentText("N35")
        form.addRow("Magnet Grade:", self._material_combo)

        self._direction_combo = QComboBox()
        self._direction_combo.addItems(MAGNET_DIRECTIONS)
        form.addRow("Magnetization:", self._direction_combo)

    def _setup_steel_fields(self, form: QFormLayout):
        self._material_combo = QComboBox()
        self._material_combo.addItems(STEEL_MATERIALS)
        form.addRow("Steel Material:", self._material_combo)

    def _setup_geometry_fields(self, form: QFormLayout):
        """Rectangular cross-section geometry (R_inner, R_outer, Z_bottom, Z_top)."""
        self._r_inner = QDoubleSpinBox()
        self._r_inner.setRange(0.0, 1000.0)
        self._r_inner.setValue(5.0)
        self._r_inner.setSuffix(" mm")
        form.addRow("R inner:", self._r_inner)

        self._r_outer = QDoubleSpinBox()
        self._r_outer.setRange(0.0, 1000.0)
        self._r_outer.setValue(10.0)
        self._r_outer.setSuffix(" mm")
        form.addRow("R outer:", self._r_outer)

        self._z_bottom = QDoubleSpinBox()
        self._z_bottom.setRange(-500.0, 500.0)
        self._z_bottom.setValue(-5.0)
        self._z_bottom.setSuffix(" mm")
        form.addRow("Z bottom:", self._z_bottom)

        self._z_top = QDoubleSpinBox()
        self._z_top.setRange(-500.0, 500.0)
        self._z_top.setValue(5.0)
        self._z_top.setSuffix(" mm")
        form.addRow("Z top:", self._z_top)

    def get_part(self) -> NodeModel:
        """Build a NodeModel from dialog inputs."""
        props: dict = {}
        props["Material"] = self._material_combo.currentText()

        if self._kind == "Coil":
            props["Turns"] = str(int(self._turns_spin.value()))
            props["Resistance"] = str(self._resistance_spin.value())
            props["CurrentDirection"] = self._direction_combo.currentText()
            props["Current"] = str(self._current_spin.value())
            props["InnerDiameter"] = str(self._r_inner.value() * 2)
            props["OuterDiameter"] = str(self._r_outer.value() * 2)
            props["Height"] = str(self._z_top.value() - self._z_bottom.value())

        elif self._kind == "Magnet":
            props["MagnetDirection"] = self._direction_combo.currentText()

        # Build shape points from rectangle geometry
        r_in = self._r_inner.value()
        r_out = self._r_outer.value()
        z_bot = self._z_bottom.value()
        z_top = self._z_top.value()

        props["ShapePoints"] = [
            {"x": r_in, "y": z_bot},
            {"x": r_out, "y": z_bot},
            {"x": r_out, "y": z_top},
            {"x": r_in, "y": z_top},
        ]

        return NodeModel(
            kind=self._kind,
            name=self._name_edit.text().strip(),
            properties=props,
        )
