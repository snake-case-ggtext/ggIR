"""
ggir: an intermediate representation for rich text in plots

`parse()` turns markdown, HTML and inline CSS into a small document tree of
plain dataclasses (`Document`, `Paragraph`, `Span`, `Text`, `LineBreak`,
`Math`, `Image`). Renderers (e.g. ggtext for matplotlib and plotnine) walk
the tree and decide how to measure and draw it. ggir itself does not
import matplotlib.
"""

from .css import css_overrides, parse_color, parse_length, split_families
from .ir import (
    Color,
    Document,
    Image,
    Length,
    LineBreak,
    Math,
    Node,
    Paragraph,
    Span,
    Text,
    UnsupportedTagError,
    parse,
)

__all__ = (
    "parse",
    "Document",
    "Paragraph",
    "Span",
    "Text",
    "LineBreak",
    "Math",
    "Image",
    "Length",
    "Color",
    "Node",
    "UnsupportedTagError",
    "css_overrides",
    "parse_color",
    "parse_length",
    "split_families",
)
