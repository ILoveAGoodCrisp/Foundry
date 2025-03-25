# Code adapted from node-arrange (GPLv3) by Leonardo Pike-Excell
# https://github.com/Leonardo-Pike-Excell/node-arrange

# https://link.springer.com/chapter/10.1007/3-540-36151-0_26
# https://doi.org/10.1016/j.jvlc.2013.11.005
# https://doi.org/10.1007/978-3-642-11805-0_14
# https://link.springer.com/chapter/10.1007/978-3-540-31843-9_22
# https://doi.org/10.7155/jgaa.00088

from __future__ import annotations

import random
from collections import defaultdict
from collections.abc import Callable, Collection, Iterator, Sequence
from dataclasses import dataclass, field, replace
from functools import cache
from itertools import chain, pairwise
from math import inf
from typing import TypeAlias, cast

import networkx as nx

from .graph import Cluster, GNode, GType, Socket

# -------------------------------------------------------------------

_MixedGraph: TypeAlias = 'nx.DiGraph[GNode | Cluster]'


def get_col_nesting_trees(
  columns: Sequence[Collection[GNode]],
  T: _MixedGraph,
) -> list[_MixedGraph]:
    trees = []
    for col in columns:
        LT = nx.DiGraph()
        nodes = set(chain(col, *[nx.ancestors(T, v) for v in col]))
        LT.add_edges_from([(u, v) for u in nodes for v in T[u] if v in nodes])
        trees.append(LT)

    return trees


@cache
def reflexive_transitive_closure(LT: _MixedGraph) -> _MixedGraph:
    return cast(_MixedGraph, nx.transitive_closure(LT, reflexive=True))


@cache
def topologically_sorted_clusters(LT: _MixedGraph) -> list[Cluster]:
    return [h for h in nx.topological_sort(LT) if h.type == GType.CLUSTER]


@dataclass(slots=True)
class _ClusterCrossingsData:
    graph: nx.MultiDiGraph[GNode | Cluster]
    reduced_free_col: list[GNode | Cluster]

    fixed_sockets: dict[GNode, list[Socket]] = field(default_factory=dict)
    free_sockets: dict[GNode | Cluster, list[Socket]] = field(default_factory=dict)
    constrained_clusters: list[Cluster] = field(default_factory=list)

    N: list[Socket] = field(default_factory=list)
    S: list[Socket] = field(default_factory=list)
    bipartite_edges: list[tuple[Socket, Socket, int]] = field(default_factory=list)


def get_crossing_reduction_graph(
  h: Cluster,
  LT: _MixedGraph,
  G: nx.MultiDiGraph[GNode],
) -> nx.MultiDiGraph[GNode | Cluster]:
    G_h = nx.MultiDiGraph()
    G_h.add_nodes_from(LT[h])
    TC = reflexive_transitive_closure(LT)
    for s, t, k, d in G.in_edges(TC[h], data=True, keys=True):  # type: ignore
        c = next(c for c in TC.pred[t] if c in LT[h])

        input_k = 'to_socket'
        output_k = 'from_socket'
        if d[output_k].owner != s:
            input_k, output_k = output_k, input_k

        if (s, c, k) in G_h.edges and G_h.edges[s, c, k][output_k] == d[output_k]:
            G_h.edges[s, c, k]['weight'] += 1
            continue

        to_socket = d[input_k] if c.type != GType.CLUSTER else replace(d[input_k], owner=c, idx=0)
        G_h.add_edge(s, c, weight=1, from_socket=d[output_k], to_socket=to_socket)

    return G_h


def add_bipartite_edges(H: _ClusterCrossingsData) -> None:
    B = nx.DiGraph()
    edges = [(d['from_socket'], d['to_socket'], d) for *_, d in H.graph.edges.data()]
    B.add_edges_from(edges)

    if B.edges:
        N, S = map(set, zip(*B.edges))
        if len(S) > len(N):
            N, S = S, N
            B = nx.reverse_view(B)

        H.N.extend(sorted(N, key=lambda d: d.idx))
        H.S.extend(sorted(S, key=lambda d: d.idx))

    H.bipartite_edges.extend(B.edges.data('weight'))


