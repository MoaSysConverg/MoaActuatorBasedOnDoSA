"""Property editor panel — editable property grid for selected part/test."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QGroupBox,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...models import NodeModel, TestModel


class PropertyEditorPanel(QWidget):
    """Editable property grid (key-value table) for parts and tests."""

    property_changed = pyqtSignal(str, str)  # key, new_value

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("Properties")
        group_layout = QVBoxLayout(group)

        self._table = QTableWidget()
        self._table.setColumnCount(2)
        self._table.setHorizontalHeaderLabels(["Property", "Value"])
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._table.verticalHeader().setVisible(False)
        self._table.cellChanged.connect(self._on_cell_changed)
        self._table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        group_layout.addWidget(self._table)

        layout.addWidget(group)

        self._current_part: NodeModel | None = None
        self._current_test: TestModel | None = None
        self._updating = False

    def load_part(self, part: NodeModel):
        """Display properties of a part."""
        self._current_part = part
        self._current_test = None

        has_shape = False
        shape_len = 0
        
        # Check if shape child node exists
        for child in part.children:
            if child.kind == "Shape":
                has_shape = True
                from ...geometry import extract_geometry
                geom = extract_geometry(part)
                if geom and geom.points:
                    shape_len = len(geom.points)
                break
        
        # Or check properties
        if not has_shape and "ShapePoints" in part.properties:
            has_shape = True
            pts = part.properties["ShapePoints"]
            if isinstance(pts, list):
                shape_len = len(pts)

        self._populate(part.kind, part.name, part.properties, has_shape, shape_len)

    def load_test(self, test: TestModel):
        """Display properties of a test."""
        self._current_test = test
        self._current_part = None
        self._populate(test.kind, test.name, test.properties, False, 0)

    def _populate(self, kind: str, name: str, properties: dict, has_shape: bool = False, shape_len: int = 0):
        """Fill the table with properties."""
        self._updating = True
        self._table.setRowCount(0)

        # Header row (read-only)
        rows = [("Kind", kind, False), ("Name", name, False)]
        # Editable properties
        for key, value in properties.items():
            if key == "ShapePoints":
                # Show as summary, not editable inline
                pts = value if isinstance(value, list) else []
                rows.append(("Shape", f"{len(pts)} points (Double-click to edit)", False))
            else:
                rows.append((key, str(value), True))

        if has_shape:
            # If the properties dictionary didn't already have ShapePoints, we append a Shape row
            if not any(r[0] == "Shape" for r in rows):
                rows.append(("Shape", f"{shape_len} points (Double-click to edit)", False))

        self._table.setRowCount(len(rows))
        for i, (key, val, editable) in enumerate(rows):
            key_item = QTableWidgetItem(key)
            from PyQt6.QtCore import Qt
            key_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self._table.setItem(i, 0, key_item)

            val_item = QTableWidgetItem(val)
            if not editable:
                val_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self._table.setItem(i, 1, val_item)

        self._updating = False

    def _on_cell_changed(self, row: int, col: int):
        """Handle user editing a property value."""
        if self._updating or col != 1:
            return

        key_item = self._table.item(row, 0)
        val_item = self._table.item(row, 1)
        if not key_item or not val_item:
            return

        key = key_item.text()
        new_value = val_item.text()

        # Skip non-editable rows
        if key in ("Kind", "Name", "Shape"):
            return

        # Update the underlying model
        if self._current_part:
            self._current_part.properties[key] = new_value
        elif self._current_test:
            self._current_test.properties[key] = new_value

        self.property_changed.emit(key, new_value)

    def _on_cell_double_clicked(self, row: int, col: int):
        """Handle user double-clicking on a cell."""
        if col != 1:
            return
        key_item = self._table.item(row, 0)
        if key_item and key_item.text() == "Shape":
            self._edit_shape_geometry()

    def _edit_shape_geometry(self):
        """Open the interactive geometry dialog for the current part."""
        if not self._current_part:
            return
            
        from ..dialogs.edit_geometry import EditGeometryDialog
        
        def notify_changed():
            # Notify main window to refresh geometries and reload
            self.property_changed.emit("Shape", "")
            # Reload our property view to update point count summary
            self.load_part(self._current_part)
            
        dialog = EditGeometryDialog(self._current_part, on_changed_callback=notify_changed, parent=self)
        dialog.exec()
