"""Abstract base class for solver backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from ..models import DesignModel


@dataclass
class SolveResult:
    """Result from a solver execution."""

    ok: bool
    mode: str  # "2d" or "3d"
    solver: str  # "maxwell", "femm", "getdp"
    commands: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    force_data: list[dict[str, Any]] = field(default_factory=list)
    project_path: str | None = None


class SolverBackend(ABC):
    """Base class for all solver backends (Maxwell, FEMM, GetDP)."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable solver name."""
        ...

    @property
    @abstractmethod
    def supported_modes(self) -> list[str]:
        """List of supported modes: ['2d'], ['3d'], or ['2d', '3d']."""
        ...

    @abstractmethod
    def solve(
        self,
        design: DesignModel,
        mode: str = "2d",
        out_dir: str | None = None,
        dry_run: bool = False,
        **kwargs: Any,
    ) -> SolveResult:
        """Run simulation and return results.

        Args:
            design: Parsed DoSA design.
            mode: '2d' or '3d'.
            out_dir: Output directory for results.
            dry_run: If True, generate command log without executing.
            **kwargs: Backend-specific options.
        """
        ...

    def supports_mode(self, mode: str) -> bool:
        return mode in self.supported_modes
