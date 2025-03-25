# Code adapted from node-arrange (GPLv3) by Leonardo Pike-Excell
# https://github.com/Leonardo-Pike-Excell/node-arrange

# http://dx.doi.org/10.1007/3-540-45848-4_3
# https://arxiv.org/abs/2008.01252

from __future__ import annotations

from collections import defaultdict
from collections.abc import Collection, Hashable
from itertools import chain, pairwise
from math import ceil, floor, inf
from statistics import fmean
from typing import cast

import networkx as nx

from .. import config
from ..arrange_utils import group_by
from ..graph import GNode


def should_ensure_alignment(G: nx.DiGraph[GNode], u: GNode) -> bool:
    if u.is_reroute:
        return any(z.is_reroute for z in G.pred[u])

    # Not in original paper
    return G.in_degree[u] == 1 and G.out_degree[u] < 2


def marked_conflicts(G: nx.DiGraph[GNode]) -> set[frozenset[GNode]]:
    marked_edges = set()
    for col1, col2 in pairwise(reversed(G.graph['columns'][1:-1])):
        k_0 = 0
        l = 0
        for l_1, u in enumerate(col2):
            if should_ensure_alignment(G, u):
                upper_nbr = next(iter(G.pred[u]))
                k_1 = upper_nbr.col.index(upper_nbr)
            elif u == col2[-1]:
                k_1 = len(col1) - 1
            else:
                continue

            while l <= l_1:
                v = col2[l]
                for pred in G.pred[v]:
                    k = pred.col.index(pred)
                    if k < k_0 or k > k_1:
                        marked_edges.add(frozenset((pred, v)))

                l += 1

            k_0 = k_1

    return marked_edges


def horizontal_alignment(
  G: nx.DiGraph[GNode],
  marked_edges: Collection[frozenset[GNode]],
) -> None:
    for col in G.graph['columns']:
        prev_i = -1
        for v in col:
            predecessors = sorted(G.pred[v], key=lambda u: u.col.index(u))
            m = (len(predecessors) - 1) / 2
            for u in predecessors[floor(m):ceil(m) + 1]:
                i = u.col.index(u)

                if v.aligned != v or {u, v} in marked_edges or prev_i >= i:
                    continue

                u.aligned = v
                v.root = u.root
                v.aligned = v.root
                prev_i = i


def precompute_cells(G: nx.DiGraph[Hashable]) -> None:
    columns = G.graph['columns']
    blocks = group_by(chain(*columns), key=lambda v: v.root)
    for block, root in blocks.items():
        indicies = [columns.index(v.col) for v in block]
        root.cells = (indicies, [v.height for v in block])


def min_separation(u: GNode, v: GNode, is_up: bool) -> float:
    if is_up:
        u, v = v, u

    assert u.root.cells
    indicies = u.root.cells[0]
    heights = [h for i, h in zip(*v.root.cells) if indicies[0] <= i <= indicies[-1]]
    return max(heights, default=0) + config.MARGIN.y


def place_block(v: GNode, is_up: bool) -> None:
    if cast(float | None, v.y) is not None:
        return

    v.y = 0
    w = v
    while True:
        if (i := w.col.index(w)) > 0:
            u = w.col[i - 1].root
            place_block(u, is_up)

            if v.sink == v:
                v.sink = u.sink

            if v.sink == u.sink:
                v.y = max(v.y, u.y + min_separation(u, v, is_up))

        w = w.aligned
        if w == v:
            break

    while w.aligned != v:
        w = w.aligned
        w.y = v.y
        w.sink = v.sink


def vertical_compaction(G: nx.DiGraph[GNode], is_up: bool) -> None:
    for v in G:
        if v.root == v:
            place_block(v, is_up)

    columns = G.graph['columns']
    neighborings = defaultdict(set)

    for col in columns:
        for v, u in pairwise(reversed(col)):
            if u.sink != v.sink:
                neighborings[tuple(v.sink.col)].add((u, v))

    for col in columns:
        if col[0].sink.shift == inf:
            col[0].sink.shift = 0

        for u, v in neighborings[tuple(col)]:
            y = v.y - (u.y + min_separation(u, v, is_up))
            u.sink.shift = min(u.sink.shift, v.sink.shift + y)

    for v in G:
        v.y += v.sink.shift


def balance(layouts: list[list[float]]) -> None:
    smallest_layout = min(layouts, key=lambda a: max(a) - min(a))

    movement = min(smallest_layout)
    for i in range(len(smallest_layout)):
        smallest_layout[i] -= movement

    for i, layout in enumerate(layouts):
        if layout == smallest_layout:
            continue

        func = min if i % 2 != 1 else max
        movement = func(smallest_layout) - func(layout)
        for j in range(len(layout)):
            layout[j] += movement


def bk_assign_y_coords(G: nx.DiGraph[GNode]) -> None:
    columns = G.graph['columns']
    for col in columns:
        col.reverse()

    marked_edges = marked_conflicts(G)
    layouts = []
    for dir_x in (-1, 1):
        G = nx.reverse_view(G)  # type: ignore
        columns.reverse()
        for dir_y in (-1, 1):
            horizontal_alignment(G, marked_edges)
            precompute_cells(G)  # type: ignore
            vertical_compaction(G, dir_y == 1)
            layouts.append([v.y * -dir_y for v in G])

            for v in G:
                v.reset()

            for col in columns:
                col.reverse()

    for col in columns:
        col.reverse()

    # if not config.SETTINGS.balance:
    #     for v, y in zip(G, layouts[1]):
    #         v.y = y
    #     return

    balance(layouts)
    for i, v in enumerate(G):
        values = [l[i] for l in layouts]
        values.sort()
        v.y = fmean(values[1:3])
