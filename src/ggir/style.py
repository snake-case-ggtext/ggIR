"""
Concrete text styles

A `Style` describes how one run of text is drawn, with every relative
value already resolved: sizes and baseline shifts are in points. Styles
are immutable and derived from one another, e.g. the style inside a
``<b>`` tag is the surrounding style with ``weight="bold"``.

`ggir.resolve` produces styles from the document tree. Renderers may
subclass `Style` to add their own helpers (e.g. ggtext adds matplotlib
``FontProperties`` conversion); `resolve` keeps the subclass of the base
style it is given. This module does not import matplotlib.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from .css import split_families

__all__ = ("Style",)


@dataclass(frozen=True)
class Style:
    """
    The visual style of a run of text

    Parameters
    ----------
    family :
        Font families in order of preference (names or generic families
        such as ``"serif"``). `None` means "inherit from the renderer".
    size :
        Font size in points. `None` means "inherit from the renderer".
    weight :
        Font weight, e.g. ``"normal"``, ``"bold"`` or 100-900.
    style :
        Font style: ``"normal"``, ``"italic"`` or ``"oblique"``.
    variant :
        ``"normal"`` or ``"small-caps"``.
    color :
        Text colour; `None` means "inherit from the renderer".
    background :
        Highlight colour drawn behind the run (CSS ``background-color``).
    underline, strike :
        Draw a line under / through the run.
    shift :
        Baseline shift in points (positive is up). Used by sup/sub and
        CSS ``vertical-align``.
    url :
        Hyperlink target.
    """

    family: tuple[str, ...] | None = None
    size: float | None = None
    weight: Any = None
    style: str | None = None
    variant: str | None = None
    color: Any = None
    background: Any = None
    underline: bool = False
    strike: bool = False
    shift: float = 0.0
    url: str | None = None

    def update(self, **kwargs: Any) -> Style:
        """
        A copy with some attributes replaced

        A ``family`` string is split at commas, as in CSS
        (``"Arial, sans-serif"`` -> ``("Arial", "sans-serif")``).
        """
        if "family" in kwargs and isinstance(kwargs["family"], str):
            kwargs["family"] = split_families(kwargs["family"])
        return replace(self, **kwargs)

    def resolve(self, base: Style) -> Style:
        """
        Fill in the attributes that are `None` from *base*

        Font attributes (family, size, weight, style, variant) and colour
        only; e.g. used to resolve a parsed style against a renderer's own
        default font at layout time.
        """
        values = {}
        for name in ("family", "size", "weight", "style", "variant", "color"):
            if getattr(self, name) is None:
                values[name] = getattr(base, name)
        return replace(self, **values) if values else self
