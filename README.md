# ggIR

An **intermediate representation for rich text in plots**. ggIR parses
markdown, HTML and inline CSS into a small, renderer-independent document
tree. It is the parsing layer of
[ggtext for Python](https://github.com/snake-case-ggtext/ggtext_ShanEllis),
which measures and draws the tree with matplotlib and plotnine.

ggIR depends only on `markdown-it-py` and does not import matplotlib.

```python
import ggir

ggir.parse("Bill size of <span style='color:#E69F00'>**Adelie**</span>, $x^2$")
```

```
Document
├── Text("Bill size of ")
├── Span(color="#E69F00")
│   └── Span(tag="strong", weight="bold")
│       └── Text("Adelie")
├── Text(", ")
└── Math("x^2")
```

## The tree

| Node | Meaning |
|---|---|
| `Document` | the root; children are inline nodes and/or paragraphs |
| `Paragraph` | `<p>`, `<div>`, or a blank-line separated chunk with `blocks=True` |
| `Span` | inline content with style overrides; `script="sup"/"sub"` for `<sup>`/`<sub>`, `valign` for CSS `vertical-align` |
| `Text` | text, whitespace as written; U+00A0 (`&nbsp;`) never breaks |
| `LineBreak` | `<br>`, a markdown hard break, or `\n` (with `newline="break"`) |
| `Math` | a `$...$` mathtext segment |
| `Image` | `<img>` or `![alt](src)` |

Style fields on `Span` and `Paragraph` are overrides of the parent's style.
`None` means "inherit". They are: `weight`, `style`, `variant`, `family`,
`size`, `color`, `background`, `underline`, `strike` and `href`. Relative
sizes (`em`, `%`, `small`, `larger`, ...) stay relative as
`Length(x, "em")`, so the renderer resolves them against the real parent
size. How a construct looks, e.g. how small and how high a superscript is,
is up to the renderer.

## Options

```python
ggir.parse(
    text,
    markdown=True,        # inline CommonMark + ~~strike~~; "1. Adelie" stays literal
    html=True,            # tags without markdown, when markdown=False
    math=True,            # $...$ -> Math
    newline="break",      # or "space" (markdown / R ggtext convention)
    blocks=False,         # True: blank lines separate Paragraphs (R ggtext / gridtext)
    on_unknown="warn",    # or "error" / "ignore" for unsupported tags
)
```

### Supported markup

| Markdown | HTML | CSS (in `style='...'`) |
|---|---|---|
| `**bold**`, `*italic*`, `~~strike~~`, `` `code` ``, `[link](url)`, `![alt](src)` | `<b>` `<strong>` `<i>` `<em>` `<u>` `<ins>` `<s>` `<del>` `<strike>` `<sup>` `<sub>` `<br>` `<p>` `<div>` `<span>` `<font>` `<code>` `<kbd>` `<tt>` `<samp>` `<small>` `<big>` `<mark>` `<a>` `<img>` | `color`, `background(-color)`, `font-size`, `font-family`, `font-weight`, `font-style`, `font-variant`, `text-decoration`, `vertical-align` |

## Resolving

`ggir.resolve` turns the tree into the flat list of styled runs a renderer
lays out: `TextRun`, `ImageRun` and `LINE_BREAK`, each with a concrete
`ggir.Style` (sizes and baseline shifts in points). ggIR makes the
resolving decisions (em sizes, nesting, paragraph breaks, merging runs);
the renderer supplies only its numbers, in a `Policy`.

```python
toks = ggir.resolve(
    ggir.parse("x<sup>2</sup> in <span style='color:red'>red</span>"),
    ggir.Style(size=12),
    policy=ggir.Policy(script_scale=0.7, sup_shift=0.4, sub_shift=-0.2, default_em=10),
    validate_color=None,  # or a callable: colour -> normalised colour / None
)
ggir.plain_text(toks)  # 'x2 in red'
```

- Styles are derived from `base` with `dataclasses.replace`, so a
  renderer's `Style` subclass (ggtext adds matplotlib `FontProperties`)
  is kept.
- ggIR validates no colours. With `validate_color`, an invalid text colour
  warns once and is ignored.
- Tags outside `ggir.KNOWN_TAGS` warn once (parse with
  `on_unknown="ignore"` to avoid a second warning from the parser).
- A renderer that does not shift scripts by a fixed fraction of the em
  (R's gridtext uses 0.8x size and half the ascent) subclasses `Policy`
  and overrides `Policy.script`.

## Install

```bash
pip install git+https://github.com/snake-case-ggtext/ggIR
```

## History

v0.1 also contained a matplotlib renderer (a port of R's gridtext layout
engine) for plotnine-ggtext. It is kept at the `v0.1.0` tag. From v0.2,
ggIR is only the parsing layer, and rendering lives in ggtext. v0.3 adds
`resolve`, moved from ggtext's adapter, so other renderers can share it.

## License

MIT. The parser is adapted from Shannon E. Ellis's ggtext for Python (MIT).
