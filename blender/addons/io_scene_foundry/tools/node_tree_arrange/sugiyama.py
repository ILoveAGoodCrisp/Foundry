# Code adapted from node-arrange (GPLv3) by Leonardo Pike-Excell
# https://github.com/Leonardo-Pike-Excell/node-arrange

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Collection, Iterable, Iterator, Sequence
from itertools import chain, pairwise, product
from statistics import fmean
from typing import Any, cast

import networkx as nx
from bpy.types import Node, NodeFrame, NodeTree
from mathutils import Vector
from mathutils.geometry import intersect_line_line_2d

from . import config
from .arrange_utils import abs_loc, get_ntree, group_by, move
from .graph import Cluster, GNode, GType, Socket, is_real
from .ordering import minimize_crossings
from .placement.bk import bk_assign_y_coords
from .placement.linear_segments import Segment, linear_segments_assign_y_coords
from .ranking import compute_ranks

# -------------------------------------------------------------------


def precompute_links(ntree: NodeTree) -> None:

    # Precompute links to ignore invalid/hidden links, and avoid `O(len(ntree.links))` time

    for link in ntree.links:
        if not link.is_hidden and link.is_valid:
            config.linked_sockets[link.to_socket].add(link.from_socket)
            config.linked_sockets[link.from_socket].add(link.to_socket)


def get_multidigraph() -> nx.MultiDiGraph[GNode]:
    parents = {n.parent: Cluster(cast(NodeFrame | None, n.parent)) for n in get_ntree().nodes}
    for c in parents.values():
        if c.node:
            c.cluster = parents[c.node.parent]

    G = nx.MultiDiGraph()
    G.add_nodes_from([
      GNode(n, parents[n.parent]) for n in config.selected if n.bl_idname != 'NodeFrame'])
    for u in G:
        for i, from_output in enumerate(u.node.outputs):
            for to_input in config.linked_sockets[from_output]:
                if not to_input.node.select:
                    continue

                v = next(v for v in G if v.node == to_input.node)
                j = to_input.node.inputs[:].index(to_input)
                G.add_edge(u, v, from_socket=Socket(u, i, True), to_socket=Socket(v, j, False))

    return G


def get_nesting_relations(v: GNode | Cluster) -> Iterator[tuple[Cluster, GNode | Cluster]]:
    if c := v.cluster:
        yield (c, v)
        yield from get_nesting_relations(c)


def save_multi_input_orders(G: nx.MultiDiGraph[GNode]) -> None:
    links = {(l.from_socket, l.to_socket): l for l in get_ntree().links}
    for v, w, d in G.edges.data():
        to_socket = d['to_socket']

        if not to_socket.bpy.is_multi_input:
            continue

        for z, u in chain([(w, v)], nx.bfs_edges(G, v, reverse=True)):
            if not u.is_reroute:
                break

        # If there's no non-reroute ancestor, the last edge is used.
        base_from_socket = G.edges[u, z, 0]['from_socket']

        link = links[(d['from_socket'].bpy, to_socket.bpy)]
        config.multi_input_sort_ids[to_socket][base_from_socket] = link.multi_input_sort_id


# -------------------------------------------------------------------


def add_dummy_edge(G: nx.DiGraph[GNode], u: GNode, v: GNode) -> None:
    G.add_edge(u, v, from_socket=Socket(u, 0, True), to_socket=Socket(v, 0, False))


def add_dummy_nodes_to_edge(
  G: nx.MultiDiGraph[GNode],
  edge: tuple[GNode, GNode, int],
  dummy_nodes: Sequence[GNode],
) -> None:
    if not dummy_nodes:
        return

    for pair in pairwise(dummy_nodes):
        add_dummy_edge(G, *pair)

    u, v, _ = edge
    d = G.edges[edge]  # type: ignore

    w = dummy_nodes[0]
    if w not in G[u]:
        G.add_edge(u, w, from_socket=d['from_socket'], to_socket=Socket(w, 0, False))

    z = dummy_nodes[-1]
    G.add_edge(z, v, from_socket=Socket(z, 0, True), to_socket=d['to_socket'])

    G.remove_edge(*edge)

    if not is_real(u) or not is_real(v):
        return

    links = get_ntree().links
    if d['to_socket'].bpy.is_multi_input:
        target_link = (d['from_socket'].bpy, d['to_socket'].bpy)
        links.remove(next(l for l in links if (l.from_socket, l.to_socket) == target_link))


