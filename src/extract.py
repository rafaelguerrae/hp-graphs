import json
import math
import argparse
import os
from collections import defaultdict
from itertools import combinations

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SRC_DIR)
DATA_DIR = os.path.join(PROJECT_DIR, "data")
OUTPUT_DIR = os.path.join(PROJECT_DIR, "output")
TRAIN_FILE = os.path.join(DATA_DIR, "en_train_set.json")
TEST_FILE = os.path.join(DATA_DIR, "en_test_set.json")

BINARY_RELATION_KEYS = [
    "friend", "classmate", "teacher", "family",
    "immediate family", "lover", "opponent",
    "colleague", "teammate", "enemy",
]


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
    """Return (affection, familiarity, dominant_relation) from a Harry-relation entry."""
    harry_aff = rel_data.get("Harry's affection to him")
    harry_fam = rel_data.get("Harry's familiarity with him")
    char_aff = rel_data.get("His affection to Harry")
    char_fam = rel_data.get("His familiarity with Harry")

    affection = (harry_aff + char_aff) / 2 if harry_aff is not None and char_aff is not None else None
    familiarity = (harry_fam + char_fam) / 2 if harry_fam is not None and char_fam is not None else None

    dominant = "acquaintance"
    for key in BINARY_RELATION_KEYS:
        if rel_data.get(key, 0.0) == 1.0:
            dominant = key
            break

    return affection, familiarity, dominant


def edge_weight(co_occurrences, affection=None, familiarity=None):
    """
    Composite edge weight.
      base   = log(co_occurrences + 1)
      bonus  = avg(norm_affection, norm_familiarity)  — Harry edges only
      weight = base * (1 + bonus)

    Returns:
        (weight: float, components: dict)
        components keys: 'base', 'bonus'  (bonus is 0.0 for non-Harry edges)
    """
    base = math.log(co_occurrences + 1)
    if affection is not None and familiarity is not None:
        norm_aff = (affection + 10) / 20   # -10..10 → 0..1
        norm_fam = familiarity / 10         #   0..10 → 0..1
        bonus = (norm_aff + norm_fam) / 2
        return round(base * (1 + bonus), 4), {"base": round(base, 4), "bonus": round(bonus, 4)}
    return round(base, 4), {"base": round(base, 4), "bonus": 0.0}


def extract(sessions, top_chars=None, min_cooccur=1):
    """Return (nodes, edges) ready for JSON serialisation."""
    appearances = defaultdict(int)
    cooccur = defaultdict(int)
    harry_rel_acc = defaultdict(lambda: {
        "affection_sum": 0.0,
        "familiarity_sum": 0.0,
        "count": 0,
        "rel_counts": defaultdict(int),
    })

    for session in sessions.values():
        speakers = session.get("speakers", [])
        for sp in speakers:
            appearances[sp] += 1

        unique = list(dict.fromkeys(speakers))
        for a, b in combinations(unique, 2):
            cooccur[frozenset([a, b])] += 1

        for char, rel_data in session.get("relations with Harry", {}).items():
            if char == "Harry":
                continue
            aff, fam, dominant = parse_relation(rel_data)
            acc = harry_rel_acc[char]
            if aff is not None:
                acc["affection_sum"] += aff
            if fam is not None:
                acc["familiarity_sum"] += fam
            acc["count"] += 1
            acc["rel_counts"][dominant] += 1

    harry_rels = {}
    for char, acc in harry_rel_acc.items():
        n = acc["count"]
        if n == 0:
            continue
        dominant = max(acc["rel_counts"], key=acc["rel_counts"].get)
        harry_rels[char] = {
            "affection": round(acc["affection_sum"] / n, 2),
            "familiarity": round(acc["familiarity_sum"] / n, 2),
            "relation_type": dominant,
        }

    keep = (
        set(char for char, _ in sorted(appearances.items(), key=lambda x: -x[1])[:top_chars])
        if top_chars else set(appearances.keys())
    )

    nodes = []
    for char in sorted(keep, key=lambda c: -appearances[c]):
        node = {"id": char, "appearances": appearances[char]}
        if char in harry_rels:
            node["affection"] = harry_rels[char]["affection"]
            node["familiarity"] = harry_rels[char]["familiarity"]
            node["relation_type"] = harry_rels[char]["relation_type"]
        nodes.append(node)

    edges = []
    for pair, count in cooccur.items():
        if count < min_cooccur:
            continue
        a, b = tuple(pair)
        if a not in keep or b not in keep:
            continue

        edge = {"source": a, "target": b, "co_occurrences": count}

        harry_neighbor = None
        if a == "Harry" and b in harry_rels:
            harry_neighbor = b
        elif b == "Harry" and a in harry_rels:
            harry_neighbor = a

        if harry_neighbor:
            rel = harry_rels[harry_neighbor]
            edge["affection"] = rel["affection"]
            edge["familiarity"] = rel["familiarity"]
            edge["relation_type"] = rel["relation_type"]

        w, components = edge_weight(count, edge.get("affection"), edge.get("familiarity"))
        edge["weight"] = w
        edge["weight_components"] = components
        edges.append(edge)

    edges.sort(key=lambda e: -e["weight"])
    return nodes, edges


