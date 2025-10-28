"""Expose tab registry and load default tabs."""

from .base import FertiMaqTab, TabRegistry, tab_registry

# Import modules that register their tabs on import.
from . import escolha_talhao  # noqa: F401
from . import dimensionamento_semeadora  # noqa: F401
from . import plantabilidade  # noqa: F401

__all__ = ["FertiMaqTab", "TabRegistry", "tab_registry"]
