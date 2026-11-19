import matplotlib.pyplot as plt
import numpy as np
import pytest
from matplotlib.text import Text

from ggir import RichText, measure_with, unit

TEXT = "The **quick** *brown* fox<br>jumps over the <span style='color:#C62828'>lazy</span> dog"


def fig_ax(w=4.0, h=3.0):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    return fig, ax


def add(ax, *args, **kwargs):
    t = RichText(*args, **kwargs)
    ax.add_artist(t)
    return t


# --- images ------------------------------------------------------------------


def test_alignments_and_rotation(compare_figure):
    fig, ax = fig_ax(6, 4.5)
    box = dict(fill="#FFF8E7", box_edgecolor="#EDAE49", padding=4, r=3)
    for ha, x in [("left", 0.05), ("center", 0.5), ("right", 0.95)]:
        for va, y in [("top", 0.95), ("center", 0.62), ("bottom", 0.3)]:
            add(ax, x, y, f"*{ha}* / **{va}**", ha=ha, va=va, fontsize=10, **box)
            ax.plot(x, y, "o", color="#1565C0", ms=3)
    for angle, x in [(30, 0.3), (-30, 0.7)]:
        add(ax, x, 0.12, TEXT, rotation=angle, fontsize=8, ha="center", va="center", **box)
        ax.plot(x, 0.12, "o", color="#1565C0", ms=3)
    compare_figure(fig, "alignments_and_rotation")


def test_wrapping_and_markup(compare_figure):
    fig, ax = fig_ax()
    add(
        ax,
        0.5,
        0.5,
        "A text box with **word wrapping**, *italics*, H<sub>2</sub>O, "
        "x<sup>2</sup> and <span style='font-size:16pt; color:#2E7D32'>big "
        "green</span> words.\n\nA second paragraph.",
        width=unit(2.6, "in"),
        padding=unit(5.5, "pt"),
        r=unit(5.5, "pt"),
        fill="#F1F8E9",
        box_edgecolor="black",
        ha="center",
        va="center",
    )
    compare_figure(fig, "wrapping_and_markup")


def test_figure_title_and_axis_labels(compare_figure):
    fig, ax = fig_ax()
    fig.subplots_adjust(left=0.22)
    fig.add_artist(
        RichText(
            0.5, 0.97, "A **rich** title with *style*", ha="center", va="top",
            fontsize=14, transform=fig.transFigure,
        )
    )  # fmt: skip
    add(
        ax, -0.18, 0.5, "y in m s<sup>-1</sup>", rotation=90, ha="center",
        va="center", transform=ax.transAxes, clip_on=False,
    )  # fmt: skip
    ax.plot([0, 1], [0, 1])
    compare_figure(fig, "figure_title_and_axis_labels")


def test_plain_text_matches_matplotlib_text(compare_figure):
    # Plain text without a box should render like a matplotlib Text
    fig, ax = fig_ax(3, 1)
    ax.set_axis_off()
    add(ax, 0.05, 0.6, "Plain words here", fontsize=14, va="baseline")
    ax.text(0.05, 0.2, "Plain words here", fontsize=14, va="baseline")
    compare_figure(fig, "plain_text_vs_text")


# --- behaviour ---------------------------------------------------------------


def test_is_a_text():
    t = RichText(0, 0, "**x**")
    assert isinstance(t, Text)
    t.set(color="red", fontsize=20, fill="yellow", padding=3)
    assert t.get_fontsize() == 20


def test_window_extent_matches_layout():
    fig, ax = fig_ax()
    t = add(ax, 0.5, 0.5, "**hello** world", ha="left", va="bottom", padding=2)
    fig.canvas.draw()
    bb = t.get_window_extent()
    x0, y0 = ax.transData.transform((0.5, 0.5))
    assert bb.x0 == pytest.approx(x0)
    assert bb.y0 == pytest.approx(y0)
    with measure_with(fig.canvas.get_renderer()):
        L = t.layout()
    assert bb.width == pytest.approx(L.width * fig.dpi / 72)
    assert bb.height == pytest.approx(L.height * fig.dpi / 72)


def test_window_extent_rotated_swaps_dimensions():
    fig, ax = fig_ax()
    t0 = add(ax, 0.5, 0.5, "some wide text", ha="center", va="center")
    t90 = add(ax, 0.5, 0.5, "some wide text", ha="center", va="center", rotation=90)
    fig.canvas.draw()
    b0, b90 = t0.get_window_extent(), t90.get_window_extent()
    assert b90.width == pytest.approx(b0.height, abs=0.5)
    assert b90.height == pytest.approx(b0.width, abs=0.5)


def test_window_extent_respects_dpi_argument():
    fig, ax = fig_ax()
    t = add(ax, 0.5, 0.5, "text")
    fig.canvas.draw()
    w72 = t.get_window_extent().width
    w144 = t.get_window_extent(dpi=144).width
    assert w144 == pytest.approx(2 * w72, rel=0.1)
    assert fig.dpi == 72


def test_baseline_alignment_matches_text():
    fig, ax = fig_ax()
    rt = add(ax, 0.2, 0.5, "Hxg", va="baseline", fontsize=20)
    pt = ax.text(0.6, 0.5, "Hxg", va="baseline", fontsize=20)
    fig.canvas.draw()
    a, b = rt.get_window_extent(), pt.get_window_extent()
    assert a.y0 == pytest.approx(b.y0, abs=1.5)
    assert a.y1 == pytest.approx(b.y1, abs=2.5)


def test_empty_and_invisible():
    fig, ax = fig_ax()
    e = add(ax, 0.5, 0.5, "")
    v = add(ax, 0.5, 0.5, "x", visible=False)
    add(ax, np.nan, 0.5, "x")  # must not fail to draw
    fig.canvas.draw()
    assert e.get_window_extent().width == 0
    assert v.get_window_extent().width == 1  # Bbox.unit(), as Text


def test_document_is_cached_and_invalidated():
    t = RichText(0, 0, "**a**")
    d = t.get_document()
    assert t.get_document() is d
    t.set_text("*b*")
    assert t.get_document() is not d
    assert t.get_document().plain_text() == "b"


def test_svg_backend(tmp_path):
    fig, ax = fig_ax()
    add(ax, 0.5, 0.5, "**svg** text", fill="white", box_edgecolor="black", gid="rt")
    out = tmp_path / "x.svg"
    fig.savefig(out)
    svg = out.read_text()
    assert 'id="rt"' in svg
