"""
Turning a layout into matplotlib artists

A [](`~ggir.layout.Layout`) is in points, with the origin at the lower-left
corner of the outer box. [](`~ggir.draw.box_transform`) maps it to display
pixels so that the point ``(hjust, vjust)`` of the box lands on the anchor,
rotated about the anchor. [](`~ggir.draw.box_artists`) then creates one
patch for the box and one `Text` per word.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from matplotlib.artist import Artist
from matplotlib.colors import to_rgba
from matplotlib.patches import PathPatch
from matplotlib.path import Path
from matplotlib.text import Text
from matplotlib.transforms import Affine2D, Bbox

from .layout import Layout
from .metrics import font_properties

__all__ = ("rounded_rect_path", "rgba", "box_transform", "box_artists", "box_extent")

# Bezier constant for approximating a quarter circle
_KAPPA = 0.5522847498


def rounded_rect_path(x: float, y: float, w: float, h: float, r: float) -> Path:
    """Rounded rectangle path, like `grid::roundrectGrob()`"""
    r = max(0.0, min(r, w / 2, h / 2))
    if r == 0:
        verts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]
        codes = [Path.MOVETO] + [Path.LINETO] * 3 + [Path.CLOSEPOLY]
        return Path(verts, codes)

    k = _KAPPA * r
    x0, y0, x1, y1 = x, y, x + w, y + h
    verts = [
        (x0 + r, y0),
        (x1 - r, y0),
        (x1 - r + k, y0), (x1, y0 + r - k), (x1, y0 + r),
        (x1, y1 - r),
        (x1, y1 - r + k), (x1 - r + k, y1), (x1 - r, y1),
        (x0 + r, y1),
        (x0 + r - k, y1), (x0, y1 - r + k), (x0, y1 - r),
        (x0, y0 + r),
        (x0, y0 + r - k), (x0 + r - k, y0), (x0 + r, y0),
        (x0 + r, y0),
    ]  # fmt: skip
    C = Path.CURVE4
    codes = (
        [Path.MOVETO, Path.LINETO]
        + [C] * 3 + [Path.LINETO]
        + [C] * 3 + [Path.LINETO]
        + [C] * 3 + [Path.LINETO]
        + [C] * 3 + [Path.CLOSEPOLY]
    )  # fmt: skip
    return Path(verts, codes)


def _is_missing(c: Any) -> bool:
    if c is None:
        return True
    if isinstance(c, float) and np.isnan(c):
        return True
    if isinstance(c, str) and c.lower() in ("none", "na", ""):
        return True
    return False


def rgba(c: Any, alpha: float | None = None):
    """Colour with alpha, or ``"none"`` for missing colours"""
    if _is_missing(c):
        return "none"
    if alpha is None or (isinstance(alpha, float) and np.isnan(alpha)):
        return to_rgba(c)
    r, g, b, a = to_rgba(c)
    return (r, g, b, a * alpha)


def box_transform(
    layout: Layout,
    anchor_px: tuple[float, float],
    *,
    hjust: float,
    vjust: float,
    angle: float,
    dpi: float,
    yoff: float | None = None,
) -> Affine2D:
    """
    Transform from layout points to display pixels

    Parameters
    ----------
    layout :
        The laid out box.
    anchor_px :
        The anchor point in display coordinates.
    hjust, vjust :
        Which point of the box is placed on the anchor, as fractions of
        its width and height.
    angle :
        Rotation in degrees, counter-clockwise, about the anchor.
    dpi :
        Pixels per inch of the target.
    yoff :
        Vertical offset in points that is placed on the anchor. Overrides
        `vjust` (used to align on a text baseline).
    """
    dy = -vjust * layout.height if yoff is None else -yoff
    return (
        Affine2D()
        .translate(-hjust * layout.width, dy)
        .scale(dpi / 72)
        .rotate_deg(angle)
        .translate(*anchor_px)
    )


def box_artists(
    layout: Layout,
    trans: Affine2D,
    *,
    angle: float = 0,
    text_color: Any = "black",
    alpha: float | None = None,
    fill: Any = None,
    edgecolor: Any = None,
    linewidth: float = 0.5,
) -> list[Artist]:
    """
    Artists that draw a laid out box: one patch and one `Text` per word

    The artists are in display coordinates and are meant to be drawn
    straight away (not added to a figure). Words without a colour of
    their own use `text_color`.
    """
    rx, ry, rw, rh = layout.rect
    out: list[Artist] = []
    if not (_is_missing(fill) and _is_missing(edgecolor)):
        out.append(
            PathPatch(
                rounded_rect_path(rx, ry, rw, rh, layout.r),
                transform=trans,
                facecolor=rgba(fill, alpha),
                edgecolor=rgba(edgecolor, alpha),
                linewidth=linewidth,
            )
        )
    for t in layout.texts:
        px, py = trans.transform((t.x, t.y))
        color = t.style.color if t.style.color is not None else text_color
        out.append(
            Text(
                px,
                py,
                t.text,
                color=rgba(color, alpha),
                fontproperties=font_properties(t.style),
                rotation=angle,
                rotation_mode="anchor",
                horizontalalignment="left",
                verticalalignment="baseline",
            )
        )
    return out


def box_extent(layout: Layout, trans: Affine2D, margins: bool = True) -> Bbox:
    """
    Display-space bounding box of the (rotated) box

    With ``margins=False``, the extent of the drawn rectangle only.
    """
    if margins:
        x, y, w, h = 0.0, 0.0, layout.width, layout.height
    else:
        x, y, w, h = layout.rect
    corners = trans.transform([(x, y), (x + w, y), (x + w, y + h), (x, y + h)])
    return Bbox.from_extents(*corners.min(0), *corners.max(0))
