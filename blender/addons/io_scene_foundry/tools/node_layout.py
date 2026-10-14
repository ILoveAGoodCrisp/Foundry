"""Fast, deterministic placement for Foundry node trees.

Lay out once after connections and game conversion are complete. No editor
redraw, graph optimisation, or changes to nodes, sockets and links are needed.
"""

from collections import defaultdict, deque
from dataclasses import dataclass
from statistics import median


_ROW = 24.0
_GAP_X = 120.0
_GAP_Y = 40.0


def _group_geometry(node):
    """Follow interface order and instance panel state, including nested panels."""
    items = list(node.node_tree.interface.items_tree)
    sockets = {(socket.is_output, socket.identifier): socket
               for socket in (*node.inputs, *node.outputs)}
    # Older Blender releases expose interface defaults but no per-node state.
    closed = {state.identifier: state.is_collapsed for state in getattr(node, 'panel_states', ())}
    parents = {}
    visible_panels = set()
    for item in items:
        path = []
        parent = item.parent
        while parent:
            path.append(parent)
            parent = parent.parent
        parents[item] = path
        if item.item_type != 'SOCKET':
            continue
        socket = sockets.get((item.in_out == 'OUTPUT', item.identifier))
        if socket is None or not socket.enabled or socket.hide or socket.is_unavailable:
            continue
        if getattr(socket, 'is_icon_visible', True) or any(closed.get(p.identifier, p.default_closed) for p in path):
            visible_panels.update(path)

    offsets, collapsed = {}, {}
    y = 40.0
    for item in items:
        parent_offset = next((collapsed[p] for p in parents[item] if p in collapsed), None)
        if item.item_type == 'PANEL':
            if parent_offset is not None:
                collapsed[item] = parent_offset
            elif item in visible_panels:
                if closed.get(item.identifier, item.default_closed):
                    collapsed[item] = y
                y += _ROW
            continue
        socket = sockets.get((item.in_out == 'OUTPUT', item.identifier))
        if socket is None or not socket.enabled or socket.hide or socket.is_unavailable:
            continue
        # Collapsed sockets attach to the visible panel header. Inferred hidden
        # sockets retain their interface order without occupying a full row.
        offsets[socket] = parent_offset if parent_offset is not None else y
        if parent_offset is None and getattr(socket, 'is_icon_visible', True):
            y += _ROW
            if not socket.is_output and socket.type == 'VECTOR' and not socket.is_linked and not socket.hide_value:
                y += 2 * _ROW
    return y + 20.0, offsets


def _geometry(node):
    """Estimate undrawn node bounds and socket offsets in node-editor units."""
    if node.bl_idname == 'NodeReroute':
        return 16.0, {socket: 8.0 for socket in (*node.inputs, *node.outputs)}
    if node.hide:
        return 40.0, {socket: 20.0 for socket in (*node.inputs, *node.outputs)}
    if node.type == 'GROUP' and node.node_tree:
        return _group_geometry(node)

    offsets = {}
    y = 40.0
    for socket in node.outputs:
        if socket.enabled and not socket.hide:
            offsets[socket] = y
            y += _ROW

    # Controls appear between the outputs and inputs. Leave conservative space
    # for nodes with previews, selectors, curves, and operation menus.
    controls = {
        'ShaderNodeTexImage': 120.0 if getattr(node, 'image', None) else 70.0,
        'ShaderNodeTexEnvironment': 180.0,
        'ShaderNodeTexCoord': 60.0,
        'ShaderNodeUVMap': 20.0,
        'ShaderNodeAttribute': 80.0,
        'ShaderNodeRGB': 180.0,
        'ShaderNodeFloatCurve': 260.0,
        'ShaderNodeVectorCurve': 260.0,
        'ShaderNodeRGBCurve': 260.0,
        'ShaderNodeValToRGB': 220.0,
        'ShaderNodeMapping': 28.0,
        'ShaderNodeOutputMaterial': 0.0,
    }
    y += controls.get(node.bl_idname, 0.0 if node.type == 'GROUP' else 60.0)
    for socket in node.inputs:
        if not socket.enabled or socket.hide:
            continue
        offsets[socket] = y
        y += _ROW
        if socket.type == 'VECTOR' and not socket.is_linked and not socket.hide_value:
            y += 2 * _ROW
    return y + 20.0, offsets


