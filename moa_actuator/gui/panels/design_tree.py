"""Design tree panel — displays parts and tests from parsed DoSA file."""

from __future__ import annotations

from PyQt6.QtWidgets import QGroupBox, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from ...models import DesignModel


class DesignTreePanel(QWidget):
    """TreeView showing design hierarchy (parts + tests)."""

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        group = QGroupBox("Design Structure")
        group_layout = QVBoxLayout(group)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Name", "Kind", "Material"])
        self._tree.setColumnWidth(0, 120)
        self._tree.setColumnWidth(1, 80)
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

        # Tests section
        tests_root = QTreeWidgetItem(self._tree, ["Tests", f"({len(design.tests)})", ""])
        tests_root.setExpanded(True)
        for test in design.tests:
            item = QTreeWidgetItem(tests_root, [test.name, test.kind, ""])
