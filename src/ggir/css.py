"""
Lengths, colours and the small inline-CSS subset understood by the parser

Pure Python (no matplotlib): values are kept as written where validating
them would need a renderer. Relative lengths stay relative, as
``Length(x, "em")``, and are resolved by consumers.

Adapted from Shannon E. Ellis's ggtext for Python (MIT).
"""

from __future__ import annotations

import re
import warnings
from typing import Any

from .ir import Color, Length, _user_stacklevel

__all__ = (
    "SMALL_SCALE",
    "BIG_SCALE",
    "parse_length",
    "parse_color",
    "split_families",
    "css_overrides",
)

# Relative font sizes of <small> / <big> (and CSS smaller / larger)
SMALL_SCALE = 0.833
BIG_SCALE = 1.2

# CSS absolute-size keywords, relative to the parent ("medium") size
_CSS_SIZE_KEYWORDS = {
    "xx-small": 0.579,
    "x-small": 0.694,
    "small": 0.833,
    "medium": 1.0,
    "large": 1.2,
    "x-large": 1.44,
    "xx-large": 1.728,
    "larger": BIG_SCALE,
    "smaller": SMALL_SCALE,
}

_LENGTH_RE = re.compile(
    r"^\s*(?P<num>[+-]?(?:\d+\.?\d*|\.\d+))\s*(?P<unit>[a-z%]*)\s*$",
    re.IGNORECASE,
)

# points per unit
_POINTS_PER = {
    "pt": 1.0,
    "px": 0.75,  # CSS px are 1/96 in
    "in": 72.0,
    "cm": 72.0 / 2.54,
    "mm": 72.0 / 25.4,
    "pc": 12.0,
}


def parse_length(value: Any, *, allow_percent: bool = True) -> Length | None:
    """
    Parse a CSS-like length

    Numbers and unitless strings are points. Absolute units (``pt``,
    ``px``, ``in``, ``cm``, ``mm``, ``pc``) become ``Length(x, "pt")``;
    ``em``, ``rem``, ``%``, the CSS size keywords (``small``,
    ``x-large``, ...) and ``larger`` / ``smaller`` become
    ``Length(x, "em")``. Returns `None` if *value* can't be parsed.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Length):
        return value
    if isinstance(value, (int, float)):
        return Length(float(value), "pt")

    s = str(value).strip().lower()
    if s in _CSS_SIZE_KEYWORDS:
        return Length(_CSS_SIZE_KEYWORDS[s], "em")

    m = _LENGTH_RE.match(s)
    if not m:
        return None
    num = float(m["num"])
    unit = m["unit"] or "pt"
    if unit in _POINTS_PER:
        return Length(num * _POINTS_PER[unit], "pt")
    if unit in ("em", "rem"):
        return Length(num, "em")
    if unit == "%" and allow_percent:
        return Length(num / 100, "em")
    return None


_RGB_RE = re.compile(r"^rgba?\((?P<args>[^)]*)\)$", re.IGNORECASE)


def parse_color(value: Any) -> Color | None:
    """
    Parse a CSS colour

    ``rgb(r, g, b)`` / ``rgba(r, g, b, a)`` (0-255 channels or
    percentages) become an RGBA tuple in [0, 1], or `None` if malformed.
    Anything else is returned stripped and unvalidated (validating colour
    names needs matplotlib); an empty value gives `None`.
    """
    if value is None:
        return None
    if isinstance(value, tuple):
        return value
    s = str(value).strip()
    if not s:
        return None
    m = _RGB_RE.match(s.replace(" ", "") if "(" in s else s)
    if not m:
        return s
    args = [a for a in re.split(r"[,\s/]+", m["args"].strip()) if a]
    try:
        chans = []
        for i, a in enumerate(args[:4]):
            if a.endswith("%"):
                chans.append(float(a[:-1]) / 100)
            elif i < 3:
                chans.append(float(a) / 255)
            else:
                chans.append(float(a))
    except ValueError:
        return None
    if len(chans) not in (3, 4):
        return None
    return tuple(min(max(c, 0.0), 1.0) for c in chans)


def split_families(value: str) -> tuple[str, ...]:
    """Split a CSS ``font-family`` list into family names, unquoted"""
    parts = [p.strip().strip("'\"") for p in value.split(",")]
    return tuple(p for p in parts if p)


# Keys we have already warned about (once per key per session)
_warned: set[str] = set()


def _warn_once(msg: str, key: str):
    if key not in _warned:
        _warned.add(key)
        warnings.warn(msg, UserWarning, stacklevel=_user_stacklevel())


def css_overrides(declarations: str) -> dict[str, Any]:
    """
    Style overrides from inline CSS *declarations*

    Returns a dict of `~ggir.ir.Span` field values. Supported properties:
    ``color``, ``background-color`` (or ``background``), ``font-size``,
    ``font-family``, ``font-weight``, ``font-style``, ``font-variant``,
    ``text-decoration`` / ``text-decoration-line`` (``underline``,
    ``line-through``, ``none``) and ``vertical-align`` (``super``,
    ``sub``, ``baseline`` or a length). ``!important`` is ignored.

    Unknown properties and invalid colours / font sizes warn once per
    key and are otherwise ignored.
    """
    changes: dict[str, Any] = {}
    for decl in (declarations or "").split(";"):
        if ":" not in decl:
            continue
        name, _, value = decl.partition(":")
        name = name.strip().lower()
        value = value.strip()
        if value.lower().endswith("!important"):
            value = value[: -len("!important")].strip()
        if not value:
            continue

        if name == "color":
            color = parse_color(value)
            if color is None:
                _warn_once(f"ggir: invalid color {value!r}", f"color:{value}")
            else:
                changes["color"] = color
        elif name in ("background-color", "background"):
            color = parse_color(value)
            if color is not None:
                changes["background"] = color
        elif name == "font-size":
            size = parse_length(value)
            if size is None:
                _warn_once(f"ggir: invalid font-size {value!r}", f"font-size:{value}")
            else:
                changes["size"] = size
        elif name == "font-family":
            changes["family"] = split_families(value)
        elif name == "font-weight":
            changes["weight"] = int(value) if value.isdigit() else value
        elif name == "font-style":
            changes["style"] = value
        elif name == "font-variant":
            changes["variant"] = value
        elif name in ("text-decoration", "text-decoration-line"):
            v = value.lower()
            if "none" in v:
                changes["underline"] = False
                changes["strike"] = False
            if "underline" in v:
                changes["underline"] = True
            if "line-through" in v:
                changes["strike"] = True
        elif name == "vertical-align":
            v = value.lower()
            if v in ("super", "sup"):
                changes["valign"] = "super"
            elif v == "sub":
                changes["valign"] = "sub"
            elif v == "baseline":
                changes["valign"] = "baseline"
            elif (length := parse_length(v)) is not None:
                changes["valign"] = length
        else:
            _warn_once(
                f"ggir: unsupported CSS property {name!r} was ignored",
                f"property:{name}",
            )
    return changes
