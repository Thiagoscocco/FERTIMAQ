"""Base classes and registry used to manage FertiMaq tabs."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Iterable, List, Tuple, Type, TypeVar, TYPE_CHECKING

import customtkinter as ctk


if TYPE_CHECKING:
    from fertimaq.app import FertiMaqApp  # circular import guard


class FertiMaqTab(ABC):
    """Abstract base for every tab rendered in the main Tabview."""

    tab_id: str
    title: str

    def __init__(self, app: "FertiMaqApp") -> None:
        self.app = app

    @abstractmethod
    def build(self, frame: ctk.CTkFrame) -> None:
        """Inflate widgets inside the provided frame."""

    def on_show(self) -> None:
        """Optional hook executed whenever the tab becomes active."""


T = TypeVar("T", bound=FertiMaqTab)


class TabRegistry:
    """Stores the ordered list of tab classes that compose the app."""

    def __init__(self) -> None:
        self._entries: List[Type[FertiMaqTab]] = []
        self._ids: Dict[str, Type[FertiMaqTab]] = {}

    def register(self, tab_cls: Type[T]) -> Type[T]:
        """Decorator/helper to register a new tab class."""
        if not getattr(tab_cls, "tab_id", None):
            raise ValueError("Tab class must define a non-empty 'tab_id'.")
        if not getattr(tab_cls, "title", None):
            raise ValueError("Tab class must define a non-empty 'title'.")
        if tab_cls.tab_id in self._ids:
            raise ValueError(f"Tab id '{tab_cls.tab_id}' already registered.")
        self._entries.append(tab_cls)
        self._ids[tab_cls.tab_id] = tab_cls
        return tab_cls

    def get_tabs(self) -> Tuple[Type[FertiMaqTab], ...]:
        """Return the registered tab classes preserving subscription order."""
        return tuple(self._entries)

    def __iter__(self) -> Iterable[Type[FertiMaqTab]]:
        return iter(self._entries)


tab_registry = TabRegistry()

__all__ = ["FertiMaqTab", "TabRegistry", "tab_registry"]
