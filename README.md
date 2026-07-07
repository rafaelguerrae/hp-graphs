# hp-graphs

> **Comunicação e Redes** — college project  
> Visualising Harry Potter character relationships as network graphs across three story periods, using the [HP Dialogue Dataset (HPD)](https://nuochenpku.github.io/HPD.github.io/).

---

## Quick start

### 1 — Install dependencies

Requires **Python 3.10+**.

```bash
make install
# or manually:
python3 -m pip install -r requirements.txt
```

### 2 — Run the pipeline

```bash
# Extract + render the full-series graph (all books)
make extract
make view

# Or do everything in one shot (all books + 3 time periods):
make all
```

The rendered PNGs land in `output/`.

---

## All make commands

| Command | What it does |
|---|---|
| `make install` | Install Python dependencies |
| `make extract` | Extract full-series graph JSON (all books, top 40 chars) |
| `make extract-periods` | Extract early / mid / late JSON snapshots |
| `make view` | Render full-series graph → `output/hpd_graph_snapshot_all.png` |
| `make view-early` | Render Books 1–2 graph |
| `make view-mid` | Render Books 3–5 graph |
| `make view-late` | Render Books 6–7 graph |
| `make view-all` | Render all four graphs |
| `make all` | Full pipeline: extract everything + render everything |
| `make clean` | Delete all generated files in `output/` |