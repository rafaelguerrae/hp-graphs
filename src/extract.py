"""
extract.py
----------
Extracts a character relationship graph from the Harry Potter Dialogue Dataset.

Output: graph_data.json
  - nodes: list of characters with appearance count and (when available)
           their explicit relation scores with Harry
  - edges: list of character pairs with:
           * co_occurrences  : how many sessions they share
           * weight          : composite strength score (see below)
           * affection       : avg bidirectional affection (Harry edges only)
           * familiarity     : avg bidirectional familiarity (Harry edges only)
           * relation_type   : dominant binary relation label (Harry edges only)

Edge weight formula
-------------------
  base   = log(co_occurrences + 1)               # log-scaled session count
  bonus  = (norm_affection + norm_familiarity) / 2  # 0-1 only for Harry edges
  weight = base * (1 + bonus)

Usage
-----
  python3 extract.py                          # all books, all characters
  python3 extract.py --books Book1 Book2      # filter to specific books
  python3 extract.py --top-chars 30           # keep only top-N characters
  python3 extract.py --min-cooccur 3          # drop edges with few shared sessions
  python3 extract.py --out my_graph.json      # custom output path
"""

import json
import math
import argparse
import os
from collections import defaultdict
from itertools import combinations

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SRC_DIR    = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SRC_DIR)
DATA_DIR   = os.path.join(PROJECT_DIR, "data")
OUTPUT_DIR = os.path.join(PROJECT_DIR, "output")
TRAIN_FILE = os.path.join(DATA_DIR, "en_train_set.json")
TEST_FILE  = os.path.join(DATA_DIR, "en_test_set.json")

BINARY_RELATION_KEYS = [
    "friend", "classmate", "teacher", "family",
    "immediate family", "lover", "opponent",
    "colleague", "teammate", "enemy",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_sessions(books_filter=None):
    """Load and merge train + test sessions, optionally filtered by book."""
    sessions = {}
    for fpath in [TRAIN_FILE, TEST_FILE]:
        with open(fpath, encoding="utf-8") as f:
            sessions.update(json.load(f))

    if books_filter:
        books_filter = set(books_filter)
        sessions = {
            sid: s for sid, s in sessions.items()
            if s.get("position", "").split("-")[0] in books_filter
        }

    return sessions


def parse_relation(rel_data):
    """
    Extract affection, familiarity, and dominant binary relation
    from a 'relations with Harry' entry.

    The dataset always uses 'him/his' keys regardless of character gender.
    """
    harry_affection   = rel_data.get("Harry's affection to him")
    harry_familiarity = rel_data.get("Harry's familiarity with him")
    char_affection    = rel_data.get("His affection to Harry")
    char_familiarity  = rel_data.get("His familiarity with Harry")

    # Bidirectional average
    affection   = None
    familiarity = None

    if harry_affection is not None and char_affection is not None:
        affection = (harry_affection + char_affection) / 2

    if harry_familiarity is not None and char_familiarity is not None:
        familiarity = (harry_familiarity + char_familiarity) / 2

    # Dominant binary relation (priority order defined in BINARY_RELATION_KEYS)
    dominant_rel = "acquaintance"
    for rel_key in BINARY_RELATION_KEYS:
        if rel_data.get(rel_key, 0.0) == 1.0:
            dominant_rel = rel_key
            break

    return affection, familiarity, dominant_rel


def edge_weight(co_occurrences, affection=None, familiarity=None):
    """
    Composite edge weight.
      base   = log(co_occurrences + 1)
      bonus  = avg of normalised affection + familiarity   [Harry edges only]
      weight = base * (1 + bonus)
    """
    base = math.log(co_occurrences + 1)

    if affection is not None and familiarity is not None:
        norm_affection   = (affection + 10) / 20   # -10..10 -> 0..1
        norm_familiarity = familiarity / 10         #   0..10 -> 0..1
        bonus = (norm_affection + norm_familiarity) / 2
        return round(base * (1 + bonus), 4)

    return round(base, 4)


# ---------------------------------------------------------------------------
# Core extraction
# ---------------------------------------------------------------------------

def extract(sessions, top_chars=None, min_cooccur=1):
    """
    Returns (nodes, edges) ready for JSON serialisation.

    Parameters
    ----------
    sessions    : dict of session_id -> session dict
    top_chars   : int or None - keep only the N most-appearing characters
    min_cooccur : int - drop edges with fewer than this many shared sessions
    """

    # ---- 1. Count appearances and co-occurrences -------------------------

    appearances = defaultdict(int)   # char -> session count
    cooccur     = defaultdict(int)   # frozenset(a,b) -> count

    # Accumulate Harry relation data across all sessions
    harry_rel_acc = defaultdict(lambda: {
        "affection_sum":   0.0,
        "familiarity_sum": 0.0,
        "count":           0,
        "rel_counts":      defaultdict(int),
    })

    for session in sessions.values():
        speakers = session.get("speakers", [])

        # Count appearances
        for sp in speakers:
            appearances[sp] += 1

        # Co-occurrences: all unique pairs in this session
        unique_speakers = list(dict.fromkeys(speakers))  # dedupe, preserve order
        for a, b in combinations(unique_speakers, 2):
            cooccur[frozenset([a, b])] += 1

        # Harry explicit relation scores
        for char, rel_data in session.get("relations with Harry", {}).items():
            if char == "Harry":
                continue
            aff, fam, dominant = parse_relation(rel_data)
            acc = harry_rel_acc[char]
            if aff is not None:
                acc["affection_sum"]   += aff
            if fam is not None:
                acc["familiarity_sum"] += fam
            acc["count"] += 1
            acc["rel_counts"][dominant] += 1

    # ---- 2. Finalise Harry relation averages -----------------------------

    harry_rels = {}   # char -> {affection, familiarity, relation_type}
    for char, acc in harry_rel_acc.items():
        n = acc["count"]
        if n == 0:
            continue
        dominant = max(acc["rel_counts"], key=acc["rel_counts"].get)
        harry_rels[char] = {
            "affection":     round(acc["affection_sum"]   / n, 2),
            "familiarity":   round(acc["familiarity_sum"] / n, 2),
            "relation_type": dominant,
        }

    # ---- 3. Optional: keep only top-N characters ------------------------

    if top_chars:
        keep = set(
            char for char, _ in
            sorted(appearances.items(), key=lambda x: -x[1])[:top_chars]
        )
    else:
        keep = set(appearances.keys())

    # ---- 4. Build node list ---------------------------------------------

    nodes = []
    for char in sorted(keep, key=lambda c: -appearances[c]):
        node = {
            "id":          char,
            "appearances": appearances[char],
        }
        if char in harry_rels:
            node["affection"]     = harry_rels[char]["affection"]
            node["familiarity"]   = harry_rels[char]["familiarity"]
            node["relation_type"] = harry_rels[char]["relation_type"]
        nodes.append(node)

    # ---- 5. Build edge list ---------------------------------------------

    edges = []
    for pair, count in cooccur.items():
        if count < min_cooccur:
            continue

        a, b = tuple(pair)

        # Skip if either node was pruned out
        if a not in keep or b not in keep:
            continue

        edge = {
            "source":        a,
            "target":        b,
            "co_occurrences": count,
        }

        # Attach explicit Harry scores when one endpoint is Harry
        harry_neighbor = None
        if a == "Harry" and b in harry_rels:
            harry_neighbor = b
        elif b == "Harry" and a in harry_rels:
            harry_neighbor = a

        if harry_neighbor:
            rel = harry_rels[harry_neighbor]
            edge["affection"]     = rel["affection"]
            edge["familiarity"]   = rel["familiarity"]
            edge["relation_type"] = rel["relation_type"]

        edge["weight"] = edge_weight(
            count,
            edge.get("affection"),
            edge.get("familiarity"),
        )

        edges.append(edge)

    # Sort strongest edges first
    edges.sort(key=lambda e: -e["weight"])

    return nodes, edges


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_output_name(books, top_chars, min_cooccur):
    """
    Build a descriptive filename so runs never silently overwrite each other.

    Examples:
      hpd_graph_all_top40_minco2.json
      hpd_graph_Book1-Book2_top30_minco1.json
    """
    scope = "-".join(sorted(books)) if books else "all"
    parts = ["hpd_graph", scope]
    if top_chars:
        parts.append(f"top{top_chars}")
    if min_cooccur and min_cooccur > 1:
        parts.append(f"minco{min_cooccur}")
    return "_".join(parts) + ".json"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Extract HPD character relationship graph data."
    )
    parser.add_argument(
        "--books", nargs="+", metavar="BOOK",
        help=(
            "Filter to specific books, e.g. --books Book1 Book2 Book3. "
            "Valid values: Book1 .. Book7. Default: all books."
        ),
    )
    parser.add_argument(
        "--top-chars", type=int, default=None, metavar="N",
        help="Keep only the top N most-appearing characters. Default: all.",
    )
    parser.add_argument(
        "--min-cooccur", type=int, default=1, metavar="N",
        help="Minimum shared sessions required for an edge. Default: 1.",
    )
    parser.add_argument(
        "--out", default=None, metavar="FILE",
        help=(
            "Output JSON path. Absolute paths are used as-is; relative paths "
            "are placed inside output/. "
            "Default: auto-generated descriptor inside output/ "
            "(e.g. hpd_graph_all_top40_minco2.json)."
        ),
    )
    return parser.parse_args()