def _pack(column, preferred, heights):
    """Closest nonoverlapping positions, preserving downstream socket order.

    Pool adjacent violations after subtracting the required node spacing.
    This avoids pushing an entire texture stack down when one branch is tall.
    """
    blocks = []
    offsets = []
    offset = 0.0
    for index, node in enumerate(column):
        offsets.append(offset)
        blocks.append([preferred[node] + offset, 1, index, index + 1])
        while len(blocks) > 1 and blocks[-2][0] / blocks[-2][1] < blocks[-1][0] / blocks[-1][1]:
            right = blocks.pop()
            left = blocks.pop()
            blocks.append([left[0] + right[0], left[1] + right[1], left[2], right[3]])
        offset += heights[node] + _GAP_Y
    return {column[index]: total / count - offsets[index]
            for total, count, start, end in blocks for index in range(start, end)}


def _ranks(nodes, links):
    incoming = defaultdict(list)
    outgoing = defaultdict(list)
    for link in links:
        incoming[link.to_node].append(link)
        outgoing[link.from_node].append(link)

    # Longest distance to a sink guarantees left-to-right links in a DAG.
    remaining = {node: len(outgoing[node]) for node in nodes}
    ranks = {node: 0 for node in nodes}
    queue = deque(node for node in nodes if not remaining[node])
    visited = []
    while queue:
        node = queue.popleft()
        visited.append(node)
        for link in incoming[node]:
            source = link.from_node
            ranks[source] = max(ranks[source], ranks[node] + 1)
            remaining[source] -= 1
            if not remaining[source]:
                queue.append(source)
    if len(visited) != len(nodes):
        return None

    # Keep texture rows together even when one texture also feeds a normal,
    # channel-splitting or animation chain. Propagate the extra depth upstream
    # so mappings and their helpers remain to the left of those rows.
    textures = [node for node in nodes if node.type in {'TEX_IMAGE', 'TEX_ENVIRONMENT'}]
    if textures:
        texture_rank = max(ranks[node] for node in textures)
        for node in textures:
            ranks[node] = texture_rank
        for node in visited:
            for link in incoming[node]:
                ranks[link.from_node] = max(ranks[link.from_node], ranks[node] + 1)

    return ranks, outgoing


def _place(nodes, links, widths, heights, sockets):
    order = {node: index for index, node in enumerate(nodes)}
    ranked = _ranks(nodes, links)
    if ranked is None:
        # Contracting frames can create a cycle even when the actual nodes form
        # a DAG (one frame contains both a source and a downstream consumer).
        # Keep those frame blocks separate in a stable column.
        ranks, outgoing = dict.fromkeys(nodes, 0), defaultdict(list)
    else:
        ranks, outgoing = ranked
    columns = defaultdict(list)
    for node in nodes:
        columns[ranks[node]].append(node)

    locations = {}
    x = 0.0
    for rank in sorted(columns):
        column = columns[rank]
        if rank:
            x -= max(widths[node] for node in column) + _GAP_X
        preferred = {}
        for node in column:
            targets = [locations[link.to_node][1] if link.to_node.type in {'TEX_IMAGE', 'TEX_ENVIRONMENT', 'MAPPING'}
                       else locations[link.to_node][1] - sockets.get(link.to_socket, 40.0)
                       + sockets.get(link.from_socket, 40.0)
                       for link in outgoing[node] if link.to_node in locations]
            preferred[node] = median(targets) if targets else 0.0
        column.sort(key=lambda node: (-preferred[node], order[node]))
        positions = _pack(column, preferred, heights)
        # A shader's connected inputs often occupy its lower half. Center a
        # taller source stack around that shader instead of extending it down
        # from those sockets, while retaining the socket-based branch order.
        targets = {link.to_node for node in column for link in outgoing[node]
                   if link.to_node in locations}
        if len(column) > 1 and len(targets) == 1:
            target = next(iter(targets))
            if target.type == 'GROUP' and any(s.type == 'SHADER' for s in target.outputs):
                top = max(positions.values())
                bottom = min(positions[node] - heights[node] for node in column)
                if top - bottom > heights[target]:
                    shift = locations[target][1] - heights[target] / 2 - (top + bottom) / 2
                    positions = {node: y + shift for node, y in positions.items()}
        for node in column:
            locations[node] = (x, positions[node])

    return locations


