"""Material info panel — shows B-H curve for selected steel part."""

from __future__ import annotations

from PyQt6.QtWidgets import QGroupBox, QVBoxLayout, QWidget, QPushButton

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure


class MaterialViewPanel(QWidget):
    """Panel displaying B-H curve for the selected part's material."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("Material B-H Curve")
        group_layout = QVBoxLayout(group)

        self._fig = Figure(figsize=(4, 3), dpi=80)
        self._ax = self._fig.add_subplot(111)
        self._canvas = FigureCanvasQTAgg(self._fig)
        group_layout.addWidget(self._canvas)

        self._btn_manage = QPushButton("Manage Materials...")
        self._btn_manage.clicked.connect(self._on_manage_materials)
        group_layout.addWidget(self._btn_manage)

        layout.addWidget(group)

        # Cache parsed B-H data
        self._bh_cache: dict | None = None
        self._current_material: str | None = None

    def _on_manage_materials(self):
        """Open the material manager dialog and reset cache on save."""
        from ..dialogs.material_manager import MaterialManagerDialog
        dialog = MaterialManagerDialog(self)
        if dialog.exec():
            self._bh_cache = None
            if self._current_material:
                self.show_material(self._current_material)

    def show_material(self, material_name: str):
        """Plot B-H curve for the given material name."""
        self._current_material = material_name
        self._ax.clear()

        curve = self._find_bh_curve(material_name)
        if curve is None:
            self._ax.text(
                0.5, 0.5,
                f"No B-H data for\n'{material_name}'",
                ha="center", va="center",
                transform=self._ax.transAxes, fontsize=9,
            )
            self._ax.set_title(material_name)
        else:
            self._ax.plot(curve.H, curve.B, "b-", linewidth=1.5)
            self._ax.set_xlabel("H (A/m)")
            self._ax.set_ylabel("B (T)")
            self._ax.set_title(f"{material_name}")
            self._ax.grid(True, alpha=0.3)

        self._fig.tight_layout()
        self._canvas.draw()

    def _find_bh_curve(self, material_name: str):
        """Look up B-H curve from bundled DoSA_MS.dmat."""
        if self._bh_cache is None:
            try:
                from ...bh_data import parse_dmat_file
                self._bh_cache = parse_dmat_file()
            except Exception:
                self._bh_cache = {}

        if not self._bh_cache:
            return None

        try:
            from ...bh_data import resolve_bh_curve
            return resolve_bh_curve(material_name, self._bh_cache)
        except Exception:
            return None