def main():
    args = parse_args()

    print("Loading sessions...")
    sessions = load_sessions(books_filter=args.books)
    book_label = ", ".join(sorted(args.books)) if args.books else "all books"
    print(f"  -> {len(sessions)} sessions loaded ({book_label})")

    print("Extracting graph...")
    nodes, edges = extract(
        sessions,
        top_chars=args.top_chars,
        min_cooccur=args.min_cooccur,
    )

    # Resolve output path
    if args.out is None:
        # Auto-generate a descriptive filename inside output/
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        out_path = os.path.join(
            OUTPUT_DIR,
            build_output_name(args.books, args.top_chars, args.min_cooccur),
        )
    elif os.path.isabs(args.out):
        out_path = args.out
    else:
        # Relative path → place it inside output/
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        out_path = os.path.join(OUTPUT_DIR, args.out)

    result = {
        "meta": {
            "books":       args.books or "all",
            "top_chars":   args.top_chars,
            "min_cooccur": args.min_cooccur,
            "sessions":    len(sessions),
        },
        "nodes": nodes,
        "edges": edges,
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\nDone!")
    print(f"  Nodes  : {len(nodes)}")
    print(f"  Edges  : {len(edges)}")
    print(f"  Output : {out_path}")

    # Quick preview of strongest edges
    print("\nTop 10 strongest edges:")
    for e in edges[:10]:
        label = f"[{e['relation_type']}]" if "relation_type" in e else ""
        print(
            f"  {e['source']:15s} <-> {e['target']:15s}  "
            f"weight={e['weight']:.3f}  co_occur={e['co_occurrences']}  {label}"
        )


if __name__ == "__main__":
    main()
