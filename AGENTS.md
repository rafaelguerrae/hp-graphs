# AGENTS.md — hp-graphs

Commands and workflows for working on this project.

## Setup

```bash
make install          # create .venv and install dependencies (run once)
```

## Extract — build a graph JSON

```bash
make extract                              # all books, top 40 chars, min 2 co-occurrences
make extract BOOKS='Book1 Book2'          # specific books
make extract BOOKS='Book4'               # single book
make extract TOP=30 MINCO=3             # custom thresholds
make extract-periods                     # early / mid / late snapshots in one shot
```

Output lands in `output/` with an auto-generated name:
- `hpd_graph_all_top40_minco2.json`
- `hpd_graph_Book1-Book2_top40_minco2.json`
- etc.

## Render — produce a PNG graph

```bash
make view                                # render the full-series snapshot
make view-early                          # Books 1–2
make view-mid                            # Books 3–5
make view-late                           # Books 6–7
make view-all                            # render all four at once
make view BOOKS='Book1 Book2'            # render a custom snapshot
```

## Export — produce GEXF files for Gephi

```bash
make export                              # export full-series snapshot → .gexf
make export-periods                      # early / mid / late snapshots → .gexf
make export-all                          # export all four snapshots
make export BOOKS='Book1 Book2'          # export a custom snapshot
```

Output lands alongside the source JSON in `output/`:
- `hpd_graph_all_top40_minco2.gexf`
- `hpd_graph_Book1-Book2_top40_minco2.gexf`
- etc.

Open the resulting `.gexf` in Gephi via **File → Open**.

## Full pipeline

```bash
make all              # extract everything + render everything
```

## Cleanup

```bash
make clean            # remove generated output files (JSON + PNG + GEXF)
make clean-venv       # remove the .venv directory
```

---

## Direct script usage

### src/extract.py

```bash
.venv/bin/python3 src/extract.py
.venv/bin/python3 src/extract.py --books Book1 Book2
.venv/bin/python3 src/extract.py --books Book3 Book4 Book5 --top-chars 30 --min-cooccur 3
.venv/bin/python3 src/extract.py --out my_graph.json
```

### src/view.py

```bash
.venv/bin/python3 src/view.py
.venv/bin/python3 src/view.py --snapshot output/hpd_graph_Book1-Book2_top40_minco2.json
.venv/bin/python3 src/view.py --min-weight 3.0
.venv/bin/python3 src/view.py --out output/my_graph.png
.venv/bin/python3 src/view.py --show
```

### src/export_gephi.py

```bash
.venv/bin/python3 src/export_gephi.py
.venv/bin/python3 src/export_gephi.py --snapshot output/hpd_graph_Book1-Book2_top40_minco2.json
.venv/bin/python3 src/export_gephi.py --out output/my_graph.gexf
```

---

## Data files

Place the HPD source datasets in `data/` before running anything:

```
data/en_train_set.json
data/en_test_set.json
```

Download from: https://nuochenpku.github.io/HPD.github.io/
