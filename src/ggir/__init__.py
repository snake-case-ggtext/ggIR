"""
ggir: an intermediate representation for rich text in plots

`parse()` turns markdown, HTML and inline CSS into a small document tree of
plain dataclasses (`Document`, `Paragraph`, `Span`, `Text`, `LineBreak`,
`Math`, `Image`). Renderers (e.g. ggtext for matplotlib and plotnine) walk
the tree and decide how to measure and draw it.

`resolve()` turns the tree into a flat list of tokens (`TextRun`,
`ImageRun`, `LINE_BREAK`) with concrete `Style`s, using a renderer's
`Policy` for the numbers (sup/sub size and shift, default em). The token
line break class is ``from ggir.resolve import LineBreak``; `ggir.LineBreak` is the tree
node. ggir itself does not import matplotlib.
"""

from .css import css_overrides, parse_color, parse_length, split_families
from .ir import (
    KNOWN_TAGS,
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
from .resolve import (
    LINE_BREAK,
    ImageRun,
    Policy,
    TextRun,
    Token,
    plain_text,
    resolve,
)
from .style import Style

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
    "KNOWN_TAGS",
    "resolve",
    "Style",
    "Policy",
    "TextRun",
    "ImageRun",
    "LINE_BREAK",
    "Token",
    "plain_text",
    "css_overrides",
    "parse_color",
    "parse_length",
    "split_families",
)
