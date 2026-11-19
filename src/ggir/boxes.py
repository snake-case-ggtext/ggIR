"""
Boxes: the tree flattened into what the line breaker consumes

Each paragraph becomes a flat list of text boxes (words with a resolved
style), glue (breakable inter-word space) and forced breaks, as in
gridtext's `process_tags()`. Resolving styles needs font metrics for the
``<sup>`` / ``<sub>`` baseline shift, so this step uses matplotlib.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Union

from .ir import Document, LineBreak, Node, Paragraph, Span, Text, parse
from .metrics import font_ascent

__all__ = ("Style", "TextBox", "Glue", "Break", "ParBox", "to_boxes", "markup_to_boxes")


@dataclass(frozen=True)
class Style:
    """Font and colour state (the `gp` of a gridtext drawing context)"""

    fontsize: float = 11.0
    family: str | None = None
    weight: str = "normal"
    style: str = "normal"
    color: object = "black"
    lineheight: float = 1.2


@dataclass
class TextBox:
    text: str
    style: Style
    voff: float = 0.0  # vertical offset from baseline, pt


@dataclass
class Glue:
    style: Style


@dataclass
class Break:
    pass


BoxNode = Union[TextBox, Glue, Break]


@dataclass
class ParBox:
    """A paragraph of boxes (gridtext's `ParBox` content)"""

    nodes: list[BoxNode] = field(default_factory=list)
    linespacing: float = 0.0  # pt
    halign: float = 0.0


@dataclass(frozen=True)
class _Context:
    style: Style
    yoff: float = 0.0


def _resolve(ctx: _Context, node: Span | Paragraph) -> _Context:
    st = ctx.style
    script = getattr(node, "script", None)
    if script:
        # shrink first, so that an explicit font-size wins
        st = replace(st, fontsize=0.8 * st.fontsize)
    kw: dict = {}
    if node.color is not None:
        kw["color"] = node.color
    if node.family is not None:
        kw["family"] = node.family
    if node.fontsize is not None:
        kw["fontsize"] = node.fontsize
    if node.bold:
        kw["weight"] = "bold"
    if node.italic:
        kw["style"] = "italic"
    if kw:
        st = replace(st, **kw)
    yoff = ctx.yoff
    if script:
        shift = font_ascent(st) / 2
        yoff += shift if script == "sup" else -shift
    return _Context(st, yoff)


class _Flattener:
    def __init__(self, halign: float):
        self.halign = halign
        self.pars: list[ParBox] = []
        self.loose: ParBox | None = None

    def _new_par(self, ctx: _Context) -> ParBox:
        st = ctx.style
        par = ParBox(linespacing=st.lineheight * st.fontsize, halign=self.halign)
        self.pars.append(par)
        return par

    def _current(self, ctx: _Context, in_par: bool) -> ParBox:
        if in_par:
            return self.pars[-1]
        if self.loose is None:
            self.loose = self._new_par(ctx)
        return self.loose

    def walk(self, nodes: list[Node], ctx: _Context, in_par: bool):
        for n in nodes:
            if isinstance(n, Text):
                self.text(n.text, ctx, in_par)
            elif isinstance(n, LineBreak):
                self._end_line(self._current(ctx, in_par), ctx)
            elif isinstance(n, Paragraph):
                c = _resolve(ctx, n)
                self.loose = None
                self._new_par(c)
                self.walk(n.children, c, True)
                self._end_line(self.pars[-1], c)
            else:
                self.walk(n.children, _resolve(ctx, n), in_par)

    @staticmethod
    def _end_line(par: ParBox, ctx: _Context):
        par.nodes.append(TextBox("", ctx.style, ctx.yoff))
        par.nodes.append(Break())

    def text(self, data: str, ctx: _Context, in_par: bool):
        # whitespace between blocks (e.g. "\n" between </p><p>)
        if data.strip() == "" and not in_par:
            return
        tokens = data.split()
        boxes: list[BoxNode] = []
        if data[:1].isspace():
            boxes.append(Glue(ctx.style))
        for tok in tokens:
            boxes.append(TextBox(tok, ctx.style, ctx.yoff))
            boxes.append(Glue(ctx.style))
        if not tokens:
            boxes = [Glue(ctx.style)]
        elif not data[-1:].isspace():
            boxes.pop()
        self._current(ctx, in_par).nodes.extend(boxes)


def to_boxes(doc: Document, style: Style, halign: float = 0.0) -> list[ParBox]:
    """
    Flatten a document into paragraphs of boxes

    Parameters
    ----------
    doc :
        The document tree.
    style :
        Base style; the tree's overrides are applied on top of it.
    halign :
        Horizontal alignment of lines within each paragraph, in [0, 1].
    """
    f = _Flattener(halign)
    f.walk(doc.children, _Context(style), False)
    return f.pars


def markup_to_boxes(
    text: str | None,
    style: Style,
    halign: float = 0.0,
    use_markdown: bool = True,
) -> list[ParBox]:
    """Shortcut for ``to_boxes(parse(text, use_markdown), style, halign)``"""
    return to_boxes(parse(text, use_markdown), style, halign)