# -------------------------------------------------------------------

_FRAME_PADDING = 29.8


def lowest_common_cluster(
  T: nx.DiGraph[GNode | Cluster],
  edges: Iterable[tuple[GNode, GNode, Any]],
) -> dict[tuple[GNode, GNode], Cluster]:
    pairs = {(u, v) for u, v, _ in edges if u.cluster != v.cluster}
    return dict(nx.tree_all_pairs_lowest_common_ancestor(T, pairs=pairs))


def label_height(c: Cluster) -> float:
    return -(_FRAME_PADDING / 2 - c.node.label_size * 1.25) if c.node and c.node.label else 0


# https://api.semanticscholar.org/CorpusID:14932050
class ClusterGraph:
    G: nx.MultiDiGraph[GNode]
    T: nx.DiGraph[GNode | Cluster]
    S: set[Cluster]
    __slots__ = tuple(__annotations__)

    def __init__(self, G: nx.MultiDiGraph[GNode]) -> None:
        self.G = G
        self.T = nx.DiGraph(chain(*map(get_nesting_relations, G)))
        self.S = {v for v in self.T if v.type == GType.CLUSTER}

    def remove_nodes_from(self, nodes: Iterable[GNode]) -> None:
        ntree = get_ntree()
        for v in nodes:
            self.G.remove_node(v)
            self.T.remove_node(v)
            if v.col:
                v.col.remove(v)

            if not is_real(v):
                continue

            sockets = {*v.node.inputs, *v.node.outputs}

            for socket in sockets:
                config.linked_sockets.pop(socket, None)

            for val in config.linked_sockets.values():
                val -= sockets

            config.selected.remove(v.node)
            ntree.nodes.remove(v.node)

    def merge_edges(self) -> None:
        G = self.G
        T = self.T
        groups = group_by(G.edges(keys=True), key=lambda e: G.edges[e]['from_socket'])
        edges: tuple[tuple[GNode, GNode, int], ...]
        for edges, from_socket in groups.items():
            long_edges = [(u, v, k) for u, v, k in edges if v.rank - u.rank > 1]

            if len(long_edges) < 2:
                continue

            long_edges.sort(key=lambda e: e[1].rank)
            lca = lowest_common_cluster(T, long_edges)
            dummy_nodes = []
            for u, v, k in long_edges:
                if dummy_nodes and dummy_nodes[-1].rank == v.rank - 1:
                    w = dummy_nodes[-1]
                else:
                    assert u.cluster
                    c = lca.get((u, v), u.cluster)
                    w = GNode(None, c, GType.DUMMY, v.rank - 1)
                    T.add_edge(c, w)
                    dummy_nodes.append(w)

                add_dummy_nodes_to_edge(G, (u, v, k), [w])
                G.remove_edge(u, w)

            for pair in pairwise(dummy_nodes):
                add_dummy_edge(G, *pair)

            w = dummy_nodes[0]
            G.add_edge(u, dummy_nodes[0], from_socket=from_socket, to_socket=Socket(w, 0, False))

    def insert_dummy_nodes(self) -> None:
        G = self.G
        T = self.T

        # -------------------------------------------------------------------

        long_edges = [(u, v, k) for u, v, k in G.edges(keys=True) if v.rank - u.rank > 1]
        lca = lowest_common_cluster(T, long_edges)
        for u, v, k in long_edges:
            assert u.cluster
            c = lca.get((u, v), u.cluster)
            dummy_nodes = []
            for i in range(u.rank + 1, v.rank):
                w = GNode(None, c, GType.DUMMY, i)
                T.add_edge(c, w)
                dummy_nodes.append(w)

            add_dummy_nodes_to_edge(G, (u, v, k), dummy_nodes)

        # -------------------------------------------------------------------

        for c in self.S:
            if not c.node:
                continue

            ranks = sorted({v.rank for v in nx.descendants(T, c) if v.type != GType.CLUSTER})
            for i, j in pairwise(ranks):
                if j - i == 1:
                    continue

                u = None
                for k in range(i + 1, j):
                    v = GNode(None, c, GType.VERTICAL_BORDER, k)
                    T.add_edge(c, v)

                    if u:
                        add_dummy_edge(G, u, v)
                    else:
                        G.add_node(v)

                    u = v

    def add_vertical_border_nodes(self) -> None:
        T = self.T
        G = self.G
        columns = G.graph['columns']
        for c in self.S:
            if not c.node:
                continue

            nodes = [v for v in nx.descendants(T, c) if v.type != GType.CLUSTER]
            lower_border_nodes = []
            upper_border_nodes = []
            for subcol in group_by(nodes, key=lambda v: columns.index(v.col), sort=True):
                col = subcol[0].col
                indices = [col.index(v) for v in subcol]

                lower_v = GNode(None, c, GType.VERTICAL_BORDER)
                col.insert(max(indices) + 1, lower_v)
                lower_v.col = col
                T.add_edge(c, lower_v)
                lower_border_nodes.append(lower_v)

                upper_v = GNode(None, c, GType.VERTICAL_BORDER)
                upper_v.height += label_height(c)
                col.insert(min(indices), upper_v)
                upper_v.col = col
                T.add_edge(c, upper_v)
                upper_border_nodes.append(upper_v)

            G.add_nodes_from(lower_border_nodes + upper_border_nodes)
            for p in *pairwise(lower_border_nodes), *pairwise(upper_border_nodes):
                add_dummy_edge(G, *p)


