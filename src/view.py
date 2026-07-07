"""
view.py
-------
Renders a Harry Potter character relationship graph from graph_data.json.

Visual encoding (matches WORK_NOTES.md § 5):
  • Node size      → appearances (log-scaled)
  • Node colour    → relation_type to Harry
                     friend=blue  enemy=red  family=green
                     teacher=purple  acquaintance=grey  Harry=gold
  • Edge thickness → weight (normalised to 0.5–6 pt)
  • Edge colour    → same relation_type palette; grey for non-Harry edges
  • Edge opacity   → co_occurrences (capped & normalised)
  • Labels         → character name

Usage
-----
  python3 view.py                                  # default: output/graph_data.json
  python3 view.py --snapshot output/graph_early.json
  python3 view.py --min-weight 3.0                 # hide weak edges
  python3 view.py --out output/my_graph.png        # custom output path
  python3 view.py --show                           # open interactive window
"""

import json
import math
import argparse
import os

import networkx as nx
import matplotlib
matplotlib.use("Agg")          # non-interactive backend (safe for all envs)
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SRC_DIR     = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SRC_DIR)
DEFAULT_IN  = os.path.join(PROJECT_DIR, "output", "hpd_graph_all_top40_minco2.json")
DEFAULT_OUT = os.path.join(PROJECT_DIR, "output", "hpd_graph_snapshot.png")

# ---------------------------------------------------------------------------
# Colour palette  (relation_type → colour)
# ---------------------------------------------------------------------------

RELATION_COLOURS = {
    "friend":           "#2171B5",   # strong blue
    "classmate":        "#4292C6",   # medium blue
    "teammate":         "#084594",   # navy blue
    "colleague":        "#6BAED6",   # sky blue
    "family":           "#238B45",   # dark green
    "immediate family": "#006D2C",   # deeper green
    "teacher":          "#6A3D9A",   # purple
    "opponent":         "#D94801",   # burnt orange
    "acquaintance":     "#969696",   # medium grey
    "enemy":            "#CB181D",   # vivid red
    "lover":            "#C51B8A",   # hot pink
}

HARRY_COLOUR        = "#E6930A"   # amber/gold (readable on white)
NON_HARRY_EDGE      = "#BBBBBB"   # light grey for non-Harry edges
DEFAULT_NODE_COLOUR = "#969696"

# Background / text colours for the light theme
BG_COLOUR    = "#FFFFFF"
FIG_COLOUR   = "#F5F5F5"   # very light grey for the figure margin
TEXT_COLOUR  = "#1A1A1A"
MUTED_COLOUR = "#666666"

# ---------------------------------------------------------------------------
# Book-period labels
# ---------------------------------------------------------------------------

PERIOD_LABELS = {
    ("Book1", "Book2"):                        "Books 1–2: Early Story",
    ("Book3", "Book4", "Book5"):               "Books 3–5: Middle Story",
    ("Book6", "Book7"):                        "Books 6–7: Late Story",
}


def period_label(books):
    """Return a human-readable period label, or fall back to the raw list."""
    if not books or books == "all":
        return "All Books"
    key = tuple(sorted(books))
    return PERIOD_LABELS.get(key, ", ".join(books))


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def load_graph(json_path):
    """Load graph_data.json and return (G, meta)."""
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    meta  = data["meta"]
    nodes = data["nodes"]
    edges = data["edges"]

    G = nx.Graph()

    for n in nodes:
        G.add_node(
            n["id"],
            appearances=n["appearances"],
            relation_type=n.get("relation_type", "acquaintance"),
            affection=n.get("affection", 0.0),
            familiarity=n.get("familiarity", 0.0),
        )

    for e in edges:
        G.add_edge(
            e["source"],
            e["target"],
            co_occurrences=e["co_occurrences"],
            weight=e["weight"],
            relation_type=e.get("relation_type"),
            affection=e.get("affection"),
            familiarity=e.get("familiarity"),
        )

    return G, meta


