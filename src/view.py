import json
import math
import argparse
import os

import networkx as nx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SRC_DIR)
DEFAULT_IN = os.path.join(PROJECT_DIR, "output", "hpd_graph_all_top40_minco2.json")
DEFAULT_OUT = os.path.join(PROJECT_DIR, "output", "hpd_graph_snapshot.png")

RELATION_COLOURS = {
    "friend":           "#2171B5",
    "classmate":        "#4292C6",
    "teammate":         "#084594",
    "colleague":        "#6BAED6",
    "family":           "#238B45",
    "immediate family": "#006D2C",
    "teacher":          "#6A3D9A",
    "opponent":         "#D94801",
    "acquaintance":     "#969696",
    "enemy":            "#CB181D",
    "lover":            "#C51B8A",
}

HARRY_COLOUR = "#E6930A"
NON_HARRY_EDGE = "#BBBBBB"
DEFAULT_NODE_COLOUR = "#969696"
BG_COLOUR = "#FFFFFF"
FIG_COLOUR = "#F5F5F5"
TEXT_COLOUR = "#1A1A1A"
MUTED_COLOUR = "#666666"

PERIOD_LABELS = {
    ("Book1", "Book2"):                  "Books 1–2: Early Story",
    ("Book3", "Book4", "Book5"):         "Books 3–5: Middle Story",
    ("Book6", "Book7"):                  "Books 6–7: Late Story",
}


def period_label(books):
    if not books or books == "all":
        return "All Books"
    return PERIOD_LABELS.get(tuple(sorted(books)), ", ".join(books))


def load_graph(json_path):
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    G = nx.Graph()
    for n in data["nodes"]:
        G.add_node(
            n["id"],
            appearances=n["appearances"],
            relation_type=n.get("relation_type", "acquaintance"),
            affection=n.get("affection", 0.0),
            familiarity=n.get("familiarity", 0.0),
        )
    for e in data["edges"]:
        G.add_edge(
            e["source"], e["target"],
            co_occurrences=e["co_occurrences"],
            weight=e["weight"],
            relation_type=e.get("relation_type"),
            affection=e.get("affection"),
            familiarity=e.get("familiarity"),
        )
    return G, data["meta"]


def node_sizes(G, base=300, scale=2500):
    return [
        base + scale * math.log(G.nodes[n].get("appearances", 1) + 1) / math.log(1100)
        for n in G.nodes()
    ]


def node_colours(G):
    return [
        HARRY_COLOUR if n == "Harry"
        else RELATION_COLOURS.get(G.nodes[n].get("relation_type", "acquaintance"), DEFAULT_NODE_COLOUR)
        for n in G.nodes()
    ]


def edge_visual(G, min_weight=0.0):
    all_weights = [d["weight"] for _, _, d in G.edges(data=True)]
    all_cooccur = [d["co_occurrences"] for _, _, d in G.edges(data=True)]
    max_w = max(all_weights) if all_weights else 1.0
    max_co = max(all_cooccur) if all_cooccur else 1.0

    edge_list, widths, colours, alphas = [], [], [], []
    for u, v, d in G.edges(data=True):
        if d["weight"] < min_weight:
            continue
        edge_list.append((u, v))
        widths.append(0.4 + 4.6 * (d["weight"] / max_w))
        rt = d.get("relation_type")
        colours.append(RELATION_COLOURS.get(rt, NON_HARRY_EDGE) if rt else NON_HARRY_EDGE)
        alphas.append(0.15 + 0.75 * (d["co_occurrences"] / max_co))

    return edge_list, widths, colours, alphas


def build_legend():
    handles = [mpatches.Patch(color=HARRY_COLOUR, label="Harry (protagonist)")]
    for rt, colour in RELATION_COLOURS.items():
        handles.append(mpatches.Patch(color=colour, label=rt.capitalize()))
    return handles


