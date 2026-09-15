"""Text serializers for the shared legacy asset models; no Blender dependency."""
from dataclasses import replace
from math import isfinite


VERSIONS = {
    'halo1': (8200, None, 16392),
    'halo2': (8210, 2, 16395),
    'halo3': (8213, 7, 16395),
    'halo3odst': (8213, 7, 16395),
}


class TextWriter:
    def __init__(self, stream, quoted=False):
        self.stream, self.quoted = stream, quoted

    def line(self, value):
        if isinstance(value, str):
            if any(c in value for c in '\r\n"\t') or (not self.quoted and (value.startswith(';') or ' ;' in value)):
                raise ValueError(f'Unrepresentable legacy string: {value!r}')
            if self.quoted:
                value = f'"{value}"'
            elif not value.strip():
                value = '<none>'
        self.stream.write(str(value) + '\n')

    def vector(self, values):
        values = tuple(float(v) for v in values)
        if not all(isfinite(v) for v in values):
            raise ValueError('Cannot export non-finite numeric data')
        self.stream.write('\t'.join(format(v, '.10g') for v in values) + '\n')

    def transform(self, value):
        self.vector(value.rotation)
        self.vector(value.translation)


def hierarchy(nodes):
    children = {}
    for index, node in enumerate(nodes):
        children.setdefault(node.parent, []).append(index)
    result = [replace(n, child=-1, sibling=-1) for n in nodes]
    for parent, indices in children.items():
        if parent != -1:
            result[parent].child = indices[0]
        for first, second in zip(indices, indices[1:]):
            result[first].sibling = second
    return result


def node_checksum(nodes):
    """Halo's ordered hierarchy hash, with 32-bit rotation at each branch."""
    def rotate(value, count):
        return ((value << count) | (value >> (32 - count))) & 0xffffffff
    children = {}
    for index, node in enumerate(nodes):
        children.setdefault(node.parent, []).append(index)
    checksum = 0
    stack = [(i, False) for i in reversed(children.get(-1, []))]
    while stack:
        index, leave = stack.pop()
        if leave:
            checksum = rotate(checksum, 30)
            continue
        name_hash = 0
        for byte in nodes[index].name.encode('utf-8'):
            name_hash = (rotate(name_hash, 1) + byte) & 0xffffffff
        checksum = rotate((rotate(checksum, 1) + name_hash) & 0xffffffff, 2)
        stack.append((index, True))
        stack.extend((child, False) for child in reversed(children.get(index, [])))
    return checksum if checksum < 0x80000000 else checksum - 0x100000000


