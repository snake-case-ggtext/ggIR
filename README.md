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

## Install

```bash
pip install git+https://github.com/snake-case-ggtext/ggIR
```

## History

v0.1 also contained a matplotlib renderer (a port of R's gridtext layout
engine) for plotnine-ggtext. It is kept at the `v0.1.0` tag. From v0.2,
ggIR is only the parsing layer, and rendering lives in ggtext.

## License

MIT. The parser is adapted from Shannon E. Ellis's ggtext for Python (MIT).
