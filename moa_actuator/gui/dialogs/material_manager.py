"""Dialog for managing the material library (.dmat) with B-H curve editing."""

from __future__ import annotations

import copy
import logging
from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QVBoxLayout,
    QGridLayout,
    QListWidget,
    QPushButton,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
    QSplitter,
    QWidget,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from ...bh_data import parse_dmat_file, write_dmat_file, BHCurve

logger = logging.getLogger(__name__)


class MaterialManagerDialog(QDialog):
    """Interactive Material Library Manager with B-H curve plotting."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Material Library Manager")
        self.resize(900, 600)

        # Load original library curves
        try:
            self._materials = parse_dmat_file()
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to load materials: {e}")
            self._materials = {}

        # Track currently editing material name
        self._current_material_name: str | None = None
        self._is_updating_ui = False

        self._setup_ui()
        self._populate_list()

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)

        # Splitter to allow resizing the left list vs right edit pane
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # --- Left Pane: List & Management ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        left_layout.addWidget(QLabel("<b>Material Library:</b>"))

        self._list_widget = QListWidget()
        self._list_widget.currentTextChanged.connect(self._on_material_selected)
        left_layout.addWidget(self._list_widget)

        # List buttons
        btn_layout = QHBoxLayout()
        self._btn_add = QPushButton("Add")
        self._btn_add.setToolTip("Add new material")
        self._btn_add.clicked.connect(self._on_add_material)
        btn_layout.addWidget(self._btn_add)

        self._btn_dup = QPushButton("Duplicate")
        self._btn_dup.setToolTip("Duplicate selected material")
        self._btn_dup.clicked.connect(self._on_duplicate_material)
        btn_layout.addWidget(self._btn_dup)

        self._btn_del = QPushButton("Delete")
        self._btn_del.setToolTip("Delete selected material")
        self._btn_del.clicked.connect(self._on_delete_material)
        btn_layout.addWidget(self._btn_del)

        left_layout.addLayout(btn_layout)
        splitter.addWidget(left_widget)

        # --- Right Pane: Edit Fields & B-H Table & Plot ---
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Properties sub-panel (Grid)
        prop_layout = QGridLayout()
        prop_layout.addWidget(QLabel("Name:"), 0, 0)
        self._name_edit = QLineEdit()
        self._name_edit.editingFinished.connect(self._on_name_edited)
        prop_layout.addWidget(self._name_edit, 0, 1)

        prop_layout.addWidget(QLabel("Conductivity (S/m):"), 1, 0)
        self._cond_edit = QLineEdit()
        self._cond_edit.editingFinished.connect(self._on_conductivity_edited)
        prop_layout.addWidget(self._cond_edit, 1, 1)

        right_layout.addLayout(prop_layout)

        # Middle part of right pane: Table (left) and Plot (right)
        mid_layout = QHBoxLayout()

        # Table & Table Buttons widget
        table_container = QWidget()
        table_container_layout = QVBoxLayout(table_container)
        table_container_layout.setContentsMargins(0, 0, 0, 0)
        table_container_layout.addWidget(QLabel("<b>B-H Coordinates:</b>"))

        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["H (A/m)", "B (T)"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.cellChanged.connect(self._on_cell_changed)
        table_container_layout.addWidget(self._table)

        # Row buttons
        row_btn_layout = QHBoxLayout()
        self._btn_add_row = QPushButton("Add Row")
        self._btn_add_row.clicked.connect(self._on_add_row)
        row_btn_layout.addWidget(self._btn_add_row)

        self._btn_del_row = QPushButton("Delete Row")
        self._btn_del_row.clicked.connect(self._on_delete_row)
        row_btn_layout.addWidget(self._btn_del_row)

        table_container_layout.addLayout(row_btn_layout)
        mid_layout.addWidget(table_container, stretch=1)

        # Plot Canvas
        plot_container = QWidget()
        plot_container_layout = QVBoxLayout(plot_container)
        plot_container_layout.setContentsMargins(0, 0, 0, 0)
        plot_container_layout.addWidget(QLabel("<b>B-H Curve Preview:</b>"))

        self._fig = Figure(figsize=(4, 4), dpi=80)
        self._ax = self._fig.add_subplot(111)
        self._canvas = FigureCanvasQTAgg(self._fig)
        plot_container_layout.addWidget(self._canvas)
        mid_layout.addWidget(plot_container, stretch=1)

        right_layout.addLayout(mid_layout, stretch=1)

        # Dialog control buttons at bottom right
        action_layout = QHBoxLayout()
        action_layout.addStretch()
        
        self._btn_save = QPushButton("Save Library")
        self._btn_save.clicked.connect(self._on_save_library)
        self._btn_save.setStyleSheet("font-weight: bold; padding: 6px 12px;")
        action_layout.addWidget(self._btn_save)

        self._btn_cancel = QPushButton("Cancel")
        self._btn_cancel.clicked.connect(self.reject)
        self._btn_cancel.setStyleSheet("padding: 6px 12px;")
        action_layout.addWidget(self._btn_cancel)

        right_layout.addLayout(action_layout)
        splitter.addWidget(right_widget)

        # Set sizes (left list narrow, right workspace wide)
        splitter.setSizes([200, 700])

    def _populate_list(self):
        self._list_widget.blockSignals(True)
        self._list_widget.clear()
        for name in sorted(self._materials.keys()):
            self._list_widget.addItem(name)
        self._list_widget.blockSignals(False)

        if self._list_widget.count() > 0:
            self._list_widget.setCurrentRow(0)

    def _on_material_selected(self, name: str):
        if not name or name not in self._materials:
            return
        
        self._current_material_name = name
        curve = self._materials[name]

        self._is_updating_ui = True
        self._name_edit.setText(curve.name)
        self._cond_edit.setText(str(curve.conductivity))

        # Populate coordinates table
        self._table.setRowCount(0)
        self._table.cellChanged.disconnect(self._on_cell_changed)
        
        for i, (h, b) in enumerate(zip(curve.H, curve.B)):
            self._table.insertRow(i)
            self._table.setItem(i, 0, QTableWidgetItem(str(h)))
            self._table.setItem(i, 1, QTableWidgetItem(str(b)))

        self._table.cellChanged.connect(self._on_cell_changed)
        self._is_updating_ui = False

        self._redraw_plot()

    def _on_name_edited(self):
        if self._is_updating_ui or not self._current_material_name:
            return
        
        new_name = self._name_edit.text().strip()
        old_name = self._current_material_name
        if not new_name or new_name == old_name:
            self._name_edit.setText(old_name)
            return

        if new_name in self._materials:
            QMessageBox.warning(self, "Duplicate Name", f"Material name '{new_name}' already exists.")
            self._name_edit.setText(old_name)
            return

        # Update in dictionary
        curve = self._materials.pop(old_name)
        curve.name = new_name
        self._materials[new_name] = curve
        self._current_material_name = new_name

        # Update list item
        self._list_widget.blockSignals(True)
        items = self._list_widget.findItems(old_name, Qt.MatchFlag.MatchExactly)
        if items:
            items[0].setText(new_name)
        self._list_widget.blockSignals(False)

    def _on_conductivity_edited(self):
        if self._is_updating_ui or not self._current_material_name:
            return
        
        txt = self._cond_edit.text().strip()
        try:
            val = float(txt)
            if val < 0:
                raise ValueError()
            self._materials[self._current_material_name].conductivity = val
        except ValueError:
            QMessageBox.warning(self, "Invalid Value", "Conductivity must be a non-negative number.")
            self._cond_edit.setText(str(self._materials[self._current_material_name].conductivity))

    def _on_cell_changed(self, row: int, col: int):
        if self._is_updating_ui or not self._current_material_name:
            return
        
        item = self._table.item(row, col)
        if not item:
            return
        
        txt = item.text().strip()
        try:
            val = float(txt)
            curve = self._materials[self._current_material_name]
            
            # Sync to lists
            if col == 0:
                if row < len(curve.H):
                    curve.H[row] = val
                else:
                    curve.H.append(val)
            else:
                if row < len(curve.B):
                    curve.B[row] = val
                else:
                    curve.B.append(val)

            self._redraw_plot()
        except ValueError:
            QMessageBox.warning(self, "Invalid Number", "Please enter a valid numeric value.")
            curve = self._materials[self._current_material_name]
            if col == 0:
                old_val = str(curve.H[row]) if row < len(curve.H) else ""
            else:
                old_val = str(curve.B[row]) if row < len(curve.B) else ""
            
            self._is_updating_ui = True
            item.setText(old_val)
            self._is_updating_ui = False

    def _on_add_row(self):
        if not self._current_material_name:
            return
        
        row = self._table.rowCount()
        self._table.cellChanged.disconnect(self._on_cell_changed)
        self._table.insertRow(row)
        
        # Propose next logical points
        curve = self._materials[self._current_material_name]
        next_h = curve.H[-1] * 1.5 if curve.H else 0.0
        next_b = curve.B[-1] * 1.1 if curve.B else 0.0
        if next_h == 0.0 and row > 0:
            next_h = 100.0
        if next_b == 0.0 and row > 0:
            next_b = 0.1

        self._table.setItem(row, 0, QTableWidgetItem(str(next_h)))
        self._table.setItem(row, 1, QTableWidgetItem(str(next_b)))
        self._table.cellChanged.connect(self._on_cell_changed)

        # Update model lists
        curve.H.append(next_h)
        curve.B.append(next_b)

        self._redraw_plot()

    def _on_delete_row(self):
        if not self._current_material_name:
            return
        
        row = self._table.currentRow()
        if row < 0:
            row = self._table.rowCount() - 1
        
        if row < 0:
            return

        curve = self._materials[self._current_material_name]
        
        self._table.cellChanged.disconnect(self._on_cell_changed)
        self._table.removeRow(row)
        self._table.cellChanged.connect(self._on_cell_changed)

        if row < len(curve.H):
            curve.H.pop(row)
        if row < len(curve.B):
            curve.B.pop(row)

        self._redraw_plot()

    def _on_add_material(self):
        # Generate unique name
        i = 1
        name = "New_Material"
        while name in self._materials:
            name = f"New_Material_{i}"
            i += 1

        # Default steel properties
        curve = BHCurve(
            name=name,
            H=[0.0, 100.0, 1000.0, 10000.0],
            B=[0.0, 0.5, 1.2, 1.6],
            conductivity=5800000.0
        )
        self._materials[name] = curve
        
        self._populate_list()
        
        # Select it
        items = self._list_widget.findItems(name, Qt.MatchFlag.MatchExactly)
        if items:
            self._list_widget.setCurrentItem(items[0])

    def _on_duplicate_material(self):
        if not self._current_material_name:
            return
        
        old_curve = self._materials[self._current_material_name]
        
        # Generate unique name
        i = 1
        name = f"{old_curve.name}_copy"
        while name in self._materials:
            name = f"{old_curve.name}_copy_{i}"
            i += 1

        new_curve = copy.deepcopy(old_curve)
        new_curve.name = name
        self._materials[name] = new_curve
        
        self._populate_list()
        
        items = self._list_widget.findItems(name, Qt.MatchFlag.MatchExactly)
        if items:
            self._list_widget.setCurrentItem(items[0])

    def _on_delete_material(self):
        if not self._current_material_name:
            return
        
        name = self._current_material_name
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete material '{name}' from the library?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.No:
            return

        self._materials.pop(name)
        self._current_material_name = None
        
        self._populate_list()

    def _redraw_plot(self):
        self._ax.clear()
        if self._current_material_name and self._current_material_name in self._materials:
            curve = self._materials[self._current_material_name]
            if len(curve.H) > 0 and len(curve.B) > 0:
                self._ax.plot(curve.H, curve.B, "b-o", linewidth=1.5, markersize=4)
                self._ax.set_xlabel("H (A/m)")
                self._ax.set_ylabel("B (T)")
                self._ax.set_title(curve.name)
                self._ax.grid(True, alpha=0.3)
        self._fig.tight_layout()
        self._canvas.draw()

    def _on_save_library(self):
        # --- Validation ---
        for name, curve in self._materials.items():
            if not curve.name or curve.name.strip() == "":
                QMessageBox.warning(self, "Validation Error", "Material name cannot be empty.")
                return
            if len(curve.H) < 2:
                QMessageBox.warning(
                    self, "Validation Error",
                    f"Material '{name}' must have at least 2 coordinate points."
                )
                return
            if len(curve.H) != len(curve.B):
                QMessageBox.warning(
                    self, "Validation Error",
                    f"Material '{name}' coordinates size mismatch (H={len(curve.H)}, B={len(curve.B)})."
                )
                return
            if curve.H[0] != 0.0 or curve.B[0] != 0.0:
                QMessageBox.warning(
                    self, "Validation Error",
                    f"Material '{name}' must start at coordinate (0,0)."
                )
                return
            
            # Monotonicity checks
            for idx in range(1, len(curve.H)):
                if curve.H[idx] <= curve.H[idx - 1]:
                    QMessageBox.warning(
                        self, "Validation Error",
                        f"Material '{name}' H values must be strictly increasing.\n"
                        f"Point {idx}: {curve.H[idx]} is not greater than {curve.H[idx-1]}."
                    )
                    return
                if curve.B[idx] < curve.B[idx - 1]:
                    QMessageBox.warning(
                        self, "Validation Error",
                        f"Material '{name}' B values must be monotonically increasing.\n"
                        f"Point {idx}: {curve.B[idx]} is less than {curve.B[idx-1]}."
                    )
                    return

        # Save to file
        try:
            write_dmat_file(None, self._materials)
            QMessageBox.information(self, "Success", "Material library saved successfully.")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save library file: {e}")