# -------------------------------------------------------------------


def get_reroute_paths(G: nx.DiGraph[GNode], function: Callable | None = None) -> list[list[GNode]]:
    reroutes = [v for v in G if v.is_reroute and (not function or function(v))]
    SG = nx.DiGraph(G.subgraph(reroutes))
    for v in SG:
        if G.out_degree[v] > 1:
            SG.remove_edges_from(tuple(SG.out_edges(v)))

    indicies = {v: i for i, v in enumerate(nx.topological_sort(G)) if v in reroutes}
    paths = [sorted(c, key=lambda v: indicies[v]) for c in nx.weakly_connected_components(SG)]
    paths.sort(key=lambda p: indicies[p[0]])
    return paths


def is_safe_to_remove(v: GNode) -> bool:
    if not is_real(v):
        return True

    if v.node.label:
        return False

    if v in {w.owner for w in chain(*config.multi_input_sort_ids.values())}:
        return False

    return all(
      s.node.select for s in chain(
      config.linked_sockets[v.node.inputs[0]],
      config.linked_sockets[v.node.outputs[0]],
      ))


def get_reroute_segments(CG: ClusterGraph) -> list[list[GNode]]:
    reroute_paths = get_reroute_paths(CG.G, is_safe_to_remove)
    order = tuple(chain(*reroute_paths))

    reroute_clusters = {#
      c for c in CG.S
      if all(v.is_reroute for v in CG.T[c] if isinstance(v, GNode))}
    reroute_segments = []
    for segment in map(Segment, reroute_paths):
        nodes = segment.nodes.copy()
        for children, cluster in group_by(segment, key=lambda v: v.cluster).items():
            if cluster not in reroute_clusters:
                continue

            s1 = segment.split(children[0])
            reroute_segments.append(s1)
            if children[-1] != nodes[-1]:
                reroute_segments.append(s1.split(nodes[nodes.index(children[-1]) + 1]))

        if segment.nodes:
            reroute_segments.append(segment)

    return sorted(map(list, reroute_segments), key=lambda s: order.index(s[0]))


def dissolve_reroute_edges(G: nx.DiGraph[GNode], path: list[GNode]) -> None:
    if not G[path[-1]]:
        return

    try:
        u, _, o = next(iter(G.in_edges(path[0], data='from_socket')))
    except StopIteration:
        return

    succ_inputs = [e[2] for e in G.out_edges(path[-1], data='to_socket')]

    # Check if a reroute has been used to link the same output to the same multi-input multiple
    # times
    for *_, d in G.out_edges(u, data=True):
        if d['from_socket'] == o and d['to_socket'] in succ_inputs:
            path.clear()
            return

    links = get_ntree().links
    for i in succ_inputs:
        G.add_edge(u, i.owner, from_socket=o, to_socket=i)
        links.new(o.bpy, i.bpy)


