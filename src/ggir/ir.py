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

import re
import warnings
from dataclasses import dataclass, field, fields
from functools import lru_cache
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
        """
        The text content without markup

        Images give their alt text, math gives ``$tex$``, and line breaks
        and paragraph boundaries give ``"\\n"`` (one per boundary, none
        at the start or end).
        """
        out: list[str] = []
        _plain_text(self.children, out, [False])
        return "".join(out)


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
    return _parse(
        text,
        markdown=markdown,
        html=html,
        math=math,
        newline=newline,
        blocks=blocks,
        on_unknown=on_unknown,
    )


# --- plain text ------------------------------------------------------------------


def _plain_text(nodes: list[Node], out: list[str], pending: list[bool]):
    """Append the text of *nodes* to *out*; *pending* marks a closed block"""

    def newline():
        if out and out[-1] != "\n":
            out.append("\n")

    for node in nodes:
        if isinstance(node, Paragraph):
            newline()
            pending[0] = False
            _plain_text(node.children, out, pending)
            pending[0] = True
        elif isinstance(node, Span):
            _plain_text(node.children, out, pending)
        else:
            if pending[0]:
                newline()
                pending[0] = False
            if isinstance(node, Text):
                piece = node.text
            elif isinstance(node, Math):
                piece = f"${node.tex}$"
            elif isinstance(node, Image):
                piece = node.alt
            else:
                piece = "\n"
            if piece:
                out.append(piece)


# --- the parser ------------------------------------------------------------------
# Adapted from ggtext's _parse.py (Shannon E. Ellis, MIT). Where ggtext
# flattens to styled tokens, we build a tree: opening a tag adds a child
# container and makes it current; closing the tag makes its parent current.

# Mathtext segments must not be touched by the markdown parser
# (``$a_1 * b_2$`` has underscores and stars). Each segment is swapped for
# a placeholder of private-use characters and restored afterwards.
_PH_OPEN, _PH_CLOSE = "", ""
_PH_RE = re.compile(f"{_PH_OPEN}(\\d+){_PH_CLOSE}")
_MATH_RE = re.compile(r"(?<!\\)\$(?:\\.|[^$\\])+?(?<!\\)\$")

_TAG_RE = re.compile(
    r"^<\s*(?P<close>/)?\s*(?P<name>[a-zA-Z][\w:-]*)(?P<attrs>.*?)(?P<self>/)?\s*>$",
    re.DOTALL,
)
_ATTR_RE = re.compile(
    r"""(?P<key>[^\s"'>/=]+)(?:\s*=\s*(?P<val>"[^"]*"|'[^']*'|[^\s"'>]+))?"""
)
_HTML_IN_TEXT_RE = re.compile(r"<!--.*?-->|</?[a-zA-Z][^<>]*>", re.DOTALL)
_BLOCK_SEP_RE = re.compile(r"\n\s*\n")

_VOID_TAGS = {"br", "img", "hr", "wbr"}
_BLOCK_TAGS = {"p", "div"}
_KNOWN_TAGS = {
    "b", "strong", "i", "em", "u", "ins", "s", "del", "strike", "sup", "sub",
    "br", "span", "font", "code", "kbd", "tt", "samp", "small", "big",
    "mark", "a", "p", "div", "img", "wbr", "hr",
}  # fmt: skip
_MONOSPACE = ("monospace",)
_PARAGRAPH_FIELDS = {f.name for f in fields(Paragraph)}

# Messages already warned about (once per session)
_warned: set[str] = set()


def _user_stacklevel() -> int:
    """The `warnings.warn` stacklevel of the first frame outside ggir"""
    import os
    import sys

    pkg = os.path.dirname(__file__)
    frame, level = sys._getframe(1), 1
    while frame is not None and os.path.dirname(frame.f_code.co_filename) == pkg:
        frame, level = frame.f_back, level + 1
    return level


def _warn_once(msg: str):
    if msg not in _warned:
        _warned.add(msg)
        warnings.warn(msg, UserWarning, stacklevel=_user_stacklevel())


def _protect_math(s: str) -> tuple[str, list[str]]:
    segments: list[str] = []

    def repl(m: re.Match) -> str:
        segments.append(m.group(0))
        return f"{_PH_OPEN}{len(segments) - 1}{_PH_CLOSE}"

    return _MATH_RE.sub(repl, s), segments


