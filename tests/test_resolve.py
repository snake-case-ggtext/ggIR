"""Tests for ggir.resolve: document tree -> styled tokens."""

from __future__ import annotations

import warnings
from dataclasses import dataclass

import pytest

import ggir
from ggir import css, ir
from ggir.resolve import (
    LINE_BREAK,
    ImageRun,
    LineBreak,
    Policy,
    TextRun,
    plain_text,
    resolve,
)
from ggir.style import Style

BASE = Style(family=("sans-serif",), size=10.0, color="black")


@pytest.fixture(autouse=True)
def _fresh_warnings():
    ir._warned.clear()
    css._warned.clear()


def toks(s: str, base: Style = BASE, *, parse: dict | None = None, **kwargs):
    doc = ggir.parse(s, on_unknown="ignore", **(parse or {}))
    return resolve(doc, base, **kwargs)


def texts(tokens):
    return [t.text if isinstance(t, TextRun) else t for t in tokens]


def one(s: str, base: Style = BASE, **kwargs) -> Style:
    """The style of the only run of text in *s*"""
    (t,) = [t for t in toks(s, base, **kwargs) if isinstance(t, TextRun)]
    return t.style


def test_exports():
    assert ggir.resolve is resolve
    assert ggir.Style is Style and ggir.Policy is Policy
    assert ggir.LINE_BREAK is LINE_BREAK
    assert ggir.LineBreak is ir.LineBreak  # the tree node, not the token
    assert {"b", "sup", "p", "img"} <= ggir.KNOWN_TAGS
    assert "blink" not in ggir.KNOWN_TAGS


class TestStyle:
    def test_defaults(self):
        s = Style()
        assert s.family is s.size is s.weight is s.color is s.url is None
        assert (s.underline, s.strike, s.shift) == (False, False, 0.0)

    def test_frozen_and_hashable(self):
        with pytest.raises(AttributeError):
            Style().size = 3  # type: ignore[misc]
        assert hash(Style(size=1)) == hash(Style(size=1))

    def test_update_splits_family(self):
        assert Style().update(family="Arial, 'DejaVu Sans'").family == (
            "Arial",
            "DejaVu Sans",
        )
        assert Style().update(family=("a",), size=3).size == 3

    def test_resolve_fills_none(self):
        base = Style(family=("serif",), size=12, weight="normal", color="k")
        s = Style(weight="bold", underline=True).resolve(base)
        assert s == Style(
            family=("serif",), size=12, weight="bold", color="k", underline=True
        )
        full = base.update(style="normal", variant="normal")
        assert full.resolve(Style()) is full


class TestTokens:
    def test_line_break_is_a_singleton(self):
        assert LineBreak() is LINE_BREAK
        assert repr(LINE_BREAK) == "LINE_BREAK"

    def test_plain_text(self):
        tokens = toks("a **b**<br><img src='x.png' alt='pic'> $x$")
        assert plain_text(tokens) == "a b\npic $x$"
        assert plain_text([]) == ""


class TestStyles:
    def test_plain(self):
        assert toks("Hello") == [TextRun("Hello", BASE)]

    def test_empty(self):
        assert toks("") == []

    @pytest.mark.parametrize(
        "src, changes",
        [
            ("**x**", {"weight": "bold"}),
            ("*x*", {"style": "italic"}),
            ("<u>x</u>", {"underline": True}),
            ("~~x~~", {"strike": True}),
            ("`x`", {"family": ("monospace",)}),
            ("<mark>x</mark>", {"background": "yellow"}),
            ("[x](http://u)", {"url": "http://u"}),
            ("<span style='font-variant:small-caps'>x</span>", {"variant": "small-caps"}),
            ("<font face='serif'>x</font>", {"family": ("serif",)}),
            ("<span style='color:red'>x</span>", {"color": "red"}),
            ("<span style='color:rgb(255,0,0)'>x</span>", {"color": (1.0, 0.0, 0.0)}),
        ],
    )  # fmt: skip
    def test_overrides(self, src, changes):
        assert one(src) == BASE.update(**changes)

    def test_nested_overrides(self):
        assert one("**<i><u>x</u></i>**") == BASE.update(
            weight="bold", style="italic", underline=True
        )

    def test_none_override_inherits(self):
        assert one("<u><span style='text-decoration:none'>x</span></u>") == BASE

    def test_math(self):
        assert toks("a $x^2$") == [
            TextRun("a ", BASE),
            TextRun("$x^2$", BASE, math=True),
        ]

    def test_math_is_not_merged(self):
        assert toks("$x$$y$") == [
            TextRun("$x$", BASE, math=True),
            TextRun("$y$", BASE, math=True),
        ]