def remove_reroutes(CG: ClusterGraph) -> None:
    reroute_clusters = {#
      c for c in CG.S
      if all(v.type != GType.CLUSTER and v.is_reroute for v in CG.T[c])}
    for path in get_reroute_segments(CG):
        if path[0].cluster in reroute_clusters:
            if len(path) > 2:
                u, *between, v = path
                add_dummy_edge(CG.G, u, v)
                CG.remove_nodes_from(between)
        else:
            dissolve_reroute_edges(CG.G, path)
            CG.remove_nodes_from(path)


# -------------------------------------------------------------------


def add_columns(G: nx.DiGraph[GNode]) -> None:
    columns = [list(c) for c in group_by(G, key=lambda v: v.rank, sort=True)]
    G.graph['columns'] = columns
    for col in columns:
        col.sort(key=lambda v: abs_loc(v.node).y if is_real(v) else 0, reverse=True)
        for v in col:
            v.col = col


# -------------------------------------------------------------------


def align_reroutes_with_sockets(G: nx.DiGraph[GNode]) -> None:
    reroute_paths: dict[tuple[GNode, ...], list[Socket]] = {}
    for path in get_reroute_paths(G):
        for subpath in group_by(path, key=lambda v: v.y):
            inputs = G.in_edges(subpath[0], data='from_socket')
            outputs = G.out_edges(subpath[-1], data='to_socket')
            reroute_paths[subpath] = [e[2] for e in (*inputs, *outputs)]

    while True:
        changed = False
        for path, foreign_sockets in tuple(reroute_paths.items()):
            y = path[0].y
            foreign_sockets.sort(key=lambda s: abs(y - s.y))
            foreign_sockets.sort(key=lambda s: y == s.owner.y, reverse=True)

            if not foreign_sockets or y - foreign_sockets[0].y == 0:
                del reroute_paths[path]
                continue

            movement = y - foreign_sockets[0].y
            y -= movement
            if movement < 0:
                above_y_vals = [
                  (w := v.col[v.col.index(v) - 1]).y - w.height for v in path if v != v.col[0]]
                if above_y_vals and y > min(above_y_vals):
                    continue
            else:
                below_y_vals = [v.col[v.col.index(v) + 1].y for v in path if v != v.col[-1]]
                if below_y_vals and max(below_y_vals) > y - path[0].height:
                    continue

            for v in path:
                v.y -= movement

            changed = True

        if not changed:
            if reroute_paths:
                for path, foreign_sockets in reroute_paths.items():
                    del foreign_sockets[0]
            else:
                break


def frame_padding(
  columns: Sequence[Collection[GNode]],
  i: int,
  T: nx.DiGraph[GNode | Cluster],
) -> float:
    col = columns[i]

    if col == columns[-1]:
        return 0

    clusters1 = {cast(Cluster, v.cluster) for v in col}
    clusters2 = {cast(Cluster, v.cluster) for v in columns[i + 1]}

    if not clusters1 ^ clusters2:
        return 0

    ST1 = T.subgraph(chain(clusters1, *[nx.ancestors(T, c) for c in clusters1])).copy()
    ST2 = T.subgraph(chain(clusters2, *[nx.ancestors(T, c) for c in clusters2])).copy()

    for *e, d in ST1.edges(data=True):
        d['weight'] = int(e not in ST2.edges)  # type: ignore

    for *e, d in ST2.edges(data=True):
        d['weight'] = int(e not in ST1.edges)  # type: ignore

    dist = nx.dag_longest_path_length(ST1) + nx.dag_longest_path_length(ST2)  # type: ignore
    return _FRAME_PADDING * dist


def assign_x_coords(G: nx.DiGraph[GNode], T: nx.DiGraph[GNode | Cluster]) -> None:
    columns: list[list[GNode]] = G.graph['columns']
    x = 0
    for i, col in enumerate(columns):
        max_width = max([v.width for v in col])

        for v in col:
            v.x = x if v.is_reroute else x - (v.width - max_width) / 2

        # https://doi.org/10.7155/jgaa.00220 (p. 139)
        delta_i = sum([
          1 for *_, d in G.out_edges(col, data=True)
          if abs(d['to_socket'].y - d['from_socket'].y) >= config.MARGIN.x * 3])
        spacing = (1 + min(delta_i / 4, 2)) * config.MARGIN.x
        x += max_width + spacing + frame_padding(columns, i, T)