def _parse_tag(raw: str) -> tuple[str, dict[str, str], str] | None:
    """
    Parse one HTML tag into ``(name, attrs, kind)``, kind being
    ``"open"``, ``"close"`` or ``"void"``; `None` if not a tag (a comment)
    """
    m = _TAG_RE.match(raw.strip())
    if not m:
        return None
    name = m["name"].lower()
    attrs = {}
    for am in _ATTR_RE.finditer(m["attrs"] or ""):
        val = am["val"]
        if val is None:
            val = ""
        elif val[:1] in "\"'":
            val = val[1:-1]
        attrs[am["key"].lower()] = val
    if m["close"]:
        kind = "close"
    elif m["self"] or name in _VOID_TAGS:
        kind = "void"
    else:
        kind = "open"
    return name, attrs, kind


def _is_number(s: str) -> bool:
    try:
        float(s)
    except (TypeError, ValueError):
        return False
    return True


class _Builder:
    """Builds the tree while tracking a stack of open containers"""

    def __init__(
        self, root: Document | Paragraph, segments: list[str], on_unknown: str
    ):
        self.root = root
        self.stack: list[tuple[str, Span | Paragraph]] = []
        self.segments = segments
        self.on_unknown = on_unknown

    @property
    def children(self) -> list[Node]:
        return self.stack[-1][1].children if self.stack else self.root.children

    # leaves ------------------------------------------------------------------
    def text(self, s: str, *, verbatim: bool = False):
        """Add text, restoring protected math segments"""
        pos = 0
        for m in _PH_RE.finditer(s):
            self._add_text(s[pos : m.start()])
            seg = self.segments[int(m.group(1))]
            if verbatim:
                self._add_text(seg)
            else:
                self.children.append(Math(seg[1:-1]))
            pos = m.end()
        self._add_text(s[pos:])

    def _add_text(self, s: str):
        if not s:
            return
        children = self.children
        if children and isinstance(children[-1], Text):
            children[-1] = Text(children[-1].text + s)
        else:
            children.append(Text(s))

    def line_break(self):
        self.children.append(LineBreak())

    def image(self, src: str, attrs: dict[str, str], alt: str = ""):
        from .css import css_overrides, parse_length

        def length(key: str) -> Length | None:
            if key not in attrs:
                return None
            # Bare numbers in width / height attributes are CSS pixels
            if _is_number(attrs[key]):
                return Length(float(attrs[key]) * 0.75, "pt")
            return parse_length(attrs[key])

        img = Image(src, length("width"), length("height"), alt or attrs.get("alt", ""))
        if css := attrs.get("style"):
            self.children.append(Span([img], tag="img", **css_overrides(css)))
        else:
            self.children.append(img)

    # containers ----------------------------------------------------------------
    def push(self, key: str, node: Span | Paragraph):
        self.children.append(node)
        self.stack.append((key, node))

    def pop(self, key: str):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == key:
                del self.stack[i:]
                return
        if not key.startswith("md:"):
            _warn_once(f"ggir: closing tag </{key}> has no opening tag")

    def node_for_tag(self, name: str, attrs: dict[str, str]) -> Span | Paragraph:
        """The container for an opening tag *name* with *attrs*"""
        from .css import (
            BIG_SCALE,
            SMALL_SCALE,
            css_overrides,
            parse_color,
            parse_length,
            split_families,
        )

        f: dict = {}
        if name in ("b", "strong"):
            f["weight"] = "bold"
        elif name in ("i", "em"):
            f["style"] = "italic"
        elif name in ("u", "ins"):
            f["underline"] = True
        elif name in ("s", "del", "strike"):
            f["strike"] = True
        elif name in ("sup", "sub"):
            f["script"] = name
        elif name in ("code", "kbd", "tt", "samp"):
            f["family"] = _MONOSPACE
        elif name == "small":
            f["size"] = Length(SMALL_SCALE, "em")
        elif name == "big":
            f["size"] = Length(BIG_SCALE, "em")
        elif name == "mark":
            f["background"] = "yellow"
        elif name == "a":
            if "href" in attrs:
                f["href"] = attrs["href"]
        elif name == "font":
            if "color" in attrs and (c := parse_color(attrs["color"])) is not None:
                f["color"] = c
            if attrs.get("face"):
                f["family"] = split_families(attrs["face"])
            if "size" in attrs and (size := parse_length(attrs["size"])) is not None:
                f["size"] = size
        elif name not in _KNOWN_TAGS:
            msg = f"ggir: the HTML tag <{name}> isn't supported"
            if self.on_unknown == "error":
                raise UnsupportedTagError(msg)
            if self.on_unknown == "warn":
                _warn_once(f"{msg}; it is treated as a plain span")

        # Any tag may carry inline CSS
        if css := attrs.get("style"):
            f.update(css_overrides(css))

        if name in _BLOCK_TAGS:
            f = {k: v for k, v in f.items() if k in _PARAGRAPH_FIELDS}
            return Paragraph(tag=name, **f)
        return Span(tag=name, **f)

    def html_tag(self, raw: str):
        parsed = _parse_tag(raw)
        if parsed is None:  # comments, doctype, ...
            return
        name, attrs, kind = parsed
        if kind == "close":
            if name not in _VOID_TAGS:
                self.pop(name)
        elif name == "br":
            self.line_break()
        elif name == "img":
            self.image(attrs.get("src", ""), attrs)
        elif name in ("wbr", "hr"):
            pass
        elif kind == "open":
            self.push(name, self.node_for_tag(name, attrs))
        # a self-closed non-void tag (<span/>) has no content: ignore


