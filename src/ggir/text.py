"""
RichText: a drop-in `matplotlib.text.Text` that renders markdown / HTML

Because it *is* a `Text`, code that positions, styles or measures text
(``set_position``, ``set_color``, ``set_fontsize``, ``get_window_extent``,
``ha``/``va``, rotation, ...) keeps working; only drawing and measuring
go through the ggir layout engine.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
from matplotlib.artist import allow_rasterization
from matplotlib.text import Text
from matplotlib.transforms import Bbox

from .boxes import Style, to_boxes
from .draw import box_artists, box_extent, box_transform
from .ir import Document, parse
from .layout import Layout, layout_rect_box
from .metrics import measure_with
from .units import UnitLike, as_margin_pt, as_pt_scalar

if TYPE_CHECKING:
    from matplotlib.backend_bases import RendererBase

__all__ = ("RichText",)

_HA = {"left": 0.0, "center": 0.5, "right": 1.0}
_VA = {"bottom": 0.0, "center": 0.5, "top": 1.0}


def _lineheight(ls) -> float:
    # matplotlib >= 3.11 accepts linespacing="normal"
    try:
        return float(ls)
    except (TypeError, ValueError):
        return 1.2


class RichText(Text):
    """
    A text artist that renders markdown / HTML

    Takes everything `matplotlib.text.Text` takes, plus the parameters
    below. The font properties of the artist (size, family, weight, style,
    colour, linespacing) are the base style that markup modifies.

    Parameters
    ----------
    use_markdown :
        If `False`, the text is taken to be HTML.
    halign :
        Alignment of lines within the box, in [0, 1]. Defaults to the
        horizontal alignment of the artist (0 for ``ha="left"``, ...).
    width :
        Width of the box including margins (points, or a
        [](`~ggir.unit`)). If given, text is word-wrapped to fit.
        `None` fits the box to the text.
    padding, margin :
        Space inside / outside the box: (top, right, bottom, left) or a
        single value, in points or a [](`~ggir.unit`).
    r :
        Corner radius of the box.
    fill :
        Background colour of the box. `None` for no background.
    box_edgecolor :
        Outline colour of the box. `None` for no outline.
    box_linewidth :
        Outline width, in points.

    Notes
    -----
    Rotation always happens about the anchor point, i.e. as
    ``rotation_mode="anchor"``. ``va="baseline"`` aligns the first
    baseline with the anchor, like a plain `Text`.
    """

    def __init__(
        self,
        x: float = 0,
        y: float = 0,
        text: str = "",
        *,
        use_markdown: bool = True,
        halign: float | None = None,
        width: UnitLike | None = None,
        padding: UnitLike = 0,
        margin: UnitLike = 0,
        r: UnitLike = 0,
        fill: Any = None,
        box_edgecolor: Any = None,
        box_linewidth: float = 0.5,
        **kwargs,
    ):
        self._use_markdown = use_markdown
        self._halign = halign
        self._box_width = width
        self._padding = padding
        self._margin = margin
        self._r = r
        self._fill = fill
        self._box_edgecolor = box_edgecolor
        self._box_linewidth = box_linewidth
        self._doc_cache: tuple[tuple[str, bool], Document] | None = None
        super().__init__(x, y, text, **kwargs)

    # --- properties --------------------------------------------------------

    def set_use_markdown(self, b: bool):
        self._use_markdown = b
        self.stale = True

    def set_halign(self, halign: float | None):
        self._halign = halign
        self.stale = True

    def set_box_width(self, width: UnitLike | None):
        self._box_width = width
        self.stale = True

    def set_padding(self, padding: UnitLike):
        self._padding = padding
        self.stale = True

    def set_margin(self, margin: UnitLike):
        self._margin = margin
        self.stale = True

    def set_r(self, r: UnitLike):
        self._r = r
        self.stale = True

    def set_fill(self, fill: Any):
        self._fill = fill
        self.stale = True

    def set_box_edgecolor(self, color: Any):
        self._box_edgecolor = color
        self.stale = True

    def set_box_linewidth(self, lw: float):
        self._box_linewidth = lw
        self.stale = True

    def get_document(self) -> Document:
        """The parsed text"""
        key = (self.get_text(), self._use_markdown)
        if self._doc_cache is None or self._doc_cache[0] != key:
            self._doc_cache = (key, parse(key[0], key[1]))
        return self._doc_cache[1]

    # --- layout ------------------------------------------------------------

    def _base_style(self) -> Style:
        fam = self.get_fontfamily()
        if isinstance(fam, (list, tuple)):
            fam = fam[0] if fam else None
        return Style(
            fontsize=float(self.get_fontsize()),
            family=fam,
            weight=self.get_fontweight(),  # type: ignore[arg-type]
            style=self.get_fontstyle(),
            color=None,
            lineheight=_lineheight(self.get_linespacing()),
        )

    def _hjust(self) -> float:
        return _HA.get(self.get_horizontalalignment(), 0.0)

    def layout(self) -> Layout:
        """
        Lay out the text, in points

        Horizontal advances are measured with the renderer that is active
        (see [](`~ggir.measure_with`)), if any.
        """
        halign = self._halign if self._halign is not None else self._hjust()
        pars = to_boxes(self.get_document(), self._base_style(), halign)
        width = as_pt_scalar(self._box_width)
        va = self.get_verticalalignment()
        return layout_rect_box(
            pars,
            as_margin_pt(self._margin),
            as_margin_pt(self._padding),
            width=width,
            wrap=width is not None,
            content_hjust=halign,
            content_vjust=_VA.get(va, 1.0),
            r=as_pt_scalar(self._r) or 0.0,
        )

    def _transform_for(self, L: Layout):
        anchor = self.get_transform().transform(self.get_unitless_position())
        va = self.get_verticalalignment()
        yoff = None
        if va in ("baseline", "center_baseline"):
            if L.texts:
                base = L.texts[0].y
                yoff = base if va == "baseline" else (L.height + base) / 2
            else:
                va = "center"
        return box_transform(
            L,
            tuple(anchor),
            hjust=self._hjust(),
            vjust=_VA.get(va, 0.5),
            angle=self.get_rotation(),
            dpi=self.get_figure(root=True).dpi,  # type: ignore[union-attr]
            yoff=yoff,
        )

    def _get_renderer(self, renderer=None):
        if renderer is not None:
            return renderer
        r = getattr(self, "_renderer", None)
        if r is not None:
            return r
        return self.get_figure(root=True)._get_renderer()  # type: ignore[union-attr]

    # --- matplotlib API ----------------------------------------------------

    @allow_rasterization
    def draw(self, renderer: RendererBase):
        if renderer is not None:
            self._renderer = renderer
        if not self.get_visible() or self.get_text() == "":
            return
        x, y = self.get_unitless_position()
        if not (np.isfinite(x) and np.isfinite(y)):
            return
        with measure_with(renderer):
            L = self.layout()
        trans = self._transform_for(L)
        artists = box_artists(
            L,
            trans,
            angle=self.get_rotation(),
            text_color=self.get_color(),
            alpha=self.get_alpha(),
            fill=self._fill,
            edgecolor=self._box_edgecolor,
            linewidth=self._box_linewidth,
        )
        renderer.open_group("richtext", gid=self.get_gid())
        fig = self.get_figure(root=False)
        clip_box = self.get_clip_box()
        clip_path = self.get_clip_path()
        for a in artists:
            a.set_figure(fig)  # type: ignore[arg-type]
            a.set_clip_on(self.get_clip_on())
            if clip_box is not None:
                a.set_clip_box(clip_box)
            if clip_path is not None:
                a.set_clip_path(clip_path)
            a.set_zorder(self.get_zorder())
            a.set_path_effects(self.get_path_effects())
            a.draw(renderer)
        renderer.close_group("richtext")
        self.stale = False

    def get_window_extent(self, renderer=None, dpi=None) -> Bbox:
        if not self.get_visible():
            return Bbox.unit()
        fig = self.get_figure(root=True)
        if fig is None:
            raise RuntimeError("Cannot get window extent of text w/o renderer")
        old_dpi = fig.dpi
        if dpi is not None:
            fig.dpi = dpi
        try:
            if self.get_text() == "":
                tx, ty = self.get_transform().transform(self.get_unitless_position())
                return Bbox.from_bounds(tx, ty, 0, 0)
            renderer = self._get_renderer(renderer)
            self._renderer = renderer
            with measure_with(renderer):
                L = self.layout()
            return box_extent(L, self._transform_for(L))
        finally:
            fig.dpi = old_dpi
