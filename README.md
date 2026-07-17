# hp-graphs

**Comunicação e Redes** — Visualising Harry Potter character relationships as network graphs across three story periods, using the [HP Dialogue Dataset (HPD)](https://nuochenpku.github.io/HPD.github.io/).

## Quick start

### 1 — Install dependencies

Requires **Python 3.10+**.

```bash
make install
```

### 2 — Run the pipeline

```bash
# Extract + render the full-series graph (all books)
make extract
make view
```

The rendered PNGs land in `output/`.

## Docs

- [docs/graph_info](docs/graph_info.md)