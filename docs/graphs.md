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

Each edge gets a composite weight:

```
base   = log(co_occurrences + 1)
bonus  = avg(norm_affection, norm_familiarity)   <- Harry edges only
weight = base x (1 + bonus)

  norm_affection   = (affection + 10) / 20    # -10..10 -> 0..1
  norm_familiarity = familiarity / 10          #   0..10 -> 0..1
```

Edges that don't touch Harry use only `base`. Harry-connected edges receive a bonus based on the bidirectional affection and familiarity scores from the dataset, so close friends like Ron and Hermione rank higher than characters Harry merely shares scenes with.

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
    { "source": "Harry", "target": "Ron", "co_occurrences": 548, "weight": 11.506,
      "affection": 6.98, "familiarity": 7.99, "relation_type": "friend" }
  ]
}
```

---

## 3. Rendering the graph (`view.py`)

The renderer loads the JSON into a **NetworkX** `Graph` object and draws it with **Matplotlib**.

### Layout

Spring layout (`nx.spring_layout`, Fruchterman-Reingold algorithm) with edge weights as attraction forces. Characters that share many strong scenes are pulled together; peripheral characters drift outward. A fixed seed (`42`) makes the layout reproducible.

### Visual encoding

| Property | Source field |
|---|---|
| Node size | `appearances` — log-scaled so Harry is large but not overwhelming |
| Node colour | `relation_type` to Harry (blue = friend, red = enemy, green = family, purple = teacher, grey = acquaintance) |
| Harry's node | Always amber/gold, regardless of relation type |
| Edge thickness | `weight` — normalised to 0.4–5 pt |
| Edge colour | Same relation palette as nodes; grey for non-Harry edges |
| Edge opacity | `co_occurrences` — faint for rare, solid for frequent |
| Label size | Scales with `appearances` so major characters are legible |
