"""
ggir: a rich text IR and layout engine for matplotlib

Markdown / HTML goes through four stages:

1. [](`~ggir.parse`): text -> document tree (pure data, no matplotlib)
2. [](`~ggir.to_boxes`): tree -> paragraphs of styled words, glue and breaks
3. [](`~ggir.layout_rect_box`): boxes -> words placed in a box, in points
4. [](`~ggir.box_artists`): layout -> matplotlib artists, in pixels

[](`~ggir.RichText`) wires all four into a `matplotlib.text.Text` subclass.

The layout engine is a port of R's gridtext by Claus O. Wilke.
"""

from typing import TYPE_CHECKING

# Imports are lazy so that `ggir.ir` (and `ggir.parse`) work without
# importing matplotlib.
_EXPORTS = {
    "ir": (
        "Document", "Paragraph", "Span", "Text", "LineBreak",
        "UnsupportedTagError", "parse", "parse_html",
    ),
    "boxes": ("Style", "TextBox", "Glue", "Break", "ParBox", "to_boxes", "markup_to_boxes"),
    "layout": ("Layout", "PlacedText", "layout_rect_box"),
    "metrics": ("measure_with",),
    "text": ("RichText",),
    "draw": ("box_artists", "box_extent", "box_transform", "rgba", "rounded_rect_path"),
    "units": ("unit", "as_pt", "as_pt_scalar", "as_margin_pt"),
}  # fmt: skip
_WHERE = {name: mod for mod, names in _EXPORTS.items() for name in names}

__all__ = tuple(_WHERE)


def __getattr__(name: str):
    if name in _WHERE:
        import importlib

        value = getattr(importlib.import_module(f".{_WHERE[name]}", __name__), name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(set(globals()) | set(__all__))


if TYPE_CHECKING:
    from .boxes import Break, Glue, ParBox, Style, TextBox, markup_to_boxes, to_boxes
    from .draw import box_artists, box_extent, box_transform, rgba, rounded_rect_path
    from .ir import (
        Document,
        LineBreak,
        Paragraph,
        Span,
        Text,
        UnsupportedTagError,
        parse,
        parse_html,
    )
    from .layout import Layout, PlacedText, layout_rect_box
    from .metrics import measure_with
    from .text import RichText
    from .units import as_margin_pt, as_pt, as_pt_scalar, unit
