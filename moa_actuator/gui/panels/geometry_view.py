"""2D cross-section geometry viewer panel using matplotlib."""

from __future__ import annotations

from PyQt6.QtWidgets import QVBoxLayout, QWidget

from ...geometry import Geometry2D, extract_geometry, geometry_from_coil_params
from ...models import DesignModel, NodeModel

try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure

    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


class GeometryViewPanel(QWidget):
    """Displays 2D axisymmetric cross-section of design parts."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        if HAS_MATPLOTLIB:
            self._figure = Figure(figsize=(5, 6), dpi=100)
            self._canvas = FigureCanvas(self._figure)
            layout.addWidget(self._canvas)
            self._ax = self._figure.add_subplot(111)
        else:
            from PyQt6.QtWidgets import QLabel
            layout.addWidget(QLabel("matplotlib not available.\nInstall with: pip install matplotlib"))
            self._figure = None
            self._canvas = None
            self._ax = None

    def load_design(self, design: DesignModel):
        """Draw all parts from design."""
        if self._ax is None:
            return

        self._ax.clear()
        self._ax.set_title(f"{design.name} — Cross Section", fontsize=10)
        self._ax.set_xlabel("R (mm)")
        self._ax.set_ylabel("Z (mm)")
        self._ax.set_aspect("equal")
        self._ax.grid(True, alpha=0.3)

        colors = {
            "Coil": "#d4a017",
            "Magnet": "#c0392b",
            "Steel": "#7f8c8d",
        }

        for part in design.parts:
            geom = self._get_geometry(part)
            if geom is None or not geom.is_valid:
                continue

            color = colors.get(part.kind, "#3498db")
            xs = [p.x for p in geom.points] + [geom.points[0].x]
            ys = [p.y for p in geom.points] + [geom.points[0].y]

            self._ax.fill(xs, ys, alpha=0.4, color=color, label=part.name)
            self._ax.plot(xs, ys, color=color, linewidth=1.2)

        # Draw symmetry axis
        if design.parts:
            self._ax.axvline(x=0, color="black", linestyle="--", linewidth=0.8, alpha=0.5)

        handles, _ = self._ax.get_legend_handles_labels()
        if handles:
            self._ax.legend(fontsize=8, loc="upper right")
        self._figure.tight_layout()
        self._canvas.draw()

    def _get_geometry(self, part: NodeModel) -> Geometry2D | None:
        """Extract geometry, falling back to coil parameters."""
        geom = extract_geometry(part)
        if geom is not None and geom.is_valid:
            return geom
        if part.kind == "Coil":
            props = part.properties
            inner_d = float(props.get("InnerDiameter", 0))
            outer_d = float(props.get("OuterDiameter", 0))
            height = float(props.get("Height", 0))
            if inner_d > 0 and outer_d > 0 and height > 0:
                return geometry_from_coil_params(part.name, inner_d, outer_d, height)
        return None