# ---------------------------------------------------------------------------
# Visual property helpers
# ---------------------------------------------------------------------------

def node_sizes(G, base=300, scale=2500):
    """Log-scale node sizes proportional to appearances."""
    sizes = []
    for node in G.nodes():
        app = G.nodes[node].get("appearances", 1)
        sizes.append(base + scale * math.log(app + 1) / math.log(1100))
    return sizes


def node_colours(G):
    colours = []
    for node in G.nodes():
        if node == "Harry":
            colours.append(HARRY_COLOUR)
        else:
            rt = G.nodes[node].get("relation_type", "acquaintance")
            colours.append(RELATION_COLOURS.get(rt, DEFAULT_NODE_COLOUR))
    return colours


def edge_visual(G, min_weight=0.0):
    """
    Returns (edge_list, widths, colours, alphas) for edges passing
    the min_weight threshold.
    """
    all_weights = [d["weight"] for _, _, d in G.edges(data=True)]
    max_w = max(all_weights) if all_weights else 1.0

    all_cooccur = [d["co_occurrences"] for _, _, d in G.edges(data=True)]
    max_co = max(all_cooccur) if all_cooccur else 1.0

    edge_list, widths, colours, alphas = [], [], [], []

    for u, v, d in G.edges(data=True):
        w = d["weight"]
        if w < min_weight:
            continue

        edge_list.append((u, v))

        # Width: normalise to 0.4 – 5.0 pt
        widths.append(0.4 + 4.6 * (w / max_w))

        # Colour: relation type for Harry edges, grey otherwise
        rt = d.get("relation_type")
        if rt:
            colours.append(RELATION_COLOURS.get(rt, NON_HARRY_EDGE))
        else:
            colours.append(NON_HARRY_EDGE)

        # Alpha: co-occurrences → 0.15 – 0.90
        co = d["co_occurrences"]
        alphas.append(0.15 + 0.75 * (co / max_co))

    return edge_list, widths, colours, alphas


# ---------------------------------------------------------------------------
# Legend
# ---------------------------------------------------------------------------

def build_legend():
    """Return legend handles for all relation types + Harry."""
    handles = [
        mpatches.Patch(color=HARRY_COLOUR, label="Harry (protagonist)")
    ]
    for rt, colour in RELATION_COLOURS.items():
        handles.append(mpatches.Patch(color=colour, label=rt.capitalize()))
    return handles


# ---------------------------------------------------------------------------
# Main render
# ---------------------------------------------------------------------------