def crossing_reduction_data(
  G: nx.MultiDiGraph[GNode],
  trees: Sequence[_MixedGraph],
  backwards: bool = False,
) -> Iterator[list[_ClusterCrossingsData]]:
    for i, LT in enumerate(trees[1:], 1):
        prev_clusters = cast(set[Cluster], set(trees[i - 1]) - G.nodes)
        data = []
        for h in topologically_sorted_clusters(LT):
            G_h = get_crossing_reduction_graph(h, LT, G)
            H = _ClusterCrossingsData(G_h, list(LT[h]))

            u: GNode
            for u in chain(*[G_h.pred[v] for v in LT[h]]):  # pyright: ignore[reportAssignmentType]
                sockets = {e[2] for e in G_h.out_edges(u, data='from_socket')}
                H.fixed_sockets[u] = sorted(sockets, key=lambda d: d.idx, reverse=not backwards)

            for v in LT[h]:
                H.free_sockets[v] = [e[2] for e in G_h.in_edges(v, data='from_socket')]

            H.constrained_clusters.extend([v for v in H.reduced_free_col if v in prev_clusters])
            add_bipartite_edges(H)

            data.append(H)

        yield data


# -------------------------------------------------------------------

_FreeColumns = list[tuple[list[GNode], _MixedGraph, list[_ClusterCrossingsData]]]
_RANDOM_AMOUNT = 0.07


def calc_socket_ranks(H: _ClusterCrossingsData, is_forwards: bool) -> None:
    for v, sockets in H.fixed_sockets.items():
        incr = 1 / (len(sockets) + 1)
        rank = v.col.index(v) + 1
        if is_forwards:
            incr = -incr

        for socket in sockets:
            rank += incr
            v.cr.socket_ranks[socket] = rank


def calc_barycenters(H: _ClusterCrossingsData) -> None:
    for w in H.reduced_free_col:
        sockets = H.free_sockets[w]

        if not sockets:
            continue

        weight = sum([s.owner.cr.socket_ranks[s] for s in sockets])
        weight += random.uniform(0, 1) * _RANDOM_AMOUNT - _RANDOM_AMOUNT / 2
        w.cr.barycenter = weight / len(sockets)


def get_barycenter(v: GNode | Cluster) -> float:
    barycenter = v.cr.barycenter
    assert barycenter is not None
    return barycenter


def fill_in_unknown_barycenters(col: list[GNode | Cluster], is_first_iter: bool) -> None:
    if is_first_iter:
        max_b = max([b for v in col if (b := v.cr.barycenter) is not None], default=0) + 2
        for v in col:
            if v.cr.barycenter is None:
                v.cr.barycenter = random.uniform(0, 1) * max_b - 1
        return

    for i, v in enumerate(col):
        if v.cr.barycenter is not None:
            continue

        prev_b = get_barycenter(col[i - 1]) if i != 0 else 0
        next_b = next((b for w in col[i + 1:] if (b := w.cr.barycenter) is not None), prev_b + 1)
        v.cr.barycenter = (prev_b + next_b) / 2


def find_violated_constraint(GC: _MixedGraph) -> tuple[GNode | Cluster, GNode | Cluster] | None:
    active = [v for v in GC if GC[v] and not GC.pred[v]]
    incoming_constraints = defaultdict(list)
    while active:
        v = active.pop(0)

        for c in incoming_constraints[v]:
            if c[0].cr.barycenter >= v.cr.barycenter:
                return c

        for t in GC[v]:
            incoming_constraints[t].insert(0, (v, t))
            if len(incoming_constraints[t]) == GC.in_degree[t]:
                active.append(t)

    return None


def handle_constraints(H: _ClusterCrossingsData) -> None:

    # Optimization: don't pass constraints to `nx.DiGraph` constructor
    GC = nx.DiGraph()
    GC.add_edges_from(pairwise(H.constrained_clusters))

    unconstrained = set(H.reduced_free_col) - GC.nodes
    L = {v: [v] for v in H.reduced_free_col}

    deg = {v: H.graph.degree[v] for v in GC}
    while c := find_violated_constraint(GC):
        v_c = GNode(type=GType.DUMMY)
        s, t = c

        deg[v_c] = deg[s] + deg[t]
        assert s.cr.barycenter and t.cr.barycenter
        if deg[v_c] > 0:
            v_c.cr.barycenter = (s.cr.barycenter * deg[s] + t.cr.barycenter * deg[t]) / deg[v_c]
        else:
            v_c.cr.barycenter = (s.cr.barycenter + t.cr.barycenter) / 2

        L[v_c] = L[s] + L[t]

        nx.relabel_nodes(GC, {s: v_c, t: v_c}, copy=False)
        if (v_c, v_c) in GC.edges:
            GC.remove_edge(v_c, v_c)

        if v_c not in GC:
            unconstrained.add(v_c)

    groups = sorted(unconstrained | GC.nodes, key=get_barycenter)
    for i, v in enumerate(chain(*[L[v] for v in groups])):
        v.cr.barycenter = i