@dataclass(slots=True)
class _FrameLink:
    from_node: object
    to_node: object
    from_socket: object
    to_socket: object


def layout_nodes(tree):
    """Place nodes in columns, ordering branches by destination sockets.

    Shared sources sit between consumers. Nested frames are laid out as blocks
    with their children inside. Preserve parents, selection, topology, values,
    drivers and existing reroutes; cyclic graphs are left untouched.
    """
    nodes = list(tree.nodes)
    if not nodes:
        return False
    links = list(tree.links)
    leaves = [node for node in nodes if node.type != 'FRAME']
    # New group links may report hidden/invalid before Blender evaluates them.
    # Use their connections directly, without forcing an editor redraw.
    if _ranks(leaves, links) is None:
        return False

    children = defaultdict(list)
    paths = {}
    widths, heights, socket_offsets = {}, {}, {}
    for node in nodes:
        children[node.parent].append(node)
        path = [node]
        while path[-1] is not None:
            path.append(path[-1].parent)
        paths[node] = path
        width = node.width
        if not node.hide and node.type not in {'FRAME', 'REROUTE'}:
            preferred_width = 260.0 if node.type in {'TEX_IMAGE', 'TEX_ENVIRONMENT', 'MAPPING'} else 180.0
            if node.type == 'GROUP':
                preferred_width = 320.0 if any(s.type == 'SHADER' for s in node.outputs) else 240.0
            width = max(width, preferred_width)
        widths[node] = width
        heights[node], socket_offsets[node] = _geometry(node)
        # Measured bounds help with custom controls on already drawn nodes.
        # Convert from UI pixels using the measured width, avoiding ui_scale=0
        # in background Blender and handling nondefault desktop scaling.
        if node.dimensions.x > 0 and not node.hide:
            heights[node] = max(heights[node], node.dimensions.y * width / node.dimensions.x)

    scope_links = defaultdict(list)
    for link in links:
        source_path, target_path = paths[link.from_node], paths[link.to_node]
        target_parents = set(target_path[1:])
        common = next(parent for parent in source_path[1:] if parent in target_parents)
        source = source_path[source_path.index(common) - 1]
        target = target_path[target_path.index(common) - 1]
        scope_links[common].append(_FrameLink(source, target, link.from_socket, link.to_socket))

    frames = [node for node in nodes if node.type == 'FRAME']
    scopes = sorted(frames, key=lambda node: len(paths[node]), reverse=True) + [None]
    locations = {}
    for scope in scopes:
        members = children[scope]
        sockets = {socket: offset for node in members for socket, offset in socket_offsets[node].items()}
        placed = _place(members, scope_links[scope], widths, heights, sockets)
        if scope is not None:
            if placed:
                left = min(x for x, y in placed.values())
                top = max(y for x, y in placed.values())
                right = max(placed[node][0] + widths[node] for node in members)
                bottom = min(placed[node][1] - heights[node] for node in members)
                padding = 40.0
                title = padding + (scope.label_size * 1.25 if scope.label else 0.0)
                placed = {node: (x - left + padding, y - top - title)
                          for node, (x, y) in placed.items()}
                widths[scope] = right - left + padding * 2
                heights[scope] = top - bottom + title + padding
                socket_offsets[scope] = {
                    socket: offset - placed[node][1]
                    for node in members for socket, offset in socket_offsets[node].items()}
            else:
                heights[scope] = max(scope.height, 150.0)
        locations.update(placed)

    # Set frame dimensions before child coordinates; Blender's automatic frame
    # fitting can then adjust its padding without changing the graph's parents.
    for node in nodes:
        if node.type == 'FRAME':
            node.width = widths[node]
            node.height = heights[node]
        elif not node.hide and node.type != 'REROUTE':
            node.width = widths[node]
    for node in sorted(nodes, key=lambda node: len(paths[node])):
        node.location = locations[node]
    return True