def is_unnecessary_bend_point(socket: Socket, other_socket: Socket) -> bool:
    v = socket.owner

    if v.is_reroute:
        return False

    i = v.col.index(v)
    is_above = other_socket.y > socket.y

    try:
        nbr = v.col[i - 1] if is_above else v.col[i + 1]
    except IndexError:
        return True

    if nbr.is_reroute:
        return True

    nbr_x_offset, nbr_y_offset = config.MARGIN / 2
    nbr_y = nbr.y - nbr.height - nbr_y_offset if is_above else nbr.y + nbr_y_offset

    assert nbr.cluster
    if nbr.cluster.node and nbr.cluster != v.cluster:
        nbr_x_offset += _FRAME_PADDING
        if is_above:
            nbr_y -= _FRAME_PADDING
        else:
            nbr_y += _FRAME_PADDING + label_height(nbr.cluster)

    line_a = ((nbr.x - nbr_x_offset, nbr_y), (nbr.x + nbr.width + nbr_x_offset, nbr_y))
    line_b = ((socket.x, socket.y), (other_socket.x, other_socket.y))
    return intersect_line_line_2d(*line_a, *line_b) is None


_MIN_X_DIFF = 30
_MIN_Y_DIFF = 15


def add_bend_points(
  G: nx.MultiDiGraph[GNode],
  v: GNode,
  bend_points: defaultdict[tuple[GNode, GNode, int], list[GNode]],
) -> None:
    d: dict[str, Socket]
    largest = max(v.col, key=lambda w: w.width)
    for u, w, k, d in *G.out_edges(v, data=True, keys=True), *G.in_edges(v, data=True, keys=True):
        socket = d['from_socket'] if v == u else d['to_socket']
        bend_point = GNode(type=GType.DUMMY)
        bend_point.x = largest.x + largest.width if socket.is_output else largest.x

        if abs(socket.x - bend_point.x) <= _MIN_X_DIFF:
            continue

        bend_point.y = socket.y
        other_socket = next(s for s in d.values() if s != socket)

        if abs(other_socket.y - bend_point.y) <= _MIN_Y_DIFF:
            continue

        if is_unnecessary_bend_point(socket, other_socket):
            continue

        bend_points[u, w, k].append(bend_point)


def route_edges(G: nx.MultiDiGraph[GNode], T: nx.DiGraph[GNode | Cluster]) -> None:
    bend_points = defaultdict(list)
    for v in chain(*G.graph['columns']):
        add_bend_points(G, v, bend_points)

    edge_of = {v: e for e, d in bend_points.items() for v in d}
    key = lambda v: (G.edges[edge_of[v]]['from_socket'], v.x, v.y)
    for (target, *redundant), (from_socket, *_) in group_by(edge_of, key=key).items():
        for v in redundant:
            dummy_nodes = bend_points[edge_of[v]]
            dummy_nodes[dummy_nodes.index(v)] = target

        u = from_socket.owner
        if not u.is_reroute or G.out_degree[u] < 2:  # type: ignore
            continue

        for e in G.out_edges(u, keys=True):
            if target not in bend_points[e]:
                bend_points[e].append(target)

    lca = lowest_common_cluster(T, bend_points)
    for (u, v, k), dummy_nodes in bend_points.items():
        dummy_nodes.sort(key=lambda v: v.x)
        add_dummy_nodes_to_edge(G, (u, v, k), dummy_nodes)

        c = lca.get((u, v), u.cluster)
        for w in dummy_nodes:
            w.cluster = c


# -------------------------------------------------------------------


def simplify_segment(CG: ClusterGraph, aligned: Sequence[GNode], path: list[GNode]) -> None:
    if len(aligned) == 1:
        return

    u, *between, v = aligned
    G = CG.G

    if G.pred[u] and (s := next(iter(G.in_edges(u, data='from_socket')))[2]).y == u.y:
        G.add_edge(s.owner, v, from_socket=s, to_socket=Socket(v, 0, False))
        between.append(u)
    elif G.out_degree[v] == 1 and v.y == (s := next(iter(G.out_edges(v, data='to_socket')))[2]).y:
        G.add_edge(u, s.owner, from_socket=Socket(u, 0, True), to_socket=s)
        between.append(v)
    elif between:
        add_dummy_edge(G, u, v)

    CG.remove_nodes_from(between)
    for v in between:
        if v not in G:
            path.remove(v)


