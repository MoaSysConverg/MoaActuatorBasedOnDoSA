"""Dialog for editing part geometry coordinates interactively with live preview."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QAbstractItemView,
)

try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

from ...geometry import Geometry2D, Point2D, extract_geometry


class EditGeometryDialog(QDialog):
    """Interactive editor for part geometry vertices."""

    def __init__(self, part, on_changed_callback=None, parent=None):
        super().__init__(parent)
        self.part = part
        self.on_changed_callback = on_changed_callback
        self.setWindowTitle(f"Edit Geometry — {part.name}")
        self.resize(800, 500)

        # Find or create Shape node
        self.shape_node = None
        for child in part.children:
            if child.kind == "Shape":
                self.shape_node = child
                break
        if self.shape_node is None:
            from ...models import NodeModel
            self.shape_node = NodeModel(kind="Shape", name="")
            part.children.append(self.shape_node)

        # Main horizontal layout
        main_layout = QHBoxLayout(self)

        # --- Left Panel: Preview ---
        if HAS_MATPLOTLIB:
            preview_container = QWidget()
            preview_layout = QVBoxLayout(preview_container)
            preview_layout.setContentsMargins(0, 0, 0, 0)
            
            self._fig = Figure(figsize=(4, 4), dpi=100)
            self._canvas = FigureCanvas(self._fig)
            self._ax = self._fig.add_subplot(111)
            self._fig.canvas.mpl_connect("button_press_event", self._on_plot_click)
            preview_layout.addWidget(self._canvas)
            main_layout.addWidget(preview_container, stretch=1)
        else:
            from PyQt6.QtWidgets import QLabel
            main_layout.addWidget(QLabel("Preview requires matplotlib"), stretch=1)

        # --- Right Panel: Coordinates & Buttons ---
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(2)
        self._table.setHorizontalHeaderLabels(["R (mm)", "Z (mm)"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.itemChanged.connect(self._on_cell_changed)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        right_layout.addWidget(self._table, stretch=1)

        # Action Buttons Layout
        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton("Add Point")
        self.btn_insert = QPushButton("Insert Point")
        self.btn_delete = QPushButton("Delete Point")
        self.btn_up = QPushButton("▲ Move Up")
        self.btn_down = QPushButton("▼ Move Down")

        self.btn_add.clicked.connect(self._add_point)
        self.btn_insert.clicked.connect(self._insert_point)
        self.btn_delete.clicked.connect(self._delete_point)
        self.btn_up.clicked.connect(self._move_up)
        self.btn_down.clicked.connect(self._move_down)

        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_insert)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addWidget(self.btn_up)
        btn_layout.addWidget(self.btn_down)
        right_layout.addLayout(btn_layout)

        # Bottom Buttons
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.accept)
        bottom_layout.addWidget(self.btn_close)
        right_layout.addLayout(bottom_layout)

        main_layout.addWidget(right_container, stretch=1)

        # Load initial geometry points
        self._updating = False
        self._load_points()

    def _load_points(self):
        """Extract points from the shape node and load into table."""
        self._updating = True
        self._table.setRowCount(0)

        geom = extract_geometry(self.part)
        points = geom.points if geom and geom.points else []

        # Default points if empty
        if not points:
            points = [Point2D(0.0, 0.0), Point2D(10.0, 0.0), Point2D(10.0, 10.0), Point2D(0.0, 10.0)]

        self._table.setRowCount(len(points))
        for idx, pt in enumerate(points):
            self._table.setItem(idx, 0, QTableWidgetItem(f"{pt.x:.4f}"))
            self._table.setItem(idx, 1, QTableWidgetItem(f"{pt.y:.4f}"))

        self._updating = False
        self._update_all()

    def _on_cell_changed(self, item):
        """Re-read coordinates, redraw, and notify callback on cell change."""
        if self._updating:
            return
        
        # Verify it's a valid float
        try:
            float(item.text())
            item.setBackground(Qt.GlobalColor.white)
        except ValueError:
            item.setBackground(Qt.GlobalColor.red)
            return

        self._update_all()

    def _update_all(self):
        """Update part model, update dialog preview canvas, and run callback."""
        points = []
        for r in range(self._table.rowCount()):
            item_r = self._table.item(r, 0)
            item_z = self._table.item(r, 1)
            if item_r and item_z:
                try:
                    points.append((float(item_r.text()), float(item_z.text())))
                except ValueError:
                    return

        # 1. Update properties and raw_lines on Shape node
        # For writer/parser persistence
        raw_lines = [
            f"BasePointX=0",
            f"BasePointY=0",
            f"FaceType=POLYGON"
        ]
        
        # Keep properties updated too
        self.shape_node.properties.clear()
        self.shape_node.properties["BasePointX"] = "0"
        self.shape_node.properties["BasePointY"] = "0"
        self.shape_node.properties["FaceType"] = "POLYGON"
        
        for idx, pt in enumerate(points):
            self.shape_node.properties[f"X{idx}"] = str(pt[0])
            self.shape_node.properties[f"Y{idx}"] = str(pt[1])
            
            raw_lines.extend([
                f"PointX={pt[0]}",
                f"PointY={pt[1]}",
                "LineKind=STRAIGHT",
                "ArcDriction=FORWARD"
            ])
            
        self.shape_node.raw_lines = raw_lines

        # 2. Redraw local Matplotlib preview
        self._redraw_preview()

        # 3. Notify parent/main window callback
        if self.on_changed_callback:
            self.on_changed_callback()

    def _redraw_preview(self):
        """Redraw the local preview canvas from current coordinates in table."""
        if not HAS_MATPLOTLIB or not self._ax:
            return

        points = []
        for r in range(self._table.rowCount()):
            item_r = self._table.item(r, 0)
            item_z = self._table.item(r, 1)
            if item_r and item_z:
                try:
                    points.append((float(item_r.text()), float(item_z.text())))
                except ValueError:
                    return

        # Get selected row index
        selected_ranges = self._table.selectedRanges()
        selected_row = selected_ranges[0].topRow() if selected_ranges else -1

        self._ax.clear()
        self._ax.set_title("Polygon Preview")
        self._ax.set_xlabel("R (mm)")
        self._ax.set_ylabel("Z (mm)")
        self._ax.set_aspect("equal")
        self._ax.grid(True, alpha=0.3)

        if len(points) >= 3:
            xs = [p[0] for p in points] + [points[0][0]]
            ys = [p[1] for p in points] + [points[0][1]]
            
            colors = {
                "Coil": "#d4a017",
                "Magnet": "#c0392b",
                "Steel": "#7f8c8d",
            }
            color = colors.get(self.part.kind, "#3498db")
            
            self._ax.fill(xs, ys, alpha=0.4, color=color)
            self._ax.plot(xs, ys, color=color, linewidth=1.5, marker="o")
            
            # Highlight selected node if valid
            if 0 <= selected_row < len(points):
                sel_x, sel_y = points[selected_row]
                self._ax.plot(sel_x, sel_y, "ro", markersize=10, fillstyle="none", markeredgewidth=2)
        elif points:
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            self._ax.plot(xs, ys, "bo-", linewidth=1.5)
            if 0 <= selected_row < len(points):
                sel_x, sel_y = points[selected_row]
                self._ax.plot(sel_x, sel_y, "ro", markersize=10, fillstyle="none", markeredgewidth=2)

        self._fig.tight_layout()
        self._canvas.draw()

    def _on_selection_changed(self):
        """Redraw preview on selection changed to show node highlight."""
        if self._updating:
            return
        self._redraw_preview()

    def _on_plot_click(self, event):
        """Select row in table when clicking on or near a plot vertex."""
        if event.xdata is None or event.ydata is None or self._updating:
            return

        # Calculate threshold as 5% of axis viewport span
        xlim = self._ax.get_xlim()
        ylim = self._ax.get_ylim()
        span = max(abs(xlim[1] - xlim[0]), abs(ylim[1] - ylim[0]))
        threshold = span * 0.05

        min_dist = float('inf')
        closest_idx = -1
        
        for idx in range(self._table.rowCount()):
            try:
                r = float(self._table.item(idx, 0).text())
                z = float(self._table.item(idx, 1).text())
                dist = ((event.xdata - r) ** 2 + (event.ydata - z) ** 2) ** 0.5
                if dist < min_dist:
                    min_dist = dist
                    closest_idx = idx
            except (ValueError, AttributeError):
                continue

        if closest_idx != -1 and min_dist < threshold:
            self._updating = True
            self._table.selectRow(closest_idx)
            self._updating = False
            self._redraw_preview()
            
            # Center scroll to the item
            item = self._table.item(closest_idx, 0)
            if item:
                self._table.scrollToItem(item)

    # --- Button actions ---

    def _add_point(self):
        row = self._table.rowCount()
        self._updating = True
        self._table.setRowCount(row + 1)
        
        # Default next point based on previous or (0,0)
        default_r = 10.0
        default_z = 10.0
        if row > 0:
            try:
                default_r = float(self._table.item(row - 1, 0).text()) + 5.0
                default_z = float(self._table.item(row - 1, 1).text())
            except (ValueError, AttributeError):
                pass
                
        self._table.setItem(row, 0, QTableWidgetItem(f"{default_r:.4f}"))
        self._table.setItem(row, 1, QTableWidgetItem(f"{default_z:.4f}"))
        self._updating = False
        self._update_all()
        self._table.selectRow(row)

    def _insert_point(self):
        selected = self._table.selectedRanges()
        row = selected[0].bottomRow() if selected else self._table.rowCount() - 1
        
        self._updating = True
        self._table.insertRow(row + 1)
        
        # Interpolate between current row and next if possible
        r_val, z_val = 10.0, 10.0
        try:
            r_val = float(self._table.item(row, 0).text())
            z_val = float(self._table.item(row, 1).text()) + 5.0
        except (ValueError, AttributeError):
            pass

        self._table.setItem(row + 1, 0, QTableWidgetItem(f"{r_val:.4f}"))
        self._table.setItem(row + 1, 1, QTableWidgetItem(f"{z_val:.4f}"))
        self._updating = False
        self._update_all()
        self._table.selectRow(row + 1)

    def _delete_point(self):
        selected = self._table.selectedRanges()
        if not selected:
            return
        row = selected[0].topRow()
        if self._table.rowCount() <= 3:
            # Keep at least a triangle
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Delete", "Geometry must have at least 3 points.")
            return

        self._updating = True
        self._table.removeRow(row)
        self._updating = False
        self._update_all()
        
        # Select adjacent row
        next_select = min(row, self._table.rowCount() - 1)
        self._table.selectRow(next_select)

    def _move_up(self):
        selected = self._table.selectedRanges()
        if not selected:
            return
        row = selected[0].topRow()
        if row == 0:
            return
            
        self._updating = True
        r1, z1 = self._table.item(row - 1, 0).text(), self._table.item(row - 1, 1).text()
        r2, z2 = self._table.item(row, 0).text(), self._table.item(row, 1).text()
        
        self._table.setItem(row - 1, 0, QTableWidgetItem(r2))
        self._table.setItem(row - 1, 1, QTableWidgetItem(z2))
        self._table.setItem(row, 0, QTableWidgetItem(r1))
        self._table.setItem(row, 1, QTableWidgetItem(z1))
        
        self._updating = False
        self._update_all()
        self._table.selectRow(row - 1)

    def _move_down(self):
        selected = self._table.selectedRanges()
        if not selected:
            return
        row = selected[0].topRow()
        if row == self._table.rowCount() - 1:
            return
            
        self._updating = True
        r1, z1 = self._table.item(row, 0).text(), self._table.item(row, 1).text()
        r2, z2 = self._table.item(row + 1, 0).text(), self._table.item(row + 1, 1).text()
        
        self._table.setItem(row, 0, QTableWidgetItem(r2))
        self._table.setItem(row, 1, QTableWidgetItem(z2))
        self._table.setItem(row + 1, 0, QTableWidgetItem(r1))
        self._table.setItem(row + 1, 1, QTableWidgetItem(z1))
        
        self._updating = False
        self._update_all()
        self._table.selectRow(row + 1)
