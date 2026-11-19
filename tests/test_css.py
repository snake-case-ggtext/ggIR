"""Tests for lengths, colours and inline CSS (ggir.css)"""

import pytest

from ggir import css
from ggir.css import css_overrides, parse_color, parse_length, split_families
from ggir.ir import Length


@pytest.fixture(autouse=True)
def _fresh_warnings():
    css._warned.clear()


class TestParseLength:
    @pytest.mark.parametrize(
        "value, expected",
        [
            (12, 12.0),
            (7.5, 7.5),
            ("12", 12.0),
            ("12pt", 12.0),
            ("16px", 12.0),  # CSS px are 0.75pt
            ("1in", 72.0),
            ("2.54cm", 72.0),
            ("25.4mm", 72.0),
            ("1pc", 12.0),
            (" 3 pt ", 3.0),
            ("12PT", 12.0),
            ("-2pt", -2.0),
        ],
    )
    def test_absolute(self, value, expected):
        length = parse_length(value)
        assert length.unit == "pt"
        assert length.value == pytest.approx(expected)

    @pytest.mark.parametrize(
        "value, expected",
        [("1.5em", 1.5), ("2rem", 2.0), ("150%", 1.5), ("larger", 1.2),
         ("smaller", 0.833), ("x-large", 1.44), ("medium", 1.0),
         ("xx-small", 0.579), ("small", 0.833), ("XX-Large", 1.728)],
    )  # fmt: skip
    def test_relative_stays_relative(self, value, expected):
        length = parse_length(value)
        assert length.unit == "em"
        assert length.value == pytest.approx(expected)

    def test_to_pt(self):
        assert parse_length("150%").to_pt(10) == pytest.approx(15.0)
        assert parse_length("16px").to_pt(10) == pytest.approx(12.0)

    @pytest.mark.parametrize("value", ["big", None, "12furlongs", "", "pt", True])
    def test_invalid(self, value):
        assert parse_length(value) is None

    def test_percent_can_be_disallowed(self):
        assert parse_length("50%", allow_percent=False) is None


class TestParseColor:
    @pytest.mark.parametrize("c", ["red", "#ff0000", "#f00", "C0", "tab:blue", "0.5"])
    def test_kept_as_written(self, c):
        assert parse_color(c) == c

    def test_stripped_not_validated(self):
        assert parse_color("  red ") == "red"
        assert parse_color("notacolor") == "notacolor"
        assert parse_color("") is None
        assert parse_color(None) is None

    def test_css_rgb(self):
        assert parse_color("rgb(255, 0, 0)") == (1.0, 0.0, 0.0)
        assert parse_color("rgba(0,0,255,0.5)") == (0.0, 0.0, 1.0, 0.5)
        assert parse_color("rgb(100%, 50%, 0%)") == (1.0, 0.5, 0.0)
        assert parse_color("RGB(510, 0, 0)") == (1.0, 0.0, 0.0)  # clipped

    def test_invalid_rgb(self):
        assert parse_color("rgb(1,2)") is None
        assert parse_color("rgb(a,b,c)") is None


def test_split_families():
    assert split_families("Arial, sans-serif") == ("Arial", "sans-serif")
    assert split_families("'DejaVu Serif', \"Times\",, ") == ("DejaVu Serif", "Times")


class TestCssOverrides:
    def test_color_and_size(self):
        assert css_overrides("color: red; font-size: 14pt") == {
            "color": "red",
            "size": Length(14.0, "pt"),
        }

    def test_relative_font_size(self):
        assert css_overrides("font-size: 150%")["size"] == Length(1.5, "em")
        assert css_overrides("font-size: 2em")["size"] == Length(2.0, "em")
        assert css_overrides("font-size: larger")["size"] == Length(1.2, "em")

    def test_font_properties(self):
        f = css_overrides(
            "font-family: 'DejaVu Serif', serif; font-weight: bold; "
            "font-style: italic; font-variant: small-caps"
        )
        assert f == {
            "family": ("DejaVu Serif", "serif"),
            "weight": "bold",
            "style": "italic",
            "variant": "small-caps",
        }

    def test_numeric_weight(self):
        assert css_overrides("font-weight: 700")["weight"] == 700
        assert css_overrides("font-weight: bolder")["weight"] == "bolder"

    def test_background(self):
        assert css_overrides("background-color: yellow") == {"background": "yellow"}
        assert css_overrides("background: rgb(0, 0, 255)") == {
            "background": (0.0, 0.0, 1.0)
        }

    def test_decorations(self):
        f = css_overrides("text-decoration: underline line-through")
        assert f == {"underline": True, "strike": True}
        assert css_overrides("text-decoration: none") == {
            "underline": False,
            "strike": False,
        }
        assert css_overrides("text-decoration-line: underline") == {"underline": True}

    @pytest.mark.parametrize(
        "value, expected",
        [
            ("super", "super"),
            ("sup", "super"),
            ("sub", "sub"),
            ("baseline", "baseline"),
            ("3pt", Length(3.0, "pt")),
            ("-0.5em", Length(-0.5, "em")),
        ],
    )
    def test_vertical_align(self, value, expected):
        assert css_overrides(f"vertical-align: {value}") == {"valign": expected}

    def test_vertical_align_invalid_is_ignored(self):
        assert css_overrides("vertical-align: middle") == {}

    def test_important_and_whitespace(self):
        assert css_overrides("  color : blue !important ;; ") == {"color": "blue"}
        assert css_overrides("COLOR: Blue") == {"color": "Blue"}

    def test_empty(self):
        assert css_overrides("") == {}
        assert css_overrides("color:; nonsense") == {}

    def test_unknown_property_warns_once(self, recwarn):
        with pytest.warns(UserWarning, match="unsupported CSS property 'margin-q'"):
            css_overrides("margin-q: 3px")
        recwarn.clear()
        css_overrides("margin-q: 4px")
        assert not recwarn.list

    def test_invalid_values_warn(self):
        with pytest.warns(UserWarning, match="invalid color"):
            f = css_overrides("color: rgb(1, 2)")
        assert "color" not in f
        with pytest.warns(UserWarning, match="invalid font-size"):
            f = css_overrides("font-size: hugeish")
        assert "size" not in f

    def test_last_declaration_wins(self):
        assert css_overrides("color: red; color: blue") == {"color": "blue"}