def add_reroute(v: GNode) -> None:
    reroute = get_ntree().nodes.new(type='NodeReroute')
    assert v.cluster
    reroute.parent = v.cluster.node
    config.selected.append(reroute)
    v.node = reroute
    v.type = GType.NODE


def realize_edges(G: nx.DiGraph[GNode], v: GNode) -> None:
    assert is_real(v)
    links = get_ntree().links

    if G.pred[v]:
        pred_output = next(iter(G.in_edges(v, data='from_socket')))[2]
        links.new(pred_output.bpy, v.node.inputs[0])

    for _, w, succ_input in G.out_edges(v, data='to_socket'):
        if is_real(w):
            links.new(v.node.outputs[0], succ_input.bpy)


def realize_dummy_nodes(CG: ClusterGraph) -> None:
    for path in get_reroute_segments(CG):
        for aligned in group_by(path, key=lambda v: v.y):
            simplify_segment(CG, aligned, path)

        for v in path:
            if not is_real(v):
                add_reroute(v)

            realize_edges(CG.G, v)


def restore_multi_input_orders(G: nx.MultiDiGraph[GNode]) -> None:
    H: nx.DiGraph[Socket] = nx.DiGraph()
    H.add_edges_from([(d['from_socket'], d['to_socket']) for *_, d in G.edges.data()])
    for sockets in group_by(H, key=lambda s: s.owner):
        outputs = {s for s in sockets if s.is_output}
        H.add_edges_from(product(set(sockets) - outputs, outputs))

    links = get_ntree().links
    for socket, sort_ids in config.multi_input_sort_ids.items():
        multi_input = socket.bpy
        assert multi_input

        as_links = {l.from_socket: l for l in links if l.to_socket == multi_input}

        if len(as_links) != len({l.multi_input_sort_id for l in as_links.values()}):
            for link in as_links.values():
                links.remove(link)

            for output in as_links:
                as_links[output] = links.new(output, multi_input)

        for base_from_socket, sort_id in sort_ids.items():
            other = min(as_links.values(), key=lambda l: abs(l.multi_input_sort_id - sort_id))
            from_socket = next(s for s, t in nx.dfs_edges(H, base_from_socket) if t == socket)
            as_links[from_socket.bpy].swap_multi_input_sort_id(other)  # type: ignore


def realize_locations(G: nx.DiGraph[GNode], old_center: Vector) -> None:
    new_center = (fmean([v.x for v in G]), fmean([v.y for v in G]))
    offset_x, offset_y = -Vector(new_center) + old_center

    for v in G:
        assert isinstance(v.node, Node)
        assert v.cluster

        # Optimization: avoid using bpy.ops for as many nodes as possible (see `utils.move()`)
        v.node.parent = None

        x, y = v.node.location
        move(v.node, x=v.x + offset_x - x, y=v.corrected_y() + offset_y - y)

        v.node.parent = v.cluster.node


# -------------------------------------------------------------------


def sugiyama_layout(ntree: NodeTree) -> None:
    locs = [abs_loc(n) for n in config.selected if n.bl_idname != 'NodeFrame']

    if not locs:
        return

    old_center = Vector(map(fmean, zip(*locs)))

    precompute_links(ntree)
    CG = ClusterGraph(get_multidigraph())
    G = CG.G
    T = CG.T

    save_multi_input_orders(G)
    remove_reroutes(CG)

    compute_ranks(CG)
    CG.merge_edges()
    CG.insert_dummy_nodes()

    add_columns(G)
    minimize_crossings(G, T)

    if len(CG.S) == 1:
        bk_assign_y_coords(G)
    else:
        CG.add_vertical_border_nodes()
        linear_segments_assign_y_coords(CG)
        CG.remove_nodes_from([v for v in G if v.type == GType.VERTICAL_BORDER])

    align_reroutes_with_sockets(G)
    assign_x_coords(G, T)
    route_edges(G, T)

    realize_dummy_nodes(CG)
    restore_multi_input_orders(G)
    realize_locations(G, old_center)
