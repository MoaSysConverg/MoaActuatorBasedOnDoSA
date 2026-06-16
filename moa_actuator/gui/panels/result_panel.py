"""Result display panel with log and chart."""

from __future__ import annotations

import json

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QGroupBox, QTextEdit, QVBoxLayout, QWidget

from ...runner import RunConfig, run
from ...solvers.base import SolveResult


class SolverWorker(QThread):
    """Worker thread for running simulations."""

    finished = pyqtSignal(object)

    def __init__(self, config: RunConfig):
        super().__init__()
        self._config = config

    def run(self):
        try:
            result = run(self._config)
            self.finished.emit(result)
        except Exception as e:
            self.finished.emit(
                SolveResult(ok=False, mode=self._config.mode, solver=self._config.solver, errors=[str(e)])
            )


class ResultPanel(QWidget):
    """Panel showing simulation results and log."""

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        group = QGroupBox("Results / Log")
        group_layout = QVBoxLayout(group)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setFontFamily("Consolas")
        group_layout.addWidget(self._log)

        layout.addWidget(group)

        self._worker: SolverWorker | None = None

    def run_simulation(self, config: RunConfig):
        """Start a simulation in a background thread."""
        self._log.clear()
        self._log.append(f"Starting {config.solver} ({config.mode}) simulation...")
        self._log.append(f"Profile: {config.profile}")
        self._log.append(f"Dry run: {config.dry_run}")
        self._log.append("---")

        self._worker = SolverWorker(config)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_finished(self, result: SolveResult):
        """Handle simulation completion."""
        self._log.append(f"\nResult: {'OK' if result.ok else 'FAILED'}")
        self._log.append(f"Commands: {len(result.commands)}")

        if result.errors:
            self._log.append(f"\nErrors ({len(result.errors)}):")
            for err in result.errors:
                self._log.append(f"  - {err}")

        if result.commands:
            self._log.append(f"\nCommand log:")
            for cmd in result.commands[:20]:
                self._log.append(f"  {cmd['method']}: {cmd.get('args', {})}")
            if len(result.commands) > 20:
                self._log.append(f"  ... and {len(result.commands) - 20} more")

        if result.project_path:
            self._log.append(f"\nProject: {result.project_path}")
