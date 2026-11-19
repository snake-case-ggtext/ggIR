# ggIR

Rich text for matplotlib: a markdown / HTML **intermediate representation**
and a **box layout engine**, ported from R's
[gridtext](https://github.com/wilkelab/gridtext).

It powers [plotnine-ggtext](https://github.com/snake-case-ggtext/plotnine-ggtext)
and works with plain matplotlib.

```python
import matplotlib.pyplot as plt
from ggir import RichText, unit

fig, ax = plt.subplots()
ax.add_artist(RichText(
    0.5, 0.5,
    "The **quick** *brown* fox<br>jumps over the "
    "<span style='color:#C62828'>lazy</span> dog",
    ha="center", va="center",
    fill="#FFF8E7", box_edgecolor="#EDAE49", padding=4, r=3,
))
```

`RichText` is a subclass of `matplotlib.text.Text`. Anything that positions,
styles or measures a `Text` (`set_position`, `set_color`, `ha`/`va`, rotation,
`get_window_extent`, tight layout, ...) also works with it.

## Pipeline

```
markdown ──► HTML ──► Document tree ──► paragraphs of boxes ──► Layout (pt) ──► artists (px)
            ggir.parse              ggir.to_boxes          ggir.layout_rect_box  ggir.box_artists
```

1. **IR (`ggir.ir`).** `parse()` turns markdown or HTML into a tree:
   `Document`, `Paragraph`, `Span` (bold, italic, sup/sub, colour, size,
   family) and `Text` / `LineBreak`. These are plain dataclasses that don't
   import matplotlib, so other renderers can use them.
2. **Boxes (`ggir.boxes`).** `to_boxes()` resolves the styles against a base
   `Style` and flattens each paragraph into words (`TextBox`), breakable
   spaces (`Glue`) and forced breaks (`Break`).
3. **Layout (`ggir.layout`).** `layout_rect_box()` breaks lines (first fit,
   as in gridtext), stacks the paragraphs and adds padding and margins. It
   returns a `Layout` with every word placed, in points.
4. **Drawing (`ggir.draw`).** `box_transform()` maps the layout to pixels
   (justification, scaling, rotation about the anchor), and `box_artists()`
   makes one `PathPatch` for the box plus one `Text` per word.

Word widths are measured with the active renderer inside
`with measure_with(renderer):`, so the spacing matches what Agg actually
draws with hinted glyphs. Outside that context, unhinted outline metrics
are used.

### Supported markup

`**bold**`, `*italic*`, `<b>`, `<strong>`, `<i>`, `<em>`, `<br>`, `<p>`,
`<sup>`, `<sub>`, and `<span style="color: ...; font-size: ...; font-family: ...">`.
Any other tag raises `UnsupportedTagError`.

## Install

```bash
pip install git+https://github.com/snake-case-ggtext/ggIR
```

## Tests

```bash
uv run pytest                      # unit + image tests
uv run pytest --update-baselines   # regenerate baseline images
```

## License

MIT. The layout engine is a port of gridtext © Claus O. Wilke (MIT).