def get_cross_count(H: _ClusterCrossingsData) -> int:
    edges = H.bipartite_edges

    if not edges:
        return 0

    reduced_free_col = set(H.reduced_free_col)

    def pos(w: Socket) -> float:
        v = w.owner
        return v.cr.barycenter if v in reduced_free_col else v.col.index(v)  # type: ignore

    H.N.sort(key=pos)
    H.S.sort(key=pos)

    south_indicies = {k: i for i, k in enumerate(H.S)}
    north_indicies = {k: i for i, k in enumerate(H.N)}

    edges.sort(key=lambda e: south_indicies[e[1]])
    edges.sort(key=lambda e: north_indicies[e[0]])

    first_idx = 1
    while first_idx < len(H.S):
        first_idx *= 2

    tree = [0] * (2 * first_idx - 1)
    first_idx -= 1

    cross_weight = 0
    for _, v, weight in edges:
        idx = south_indicies[v] + first_idx
        tree[idx] += weight
        weight_sum = 0
        while idx > 0:
            if idx % 2 == 1:
                weight_sum += tree[idx + 1]

            idx = (idx - 1) // 2
            tree[idx] += weight

        cross_weight += weight * weight_sum

    return cross_weight


def get_new_col_order(v: GNode | Cluster, LT: _MixedGraph) -> Iterator[GNode]:
    if v.type == GType.CLUSTER:
        for w in sorted(LT[v], key=get_barycenter):
            yield from get_new_col_order(w, LT)
    else:
        yield v


def sort_internal_columns(items: _FreeColumns) -> None:
    for free_col, LT, data in items:

        def key(v: GNode | Cluster) -> int:
            if v.type == GType.CLUSTER:
                descendants = nx.descendants(LT, v)
                w = next(w for w in free_col if w in descendants)
            else:
                w = v

            return free_col.index(w)

        for H in data:
            H.reduced_free_col.sort(key=key)


# -------------------------------------------------------------------


def minimized_cross_count(
  columns: Sequence[list[GNode]],
  forward_items: _FreeColumns,
  backward_items: _FreeColumns,
  T: _MixedGraph,
) -> float:
    cross_count = inf
    is_forwards = random.choice((True, False))
    is_first_sweep = True
    while True:
        for v in T:
            v.cr.reset()

        if cross_count == 0:
            return 0

        is_forwards = not is_forwards
        old_cross_count = cross_count
        cross_count = 0

        items = forward_items if is_forwards else backward_items
        for i, (free_col, LT, data) in enumerate(items):
            if i == 0:
                fixed_col = columns[0] if is_forwards else columns[-1]
                clusters = {c: j for j, v in enumerate(fixed_col) for c in nx.ancestors(T, v)}
                key = cast(Callable[[Cluster], int], clusters.get)
            else:
                key = get_barycenter

            for H in data:
                H.constrained_clusters.sort(key=key)
                calc_socket_ranks(H, is_forwards)
                calc_barycenters(H)
                fill_in_unknown_barycenters(H.reduced_free_col, is_first_sweep)
                handle_constraints(H)
                cross_count += get_cross_count(H)

            root = topologically_sorted_clusters(LT)[0]
            new_order = tuple(get_new_col_order(root, LT))
            free_col.sort(key=new_order.index)

        if old_cross_count > cross_count:
            sort_internal_columns(forward_items + backward_items)
            best_columns = [c.copy() for c in columns]
            is_first_sweep = False
        else:
            for first_col, best_col in zip(columns, best_columns):
                first_col.sort(key=best_col.index)
            break

    return old_cross_count


_ITERATIONS = 15


def minimize_crossings(G: nx.MultiDiGraph[GNode], T: _MixedGraph) -> None:
    columns = G.graph['columns']
    trees = get_col_nesting_trees(columns, T)

    forward_data = crossing_reduction_data(G, trees)
    forward_items = list(zip(columns[1:], trees[1:], forward_data))

    trees.reverse()
    backward_data = crossing_reduction_data(nx.reverse_view(G), trees, True)  # type: ignore
    backward_items = list(zip(columns[-2::-1], trees[1:], backward_data))

    # -------------------------------------------------------------------

    random.seed(0)
    best_cross_count = inf
    best_columns = [c.copy() for c in columns]
    for _ in range(_ITERATIONS):
        cross_count = minimized_cross_count(columns, forward_items, backward_items, T)
        if cross_count < best_cross_count:
            best_cross_count = cross_count
            best_columns = [c.copy() for c in columns]
            if best_cross_count == 0:
                break
        else:
            for col, best_col in zip(columns, best_columns):
                col.sort(key=best_col.index)
            sort_internal_columns(forward_items + backward_items)