class TestSizes:
    @pytest.mark.parametrize(
        "src, size",
        [
            ("<span style='font-size:14pt'>x</span>", 14.0),
            ("<span style='font-size:2em'>x</span>", 20.0),
            ("<span style='font-size:150%'>x</span>", 15.0),
            ("<span style='font-size:2em'><span style='font-size:50%'>x</span></span>", 10.0),
            ("<small>x</small>", 8.33),
            ("<big>x</big>", 12.0),
            ("<big><big>x</big></big>", 14.4),
            ("<font size='2em'>x</font>", 20.0),
            ("<font size=12>x</font>", 12.0),
        ],
    )  # fmt: skip
    def test_with_base_size(self, src, size):
        assert one(src).size == pytest.approx(size)

    @pytest.mark.parametrize(
        "src, size",
        [
            ("x", None),
            ("**x**", None),
            ("<span style='font-size:2em'>x</span>", 20.0),
            ("<span style='font-size:14pt'>x</span>", 14.0),
            ("<small>x</small>", 8.33),
        ],
    )
    def test_without_base_size_em_is_default_em(self, src, size):
        assert one(src, Style()).size == (size and pytest.approx(size))

    def test_default_em_from_policy(self):
        s = one(
            "<span style='font-size:2em'>x</span>",
            Style(),
            policy=Policy(default_em=12),
        )
        assert s.size == 24.0

    def test_css_size_on_sizing_tag_is_relative_to_parent(self):
        # ggIR keeps one size per node: font-size on <small> replaces it
        assert one("<small style='font-size:2em'>x</small>").size == 20.0

    def test_css_size_on_sup_is_relative_to_the_script_size(self):
        assert one("<sup style='font-size:2em'>x</sup>").size == pytest.approx(14.0)


class TestScripts:
    def test_sup_and_sub(self):
        tokens = toks("x<sup>2</sup><sub>i</sub>")
        assert tokens[1].style == BASE.update(size=7.0, shift=4.0)
        assert tokens[2].style == BASE.update(size=7.0, shift=-2.0)

    def test_nested(self):
        s = one("<sup><sup>x</sup></sup>")
        assert s.size == pytest.approx(4.9)
        assert s.shift == pytest.approx(4.0 + 2.8)

    def test_without_base_size(self):
        assert one("<sup>x</sup>", Style()) == Style(size=7.0, shift=4.0)

    def test_policy_numbers(self):
        policy = Policy(script_scale=0.8, sup_shift=0.5, sub_shift=-0.25)
        assert one("<sup>x</sup>", policy=policy) == BASE.update(size=8.0, shift=5.0)
        assert one("<sub>x</sub>", policy=policy) == BASE.update(size=8.0, shift=-2.5)
        assert one("<sub>x</sub>", Style(), policy=Policy(default_em=20)) == Style(
            size=14.0, shift=-4.0
        )

    def test_policy_subclass(self):
        @dataclass(frozen=True)
        class Gridtext(Policy):
            """0.8x size, shifted by half an ascent of 0.75em"""

            def script(self, kind, em, parent):
                dy = 0.75 * em / 2
                return 0.8 * em, dy if kind == "sup" else -dy

        assert one("<sup>x</sup>", policy=Gridtext()) == BASE.update(
            size=8.0, shift=3.75
        )

    @pytest.mark.parametrize(
        "css, shift",
        [("super", 4.0), ("sub", -2.0), ("3pt", 3.0), ("-0.5em", -5.0), ("20%", 2.0)],
    )
    def test_vertical_align_shifts_without_resizing(self, css, shift):
        s = one(f"<span style='vertical-align:{css}'>x</span>")
        assert s == BASE.update(shift=shift)

    def test_vertical_align_uses_policy(self):
        s = one(
            "<span style='vertical-align:super'>x</span>", policy=Policy(sup_shift=1)
        )
        assert s.shift == 10.0

    def test_vertical_align_relative_to_size_after_the_tag(self):
        # The CSS font-size of the same node does not count (as in ggtext)
        s = one("<span style='font-size:20pt; vertical-align:super'>x</span>")
        assert s == BASE.update(size=20.0, shift=4.0)
        s = one("<sup style='vertical-align:1em'>x</sup>")
        assert s == BASE.update(size=7.0, shift=4.0 + 7.0)

    def test_baseline_resets_shift(self):
        s = one("<sup><span style='vertical-align:baseline'>x</span></sup>")
        assert s == BASE.update(size=7.0)