def build_output_name(books, top_chars, min_cooccur):
    """Build a descriptive filename from the flags used, e.g. hpd_graph_all_top40_minco2.json"""
    scope = "-".join(sorted(books)) if books else "all"
    parts = ["hpd_graph", scope]
    if top_chars:
        parts.append(f"top{top_chars}")
    if min_cooccur and min_cooccur > 1:
        parts.append(f"minco{min_cooccur}")
    return "_".join(parts) + ".json"


def parse_args():
    parser = argparse.ArgumentParser(description="Extract HPD character relationship graph data.")
    parser.add_argument("--books", nargs="+", metavar="BOOK",
                        help="Filter to specific books, e.g. --books Book1 Book2. Default: all.")
    parser.add_argument("--top-chars", type=int, default=None, metavar="N",
                        help="Keep only the top N most-appearing characters. Default: all.")
    parser.add_argument("--min-cooccur", type=int, default=1, metavar="N",
                        help="Minimum shared sessions required for an edge. Default: 1.")
    parser.add_argument("--out", default=None, metavar="FILE",
                        help="Output JSON path. Relative paths go into output/. Default: auto-named.")
    return parser.parse_args()


def main():
    args = parse_args()

    print("Loading sessions...")
    sessions = load_sessions(books_filter=args.books)
    book_label = ", ".join(sorted(args.books)) if args.books else "all books"
    print(f"  -> {len(sessions)} sessions ({book_label})")

    print("Extracting graph...")
    nodes, edges = extract(sessions, top_chars=args.top_chars, min_cooccur=args.min_cooccur)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    if args.out is None:
        out_path = os.path.join(OUTPUT_DIR, build_output_name(args.books, args.top_chars, args.min_cooccur))
    elif os.path.isabs(args.out):
        out_path = args.out
    else:
        out_path = os.path.join(OUTPUT_DIR, args.out)

    result = {
        "meta": {
            "books": args.books or "all",
            "top_chars": args.top_chars,
            "min_cooccur": args.min_cooccur,
            "sessions": len(sessions),
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

    print("\nTop 10 strongest edges:")
    for e in edges[:10]:
        label = f"[{e['relation_type']}]" if "relation_type" in e else ""
        comps = e.get("weight_components", {})
        base  = comps.get("base", 0.0)
        bonus = comps.get("bonus", 0.0)
        print(
            f"  {e['source']:15s} <-> {e['target']:15s}  "
            f"weight={e['weight']:.3f}  "
            f"(base={base:.3f} bonus={bonus:.3f})  "
            f"co_occur={e['co_occurrences']}  {label}"
        )


if __name__ == "__main__":
    main()
