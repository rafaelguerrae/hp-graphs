"""
export_gephi.py — Export a hp-graphs JSON snapshot to GEXF for Gephi.

Usage
-----
    .venv/bin/python3 src/export_gephi.py
    .venv/bin/python3 src/export_gephi.py --snapshot output/hpd_graph_Book1-Book2_top40_minco2.json
    .venv/bin/python3 src/export_gephi.py --snapshot output/hpd_graph_all_top40_minco2.json --out my_graph.gexf

The output GEXF file can be opened directly in Gephi (File → Open).

Node attributes exported
    appearances     int     total dialogue-session appearances
    affection       float   Harry ↔ character averaged affection  (-10..10), Harry edges only
    familiarity     float   Harry ↔ character averaged familiarity (0..10),  Harry edges only
    relation_type   string  dominant binary relation label

Edge attributes exported
    co_occurrences  int     raw co-occurrence count
    weight          float   composite edge weight
    weight_base     float   log(co_occurrences + 1) component
    weight_bonus    float   affection/familiarity bonus component
    affection       float   edge-level affection (Harry edges only)
    familiarity     float   edge-level familiarity (Harry edges only)
    relation_type   string  dominant binary relation label (Harry edges only)
"""

import argparse
import os
import sys

import networkx as nx

# Reuse load_graph from view.py in the same package directory
SRC_DIR     = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SRC_DIR)
OUTPUT_DIR  = os.path.join(PROJECT_DIR, "output")
DEFAULT_IN  = os.path.join(OUTPUT_DIR, "hpd_graph_all_top40_minco2.json")

sys.path.insert(0, SRC_DIR)
from view import load_graph  # noqa: E402  (import after sys.path patch)


# ---------------------------------------------------------------------------
# GEXF helpers
# ---------------------------------------------------------------------------

def _gexf_safe(value, default=None):
    """Return *value* if it is not None, else *default*."""
    return value if value is not None else default


def build_gexf_graph(G: nx.Graph) -> nx.Graph:
    """
    Return a copy of *G* with all attributes cast to types that
    nx.write_gexf() can serialise cleanly (str / int / float).
    """
    G2 = nx.Graph()

    for node, attrs in G.nodes(data=True):
        G2.add_node(
            node.strip(),
            appearances=int(_gexf_safe(attrs.get("appearances"), 0)),
            affection=float(_gexf_safe(attrs.get("affection"), 0.0)),
            familiarity=float(_gexf_safe(attrs.get("familiarity"), 0.0)),
            relation_type=str(_gexf_safe(attrs.get("relation_type"), "acquaintance")),
        )

    for u, v, attrs in G.edges(data=True):
        components = attrs.get("weight_components") or {}
        G2.add_edge(
            u.strip(), v.strip(),
            co_occurrences=int(_gexf_safe(attrs.get("co_occurrences"), 0)),
            weight=float(_gexf_safe(attrs.get("weight"), 0.0)),
            weight_base=float(_gexf_safe(components.get("base"), 0.0)),
            weight_bonus=float(_gexf_safe(components.get("bonus"), 0.0)),
            affection=float(_gexf_safe(attrs.get("affection"), 0.0)),
            familiarity=float(_gexf_safe(attrs.get("familiarity"), 0.0)),
            relation_type=str(_gexf_safe(attrs.get("relation_type"), "")),
        )

    return G2


# ---------------------------------------------------------------------------
# Output path helpers
# ---------------------------------------------------------------------------

def default_out_path(snapshot_path: str) -> str:
    """Derive a .gexf path from the snapshot .json path (same dir, same stem)."""
    base = os.path.splitext(snapshot_path)[0]
    return base + ".gexf"


def resolve_out(out_arg: str | None, snapshot_path: str) -> str:
    if out_arg is None:
        return default_out_path(snapshot_path)
    if os.path.isabs(out_arg):
        return out_arg
    return os.path.join(OUTPUT_DIR, out_arg)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Convert an hp-graphs JSON snapshot to GEXF format for Gephi.\n\n"
            "The output file is placed next to the input JSON by default."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--snapshot", default=DEFAULT_IN, metavar="FILE",
        help=f"Path to graph JSON. Default: {DEFAULT_IN}",
    )
    parser.add_argument(
        "--out", default=None, metavar="FILE",
        help=(
            "Output GEXF path. Relative paths go into output/. "
            "Default: same name as snapshot with .gexf extension."
        ),
    )
    return parser.parse_args()


def main():
    args = parse_args()

    snapshot = args.snapshot if os.path.isabs(args.snapshot) \
        else os.path.abspath(args.snapshot)

    if not os.path.exists(snapshot):
        print(f"Error: snapshot not found: {snapshot}", file=sys.stderr)
        print("Run `make extract` first to generate graph JSON files.", file=sys.stderr)
        sys.exit(1)

    out_path = resolve_out(args.out, snapshot)

    print(f"Loading  : {snapshot}")
    G, meta = load_graph(snapshot)
    print(f"Graph    : {len(G.nodes())} nodes, {len(G.edges())} edges")

    print("Building GEXF graph...")
    G_gexf = build_gexf_graph(G)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    nx.write_gexf(G_gexf, out_path, version="1.3")

    print(f"\nDone!")
    print(f"  Output : {out_path}")
    print()
    print("Next steps in Gephi:")
    print("  1. File → Open → select the .gexf file")
    print("  2. Run a layout (e.g. ForceAtlas2) to position nodes")
    print("  3. Use 'Appearance' panel → Nodes → Size → 'appearances' attribute")
    print("  4. Use 'Appearance' panel → Edges → Color → 'relation_type' attribute")
    print("  5. Use 'Data Laboratory' to inspect all attributes")


if __name__ == "__main__":
    main()
