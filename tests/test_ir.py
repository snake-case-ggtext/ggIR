import subprocess
import sys

import pytest

from ggir.ir import (
    Document,
    LineBreak,
    Paragraph,
    Span,
    Text,
    UnsupportedTagError,
    parse,
    parse_html,
)


def test_ir_does_not_need_matplotlib():
    code = "import sys, ggir.ir; ggir.ir.parse('**x**'); print('matplotlib' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "False"


def test_markdown_tree():
    doc = parse("The **quick** *brown* fox")
    assert doc == Document(
        [
            Paragraph(
                [
                    Text("The "),
                    Span([Text("quick")], bold=True, tag="strong"),
                    Text(" "),
                    Span([Text("brown")], italic=True, tag="em"),
                    Text(" fox"),
                ]
            )
        ]
    )


def test_paragraphs_and_whitespace_between_them():
    doc = parse("one\n\ntwo")
    pars = [n for n in doc.children if isinstance(n, Paragraph)]
    assert [p.children for p in pars] == [[Text("one")], [Text("two")]]
    # whitespace between blocks is kept in the tree, dropped when flattened
    assert all(isinstance(n, (Paragraph, Text)) for n in doc.children)


def test_css_overrides():
    doc = parse_html(
        "<span style=\"color:red; font-size:12px; font-family:'Courier New'\">x</span>"
    )
    (span,) = doc.children
    assert isinstance(span, Span)
    assert span.color == "red"
    assert span.fontsize == pytest.approx(9.0)
    assert span.family == "Courier New"


def test_sup_sub_scripts():
    doc = parse_html("x<sup>2</sup><sub>i</sub>")
    _, sup, sub = doc.children
    assert sup.script == "sup" and sub.script == "sub"


def test_br_and_self_closing_br():
    for html in ["a<br>b", "a<br/>b"]:
        assert parse_html(html).children == [Text("a"), LineBreak(), Text("b")]


def test_mismatched_end_tag_closes_inner_elements():
    doc = parse_html("<b>x<i>y</b>z</i>")
    b, z = doc.children
    assert isinstance(b, Span) and b.bold
    assert b.children == [Text("x"), Span([Text("y")], italic=True, tag="i")]
    assert z == Text("z")


def test_entities_decoded():
    assert parse_html("a &amp; b").children == [Text("a & b")]


@pytest.mark.parametrize("md", ["<h1>x</h1>", "# x", "<div>x</div>"])
def test_unsupported_tags(md):
    with pytest.raises(UnsupportedTagError, match="isn't supported"):
        parse(md)


@pytest.mark.parametrize("text", [None, float("nan"), ""])
def test_missing_text(text):
    assert parse(text).children == []


def test_plain_text():
    doc = parse("Hello **there**<br>you\n\nnext *one*")
    assert doc.plain_text() == "Hello there\nyou\n\nnext one"
