"""Result display panel with log, Build/Solve buttons, and force plot."""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from ...runner import RunConfig, run
from ...solvers.base import SolveResult


class SolverWorker(QThread):
    """Worker thread for running simulations."""

    finished = pyqtSignal(object)

    def __init__(self, config: RunConfig, phase: str = "all"):
        super().__init__()
        self._config = config
        self._phase = phase  # "build", "solve", or "all"

    def run(self):
        try:
            import pythoncom
            pythoncom.CoInitialize()
        except ImportError:
            pass

        try:
            if self._phase == "build":
                self._config.dry_run = False
                self._config.build_only = True
            elif self._phase == "solve":
                self._config.dry_run = False
                self._config.build_only = False
            result = run(self._config)
            self.finished.emit(result)
        except Exception as e:
            self.finished.emit(
                SolveResult(
                    ok=False, mode=self._config.mode,
                    solver=self._config.solver, errors=[str(e)],
                )
            )
        finally:
            try:
                import pythoncom
                pythoncom.CoUninitialize()
            except Exception:
                pass


class ResultPanel(QWidget):
    """Panel showing Build/Solve buttons, log, and force plot."""

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        # --- Buttons ---
        btn_layout = QHBoxLayout()
        self._btn_build = QPushButton("Build")
        self._btn_build.setToolTip(
            "Build: geometry + materials + excitations (no solve)"
        )
        self._btn_build.clicked.connect(self._on_build)
        btn_layout.addWidget(self._btn_build)

        self._btn_solve = QPushButton("Solve")
        self._btn_solve.setToolTip("Solve the analysis setup")
        self._btn_solve.clicked.connect(self._on_solve)
        btn_layout.addWidget(self._btn_solve)

        self._btn_results = QPushButton("Get Results")
        self._btn_results.setToolTip(
            "Fetch force data from solved project and plot"
        )
        self._btn_results.clicked.connect(self._on_get_results)
        self._btn_results.setEnabled(False)
        btn_layout.addWidget(self._btn_results)

        layout.addLayout(btn_layout)

        # --- Splitter: log + plot ---
        splitter = QSplitter()
        splitter.setOrientation(
            splitter.orientation()  # default horizontal
        )

        # Log area
        log_group = QGroupBox("Log")
        log_layout = QVBoxLayout(log_group)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setFontFamily("Consolas")
        log_layout.addWidget(self._log)
        splitter.addWidget(log_group)

        # Plot area
        plot_group = QGroupBox("Force Plot")
        plot_layout = QVBoxLayout(plot_group)
        self._fig = Figure(figsize=(5, 4), dpi=80)
        self._ax = self._fig.add_subplot(111)
        self._canvas = FigureCanvasQTAgg(self._fig)
        plot_layout.addWidget(self._canvas)
        splitter.addWidget(plot_group)

        from PyQt6.QtCore import Qt
        splitter.setOrientation(Qt.Orientation.Vertical)
        splitter.setSizes([200, 300])
        layout.addWidget(splitter)

        self._worker: SolverWorker | None = None
        self._config: RunConfig | None = None
        self._last_result: SolveResult | None = None
        self._solver_panel: SolverPanel | None = None

    # --- public API called from main_window ---

    def set_solver_panel(self, solver_panel):
        """Store solver panel reference to get up-to-date configuration on run."""
        self._solver_panel = solver_panel

    def set_config(self, config: RunConfig):
        """Store config for Build/Solve buttons."""
        self._config = config

    def run_simulation(self, config: RunConfig):
        """Start a full Build+Solve (legacy, called by F5)."""
        self._config = config
        self._run_worker(config, "all")

    # --- button handlers ---

    def _on_build(self):
        if self._config is None:
            self._log.append("ERROR: No config — load a design first.")
            return
        if self._solver_panel:
            design = self._config.design
            self._config = self._solver_panel.get_run_config()
            self._config.design = design
        cfg = self._copy_config(self._config)
        cfg.dry_run = True  # Build only = dry run (setup without solve)
        self._run_worker(cfg, "build")

    def _on_solve(self):
        if self._config is None:
            self._log.append("ERROR: No config — load a design first.")
            return
        if self._solver_panel:
            design = self._config.design
            self._config = self._solver_panel.get_run_config()
            self._config.design = design
        cfg = self._copy_config(self._config)
        cfg.dry_run = False
        self._run_worker(cfg, "solve")

    def _on_get_results(self):
        """Fetch results from the solved AEDT project and plot."""
        if not self._last_result or not self._last_result.project_path:
            self._log.append("No solved project to fetch results from.")
            return

        self._log.append("\nFetching results...")
        self._ax.clear()

        try:
            from ...post import extract_force_surface_data
            from ansys.aedt.core import Maxwell2d

            proj = self._last_result.project_path
            app = Maxwell2d(
                project=proj,
                non_graphical=False,
                new_desktop=False,
            )

            rows = extract_force_surface_data(app)
            app.release_desktop(
                close_projects=False, close_desktop=False
            )

            # Resolve actual expression and variable keys dynamically
            expr_key = [k for k in rows[0] if "Force" in k]
            expr = expr_key[0] if expr_key else "Force.Force_z"

            amp_var = None
            move_var = None

            for k in rows[0].keys():
                if "amp" in k.lower():
                    amp_var = k
                elif "move" in k.lower() or "stroke" in k.lower():
                    move_var = k

            if not amp_var:
                amp_var = "Amp_1"
            if not move_var:
                move_var = "move"

            unique_moves = sorted(list({r.get(move_var, 0.0) for r in rows}))
            unique_amps = sorted(list({r.get(amp_var, "Default") for r in rows}))

            def get_amp_numeric(amp_str):
                try:
                    cleaned = "".join(c for c in str(amp_str) if c.isdigit() or c == '.')
                    return float(cleaned)
                except ValueError:
                    return 0.0

            if len(unique_moves) > 1:
                # Plot Force vs Stroke (group by Amp)
                amp_groups: dict[str, list] = {}
                for row in rows:
                    amp = str(row.get(amp_var, "Default"))
                    amp_groups.setdefault(amp, []).append(row)

                for amp, data in sorted(amp_groups.items(), key=lambda item: get_amp_numeric(item[0])):
                    data_sorted = sorted(data, key=lambda d: d.get(move_var, 0.0))
                    xs = [d[move_var] for d in data_sorted]
                    ys = [d[expr] for d in data_sorted]
                    self._ax.plot(xs, ys, "o-", label=f"{amp_var}={amp}", markersize=4)

                self._ax.set_xlabel(f"Stroke ({move_var}) (mm)")
                self._ax.set_ylabel("Force (N)")
                self._ax.set_title("Force vs Stroke")
            else:
                # Only current is swept (or a single stroke position)
                # Plot Force vs Current (group by Stroke)
                move_groups: dict[float, list] = {}
                for row in rows:
                    m_val = float(row.get(move_var, 0.0))
                    move_groups.setdefault(m_val, []).append(row)

                for m_val, data in sorted(move_groups.items()):
                    data_sorted = sorted(data, key=lambda d: get_amp_numeric(d.get(amp_var, "0.0")))
                    xs = [get_amp_numeric(d.get(amp_var, "0.0")) for d in data_sorted]
                    ys = [d[expr] for d in data_sorted]
                    labels = [str(d.get(amp_var, "0.0")) for d in data_sorted]
                    
                    self._ax.plot(xs, ys, "o-", label=f"{move_var}={m_val} mm", markersize=4)
                    if len(xs) > 0:
                        self._ax.set_xticks(xs)
                        self._ax.set_xticklabels(labels, rotation=15)

                self._ax.set_xlabel(f"Current ({amp_var}) (A)")
                self._ax.set_ylabel("Force (N)")
                self._ax.set_title("Force vs Current")

            self._ax.legend(fontsize=7)
            self._ax.grid(True, alpha=0.3)
            self._fig.tight_layout()
            self._canvas.draw()

            self._log.append(
                f"Plot OK — {len(rows)} data points, "
                f"{len(amp_groups)} current levels"
            )

        except Exception as e:
            self._log.append(f"Results ERROR: {e}")
            self._ax.text(
                0.5, 0.5, f"Error:\n{e}",
                ha="center", va="center",
                transform=self._ax.transAxes, fontsize=9,
            )
            self._canvas.draw()

    # --- internal ---

    def _run_worker(self, config: RunConfig, phase: str):
        self._log.clear()
        self._log.append(
            f"[{phase.upper()}] {config.solver} ({config.mode})..."
        )
        self._log.append(f"Profile: {config.profile}")
        self._log.append("---")

        self._btn_build.setEnabled(False)
        self._btn_solve.setEnabled(False)

        self._worker = SolverWorker(config, phase)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_finished(self, result: SolveResult):
        """Handle simulation completion."""
        self._last_result = result
        self._btn_build.setEnabled(True)
        self._btn_solve.setEnabled(True)
        self._btn_results.setEnabled(
            result.ok and result.project_path is not None
        )

        status = "OK" if result.ok else "FAILED"
        self._log.append(f"\nResult: {status}")

        if result.errors:
            for err in result.errors:
                self._log.append(f"  ERROR: {err}")

        if result.commands:
            self._log.append(f"\nCommands ({len(result.commands)}):")
            for cmd in result.commands[:20]:
                self._log.append(
                    f"  {cmd['method']}: {cmd.get('args', {})}"
                )

        if result.project_path:
            self._log.append(f"\nProject: {result.project_path}")

        # Auto-fetch results if solve succeeded
        if result.ok and result.project_path:
            self._on_get_results()

    @staticmethod
    def _copy_config(cfg: RunConfig) -> RunConfig:
        """Shallow copy of RunConfig."""
        from dataclasses import asdict
        return RunConfig(**asdict(cfg))