def write_jms(asset, stream):
    """Write the game-selected H1, H2 or H3 dialect, without mutating the asset."""
    v = asset.version
    if v not in {8200, 8210, 8213}:
        raise ValueError(f'Unsupported JMS output version {v}')
    nodes = hierarchy(asset.nodes)
    checked = replace(asset, nodes=nodes)
    checked.validate()
    w = TextWriter(stream)
    w.line(v)
    if v < 8205:
        if asset.shapes or asset.constraints or asset.xrefs or asset.instances:
            raise ValueError('H1 JMS cannot represent these physics or instance records')
        w.line(asset.checksum)
    w.line(len(nodes))
    for n in nodes:
        w.line(n.name)
        if v >= 8205:
            w.line(n.parent)
        else:
            w.line(n.child)
            w.line(n.sibling)
        w.transform(n.transform)
    w.line(len(asset.materials))
    for m in asset.materials:
        w.line(m.name)
        w.line(m.definition or '<none>')
    w.line(len(asset.markers))
    for m in asset.markers:
        w.line(m.name)
        if v < 8205:
            w.line(m.region)
        w.line(m.parent)
        w.transform(m.transform)
        w.vector((m.radius,))
    if v >= 8205:
        w.line(len(asset.xrefs))
        for path, name in asset.xrefs:
            w.line(path)
            w.line(name)
        w.line(len(asset.instances))
        for name, uid, xref, transform in asset.instances:
            for value in (name, uid, xref):
                w.line(value)
            w.transform(transform)
    else:
        w.line(len(asset.regions))
        for region in asset.regions:
            w.line(region)
    w.line(len(asset.vertices))
    for vertex in asset.vertices:
        weights = [(i, weight) for i, weight in vertex.influences if i >= 0 and weight > 0]
        total = sum(weight for _, weight in weights)
        weights = [(i, weight / total) for i, weight in weights]
        if v >= 8205:
            w.vector(vertex.position)
            w.vector(vertex.normal)
            w.line(len(weights))
            for i, weight in weights:
                w.line(i)
                w.vector((weight,))
            w.line(len(vertex.uvs))
            for uv in vertex.uvs:
                w.vector(uv[:2])
            if v >= 8211:
                w.vector(vertex.color or (1, 1, 1))
        else:
            if len(weights) > 2:
                raise ValueError('H1 JMS supports at most two influences per vertex')
            weights += [(-1, 0)] * (2 - len(weights))
            w.line(weights[0][0])
            w.vector(vertex.position)
            w.vector(vertex.normal)
            w.line(weights[1][0])
            w.vector((weights[1][1],))
            w.vector(vertex.uvs[0][:2] if vertex.uvs else (0, 0))
            w.line(0)
    w.line(len(asset.triangles))
    for t in asset.triangles:
        if v < 8205:
            w.line(t.region)
        w.line(t.material)
        for i in t.vertices:
            w.line(i)
    if v >= 8206:
        for kind in ('sphere', 'box', 'pill', 'convex'):
            shapes = [s for s in asset.shapes if s.kind == kind]
            w.line(len(shapes))
            for s in shapes:
                for value in (s.name, s.parent, s.material):
                    w.line(value)
                w.transform(s.transform)
                if s.dimensions:
                    w.vector(s.dimensions)
                if kind == 'convex':
                    w.line(len(s.vertices))
                    for p in s.vertices:
                        w.vector(p)
        for kind in ('ragdoll', 'hinge', 'car_wheel', 'point_to_point', 'prismatic'):
            constraints = [c for c in asset.constraints if c.kind == kind]
            w.line(len(constraints))
            for c in constraints:
                for value in (c.name, c.parent, c.child):
                    w.line(value)
                w.transform(c.parent_transform)
                w.transform(c.child_transform)
                w.vector(c.limits)
        w.line(len(asset.bounding_spheres))
        for position, radius in asset.bounding_spheres:
            w.vector(position)
            w.vector((radius,))
        if v >= 8212:
            w.line(len(asset.skylights))
            for direction, color, power in asset.skylights:
                w.vector(direction)
                w.vector(color)
                w.vector((power,))


def write_ass(asset, stream):
    if asset.version not in {2, 7}:
        raise ValueError(f'Unsupported ASS output version {asset.version}')
    asset.validate()
    w = TextWriter(stream, quoted=True)
    w.line(asset.version)
    for value in asset.header or ('Foundry', 'Blender', '', ''):
        w.line(value)
    w.line(len(asset.materials))
    for m in asset.materials:
        w.line(m.name)
        w.line(m.variant)
        if asset.version >= 4:
            w.line(len(m.lighting))
            for record in m.lighting:
                w.line(record)
    w.line(len(asset.geometries))
    for g in asset.geometries:
        for value in (g.kind, g.xref_path, g.xref_name):
            w.line(value)
        if g.kind == 'MESH':
            w.line(len(g.vertices))
            for vertex in g.vertices:
                w.vector(vertex.position)
                w.vector(vertex.normal)
                if asset.version >= 6:
                    w.vector(vertex.color or (1, 1, 1))
                w.line(len(vertex.influences))
                for i, weight in vertex.influences:
                    w.line(i)
                    w.vector((weight,))
                w.line(len(vertex.uvs))
                for uv in vertex.uvs:
                    w.vector((tuple(uv) + (0, 0, 0))[:3 if asset.version >= 5 else 2])
            w.line(len(g.triangles))
            for t in g.triangles:
                w.line(t.material)
                for i in t.vertices:
                    w.line(i)
        elif g.kind in {'SPHERE', 'BOX', 'PILL'}:
            w.line(g.material)
            w.vector(g.dimensions)
        else:
            raise ValueError(f'Unsupported ASS output geometry {g.kind}')
    w.line(len(asset.instances))
    for i in asset.instances:
        for value in (i.geometry, i.name, i.unique_id, i.parent, i.inheritance):
            w.line(value)
        for transform in (i.local, i.pivot):
            w.transform(transform)
            if max(transform.scale) - min(transform.scale) > 1e-5:
                raise ValueError('ASS instance scale must be uniform; bake nonuniform scale into geometry')
            w.vector((transform.scale[0],))
        for bone in i.bones:
            w.line(bone)