class TestColors:
    def test_without_validator_colors_are_kept(self):
        assert one("<span style='color:nocolorxyz'>x</span>").color == "nocolorxyz"

    def validate(self, value):
        return {"red": "#ff0000", "blue": "#0000ff"}.get(value)

    def test_validator_normalises(self):
        assert one(
            "<span style='color:red'>x</span>", validate_color=self.validate
        ) == (BASE.update(color="#ff0000"))

    def test_invalid_color_warns_once_and_is_ignored(self):
        with pytest.warns(UserWarning, match="ggir: invalid color 'nocolorxyz'"):
            s = one("<font color='nocolorxyz'>x</font>", validate_color=self.validate)
        assert s == BASE
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            one("<span style='color:nocolorxyz'>x</span>", validate_color=self.validate)

    def test_invalid_background_is_ignored_silently(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            s = one(
                "<span style='background:nope'>x</span>", validate_color=self.validate
            )
        assert s == BASE

    def test_rgb_tuples_skip_the_validator(self):
        s = one(
            "<span style='color:rgb(0,0,255)'>x</span>", validate_color=lambda v: None
        )
        assert s.color == (0.0, 0.0, 1.0)


class TestUnknownTags:
    def test_warns_once(self):
        with pytest.warns(
            UserWarning, match=r"ggir: unsupported HTML tag <blink> was ignored"
        ):
            assert texts(toks("<blink>x</blink>")) == ["x"]
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            toks("<blink>y</blink>")

    def test_prefix(self):
        with pytest.warns(UserWarning, match=r"^ggtext: unsupported HTML tag <blink>"):
            toks("<blink>x</blink>", warn_prefix="ggtext")

    def test_can_be_silenced(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            toks("<blink>x</blink>", warn_unknown=False)

    def test_known_tags_do_not_warn(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            toks("<b>a</b><kbd>b</kbd><a>c</a><p>d</p><div>e</div><br><wbr><hr>")


class TestSubclass:
    def test_subclass_is_kept(self):
        class MyStyle(Style):
            def describe(self):
                return f"{self.size}pt"

        base = MyStyle(size=10.0)
        tokens = toks(
            "a **b** <sup>c</sup> <span style='color:red;font-size:2em'>d</span>"
            " <img src='x.png'> <p>e</p>",
            base,
        )
        styles = [t.style for t in tokens if t is not LINE_BREAK]
        assert len(styles) > 5
        assert all(type(s) is MyStyle for s in styles)
        assert styles[-1].describe() == "10.0pt"


class TestMerging:
    def test_same_style_merges(self):
        assert toks("<b>a</b><b>b</b>") == [TextRun("ab", BASE.update(weight="bold"))]
        assert toks("a<span>b</span>c") == [TextRun("abc", BASE)]

    def test_different_styles_do_not_merge(self):
        assert texts(toks("<b>a</b><i>b</i>")) == ["a", "b"]

    def test_not_across_breaks_math_or_images(self):
        assert texts(toks("a<br>b")) == ["a", LINE_BREAK, "b"]
        assert texts(toks("a$x$b")) == ["a", "$x$", "b"]
        assert len(toks("a<img src='i.png'>b")) == 3


class TestParagraphs:
    @pytest.mark.parametrize(
        "src, expected",
        [
            ("<p>one</p><p>two</p>", ["one", LINE_BREAK, "two"]),
            ("<p>one</p>", ["one"]),
            ("a<p>b</p>c", ["a", LINE_BREAK, "b", LINE_BREAK, "c"]),
            ("<p></p>", []),
            ("a<p></p>b", ["a", LINE_BREAK, "b"]),
            ("x<br><p>a</p>", ["x", LINE_BREAK, "a"]),
            ("<p>a<br></p>b", ["a", LINE_BREAK, "b"]),
            ("<div>a<p>b</p>c</div>", ["a", LINE_BREAK, "b", LINE_BREAK, "c"]),
            ("<b><p>a</p></b>", ["a"]),
            ("<p>a</p>  ", ["a", LINE_BREAK, "  "]),
        ],
    )
    def test_breaks(self, src, expected):
        assert texts(toks(src)) == expected

    def test_trailing_line_break_after_text_is_kept(self):
        assert texts(toks("a<br>")) == ["a", LINE_BREAK]

    def test_paragraph_style(self):
        tokens = toks("<p style='color:red'>a</p>b")
        assert tokens == [
            TextRun("a", BASE.update(color="red")),
            LINE_BREAK,
            TextRun("b", BASE),
        ]

    def test_markdown_blocks(self):
        tokens = toks("a\n\nb", parse={"blocks": True, "newline": "space"})
        assert texts(tokens) == ["a", LINE_BREAK, "b"]


class TestImages:
    def test_sizes_in_points(self):
        (img,) = toks("<img src='a.png' width='20' height='10pt' alt='logo'>")
        assert img == ImageRun("a.png", BASE, 15.0, 10.0, "logo")

    def test_relative_sizes(self):
        (img,) = toks("<img src='a.png' width='2em' height='50%'>")
        assert (img.width, img.height) == (20.0, 5.0)
        (img,) = toks(
            "<img src='a.png' width='2em'>", Style(), policy=Policy(default_em=8)
        )
        assert img.width == 16.0 and img.height is None

    def test_style_from_parent_and_own_css(self):
        (img,) = toks(
            "<span style='font-size:20pt'><img src='a.png' width='1em'></span>"
        )
        assert img.width == 20.0 and img.style.size == 20.0
        (img,) = toks("<img src='a.png' style='vertical-align:-2pt'>")
        assert img.style.shift == -2.0

    def test_markdown_image(self):
        (img,) = toks("![alt](b.png)")
        assert img == ImageRun("b.png", BASE, None, None, "alt")
