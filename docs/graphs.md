# Graph Generation

## 1. Source data

Two JSON files from the [HP Dialogue Dataset](https://nuochenpku.github.io/HPD.github.io/) (`data/`), covering 1 097 dialogue sessions extracted from all seven books. Each session has a list of speakers, a position tag (`Book3-chapter5`), and explicit relation scores between Harry and every other character in the scene.

---

## 2. Building the graph JSON (`extract.py`)

The extractor reads every session and counts two things:

- **Appearances** — how many sessions each character participates in.
- **Co-occurrences** — how many sessions any two characters share.

For every pair that co-occurs at least `--min-cooccur` times (default 2), an edge is created. The top `--top-chars` characters by appearances are kept (default 40); everyone else is dropped along with their edges.

### Edge weight

Each edge gets a composite weight with two named components:

```
base   = log(co_occurrences + 1)
bonus  = avg(norm_affection, norm_familiarity)   ← Harry edges only
weight = base × (1 + bonus)

  norm_affection   = (affection + 10) / 20    # -10..10 → 0..1
  norm_familiarity = familiarity / 10          #   0..10 → 0..1
```

Edges that don't touch Harry use only `base` (bonus = 0.0). Harry-connected edges receive a bonus based on the bidirectional affection and familiarity scores from the dataset, so close friends like Ron and Hermione rank higher than characters Harry merely shares scenes with.

Both components are stored on every edge as `weight_components: {base, bonus}` for transparency and downstream filtering.

### Harry relation fields

For each character the dataset provides binary role flags (`friend`, `enemy`, `family`, `teacher`, ...) and four scored fields:

| Field | Range |
|---|---|
| Harry's affection to them | -10 to 10 |
| Their affection to Harry | -10 to 10 |
| Harry's familiarity with them | 0 to 10 |
| Their familiarity with Harry | 0 to 10 |

The extractor averages each pair bidirectionally and picks the most frequent binary label across sessions as the dominant `relation_type`.

### Output format

```
output/hpd_graph_<scope>_top<N>_minco<M>.json
```

```json
{
  "meta": { "books": "all", "top_chars": 40, "min_cooccur": 2, "sessions": 1097 },
  "nodes": [
    { "id": "Harry", "appearances": 1066 },
    { "id": "Ron", "appearances": 562, "affection": 6.98, "familiarity": 7.99, "relation_type": "friend" }
  ],
  "edges": [
    {
      "source": "Harry", "target": "Ron",
      "co_occurrences": 548, "weight": 11.506,
      "weight_components": { "base": 6.309, "bonus": 0.824 },
      "affection": 6.98, "familiarity": 7.99, "relation_type": "friend"
    }
  ]
}
```

---

## 3. Rendering the graph (`view.py`)

The renderer loads the JSON into a **NetworkX** `Graph` object and draws it with **Matplotlib** on a dark (`#0F172A`) background.

### Layout

**Radial layout** with Harry fixed at the origin (0, 0):

- **Inner ring** (r = 0.55): all nodes directly connected to Harry, arranged clockwise and grouped by relation type, then sorted by descending edge weight within each group.
- **Outer ring** (r = 1.05): peripheral characters not directly connected to Harry.

This replaces the old Fruchterman-Reingold spring layout, which compressed the most-connected nodes into an unreadable hairball at the center.

### Edge layers

Edges are drawn in two separate passes to avoid visual confusion:

1. **Non-Harry edges** (background) — faint slate-grey (`#334155`), very low opacity (≈ 0.22), context only.
2. **Harry edges** (foreground) — coloured by relation type, thickness driven by `weight` (0.8–6 pt), high opacity (≈ 0.88).

Use `--min-weight W` to suppress weak edges. Recommended: `2.0` for all-books graphs.

### Visual encoding

| Property | Source field | Notes |
|---|---|---|
| Node size | `appearances` — log-scaled | Capped lower than before so Harry isn't overwhelming |
| Node colour | `relation_type` to Harry | 11 visually distinct hues (see palette below) |
| Harry's node | Amber `#FCD34D` + soft glow halo | Always fixed regardless of relation type |
| Edge thickness | `weight` — normalised 0.8–6 pt | Harry edges only; non-Harry edges are thin grey |
| Edge colour | Relation type palette | Harry edges coloured; non-Harry edges flat grey |
| Weight labels | Top-N Harry edges annotated | Controlled by `--label-top N` (default 8) |
| Output DPI | 200 (was 150) | Crisper labels, better readability when zoomed |

### Colour palette

| Relation | Colour | Hex |
|---|---|---|
| Friend | Blue-700 | `#1D4ED8` |
| Classmate | Sky-700 | `#0369A1` |
| Teammate | Indigo-700 | `#4338CA` |
| Colleague | Teal-700 | `#0F766E` |
| Family | Green-700 | `#15803D` |
| Immediate family | Green-800 | `#166534` |
| Teacher | Purple-700 | `#7E22CE` |
| Opponent | Orange-700 | `#C2410C` |
| Acquaintance | Slate-600 | `#475569` |
| Enemy | Red-700 | `#B91C1C` |
| Lover | Pink-700 | `#BE185D` |
| Harry | Amber-600 | `#D97706` |

All hues are rich, saturated tones chosen for legibility on a white background, with enough contrast between every pair to be distinguishable at a glance.
