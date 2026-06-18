"""Main window for MoA Actuator GUI — DoSA-style native interface.

Replicates the DoSA-2D/3D C# WinForms application layout:
- Menu bar: File / Part / Test / Solver / Help
- Left panel: Design tree + Property editor
- Center: Geometry viewer + Solver settings
- Right: Results
- Bottom: Log output
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ..models import DesignModel, NodeModel, TestModel
from ..parser import parse_dosa_file
from .dialogs.add_part import AddPartDialog
from .dialogs.add_test import AddTestDialog
from .panels.design_tree import DesignTreePanel
from .panels.geometry_view import GeometryViewPanel
from .panels.property_editor import PropertyEditorPanel
from .panels.result_panel import ResultPanel
from .panels.solver_panel import SolverPanel


class MainWindow(QMainWindow):
    """MoA Actuator main application window — DoSA-style interface."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MoA Actuator — DoSA Native")
        self.setMinimumSize(1280, 800)

        self._design: DesignModel | None = None
        self._file_path: str | None = None
        self._modified: bool = False

        self._setup_menubar()
        self._setup_toolbar()
        self._setup_ui()
        self._setup_statusbar()
        self._new_project()

    # ==================================================================
    # Menu bar
    # ==================================================================

    def _setup_menubar(self):
        menubar = self.menuBar()

        # --- File menu ---
        file_menu = menubar.addMenu("&File")

        act = file_menu.addAction("&New Project")
        act.setShortcut(QKeySequence.StandardKey.New)
        act.triggered.connect(self._new_project)

        act = file_menu.addAction("&Open...")
        act.setShortcut(QKeySequence.StandardKey.Open)
        act.triggered.connect(self._open_file)

        file_menu.addAction("Open &AEDT...").triggered.connect(self._open_aedt_file)

        file_menu.addSeparator()

        act = file_menu.addAction("&Save")
        act.setShortcut(QKeySequence.StandardKey.Save)
        act.triggered.connect(self._save_file)

        act = file_menu.addAction("Save &As...")
        act.setShortcut(QKeySequence("Ctrl+Shift+S"))
        act.triggered.connect(self._save_file_as)

        file_menu.addSeparator()
        file_menu.addAction("Import &DXF...").triggered.connect(self._import_dxf)
        file_menu.addSeparator()

        act = file_menu.addAction("E&xit")
        act.setShortcut(QKeySequence("Alt+F4"))
        act.triggered.connect(self.close)

        # --- Part menu ---
        part_menu = menubar.addMenu("&Part")
        part_menu.addAction("Add &Coil...").triggered.connect(lambda: self._add_part("Coil"))
        part_menu.addAction("Add &Magnet...").triggered.connect(lambda: self._add_part("Magnet"))
        part_menu.addAction("Add &Steel...").triggered.connect(lambda: self._add_part("Steel"))
        part_menu.addSeparator()

        act = part_menu.addAction("&Delete Selected Part")
        act.setShortcut(QKeySequence.StandardKey.Delete)
        act.triggered.connect(self._delete_selected_part)

        # --- Test menu ---
        test_menu = menubar.addMenu("&Test")
        test_menu.addAction("Add &Force Test...").triggered.connect(lambda: self._add_test("ForceTest"))
        test_menu.addAction("Add &Stroke Test...").triggered.connect(lambda: self._add_test("StrokeTest"))
        test_menu.addAction("Add &Current Test...").triggered.connect(lambda: self._add_test("CurrentTest"))
        test_menu.addSeparator()

        act = test_menu.addAction("&Run Selected Test")
        act.setShortcut(QKeySequence("F5"))
        act.triggered.connect(self._run_simulation)

        # --- Solver menu ---
        solver_menu = menubar.addMenu("&Solver")
        solver_menu.addAction("Run with &Maxwell").triggered.connect(lambda: self._run_with_solver("maxwell"))
        solver_menu.addAction("Run with &FEMM").triggered.connect(lambda: self._run_with_solver("femm"))
        solver_menu.addAction("Run with &GetDP").triggered.connect(lambda: self._run_with_solver("getdp"))

        # --- Help menu ---
        help_menu = menubar.addMenu("&Help")
        help_menu.addAction("Show &Profiles...").triggered.connect(self._show_profiles)
        help_menu.addAction("&About...").triggered.connect(self._show_about)

    # ==================================================================
    # Toolbar
    # ==================================================================

    def _setup_toolbar(self):
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.addToolBar(toolbar)

        toolbar.addAction("New", self._new_project)
        toolbar.addAction("Open", self._open_file)
        toolbar.addAction("Save", self._save_file)
        toolbar.addSeparator()
        toolbar.addAction("+ Coil", lambda: self._add_part("Coil"))
        toolbar.addAction("+ Magnet", lambda: self._add_part("Magnet"))
        toolbar.addAction("+ Steel", lambda: self._add_part("Steel"))
        toolbar.addSeparator()
        toolbar.addAction("+ Force", lambda: self._add_test("ForceTest"))
        toolbar.addAction("+ Stroke", lambda: self._add_test("StrokeTest"))
        toolbar.addSeparator()
        toolbar.addAction("Run (F5)", self._run_simulation)

    # ==================================================================
    # UI Layout
    # ==================================================================

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(4, 4, 4, 4)

        # Main horizontal splitter
        h_splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- Left panel: Tree + Properties ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self._tree_panel = DesignTreePanel()
        self._tree_panel.part_selected.connect(self._on_part_selected)
        self._tree_panel.test_selected.connect(self._on_test_selected)
        left_layout.addWidget(self._tree_panel, stretch=1)

        self._property_panel = PropertyEditorPanel()
        self._property_panel.property_changed.connect(self._on_property_changed)
        left_layout.addWidget(self._property_panel, stretch=1)

        h_splitter.addWidget(left_widget)

        # --- Center: Geometry viewer + Solver panel ---
        center_splitter = QSplitter(Qt.Orientation.Vertical)

        self._geometry_panel = GeometryViewPanel()
        center_splitter.addWidget(self._geometry_panel)

        self._solver_panel = SolverPanel()
        center_splitter.addWidget(self._solver_panel)

        center_splitter.setSizes([500, 200])
        h_splitter.addWidget(center_splitter)

        # --- Right: Results ---
        self._result_panel = ResultPanel()
        h_splitter.addWidget(self._result_panel)

        h_splitter.setSizes([300, 500, 450])
        main_layout.addWidget(h_splitter, stretch=4)

        # --- Bottom: Log ---
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(150)
        self._log.setFontFamily("Consolas")
        self._log.setPlaceholderText("Log output...")
        main_layout.addWidget(self._log, stretch=0)

    def _setup_statusbar(self):
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._statusbar.showMessage("Ready")

    # ==================================================================
    # File operations
    # ==================================================================

    def _new_project(self):
        if self._modified and not self._confirm_discard():
            return
        self._design = DesignModel(name="Untitled", source_type="dsa")
        self._file_path = None
        self._modified = False
        self._refresh_all()
        self._log_message("New project created.")
        self._update_title()

    def _open_file(self):
        if self._modified and not self._confirm_discard():
            return

        path, _ = QFileDialog.getOpenFileName(
            self, "Open DoSA Design File", "",
            "DoSA Files (*.dsa *.dsa3d);;All Files (*)",
        )
        if not path:
            return

        try:
            self._design = parse_dosa_file(path)
            self._file_path = path
            self._modified = False
            self._refresh_all()
            self._log_message(f"Opened: {path}")
            self._update_title()
        except Exception as e:
            QMessageBox.critical(self, "Parse Error", str(e))
            self._log_message(f"ERROR: {e}")

    def _open_aedt_file(self):
        """Open an AEDT Maxwell project file and display its contents."""
        if self._modified and not self._confirm_discard():
            return

        path, _ = QFileDialog.getOpenFileName(
            self, "Open AEDT Maxwell File", "",
            "AEDT Files (*.aedt);;All Files (*)",
        )
        if not path:
            return

        self._log_message(f"Opening AEDT: {path} ...")
        self._statusbar.showMessage("Connecting to AEDT Desktop...")
        QApplication.processEvents()

        try:
            from ..aedt_reader import read_aedt_file

            # Get settings from solver panel
            version = "2026.1"
            non_graphical = self._solver_panel._non_graphical.isChecked()

            self._design = read_aedt_file(
                path,
                aedt_version=version,
                non_graphical=non_graphical,
                new_desktop=False,
            )
            self._file_path = path
            self._modified = False
            self._refresh_all()

            # Show project info in log
            if self._design.nodes:
                info = self._design.nodes[0].properties
                self._log_message(
                    f"AEDT Project: {info.get('project_name', '')}\n"
                    f"  Design: {info.get('design_name', '')}\n"
                    f"  Solution: {info.get('solution_type', '')}\n"
                    f"  Units: {info.get('model_units', '')}\n"
                    f"  Objects: {len(self._design.parts)} parts, "
                    f"{len(self._design.tests)} setups"
                )

                # Update solver panel with the actual solution type from AEDT
                sol_type = info.get("solution_type", "")
                if sol_type:
                    self._solver_panel._solution_type_combo.setCurrentText(sol_type)

            self._update_title()
            self._log_message("AEDT file loaded successfully.")

        except ImportError:
            QMessageBox.critical(
                self, "Missing Dependency",
                "pyaedt (ansys.aedt.core) is required to open AEDT files.\n"
                "Install with: pip install pyaedt"
            )
        except Exception as e:
            QMessageBox.critical(self, "AEDT Error", str(e))
            self._log_message(f"ERROR opening AEDT: {e}")

    def _save_file(self):
        if not self._file_path:
            self._save_file_as()
            return
        self._write_dosa_file(self._file_path)

    def _save_file_as(self):
        if self._design is None:
            return
        ext_filter = (
            "DoSA 3D (*.dsa3d)" if self._design.source_type == "dsa3d"
            else "DoSA 2D (*.dsa);;DoSA 3D (*.dsa3d)"
        )
        path, _ = QFileDialog.getSaveFileName(self, "Save Design As", "", ext_filter)
        if not path:
            return
        self._file_path = path
        self._write_dosa_file(path)

    def _write_dosa_file(self, path: str):
        from ..writer import write_dosa_file
        try:
            write_dosa_file(self._design, path)
            self._modified = False
            self._update_title()
            self._log_message(f"Saved: {path}")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))
            self._log_message(f"ERROR saving: {e}")

    def _import_dxf(self):
        QMessageBox.information(
            self, "DXF Import",
            "DXF import will be supported in a future version.\n"
            "For now, use the Part dialogs to define geometry."
        )

    # ==================================================================
    # Part operations
    # ==================================================================

    def _add_part(self, kind: str):
        if self._design is None:
            return
        dialog = AddPartDialog(kind, self._design, parent=self)
        if dialog.exec():
            part = dialog.get_part()
            self._design.parts.append(part)
            self._modified = True
            self._refresh_all()
            self._log_message(f"Added {kind}: {part.name}")

    def _delete_selected_part(self):
        if self._design is None:
            return
        selected = self._tree_panel.get_selected_part_name()
        if not selected:
            QMessageBox.information(self, "Delete", "Select a part in the tree first.")
            return
        reply = QMessageBox.question(
            self, "Confirm Delete", f"Delete part '{selected}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._design.parts = [p for p in self._design.parts if p.name != selected]
            self._modified = True
            self._refresh_all()
            self._log_message(f"Deleted part: {selected}")

    # ==================================================================
    # Test operations
    # ==================================================================

    def _add_test(self, kind: str):
        if self._design is None:
            return
        dialog = AddTestDialog(kind, self._design, parent=self)
        if dialog.exec():
            test = dialog.get_test()
            self._design.tests.append(test)
            self._modified = True
            self._refresh_all()
            self._log_message(f"Added test: {test.name} ({kind})")

    # ==================================================================
    # Simulation
    # ==================================================================

    def _run_simulation(self):
        if self._design is None:
            QMessageBox.warning(self, "No Design", "Create or open a design first.")
            return
        config = self._solver_panel.get_run_config()
        config.design = self._design
        self._result_panel.run_simulation(config)
        self._log_message(f"Running {config.solver} ({config.mode})...")

    def _run_with_solver(self, solver: str):
        if self._design is None:
            QMessageBox.warning(self, "No Design", "Create or open a design first.")
            return
        self._solver_panel.set_solver(solver)
        self._run_simulation()

    # ==================================================================
    # Event handlers
    # ==================================================================

    def _on_part_selected(self, part_name: str):
        if self._design is None:
            return
        for part in self._design.parts:
            if part.name == part_name:
                self._property_panel.load_part(part)
                break

    def _on_test_selected(self, test_name: str):
        if self._design is None:
            return
        for test in self._design.tests:
            if test.name == test_name:
                self._property_panel.load_test(test)
                break

    def _on_property_changed(self, key: str, value: str):
        self._modified = True
        self._geometry_panel.load_design(self._design)
        self._update_title()

    # ==================================================================
    # Helpers
    # ==================================================================

    def _refresh_all(self):
        if self._design:
            self._tree_panel.load_design(self._design)
            self._geometry_panel.load_design(self._design)
            self._solver_panel.set_mode(
                "3d" if self._design.source_type == "dsa3d" else "2d"
            )
            self._statusbar.showMessage(
                f"{self._design.name} — {len(self._design.parts)} parts, "
                f"{len(self._design.tests)} tests"
            )

    def _update_title(self):
        name = Path(self._file_path).name if self._file_path else "Untitled"
        mod = " *" if self._modified else ""
        self.setWindowTitle(f"MoA Actuator — {name}{mod}")

    def _log_message(self, msg: str):
        self._log.append(msg)

    def _confirm_discard(self) -> bool:
        reply = QMessageBox.question(
            self, "Unsaved Changes",
            "Current design has unsaved changes. Discard?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    def _show_about(self):
        QMessageBox.about(
            self, "About MoA Actuator",
            "MoA Actuator v0.1\n\n"
            "DoSA-2D/3D Compatible Electromagnetic Actuator Design\n"
            "Solvers: Maxwell (pyAEDT), FEMM, GetDP\n\n"
            "© 2024 MoaSysConverg"
        )

    def _show_profiles(self):
        from ..profiles import list_profiles
        profiles = list_profiles()
        text = "\n".join(
            f"{p['name']:15s} | {p['solution_type']:15s} | {p['notes']}"
            for p in profiles
        )
        QMessageBox.information(self, "Available Profiles", text)

    def closeEvent(self, event):
        if self._modified:
            reply = QMessageBox.question(
                self, "Exit", "Save changes before closing?",
                QMessageBox.StandardButton.Save |
                QMessageBox.StandardButton.Discard |
                QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Save:
                self._save_file()
            elif reply == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
        event.accept()
