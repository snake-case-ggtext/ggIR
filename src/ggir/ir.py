"""
The intermediate representation: a small, resolved document tree

Markdown is converted to HTML, and the supported subset of HTML is parsed
into a tree of plain dataclasses. The tree holds *what* the text says and
*how it is styled* (as overrides relative to the parent), but no fonts,
measurements or positions, so building it needs neither matplotlib nor a
renderer. [](`~ggir.boxes.to_boxes`) turns a tree into boxes for layout.

Supported tags (the same as gridtext): ``<p>``, ``<b>``/``<strong>``,
``<i>``/``<em>``, ``<br>``, ``<span>``, ``<sup>``, ``<sub>``.
Supported CSS properties in a ``style`` attribute: ``color``,
``font-size`` and ``font-family``.

Example
-------
``parse("A **bold** claim")`` gives::

    Document
    └── Paragraph
        ├── Text("A ")
        ├── Span(bold=True, tag="strong")
        │   └── Text("bold")
        └── Text(" claim")
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Literal, Union

import markdown as _markdown

__all__ = (
    "Document",
    "Paragraph",
    "Span",
    "Text",
    "LineBreak",
    "Node",
    "parse",
    "parse_html",
    "to_html",
    "parse_css",
    "convert_css_unit_pt",
    "UnsupportedTagError",
)


@dataclass
class Text:
    """A run of text, whitespace as written in the source"""

    text: str


@dataclass
class LineBreak:
    """A forced line break (``<br>``)"""


@dataclass
class _Styled:
    children: list[Node] = field(default_factory=list)
    bold: bool = False
    italic: bool = False
    color: str | None = None
    fontsize: float | None = None  # points, absolute
    family: str | None = None


@dataclass
class Span(_Styled):
    """
    Inline content with style overrides

    `script` (``"sup"`` / ``"sub"``) shrinks the font to 80% of the
    parent's size and raises / lowers the baseline by half the ascent.
    """

    script: Literal["sup", "sub"] | None = None
    tag: str = "span"  # source tag, informational


@dataclass
class Paragraph(_Styled):
    """A paragraph (``<p>``); it always ends with a line break"""


@dataclass
class Document:
    """
    Root of the tree

    Its children are usually paragraphs (markdown always produces them),
    but inline content outside a paragraph is allowed, as in HTML.
    """

    children: list[Node] = field(default_factory=list)

    def plain_text(self) -> str:
        """The text content, without markup"""
        out: list[str] = []

        def walk(nodes, depth=0):
            for n in nodes:
                if isinstance(n, Text):
                    out.append(n.text)
                elif isinstance(n, LineBreak):
                    out.append("\n")
                elif isinstance(n, Paragraph):
                    if out and not out[-1].endswith("\n"):
                        out.append("\n")
                    walk(n.children)
                    out.append("\n")
                else:
                    walk(n.children)

        walk(self.children)
        return re.sub(r"[ \t]+", " ", "".join(out)).strip()


Node = Union[Text, LineBreak, Span, Paragraph]


class UnsupportedTagError(ValueError):
    """A tag outside the supported subset was encountered"""


_UNSUPPORTED_MSG = (
    "ggir has encountered a tag that isn't supported yet: <{}>\n"
    "Only a very limited number of tags are currently supported."
)

_INLINE_TAGS = {"b", "strong", "i", "em", "span", "sup", "sub"}
_SUPPORTED_TAGS = _INLINE_TAGS | {"p", "br"}


# --- CSS ---------------------------------------------------------------------


def parse_css(style: str | None) -> dict[str, str]:
    """Parse an inline CSS declaration list into a dict"""
    out: dict[str, str] = {}
    if not style:
        return out
    for decl in style.split(";"):
        if ":" not in decl:
            continue
        k, v = decl.split(":", 1)
        out[k.strip().lower()] = v.strip()
    return out


_CSS_UNIT_RE = re.compile(r"^\s*([0-9]*\.?[0-9]+)\s*([a-z%]*)\s*$")
_CSS_TO_PT = {
    "pt": 1.0,
    "px": 72 / 96,
    "in": 72.0,
    "cm": 72 / 2.54,
    "mm": 72 / 25.4,
}


def convert_css_unit_pt(x: str) -> float:
    """Convert a CSS length (e.g. ``"12px"``) to points"""
    m = _CSS_UNIT_RE.match(x)
    if not m:
        raise ValueError(f"Cannot parse CSS length {x!r}")
    value, u = float(m.group(1)), m.group(2) or "pt"
    if u not in _CSS_TO_PT:
        raise ValueError(f"Cannot convert {value}{u} to pt.")
    return value * _CSS_TO_PT[u]


def _css_overrides(style_attr: str | None) -> dict:
    css = parse_css(style_attr)
    kw: dict = {}
    if "color" in css:
        kw["color"] = css["color"]
    if "font-family" in css:
        kw["family"] = css["font-family"].strip("'\"")
    if "font-size" in css:
        kw["fontsize"] = convert_css_unit_pt(css["font-size"])
    return kw


# --- HTML -> tree --------------------------------------------------------------


class _TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.doc = Document()
        # (tag, children list of the open element)
        self.stack: list[tuple[str, list[Node]]] = [("body", self.doc.children)]

    @property
    def children(self) -> list[Node]:
        return self.stack[-1][1]

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag not in _SUPPORTED_TAGS:
            raise UnsupportedTagError(_UNSUPPORTED_MSG.format(tag))
        if tag == "br":
            self.children.append(LineBreak())
            return
        kw = _css_overrides(dict(attrs).get("style"))
        node: Span | Paragraph
        if tag == "p":
            node = Paragraph(**kw)
        else:
            node = Span(
                tag=tag,
                bold=tag in ("b", "strong"),
                italic=tag in ("i", "em"),
                script=tag if tag in ("sup", "sub") else None,  # type: ignore[arg-type]
                **kw,
            )
        self.children.append(node)
        self.stack.append((tag, node.children))

    def handle_startendtag(self, tag, attrs):
        if tag.lower() == "br":
            self.children.append(LineBreak())
        else:
            self.handle_starttag(tag, attrs)
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        tag = tag.lower()
        # close the innermost matching element (and anything inside it)
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        if not data:
            return
        children = self.children
        if children and isinstance(children[-1], Text):
            children[-1].text += data
        else:
            children.append(Text(data))


def to_html(text: str, use_markdown: bool = True) -> str:
    """Convert markdown to HTML (or pass HTML through)"""
    if use_markdown:
        return _markdown.markdown(text)
    return text


def parse_html(html: str) -> Document:
    """Parse (the supported subset of) HTML into a tree"""
    b = _TreeBuilder()
    b.feed(html)
    b.close()
    return b.doc


def parse(text: str | None, use_markdown: bool = True) -> Document:
    """
    Parse markdown (or HTML) into a tree

    Parameters
    ----------
    text :
        Markdown or HTML. `None` and NaN give an empty document.
    use_markdown :
        Whether to run the text through a markdown processor first.
        If `False`, the text is taken to be HTML.
    """
    if text is None or (isinstance(text, float) and text != text):
        text = ""
    return parse_html(to_html(str(text), use_markdown))
