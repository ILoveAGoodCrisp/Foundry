"""Shared surface selection and constant inputs for node-to-tag export."""


def surface_links(tree):
    if tree is None:
        return
    outputs = [node for node in tree.nodes if node.type == 'OUTPUT_MATERIAL']
    active = [node for node in outputs if node.is_active_output]
    for node in active or outputs:
        socket = node.inputs.get('Surface')
        if socket is not None:
            yield from socket.links


def connected_nodes(tree):
    pending = [link.from_node for link in surface_links(tree)]
    seen = set()
    while pending:
        node = pending.pop(0)
        if node in seen:
            continue
        seen.add(node)
        yield node
        pending.extend(link.from_node for socket in node.inputs for link in socket.links)


def constant_input(socket, default=None, group_stack=()):
    """Read literals through reroutes; leave animated/procedural inputs alone."""
    seen = set()
    while socket is not None and socket.is_linked:
        socket = socket.links[0].from_socket
        node = socket.node
        key = (node, group_stack)
        if key in seen:
            return default
        seen.add(key)
        if node.type == 'REROUTE':
            socket = node.inputs[0]
        elif node.type in {'RGB', 'VALUE'}:
            return socket.default_value
        elif node.type == 'GROUP_INPUT' and group_stack:
            parent = group_stack[-1]
            socket = next((s for s in parent.inputs if s.identifier == socket.identifier), None)
            group_stack = group_stack[:-1]
        else:
            return default
    return getattr(socket, 'default_value', default)