def render(G, meta, out_path, min_weight=0.0, show=False):
    title = period_label(meta.get("books"))
    pos = nx.spring_layout(G, weight="weight", seed=42, k=2.5 / math.sqrt(len(G)))

    fig, ax = plt.subplots(figsize=(20, 16))
    fig.patch.set_facecolor(FIG_COLOUR)
    ax.set_facecolor(BG_COLOUR)
    ax.set_axis_off()

    edge_list, widths, colours, alphas = edge_visual(G, min_weight=min_weight)
    for (u, v), lw, col, alpha in zip(edge_list, widths, colours, alphas):
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        ax.plot([x0, x1], [y0, y1], color=col, linewidth=lw, alpha=alpha,
                solid_capstyle="round", zorder=1)

    n_sizes = node_sizes(G)
    n_colours = node_colours(G)

    ring = nx.draw_networkx_nodes(G, pos, ax=ax, node_size=[s * 1.15 for s in n_sizes],
                                  node_color="white", alpha=0.25, linewidths=0)
    ring.set_zorder(2)
    nodes_pc = nx.draw_networkx_nodes(G, pos, ax=ax, node_size=n_sizes, node_color=n_colours,
                                      linewidths=1.5, edgecolors="white", alpha=0.95)
    nodes_pc.set_zorder(2)

    app_vals = [G.nodes[n].get("appearances", 1) for n in G.nodes()]
    max_app = max(app_vals) if app_vals else 1
    for node, (x, y) in pos.items():
        app = G.nodes[node].get("appearances", 1)
        fontsize = 7 + 6 * (math.log(app + 1) / math.log(max_app + 1))
        ax.text(x, y, node,
                fontsize=fontsize,
                fontweight="bold" if node == "Harry" else "normal",
                color=HARRY_COLOUR if node == "Harry" else TEXT_COLOUR,
                ha="center", va="center", zorder=3, fontfamily="DejaVu Sans")

    ax.set_title(
        f"Harry Potter — Character Relationship Network\n{title}",
        fontsize=18, fontweight="bold", color=TEXT_COLOUR, pad=20, fontfamily="DejaVu Sans",
    )

    n_nodes = len(G.nodes())
    n_edges = len(edge_list)
    stats = f"{n_nodes} characters  ·  {n_edges} relationships  ·  {meta.get('sessions', '?')} dialogue sessions"
    ax.text(0.5, 0.01, stats, transform=ax.transAxes, ha="center",
            fontsize=9, color=MUTED_COLOUR, fontfamily="DejaVu Sans")

    legend = ax.legend(
        handles=build_legend(), loc="lower left",
        framealpha=0.85, facecolor="white", edgecolor="#CCCCCC",
        labelcolor=TEXT_COLOUR, fontsize=8,
        title="Relation to Harry", title_fontsize=9, ncol=2,
    )
    legend.get_title().set_color(TEXT_COLOUR)

    ax.text(0.01, 0.99,
            "Edge thickness = relationship strength\nEdge opacity = co-occurrence frequency",
            transform=ax.transAxes, va="top", fontsize=7.5,
            color=MUTED_COLOUR, fontfamily="DejaVu Sans")

    plt.tight_layout()
    if show:
        matplotlib.use("TkAgg")
        plt.show()
    else:
        fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
        print(f"Saved → {out_path}")
    plt.close(fig)


def parse_args():
    parser = argparse.ArgumentParser(description="Render a Harry Potter character relationship graph.")
    parser.add_argument("--snapshot", default=DEFAULT_IN, metavar="FILE",
                        help=f"Path to graph JSON. Default: {DEFAULT_IN}")
    parser.add_argument("--min-weight", type=float, default=0.0, metavar="W",
                        help="Hide edges below this weight. Default: 0.")
    parser.add_argument("--out", default=DEFAULT_OUT, metavar="FILE",
                        help=f"Output PNG path. Default: {DEFAULT_OUT}")
    parser.add_argument("--show", action="store_true",
                        help="Open an interactive window instead of saving.")
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
