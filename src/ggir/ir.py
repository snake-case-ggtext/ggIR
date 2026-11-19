"""
The intermediate representation: a small document tree for rich text

Markdown, HTML and inline CSS are parsed into a tree of plain dataclasses.
The tree records *what* the text says and *how it is marked up*, as
overrides relative to the parent. It holds no fonts, measurements or
positions, and building it does not import matplotlib.

Consumers (ggir's own box layout, ggtext's token layout, ...) walk the
tree and decide how to realise each construct. For example, `script="sup"`
says "superscript"; how much smaller and how far up is the consumer's
choice (gridtext uses 0.8x size and half the ascent, CSS-style renderers
use other numbers).

Conventions
-----------
- `None` on a style field means "inherit from the parent".
- Absolute lengths are in points. Relative lengths (``em``, ``%``, CSS
  size keywords, ``<small>``/``<big>``) are kept relative as
  ``Length(x, "em")`` and resolved by the consumer against the parent's
  font size.
- Colours are kept as written (a CSS/matplotlib colour string), except
  that CSS ``rgb()``/``rgba()`` are converted to an RGBA tuple in [0, 1].
  Validating colour names needs matplotlib, so it is left to consumers.
- `Text` keeps whitespace as written. U+00A0 (``&nbsp;``) is a
  non-breaking space: consumers must not break lines at it.

``parse("A **bold** claim, $x^2$")`` gives::

    Document
    ├── Text("A ")
    ├── Span(tag="strong", weight="bold")
    │   └── Text("bold")
    ├── Text(" claim, ")
    └── Math("x^2")

The parser is adapted from Shannon E. Ellis's ggtext for Python (MIT).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Union

__all__ = (
    "Length",
    "Text",
    "LineBreak",
    "Math",
    "Image",
    "Span",
    "Paragraph",
    "Document",
    "Node",
    "Color",
    "UnsupportedTagError",
    "parse",
)


# --- values ------------------------------------------------------------------


@dataclass(frozen=True)
class Length:
    """
    A length: absolute (``"pt"``) or relative to the parent font size
    (``"em"``)
    """

    value: float
    unit: Literal["pt", "em"] = "pt"

    def to_pt(self, em: float) -> float:
        """Resolve to points, given the size of 1em in points"""
        return self.value * em if self.unit == "em" else self.value


# A colour as written ("red", "#ff0000", "C0", "tab:blue", ...) or an
# RGBA tuple with channels in [0, 1] (from CSS rgb()/rgba())
Color = Union[str, tuple[float, ...]]


# --- leaves ------------------------------------------------------------------


@dataclass
class Text:
    """A run of text; whitespace as written, U+00A0 is non-breaking"""

    text: str


@dataclass
class LineBreak:
    """A forced line break (``<br>``, a markdown hard break, or ``\\n``)"""


@dataclass
class Math:
    """A matplotlib mathtext segment, without the ``$`` delimiters"""

    tex: str


@dataclass
class Image:
    """
    An inline image (``<img>`` or ``![alt](src)``)

    A size of `None` lets the consumer choose (e.g. the font height).
    """

    src: str
    width: Length | None = None
    height: Length | None = None
    alt: str = ""


# --- containers ----------------------------------------------------------------


@dataclass
class _Styled:
    """Style overrides shared by inline and block containers"""

    children: list[Node] = field(default_factory=list)
    tag: str = "span"  # source tag, e.g. "strong", "em", "code", "p"
    weight: str | int | None = None  # "bold", "normal", 100-900
    style: str | None = None  # font style: "normal", "italic", "oblique"
    variant: str | None = None  # "normal", "small-caps"
    family: tuple[str, ...] | None = None  # in order of preference
    size: Length | None = None  # font size
    color: Color | None = None
    background: Color | None = None
    underline: bool | None = None
    strike: bool | None = None
    href: str | None = None


@dataclass
class Span(_Styled):
    """
    Inline content with style overrides

    Parameters
    ----------
    script :
        ``"sup"`` / ``"sub"`` from the HTML tags: the content is smaller
        *and* raised / lowered. The amounts are the consumer's choice.
    valign :
        CSS ``vertical-align``: ``"super"`` / ``"sub"`` shift the
        baseline without changing the size, ``"baseline"`` resets any
        inherited shift, and a `Length` shifts by that much (up is
        positive, ``em`` relative to the parent font size).
    """

    script: Literal["sup", "sub"] | None = None
    valign: Literal["super", "sub", "baseline"] | Length | None = None


@dataclass
class Paragraph(_Styled):
    """
    A block (``<p>``, ``<div>``, or a blank-line separated chunk of
    markdown when parsing with ``blocks=True``)

    Content after a paragraph starts on a new line.
    """

    tag: str = "p"


@dataclass
class Document:
    """
    Root of the tree

    Children may be a mix of inline nodes and paragraphs, as in HTML.
    """

    children: list[Node] = field(default_factory=list)

    def plain_text(self) -> str:
        """The text content without markup (images give their alt text)"""
        raise NotImplementedError


Node = Union[Text, LineBreak, Math, Image, Span, Paragraph]


class UnsupportedTagError(ValueError):
    """An unknown tag was found while parsing with ``on_unknown="error"``"""


def parse(
    text: str | None,
    *,
    markdown: bool = True,
    html: bool = True,
    math: bool = True,
    newline: Literal["break", "space"] = "break",
    blocks: bool = False,
    on_unknown: Literal["warn", "error", "ignore"] = "warn",
) -> Document:
    """
    Parse markdown / HTML / inline CSS into a document tree

    Parameters
    ----------
    text :
        The text. `None` and NaN give an empty document.
    markdown :
        Interpret inline markdown (CommonMark inline syntax plus
        ``~~strike~~``). Block syntax (lists, headings, quotes) is left
        as literal text, so ``"1. Adelie"`` stays as typed.
    html :
        Interpret HTML tags when ``markdown=False`` (with markdown, tags
        are always recognised). If both are `False`, the text is literal.
    math :
        Treat ``$...$`` segments as matplotlib mathtext (`Math` nodes).
        ``\\$`` is a literal dollar.
    newline :
        What a ``"\\n"`` in the text means: ``"break"`` (matplotlib's
        convention) or ``"space"`` (markdown / HTML / R ggtext).
    blocks :
        Split the text at blank lines into `Paragraph` nodes, as markdown
        paragraphs (R ggtext / gridtext behaviour).
    on_unknown :
        What to do with an unsupported tag: warn once and treat it as a
        plain `Span`, raise [](`~ggir.ir.UnsupportedTagError`), or ignore.
    """
    raise NotImplementedError
