"""Tests for the markdown / HTML / CSS parser (ggir.ir)"""

import subprocess
import sys
import warnings

import pytest

from ggir import css, ir
from ggir.ir import (
    Document,
    Image,
    Length,
    LineBreak,
    Math,
    Paragraph,
    Span,
    Text,
    UnsupportedTagError,
    parse,
)


@pytest.fixture(autouse=True)
def _fresh_warnings():
    ir._warned.clear()
    css._warned.clear()


def S(*children, **kwargs):
    return Span(list(children), **kwargs)


def P(*children, **kwargs):
    return Paragraph(list(children), **kwargs)


def kids(s, **kwargs):
    return parse(s, **kwargs).children


def plain(s, **kwargs):
    return parse(s, **kwargs).plain_text()


def test_ir_does_not_need_matplotlib():
    code = (
        "import sys, ggir.ir; "
        "ggir.ir.parse(\"**x** <span style='color:red;font-size:2em'>y</span> $z$\"); "
        "print('ggir.css' in sys.modules, 'matplotlib' in sys.modules)"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert out.stdout.split() == ["True", "False"]


def test_docstring_example():
    assert parse("A **bold** claim, $x^2$") == Document(
        [
            Text("A "),
            S(Text("bold"), tag="strong", weight="bold"),
            Text(" claim, "),
            Math("x^2"),
        ]
    )


class TestMarkdown:
    def test_plain(self):
        assert kids("Hello world") == [Text("Hello world")]

    @pytest.mark.parametrize(
        "src, tag",
        [("**bold**", "strong"), ("__bold__", "strong"), ("<b>bold</b>", "b"),
         ("<strong>bold</strong>", "strong")],
    )  # fmt: skip
    def test_bold(self, src, tag):
        assert kids(src) == [S(Text("bold"), tag=tag, weight="bold")]

    @pytest.mark.parametrize(
        "src, tag",
        [("*it*", "em"), ("_it_", "em"), ("<i>it</i>", "i"), ("<em>it</em>", "em")],
    )
    def test_italic(self, src, tag):
        assert kids(src) == [S(Text("it"), tag=tag, style="italic")]

    def test_bold_italic_nests(self):
        (outer,) = kids("***both***")
        (inner,) = outer.children
        assert {outer.tag, inner.tag} == {"strong", "em"}
        assert inner.children == [Text("both")]

    def test_strikethrough(self):
        assert kids("~~gone~~") == [S(Text("gone"), tag="s", strike=True)]

    def test_code_span_is_verbatim_and_monospace(self):
        assert kids("`a_b*c* $x$`") == [
            S(Text("a_b*c* $x$"), tag="code", family=("monospace",))
        ]

    @pytest.mark.parametrize(
        "src",
        [
            "bill_length_mm",
            "flipper_length_mm vs body_mass_g",
            "snake_case_name",
            "x_1 and y_2",
        ],
    )
    def test_snake_case_is_not_italic(self, src):
        assert kids(src) == [Text(src)]

    def test_dunder_gotcha_and_fixes(self):
        # CommonMark reads __init__ as bold "init" (documented gotcha) ...
        assert kids("__init__") == [S(Text("init"), tag="strong", weight="bold")]
        # ... use backticks or escapes to keep it literal
        assert plain("`__init__`") == "__init__"
        assert kids(r"\_\_init\_\_") == [Text("__init__")]

    def test_escapes_and_entities(self):
        assert kids(r"\*not italic\* &amp; &lt;tag&gt;") == [
            Text("*not italic* & <tag>")
        ]

    def test_nbsp(self):
        assert kids("a&nbsp;b") == [Text("a\xa0b")]
        assert kids("a&nbsp;b", markdown=False) == [Text("a\xa0b")]

    @pytest.mark.parametrize("src", ["1. one", "# hash", "- item", "> quote"])
    def test_block_syntax_is_literal(self, src):
        assert kids(src) == [Text(src)]

    def test_link(self):
        assert kids("[docs](https://example.org)") == [
            S(Text("docs"), tag="a", href="https://example.org")
        ]

    def test_link_with_markup(self):
        assert kids("[**b**](u)") == [
            S(S(Text("b"), tag="strong", weight="bold"), tag="a", href="u")
        ]

    def test_image(self):
        assert kids("![a flag](flag.png)") == [Image("flag.png", alt="a flag")]

    def test_markdown_disabled(self):
        assert kids("**not bold** <b>bold</b>", markdown=False) == [
            Text("**not bold** "),
            S(Text("bold"), tag="b", weight="bold"),
        ]

    def test_markdown_and_html_disabled(self):
        assert kids("**x** <b>y</b> &amp;", markdown=False, html=False) == [
            Text("**x** <b>y</b> &amp;")
        ]

    def test_markdown_inside_html(self):
        assert kids("<span style='color:blue'>**x**</span>") == [
            S(S(Text("x"), tag="strong", weight="bold"), color="blue")
        ]


class TestLineBreaks:
    def test_newline_breaks_by_default(self):
        assert kids("a\nb") == [Text("a"), LineBreak(), Text("b")]

    def test_newline_as_space(self):
        assert kids("a\nb", newline="space") == [Text("a b")]
        assert kids("**a\nb**", newline="space") == [
            S(Text("a b"), tag="strong", weight="bold")
        ]

    def test_br_and_hard_break(self):
        assert kids("a<br>b<br/>c") == [
            Text("a"),
            LineBreak(),
            Text("b"),
            LineBreak(),
            Text("c"),
        ]
        assert kids("a  \nb", newline="space") == [Text("a"), LineBreak(), Text("b")]
        assert kids("a\\\nb", newline="space") == [Text("a"), LineBreak(), Text("b")]

    def test_close_br_is_ignored(self):
        assert kids("a</br>b") == [Text("ab")]

    def test_newline_in_html_mode(self):
        assert kids("a\nb", markdown=False) == [Text("a"), LineBreak(), Text("b")]
        assert kids("a\nb", markdown=False, newline="space") == [Text("a b")]

    def test_newline_in_literal_mode(self):
        kw = dict(markdown=False, html=False)
        assert kids("a\nb", **kw) == [Text("a"), LineBreak(), Text("b")]
        assert kids("a\nb", newline="space", **kw) == [Text("a b")]

    def test_bad_newline_value(self):
        with pytest.raises(ValueError, match="newline"):
            parse("x", newline="wrap")


class TestParagraphs:
    def test_p_tags(self):
        assert kids("<p>one</p><p>two</p>") == [
            P(Text("one"), tag="p"),
            P(Text("two"), tag="p"),
        ]
        assert plain("<p>one</p><p>two</p>") == "one\ntwo"

    def test_div_with_style(self):
        assert kids("a<div style='color:red'>b</div>c") == [
            Text("a"),
            P(Text("b"), tag="div", color="red"),
            Text("c"),
        ]
        assert plain("a<div>b</div>c") == "a\nb\nc"

    def test_paragraph_drops_inline_only_css(self):
        (p,) = kids("<p style='vertical-align: super; color: red'>x</p>")
        assert p == P(Text("x"), tag="p", color="red")

    def test_blocks(self):
        doc = parse("one *a*\n\n  \n two\nlines\n\n", blocks=True)
        assert doc.children == [
            P(Text("one "), S(Text("a"), tag="em", style="italic"), tag="p"),
            P(Text("two"), LineBreak(), Text("lines"), tag="p"),
        ]
        assert doc.plain_text() == "one a\ntwo\nlines"

    def test_blocks_newline_space(self):
        assert kids("a\nb\n\nc", blocks=True, newline="space") == [
            P(Text("a b"), tag="p"),
            P(Text("c"), tag="p"),
        ]

    def test_blocks_with_explicit_p_nest(self):
        assert kids("x <p>y</p>\n\nz", blocks=True) == [
            P(Text("x "), P(Text("y"), tag="p"), tag="p"),
            P(Text("z"), tag="p"),
        ]

    def test_blocks_math_spanning_a_blank_line(self):
        assert kids("a $x\n\ny$ b\n\nc", blocks=True) == [
            P(Text("a "), Math("x\n\ny"), Text(" b"), tag="p"),
            P(Text("c"), tag="p"),
        ]

    def test_blocks_close_open_tags(self):
        with pytest.warns(UserWarning, match="</b> has no opening tag"):
            doc = parse("<b>a\n\nb</b>", blocks=True)
        assert doc.children == [
            P(S(Text("a"), tag="b", weight="bold"), tag="p"),
            P(Text("b"), tag="p"),
        ]

    def test_blocks_in_html_and_literal_modes(self):
        for kw in (dict(markdown=False), dict(markdown=False, html=False)):
            assert kids("a\n\nb", blocks=True, **kw) == [
                P(Text("a"), tag="p"),
                P(Text("b"), tag="p"),
            ]

    def test_without_blocks_blank_lines_are_breaks(self):
        assert kids("a\n\nb") == [Text("a"), LineBreak(), LineBreak(), Text("b")]


class TestHtml:
    def test_span_style(self):
        assert kids("a <span style='color:red; font-size:15pt'>b</span> c") == [
            Text("a "),
            S(Text("b"), color="red", size=Length(15.0)),
            Text(" c"),
        ]

    def test_css_on_span(self):
        (span,) = kids(
            "<span style=\"color:red; font-size:12px; font-family:'Courier New'\">"
            "x</span>"
        )
        assert span.color == "red"
        assert span.size == Length(9.0, "pt")
        assert span.family == ("Courier New",)

    def test_nesting(self):
        assert kids("<b>bold <i>both</i> bold</b> plain") == [
            S(
                Text("bold "),
                S(Text("both"), tag="i", style="italic"),
                Text(" bold"),
                tag="b",
                weight="bold",
            ),
            Text(" plain"),
        ]

    def test_sup_sub(self):
        assert kids("x<sup>2</sup>H<sub>2</sub>") == [
            Text("x"),
            S(Text("2"), tag="sup", script="sup"),
            Text("H"),
            S(Text("2"), tag="sub", script="sub"),
        ]

    def test_nested_sup(self):
        assert kids("e<sup>x<sup>2</sup></sup>") == [
            Text("e"),
            S(
                Text("x"),
                S(Text("2"), tag="sup", script="sup"),
                tag="sup",
                script="sup",
            ),
        ]

    @pytest.mark.parametrize(
        "tag, attr, value",
        [
            ("u", "underline", True),
            ("ins", "underline", True),
            ("s", "strike", True),
            ("del", "strike", True),
            ("strike", "strike", True),
            ("mark", "background", "yellow"),
            ("code", "family", ("monospace",)),
            ("kbd", "family", ("monospace",)),
            ("tt", "family", ("monospace",)),
            ("samp", "family", ("monospace",)),
            ("small", "size", Length(0.833, "em")),
            ("big", "size", Length(1.2, "em")),
        ],
    )
    def test_simple_tags(self, tag, attr, value):
        assert kids(f"<{tag}>x</{tag}>") == [S(Text("x"), tag=tag, **{attr: value})]

    def test_tag_names_are_case_insensitive(self):
        assert kids("<B>x</b>") == [S(Text("x"), tag="b", weight="bold")]

    def test_html_code_tag_is_not_verbatim(self):
        assert kids("<code>*x*</code>") == [
            S(S(Text("x"), tag="em", style="italic"), tag="code", family=("monospace",))
        ]

    def test_font_tag(self):
        assert kids("<font color='green' face='serif, Arial' size='14'>x</font>") == [
            S(
                Text("x"),
                tag="font",
                color="green",
                family=("serif", "Arial"),
                size=Length(14.0),
            )
        ]

    def test_a_tag(self):
        assert kids("<a href='https://x.org'>x</a>") == [
            S(Text("x"), tag="a", href="https://x.org")
        ]

    def test_style_attribute_on_any_tag(self):
        assert kids("<b style='color:red'>x</b>") == [
            S(Text("x"), tag="b", weight="bold", color="red")
        ]

    def test_css_overrides_tag_style(self):
        assert kids("<b style='font-weight: 300'>x</b>") == [
            S(Text("x"), tag="b", weight=300)
        ]

    def test_css_vertical_align(self):
        assert kids("<span style='vertical-align: super'>x</span>") == [
            S(Text("x"), valign="super")
        ]

    def test_unclosed_tag_extends_to_end(self):
        assert kids("<b>to the end") == [S(Text("to the end"), tag="b", weight="bold")]

    def test_mismatched_close_warns(self):
        with pytest.warns(UserWarning, match="has no opening tag"):
            assert kids("text</zzz>") == [Text("text")]

    def test_unmatched_markdown_close_is_silent(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            # </b> also closes the **, so the markdown close has no match
            assert kids("<b>**a</b> b**") == [
                S(S(Text("a"), tag="strong", weight="bold"), tag="b", weight="bold"),
                Text(" b"),
            ]

    def test_close_pops_intermediate(self):
        assert kids("<b><i>x</b>y") == [
            S(S(Text("x"), tag="i", style="italic"), tag="b", weight="bold"),
            Text("y"),
        ]

    def test_mismatched_end_tag_closes_inner_elements(self):
        with pytest.warns(UserWarning, match="</i> has no opening tag"):
            doc = parse("<b>x<i>y</b>z</i>")
        assert doc.children == [
            S(Text("x"), S(Text("y"), tag="i", style="italic"), tag="b", weight="bold"),
            Text("z"),
        ]

    def test_self_closed_span_is_ignored(self):
        assert kids("a<span/>b") == [Text("ab")]

    def test_comments_hr_wbr_are_ignored(self):
        assert kids("a<!-- hidden -->b<hr>c<wbr>d<hr/>e") == [Text("abcde")]
        assert kids("a<!-- hidden -->b", markdown=False) == [Text("ab")]

    def test_img(self):
        assert kids("<img src='logo.png' width='20' height='10pt' alt='logo'>") == [
            Image("logo.png", width=Length(15.0), height=Length(10.0), alt="logo")
        ]

    def test_img_relative_size(self):
        (img,) = kids("<img src='a.png' height='1.5em'/>")
        assert img == Image("a.png", height=Length(1.5, "em"))

    def test_img_style_wraps_in_span(self):
        assert kids("<img src='a.png' style='background: red'>") == [
            S(Image("a.png"), tag="img", background="red")
        ]

    def test_less_than_is_text(self):
        assert kids("5 < 6 and 7 > 3") == [Text("5 < 6 and 7 > 3")]
        assert kids("5 < 6 and 7 > 3", markdown=False) == [Text("5 < 6 and 7 > 3")]

    def test_adjacent_text_is_merged(self):
        assert kids("a&amp;b") == [Text("a&b")]
        assert kids(r"a\*b") == [Text("a*b")]


class TestUnknownTags:
    def test_warn_once(self, recwarn):
        with pytest.warns(UserWarning, match="<blink> isn't supported"):
            assert kids("<blink>x</blink>") == [S(Text("x"), tag="blink")]
        recwarn.clear()
        parse("<blink>y</blink>")
        assert not recwarn.list

    @pytest.mark.parametrize("src", ["<h1>x</h1>", "a <blink>x</blink>"])
    def test_error(self, src):
        with pytest.raises(UnsupportedTagError, match="isn't supported"):
            parse(src, on_unknown="error")
        with pytest.raises(UnsupportedTagError, match="isn't supported"):
            parse(src, markdown=False, on_unknown="error")

    def test_error_is_a_value_error(self):
        assert issubclass(UnsupportedTagError, ValueError)

    def test_ignore(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            assert kids("<h1 style='color:red'>x</h1>", on_unknown="ignore") == [
                S(Text("x"), tag="h1", color="red")
            ]

    def test_known_tags_never_raise(self):
        parse("<span><p><div><b>x</b></div></p></span>", on_unknown="error")

    def test_bad_value(self):
        with pytest.raises(ValueError, match="on_unknown"):
            parse("x", on_unknown="explode")


class TestMath:
    def test_math_segment(self):
        assert kids(r"The $\alpha_1 * \beta$ value") == [
            Text("The "),
            Math(r"\alpha_1 * \beta"),
            Text(" value"),
        ]

    def test_multiple_math(self):
        assert kids("$a$ and $b$") == [Math("a"), Text(" and "), Math("b")]

    def test_escaped_dollar(self):
        assert kids(r"costs \$5") == [Text("costs $5")]
        assert kids(r"costs \$5", markdown=False) == [Text("costs $5")]
        assert kids(r"costs \$5", markdown=False, html=False) == [Text("costs $5")]

    def test_escaped_dollar_inside_math(self):
        assert kids(r"$a\$b$ c") == [Math(r"a\$b"), Text(" c")]

    def test_single_dollar_is_text(self):
        assert kids("only $5") == [Text("only $5")]

    def test_math_disabled(self):
        assert kids("$a *b* c$", math=False) == [
            Text("$a "),
            S(Text("b"), tag="em", style="italic"),
            Text(" c$"),
        ]

    def test_math_keeps_style(self):
        assert kids("<span style='color:red'>a $x$</span>") == [
            S(Text("a "), Math("x"), color="red")
        ]

    def test_math_in_html_and_literal_modes(self):
        assert kids("<b>$a_1$</b>", markdown=False) == [
            S(Math("a_1"), tag="b", weight="bold")
        ]
        assert kids("<b>$a_1$</b>", markdown=False, html=False) == [
            Text("<b>"),
            Math("a_1"),
            Text("</b>"),
        ]


@pytest.mark.parametrize("text", [None, float("nan"), ""])
def test_missing_text(text):
    assert parse(text) == Document()


def test_non_string_text():
    assert kids(12) == [Text("12")]


class TestPlainText:
    def test_roundtrip(self):
        s = "**Bold** <span style='color:red'>red</span>\nline 2 ![alt](x.png)"
        assert plain(s) == "Bold red\nline 2 alt"

    def test_math_keeps_delimiters(self):
        assert plain("a $x^2$ b") == "a $x^2$ b"

    def test_breaks_and_paragraphs(self):
        assert plain("Hello **there**<br>you<p>next *one*</p>") == (
            "Hello there\nyou\nnext one"
        )
        assert plain("a<br><p>b</p><br>c") == "a\nb\n\nc"
        assert plain("<p>a</p>") == "a"
        assert plain("a<p></p>b") == "a\nb"

    def test_empty(self):
        assert Document().plain_text() == ""
