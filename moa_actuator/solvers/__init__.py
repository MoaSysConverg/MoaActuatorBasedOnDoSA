"""Solver backend abstraction layer."""

from .base import SolverBackend, SolveResult
from .femm_backend import FemmBackend
from .getdp_backend import GetDPBackend
from .maxwell_backend import MaxwellBackend

__all__ = ["SolverBackend", "SolveResult", "MaxwellBackend", "FemmBackend", "GetDPBackend"]
