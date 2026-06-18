"""Design tree panel — displays parts and tests from parsed DoSA file."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QGroupBox, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from ...models import DesignModel


class DesignTreePanel(QWidget):
    """TreeView showing design hierarchy (parts + tests)."""

    part_selected = pyqtSignal(str)   # emits part name
    test_selected = pyqtSignal(str)   # emits test name

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        group = QGroupBox("Design Structure")
        group_layout = QVBoxLayout(group)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Name", "Kind", "Material"])
        self._tree.setColumnWidth(0, 120)
        self._tree.setColumnWidth(1, 80)
        self._tree.itemClicked.connect(self._on_item_clicked)
        group_layout.addWidget(self._tree)

        layout.addWidget(group)

    def load_design(self, design: DesignModel):
        """Populate tree with design data."""
        self._tree.clear()

        # Parts section
        parts_root = QTreeWidgetItem(self._tree, ["Parts", f"({len(design.parts)})", ""])
        parts_root.setExpanded(True)
        for part in design.parts:
            mat = part.properties.get("Material", "")
            item = QTreeWidgetItem(parts_root, [part.name, part.kind, mat])
            item.setData(0, 100, ("part", part.name))

        # Tests section
        tests_root = QTreeWidgetItem(self._tree, ["Tests", f"({len(design.tests)})", ""])
        tests_root.setExpanded(True)
        for test in design.tests:
            item = QTreeWidgetItem(tests_root, [test.name, test.kind, ""])
            item.setData(0, 100, ("test", test.name))

    def get_selected_part_name(self) -> str | None:
        """Return name of currently selected part, or None."""
        item = self._tree.currentItem()
        if item is None:
            return None
        data = item.data(0, 100)
        if data and data[0] == "part":
            return data[1]
        return None

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int):
        """Emit signal when a part or test is clicked."""
        data = item.data(0, 100)
        if not data:
            return
        kind, name = data
        if kind == "part":
            self.part_selected.emit(name)
        elif kind == "test":
            self.test_selected.emit(name)
