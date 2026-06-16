"""Main window for MoA Actuator GUI."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ..models import DesignModel
from ..parser import parse_dosa_file
from .panels.design_tree import DesignTreePanel
from .panels.geometry_view import GeometryViewPanel
from .panels.result_panel import ResultPanel
from .panels.solver_panel import SolverPanel


class MainWindow(QMainWindow):
    """MoA Actuator main application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MoA Actuator — DoSA Maxwell/FEMM Automation")
        self.setMinimumSize(1200, 700)

        self._design: DesignModel | None = None

        self._setup_toolbar()
        self._setup_ui()
        self._setup_statusbar()

    def _setup_toolbar(self):
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        toolbar.addAction("Open .dsa/.dsa3d", self._open_file)
        toolbar.addSeparator()
        toolbar.addAction("Run Simulation", self._run_simulation)
        toolbar.addSeparator()
        toolbar.addAction("Profiles", self._show_profiles)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Design tree
        self._tree_panel = DesignTreePanel()
        splitter.addWidget(self._tree_panel)

        # Center-left: Geometry viewer
        self._geometry_panel = GeometryViewPanel()
        splitter.addWidget(self._geometry_panel)

        # Center-right: Solver settings
        self._solver_panel = SolverPanel()
        splitter.addWidget(self._solver_panel)

        # Right: Results
        self._result_panel = ResultPanel()
        splitter.addWidget(self._result_panel)

        splitter.setSizes([250, 350, 300, 500])
        layout.addWidget(splitter)

    def _setup_statusbar(self):
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._statusbar.showMessage("Ready — Open a .dsa or .dsa3d file to begin")

    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open DoSA Design File",
            "",
            "DoSA Files (*.dsa *.dsa3d);;All Files (*)",
        )
        if not path:
            return

        try:
            self._design = parse_dosa_file(path)
            self._tree_panel.load_design(self._design)
            self._geometry_panel.load_design(self._design)
            self._solver_panel.set_mode("3d" if self._design.source_type == "dsa3d" else "2d")
            self._statusbar.showMessage(
                f"Loaded: {self._design.name} ({len(self._design.parts)} parts, "
                f"{len(self._design.tests)} tests) — {Path(path).name}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Parse Error", str(e))

    def _run_simulation(self):
        if self._design is None:
            QMessageBox.warning(self, "No Design", "Open a .dsa file first.")
            return

        config = self._solver_panel.get_run_config()
        config.design = self._design
        self._result_panel.run_simulation(config)
        self._statusbar.showMessage("Simulation started...")

    def _show_profiles(self):
        from ..profiles import list_profiles
        profiles = list_profiles()
        text = "\n".join(
            f"{p['name']:15s} | {p['solution_type']:15s} | {p['notes']}"
            for p in profiles
        )
        QMessageBox.information(self, "Available Profiles", text)
