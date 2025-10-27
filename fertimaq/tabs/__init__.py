"""Expose tab registry and load default tabs."""

from .base import FertiMaqTab, TabRegistry, tab_registry

# Import modules that register their tabs on import.
from . import escolha_talhao  # noqa: F401
from . import calculadora_manual  # noqa: F401

__all__ = ["FertiMaqTab", "TabRegistry", "tab_registry"]