def _split_newlines(b: _Builder, s: str, newline: str):
    """Add text that may contain newline characters"""
    for i, part in enumerate(s.split("\n")):
        if i:
            if newline == "break":
                b.line_break()
            else:
                b.text(" ")
        b.text(part)


@lru_cache(maxsize=1)
def _markdown_parser():
    from markdown_it import MarkdownIt

    return MarkdownIt("commonmark", {"html": True}).enable("strikethrough")


_MD_OPEN = {
    "strong_open": ("md:strong", "strong", {"weight": "bold"}),
    "em_open": ("md:em", "em", {"style": "italic"}),
    "s_open": ("md:s", "s", {"strike": True}),
}
_MD_CLOSE = {
    "strong_close": "md:strong",
    "em_close": "md:em",
    "s_close": "md:s",
    "link_close": "md:a",
}


def _parse_markdown(s: str, b: _Builder, newline: str):
    tokens = _markdown_parser().parseInline(s)
    children = tokens[0].children if tokens and tokens[0].children else []
    for tok in children:
        t = tok.type
        if t == "text":
            _split_newlines(b, tok.content, newline)
        elif t == "softbreak":
            if newline == "break":
                b.line_break()
            else:
                b.text(" ")
        elif t == "hardbreak":
            b.line_break()
        elif t in _MD_OPEN:
            key, tag, f = _MD_OPEN[t]
            b.push(key, Span(tag=tag, **f))
        elif t in _MD_CLOSE:
            b.pop(_MD_CLOSE[t])
        elif t == "code_inline":
            b.push("md:code", Span(tag="code", family=_MONOSPACE))
            b.text(tok.content, verbatim=True)
            b.pop("md:code")
        elif t == "link_open":
            b.push("md:a", Span(tag="a", href=str(tok.attrGet("href") or "")))
        elif t == "image":
            b.image(str(tok.attrGet("src") or ""), {}, alt=tok.content or "")
        elif t == "html_inline":
            b.html_tag(tok.content)
        else:  # pragma: no cover - future token types
            _split_newlines(b, tok.content, newline)


def _parse_html(s: str, b: _Builder, newline: str):
    """Parse text that may contain HTML tags but no markdown"""
    import html

    def unescape(chunk: str) -> str:
        return html.unescape(chunk).replace(r"\$", "$")

    pos = 0
    for m in _HTML_IN_TEXT_RE.finditer(s):
        _split_newlines(b, unescape(s[pos : m.start()]), newline)
        b.html_tag(m.group(0))
        pos = m.end()
    _split_newlines(b, unescape(s[pos:]), newline)


def _parse(
    text: str | None,
    *,
    markdown: bool,
    html: bool,
    math: bool,
    newline: str,
    blocks: bool,
    on_unknown: str,
) -> Document:
    if newline not in ("break", "space"):
        raise ValueError(f"newline must be 'break' or 'space', not {newline!r}")
    if on_unknown not in ("warn", "error", "ignore"):
        raise ValueError(
            f"on_unknown must be 'warn', 'error' or 'ignore', not {on_unknown!r}"
        )

    doc = Document()
    if text is None or (isinstance(text, float) and text != text):
        return doc
    s = str(text)

    # Protect math before splitting into blocks, so that a segment can't
    # be cut in two
    segments: list[str] = []
    if math and s.count("$") - s.count(r"\$") >= 2:
        s, segments = _protect_math(s)

    if blocks:
        chunks = [c.strip() for c in _BLOCK_SEP_RE.split(s)]
        targets: list[tuple[str, Document | Paragraph]] = []
        for chunk in chunks:
            if chunk:
                par = Paragraph(tag="p")
                doc.children.append(par)
                targets.append((chunk, par))
    else:
        targets = [(s, doc)]

    for chunk, root in targets:
        # Tags left open at the end of a block are closed there
        b = _Builder(root, segments, on_unknown)
        if markdown:
            _parse_markdown(chunk, b, newline)
        elif html:
            _parse_html(chunk, b, newline)
        else:
            _split_newlines(b, chunk.replace(r"\$", "$") if math else chunk, newline)
    return doc