def render(G, meta, out_path, min_weight=0.0, show=False):
    """Draw and save (or show) the network graph."""

    title = period_label(meta.get("books"))

    # --- Layout -----------------------------------------------------------
    # Use spring layout with a fixed seed for reproducibility.
    # weight= tells networkx to treat edge weight as attraction force.
    pos = nx.spring_layout(G, weight="weight", seed=42, k=2.5 / math.sqrt(len(G)))

    # --- Figure -----------------------------------------------------------
    fig, ax = plt.subplots(figsize=(20, 16))
    fig.patch.set_facecolor(FIG_COLOUR)
    ax.set_facecolor(BG_COLOUR)
    ax.set_axis_off()

    # --- Edges ------------------------------------------------------------
    edge_list, widths, colours, alphas = edge_visual(G, min_weight=min_weight)

    # Draw edges one at a time so each can have its own alpha
    # (draw_networkx_edges doesn't support per-edge alpha directly)
    for (u, v), lw, col, alpha in zip(edge_list, widths, colours, alphas):
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        ax.plot(
            [x0, x1], [y0, y1],
            color=col,
            linewidth=lw,
            alpha=alpha,
            solid_capstyle="round",
            zorder=1,
        )

    # --- Nodes ------------------------------------------------------------
    n_sizes  = node_sizes(G)
    n_colours = node_colours(G)

    # Draw a subtle white border ring around each node
    ring = nx.draw_networkx_nodes(
        G, pos, ax=ax,
        node_size=[s * 1.15 for s in n_sizes],
        node_color="white",
        alpha=0.25,
        linewidths=0,
    )
    ring.set_zorder(2)
    nodes_pc = nx.draw_networkx_nodes(
        G, pos, ax=ax,
        node_size=n_sizes,
        node_color=n_colours,
        linewidths=1.5,
        edgecolors="white",
        alpha=0.95,
    )
    nodes_pc.set_zorder(2)

    # --- Labels -----------------------------------------------------------
    # Scale label font size by node size so big nodes get bigger labels
    app_vals = [G.nodes[n].get("appearances", 1) for n in G.nodes()]
    max_app  = max(app_vals) if app_vals else 1

    for node, (x, y) in pos.items():
        app      = G.nodes[node].get("appearances", 1)
        fontsize = 7 + 6 * (math.log(app + 1) / math.log(max_app + 1))
        weight   = "bold" if node == "Harry" else "normal"
        colour   = "white" if node != "Harry" else HARRY_COLOUR

        ax.text(
            x, y,
            node,
            fontsize=fontsize,
            fontweight=weight,
            color=colour,
            ha="center",
            va="center",
            zorder=3,
            fontfamily="DejaVu Sans",
        )

    # --- Title & subtitle -------------------------------------------------
    ax.set_title(
        f"Harry Potter — Character Relationship Network\n{title}",
        fontsize=18,
        fontweight="bold",
        color=TEXT_COLOUR,
        pad=20,
        fontfamily="DejaVu Sans",
    )

    # Stats subtitle
    n_nodes = len(G.nodes())
    n_edges = len(edge_list)
    stats   = f"{n_nodes} characters  ·  {n_edges} relationships  ·  {meta.get('sessions', '?')} dialogue sessions"
    ax.text(
        0.5, 0.01, stats,
        transform=ax.transAxes,
        ha="center",
        fontsize=9,
        color=MUTED_COLOUR,
        fontfamily="DejaVu Sans",
    )

    # --- Legend -----------------------------------------------------------
    handles = build_legend()
    legend = ax.legend(
        handles=handles,
        loc="lower left",
        framealpha=0.85,
        facecolor="white",
        edgecolor="#CCCCCC",
        labelcolor=TEXT_COLOUR,
        fontsize=8,
        title="Relation to Harry",
        title_fontsize=9,
        ncol=2,
    )
    legend.get_title().set_color(TEXT_COLOUR)

    # --- Edge weight scale bar (small note) --------------------------------
    ax.text(
        0.01, 0.99,
        "Edge thickness = relationship strength\nEdge opacity = co-occurrence frequency",
        transform=ax.transAxes,
        va="top",
        fontsize=7.5,
        color=MUTED_COLOUR,
        fontfamily="DejaVu Sans",
    )

    plt.tight_layout()

    if show:
        matplotlib.use("TkAgg")
        plt.show()
    else:
        fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
        print(f"Saved → {out_path}")

    plt.close(fig)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Render a Harry Potter character relationship graph."
    )
    parser.add_argument(
        "--snapshot", default=DEFAULT_IN, metavar="FILE",
        help=f"Path to graph JSON. Default: {DEFAULT_IN}",
    )
    parser.add_argument(
        "--min-weight", type=float, default=0.0, metavar="W",
        help="Hide edges below this weight threshold. Default: 0 (show all).",
    )
    parser.add_argument(
        "--out", default=DEFAULT_OUT, metavar="FILE",
        help=f"Output PNG path. Default: {DEFAULT_OUT}",
    )
    parser.add_argument(
        "--show", action="store_true",
        help="Open an interactive matplotlib window instead of saving.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    print(f"Loading  : {args.snapshot}")
    G, meta = load_graph(args.snapshot)
    print(f"Graph    : {len(G.nodes())} nodes, {len(G.edges())} edges")
    print(f"Period   : {period_label(meta.get('books'))}")

    render(G, meta, out_path=args.out, min_weight=args.min_weight, show=args.show)


if __name__ == "__main__":
    main()
