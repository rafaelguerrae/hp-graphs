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
    "friend":           "#1D4ED8",
    "classmate":        "#0369A1",
    "teammate":         "#4338CA",
    "colleague":        "#0F766E",
    "family":           "#15803D",
    "immediate family": "#166534",
    "teacher":          "#7E22CE",
    "opponent":         "#C2410C",
    "acquaintance":     "#475569",
    "enemy":            "#B91C1C",
    "lover":            "#BE185D",
}

HARRY_COLOUR        = "#D97706"
NON_HARRY_EDGE      = "#CBD5E1"
DEFAULT_NODE_COLOUR = "#64748B"
BG_COLOUR           = "#FFFFFF"
FIG_COLOUR          = "#F1F5F9"
TEXT_COLOUR         = "#1E293B"
MUTED_COLOUR        = "#64748B"

RELATION_ORDER = [
    "friend", "classmate", "teammate", "colleague", "lover",
    "family", "immediate family", "teacher",
    "opponent", "acquaintance", "enemy",
]

PERIOD_LABELS = {
    ("Book1", "Book2"):              "Books 1–2: Early Story",
    ("Book3", "Book4", "Book5"):     "Books 3–5: Middle Story",
    ("Book6", "Book7"):              "Books 6–7: Late Story",
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


def radial_layout(G, center="Harry"):
    """
    Radial layout with `center` at the origin.

    - Inner ring (r = 0.55): nodes directly connected to `center`, arranged
      clockwise grouped by relation type, then sorted by descending edge weight
      within each group.
    - Outer ring (r = 1.05): all remaining nodes, evenly spaced.

    Produces a clean, spoke-and-wheel structure that eliminates the spring-
    layout hairball that forms with dense graphs.
    """
    pos = {center: (0.0, 0.0)}

    # Collect center's neighbors
    connected = []
    for n in G.neighbors(center):
        w = G[center][n].get("weight", 0.0)
        rt = (G[center][n].get("relation_type")
              or G.nodes[n].get("relation_type", "acquaintance"))
        connected.append((n, w, rt))

    def _sort_key(item):
        _, w, rt = item
        group = RELATION_ORDER.index(rt) if rt in RELATION_ORDER else len(RELATION_ORDER)
        return (group, -w)

    connected.sort(key=_sort_key)
    inner_nodes = [n for n, _, _ in connected]
    outer_nodes = [n for n in G.nodes() if n != center and n not in inner_nodes]

    # Place inner ring, starting from the top (−π/2) going clockwise
    if inner_nodes:
        n_in = len(inner_nodes)
        for i, n in enumerate(inner_nodes):
            angle = 2 * math.pi * i / n_in - math.pi / 2
            pos[n] = (0.55 * math.cos(angle), 0.55 * math.sin(angle))

    # Place outer ring
    if outer_nodes:
        n_out = len(outer_nodes)
        for i, n in enumerate(outer_nodes):
            angle = 2 * math.pi * i / n_out - math.pi / 2
            pos[n] = (1.05 * math.cos(angle), 1.05 * math.sin(angle))

    return pos

def node_sizes(G, base=180, scale=1800):
    """Log-scaled node sizes; capped so Harry isn't overwhelming."""
    return [
        base + scale * math.log(G.nodes[n].get("appearances", 1) + 1) / math.log(1100)
        for n in G.nodes()
    ]


def node_colours(G):
    return [
        HARRY_COLOUR if n == "Harry"
        else RELATION_COLOURS.get(
            G.nodes[n].get("relation_type", "acquaintance"), DEFAULT_NODE_COLOUR
        )
        for n in G.nodes()
    ]


def edge_visuals(G, min_weight=0.0):
    harry_weights = [
        d["weight"] for u, v, d in G.edges(data=True)
        if "Harry" in (u, v) and d["weight"] >= min_weight
    ]
    all_weights = [
        d["weight"] for _, _, d in G.edges(data=True)
        if d["weight"] >= min_weight
    ]
    max_hw = max(harry_weights) if harry_weights else 1.0
    max_aw = max(all_weights) if all_weights else 1.0

    harry_edges, harry_widths, harry_colours = [], [], []
    other_edges, other_widths = [], []

    for u, v, d in G.edges(data=True):
        if d["weight"] < min_weight:
            continue
        if "Harry" in (u, v):
            harry_edges.append((u, v))
            harry_widths.append(0.8 + 5.2 * (d["weight"] / max_hw))
            rt = d.get("relation_type")
            harry_colours.append(RELATION_COLOURS.get(rt, NON_HARRY_EDGE))
        else:
            other_edges.append((u, v))
            other_widths.append(0.3 + 1.0 * (d["weight"] / max_aw))

    return (harry_edges, harry_widths, harry_colours), (other_edges, other_widths)


def top_harry_edges(G, n=8, min_weight=0.0):
    """Return the n strongest Harry edges, for weight label annotation."""
    edges = [
        (u, v, d) for u, v, d in G.edges(data=True)
        if "Harry" in (u, v) and d["weight"] >= min_weight
    ]
    edges.sort(key=lambda x: -x[2]["weight"])
    return edges[:n]


def build_legend():
    handles = [mpatches.Patch(color=HARRY_COLOUR, label="Harry (protagonist)")]
    for rt, colour in RELATION_COLOURS.items():
        handles.append(mpatches.Patch(color=colour, label=rt.capitalize()))
    return handles

def render(G, meta, out_path, min_weight=0.0, show=False, label_top=8):
    title = period_label(meta.get("books"))
    center = "Harry" if "Harry" in G else list(G.nodes())[0]

    pos = radial_layout(G, center=center)

    fig, ax = plt.subplots(figsize=(22, 18))
    fig.patch.set_facecolor(FIG_COLOUR)
    ax.set_facecolor(BG_COLOUR)
    ax.set_axis_off()

    for r, alpha in [(0.55, 0.12), (1.05, 0.08)]:
        circle = plt.Circle(
            (0, 0), r, color="#94A3B8", fill=False,
            linewidth=0.8, alpha=alpha, linestyle="--", zorder=0,
        )
        ax.add_patch(circle)

    (harry_edges, harry_widths, harry_colours), (other_edges, other_widths) = \
        edge_visuals(G, min_weight)

    for (u, v), lw in zip(other_edges, other_widths):
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        ax.plot([x0, x1], [y0, y1],
                color=NON_HARRY_EDGE, linewidth=lw, alpha=0.55,
                solid_capstyle="round", zorder=1)

    for (u, v), lw, col in zip(harry_edges, harry_widths, harry_colours):
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        ax.plot([x0, x1], [y0, y1],
                color=col, linewidth=lw, alpha=0.82,
                solid_capstyle="round", zorder=2)

    n_sizes   = node_sizes(G)
    n_colours = node_colours(G)
    nodes_list = list(G.nodes())

    if center in G:
        harry_idx   = nodes_list.index(center)
        harry_sz    = n_sizes[harry_idx]
        glow = nx.draw_networkx_nodes(
            G, pos, ax=ax,
            nodelist=[center],
            node_size=[harry_sz * 2.6],
            node_color=HARRY_COLOUR, alpha=0.20, linewidths=0,
        )
        glow.set_zorder(3)

    nodes_pc = nx.draw_networkx_nodes(
        G, pos, ax=ax,
        node_size=n_sizes, node_color=n_colours,
        linewidths=1.5, edgecolors="white", alpha=0.95,
    )
    nodes_pc.set_zorder(4)

    app_vals = [G.nodes[n].get("appearances", 1) for n in G.nodes()]
    max_app  = max(app_vals) if app_vals else 1
    for node, (x, y) in pos.items():
        app      = G.nodes[node].get("appearances", 1)
        fontsize = 6.5 + 5.5 * (math.log(app + 1) / math.log(max_app + 1))
        is_center = node == center
        ax.text(
            x, y, node,
            fontsize=fontsize,
            fontweight="bold" if is_center else "normal",
            color=HARRY_COLOUR if is_center else TEXT_COLOUR,
            ha="center", va="center",
            zorder=5, fontfamily="DejaVu Sans",
            bbox=dict(boxstyle="round,pad=0.18", fc="white", ec="none", alpha=0.7)
            if not is_center else None,
        )

    # ── Weight + relation-type annotations on top-N Harry edges ─────────────
    # Each label shows: weight number on top, short relation tag below.
    # Pill background is white with a coloured border matching the edge colour.
    RELATION_SHORT = {
        "friend": "friend", "classmate": "class", "teammate": "team",
        "colleague": "colleg", "family": "family", "immediate family": "imm.fam",
        "teacher": "teacher", "opponent": "opp", "acquaintance": "acq",
        "enemy": "enemy", "lover": "lover",
    }
    for u, v, d in top_harry_edges(G, n=label_top, min_weight=min_weight):
        mx = (pos[u][0] + pos[v][0]) / 2
        my = (pos[u][1] + pos[v][1]) / 2
        rt   = d.get("relation_type") or "—"
        col  = RELATION_COLOURS.get(rt, MUTED_COLOUR)
        tag  = RELATION_SHORT.get(rt, rt)
        text = f"{d['weight']:.1f}\n{tag}"
        ax.text(
            mx, my, text,
            fontsize=8, color=col, alpha=1.0,
            ha="center", va="center", zorder=6,
            fontweight="bold",
            fontfamily="DejaVu Sans",
            bbox=dict(
                boxstyle="round,pad=0.30",
                fc="white", ec=col,
                linewidth=1.2, alpha=0.92,
            ),
        )

    # ── Title ─────────────────────────────────────────────────────────────────
    ax.set_title(
        f"Harry Potter — Character Relationship Network\n{title}",
        fontsize=20, fontweight="bold", color=TEXT_COLOUR, pad=22,
        fontfamily="DejaVu Sans",
    )

    # ── Stats footer ──────────────────────────────────────────────────────────
    n_nodes = len(G.nodes())
    n_shown = len(harry_edges) + len(other_edges)
    n_total = len(G.edges())
    stats = (
        f"{n_nodes} characters  ·  {n_shown}/{n_total} relationships shown"
        f"  (min weight ≥ {min_weight:.1f})  ·  {meta.get('sessions', '?')} dialogue sessions"
    )
    ax.text(0.5, 0.01, stats, transform=ax.transAxes, ha="center",
            fontsize=9, color=MUTED_COLOUR, fontfamily="DejaVu Sans")

    # ── Legend ────────────────────────────────────────────────────────────────
    legend = ax.legend(
        handles=build_legend(), loc="lower left",
        framealpha=0.92, facecolor="white", edgecolor="#CBD5E1",
        labelcolor=TEXT_COLOUR, fontsize=8,
        title="Relation to Harry", title_fontsize=9, ncol=2,
    )
    legend.get_title().set_color(TEXT_COLOUR)

    # ── Key (top-left) ────────────────────────────────────────────────────────
    ax.text(
        0.01, 0.99,
        "Edge thickness  =  relationship weight\n"
        "Coloured edges  =  Harry's direct relationships\n"
        "Grey edges        =  secondary character relationships\n"
        "Labels             =  weight score + relation type\n"
        "Inner ring        =  Harry's direct contacts\n"
        "Outer ring        =  peripheral characters",
        transform=ax.transAxes, va="top", fontsize=7.5,
        color=MUTED_COLOUR, fontfamily="DejaVu Sans",
        bbox=dict(boxstyle="round,pad=0.4", fc="white", ec="#E2E8F0", alpha=0.85),
    )

    plt.tight_layout()

    if show:
        matplotlib.use("TkAgg")
        plt.show()
    else:
        fig.savefig(out_path, dpi=200, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        print(f"Saved → {out_path}")
    plt.close(fig)


# ── CLI ───────────────────────────────────────────────────────────────────────

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
        help=(
            "Hide edges below this weight. "
            "Tip: use 2.0–3.0 on all-books graphs to cut visual noise. "
            "Default: 0 (show all)."
        ),
    )
    parser.add_argument(
        "--label-top", type=int, default=8, metavar="N",
        help="Annotate the top N Harry edges with their numeric weight. Default: 8.",
    )
    parser.add_argument(
        "--out", default=DEFAULT_OUT, metavar="FILE",
        help=f"Output PNG path. Default: {DEFAULT_OUT}",
    )
    parser.add_argument(
        "--show", action="store_true",
        help="Open an interactive window instead of saving to file.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    print(f"Loading  : {args.snapshot}")
    G, meta = load_graph(args.snapshot)
    print(f"Graph    : {len(G.nodes())} nodes, {len(G.edges())} edges")
    print(f"Period   : {period_label(meta.get('books'))}")
    render(
        G, meta,
        out_path=args.out,
        min_weight=args.min_weight,
        show=args.show,
        label_top=args.label_top,
    )


if __name__ == "__main__":
    main()
