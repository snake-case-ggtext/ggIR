"""
Resolve a document tree into a flat list of styled runs

`parse` gives a tree of style *overrides*, relative to the parent.
`resolve` walks that tree from a base `Style` and gives the tokens a
renderer lays out: `TextRun`, `ImageRun` and `LINE_BREAK`, each run with
a concrete style. Relative sizes become points, ``<sup>``/``<sub>`` and
CSS ``vertical-align`` become baseline shifts, and colours are optionally
validated by a renderer-supplied callable.

The numbers that differ between renderers (how small and how high a
superscript is, what 1em is when no size is known) are in a `Policy`.

``resolve(parse("Hello **world**"), Style(size=10))`` gives::

    [TextRun("Hello ", Style(size=10)), TextRun("world", Style(size=10, weight="bold"))]

This module does not import matplotlib.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from typing import Any, Literal, Union

from .ir import (
    KNOWN_TAGS,
    Document,
    Image,
    LineBreak as _IRLineBreak,
    Math,
    Paragraph,
    Span,
    Text,
    _warn_once,
)
from .style import Style

__all__ = (
    "TextRun",
    "ImageRun",
    "LineBreak",
    "LINE_BREAK",
    "Token",
    "Policy",
    "resolve",
    "plain_text",
)


# --- tokens ------------------------------------------------------------------


@dataclass(frozen=True)
class TextRun:
    """A run of text drawn in a single style"""

    text: str
    style: Style
    math: bool = False


@dataclass(frozen=True)
class ImageRun:
    """An inline image (``<img>`` or ``![alt](src)``)"""

    src: str
    style: Style
    width: float | None = None  # points
    height: float | None = None  # points
    alt: str = ""


class LineBreak:
    """A hard line break (use the `LINE_BREAK` singleton)"""

    _instance: LineBreak | None = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "LINE_BREAK"


LINE_BREAK = LineBreak()

Token = Union[TextRun, ImageRun, LineBreak]


def plain_text(tokens: Sequence[Token]) -> str:
    """The text content of *tokens*: images give their alt text, breaks ``"\\n"``"""
    out = []
    for t in tokens:
        if isinstance(t, TextRun):
            out.append(t.text)
        elif isinstance(t, ImageRun):
            out.append(t.alt)
        else:
            out.append("\n")
    return "".join(out)


# --- policy ------------------------------------------------------------------


@dataclass(frozen=True)
class Policy:
    """
    The renderer-specific numbers used by `resolve`

    The defaults are ggtext's (matplotlib). Lengths are in ems of the
    parent font, i.e. multiples of its size in points.

    Parameters
    ----------
    default_em :
        Points per em when the style has no size (the base style left the
        size to the renderer). 10.0 is matplotlib's "medium".
    script_scale :
        Size of ``<sup>``/``<sub>`` text relative to its parent.
    sup_shift :
        Baseline shift of ``<sup>`` and CSS ``vertical-align: super``, in
        parent ems (positive is up).
    sub_shift :
        Baseline shift of ``<sub>`` and CSS ``vertical-align: sub``, in
        parent ems (negative is down).

    Notes
    -----
    Renderers that do not shift by a fixed fraction of the em can
    subclass `Policy` and override `script`. For example, R's gridtext
    draws scripts at 0.8x size and shifts them by half the parent font's
    ascent, which a subclass could look up from its font metrics for the
    parent style.
    """

    default_em: float = 10.0
    script_scale: float = 0.7
    sup_shift: float = 0.40
    sub_shift: float = -0.20

    def em(self, style: Style) -> float:
        """Points per em in *style*"""
        return style.size if style.size is not None else self.default_em

    def script(
        self, kind: Literal["sup", "sub"], em: float, parent: Style
    ) -> tuple[float, float]:
        """
        ``(size, shift)`` in points of *kind* script text

        *em* is the parent size in points (`default_em` if the parent has
        none) and *parent* the parent style. For CSS ``vertical-align``
        only the shift is used.
        """
        shift = self.sup_shift if kind == "sup" else self.sub_shift
        return em * self.script_scale, shift * em


# --- resolving ---------------------------------------------------------------

# Tags whose own meaning sets the font size. Their size is resolved against
# the parent (it may also come from the tag's inline CSS; ggIR keeps one
# size per node).
_SIZING_TAGS = frozenset({"small", "big", "font"})


def resolve(
    doc: Document,
    base: Style,
    *,
    policy: Policy = Policy(),
    validate_color: Callable[[Any], Any] | None = None,
    warn_unknown: bool = True,
    warn_prefix: str = "ggir",
) -> list[Token]:
    """
    Resolve a document tree into styled tokens

    Parameters
    ----------
    doc :
        The output of `ggir.parse`.
    base :
        The style of text outside of any markup. Every style in the
        result is derived from it with `dataclasses.replace`, so a
        subclass of `Style` is kept.
    policy :
        The renderer's numbers for em sizes and scripts.
    validate_color :
        Called with each colour string (CSS ``rgb()`` tuples are already
        valid) and returns the colour to use, or `None` if it is invalid.
        An invalid text colour warns once; either kind is then ignored.
        Without it colours are used as written.
    warn_unknown :
        Warn once for each tag not in `KNOWN_TAGS`. Parse with
        ``on_unknown="ignore"`` to avoid warning twice.
    warn_prefix :
        Start of the warning messages, e.g. the renderer's name.

    Returns
    -------
    list
        `TextRun` (``math=True`` for ``$...$``, delimiters included),
        `ImageRun` and `LINE_BREAK` tokens. Adjacent text runs with the
        same style are merged. A paragraph starts and ends a line, and a
        trailing paragraph does not leave an empty last line.
    """
    walker = _Walker(policy, validate_color, warn_unknown, warn_prefix)
    walker.walk(doc.children, base)
    return walker.finish()


class _Walker:
    def __init__(
        self,
        policy: Policy,
        validate_color: Callable[[Any], Any] | None,
        warn_unknown: bool,
        warn_prefix: str,
    ):
        self.policy = policy
        self.validate_color = validate_color
        self.warn_unknown = warn_unknown
        self.prefix = warn_prefix
        self.tokens: list[Token] = []
        # True after a paragraph closes, until real content follows: a
        # trailing paragraph must not leave an empty last line
        self.after_paragraph = False

    # tree -----------------------------------------------------------------
    def walk(self, nodes: Sequence, style: Style):
        for node in nodes:
            if isinstance(node, Text):
                self.text(node.text, style)
            elif isinstance(node, Math):
                self.tokens.append(TextRun(f"${node.tex}$", style, math=True))
                self.after_paragraph = False
            elif isinstance(node, _IRLineBreak):
                self.tokens.append(LINE_BREAK)
            elif isinstance(node, Image):
                self.image(node, style)
            elif isinstance(node, Paragraph):
                self.paragraph_break()
                self.walk(node.children, self.derive(node, style))
                self.paragraph_break()
                self.after_paragraph = True
            elif isinstance(node, Span):
                self.walk(node.children, self.derive(node, style))
            else:  # pragma: no cover - a node type this resolver doesn't know
                raise TypeError(f"{self.prefix}: unknown ggIR node {node!r}")

    def derive(self, node: Span | Paragraph, style: Style) -> Style:
        """The style inside *node*, a container in the parent *style*"""
        if self.warn_unknown and node.tag not in KNOWN_TAGS:
            _warn_once(f"{self.prefix}: unsupported HTML tag <{node.tag}> was ignored")

        policy = self.policy
        em = policy.em(style)
        size = style.size
        shift = style.shift

        # What the tag itself does
        script = getattr(node, "script", None)
        if script is not None:
            size, dy = policy.script(script, em, style)
            shift = shift + dy
        if node.size is not None and node.tag in _SIZING_TAGS:
            size = node.size.to_pt(em)

        # Inline CSS: relative values are relative to the size after the tag
        css_em = size if size is not None else policy.default_em
        if node.size is not None and node.tag not in _SIZING_TAGS:
            size = node.size.to_pt(css_em)
        valign = getattr(node, "valign", None)
        if valign in ("super", "sub"):
            shift = (
                shift
                + policy.script("sup" if valign == "super" else "sub", css_em, style)[1]
            )
        elif valign == "baseline":
            shift = 0.0
        elif valign is not None:
            shift = shift + valign.to_pt(css_em)

        changes: dict[str, Any] = {}
        if size != style.size:
            changes["size"] = size
        if shift != style.shift:
            changes["shift"] = shift
        for name in ("weight", "style", "variant", "family", "underline", "strike"):
            value = getattr(node, name)
            if value is not None:
                changes[name] = value
        if node.color is not None and (c := self.color(node.color, True)) is not None:
            changes["color"] = c
        if (
            node.background is not None
            and (c := self.color(node.background, False)) is not None
        ):
            changes["background"] = c
        if node.href is not None:
            changes["url"] = node.href
        return replace(style, **changes) if changes else style

    def color(self, value: Any, warn: bool) -> Any:
        """The colour to use for *value*, or None (with a warning if *warn*)"""
        if isinstance(value, tuple) or self.validate_color is None:
            return value
        color = self.validate_color(value)
        if color is None and warn:
            _warn_once(f"{self.prefix}: invalid color {value!r}")
        return color

    # tokens ---------------------------------------------------------------
    def text(self, s: str, style: Style):
        if not s:
            return
        if s.strip():
            self.after_paragraph = False
        tokens = self.tokens
        # Merge with the previous run if the style is the same
        if (
            tokens
            and isinstance(prev := tokens[-1], TextRun)
            and not prev.math
            and prev.style == style
        ):
            tokens[-1] = TextRun(prev.text + s, style)
        else:
            tokens.append(TextRun(s, style))

    def image(self, node: Image, style: Style):
        em = self.policy.em(style)
        width = node.width.to_pt(em) if node.width is not None else None
        height = node.height.to_pt(em) if node.height is not None else None
        self.tokens.append(ImageRun(node.src, style, width, height, node.alt))
        self.after_paragraph = False

    def paragraph_break(self):
        """Start a new line unless already at the start of one"""
        if self.tokens and self.tokens[-1] is not LINE_BREAK:
            self.tokens.append(LINE_BREAK)

    def finish(self) -> list[Token]:
        if self.after_paragraph and self.tokens and self.tokens[-1] is LINE_BREAK:
            self.tokens.pop()
        return self.tokens
