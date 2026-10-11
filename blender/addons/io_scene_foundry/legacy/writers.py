"""Text serializers for prepared legacy asset models; no Blender dependency.

Export trusts the prepared records. Format compatibility is checked in tests,
without validating the records or parsing the generated files during export.
"""
from ..exceptions import ExportCancelled
from dataclasses import replace


VERSIONS = {
    'halo1': (8200, None, 16392),
    'halo2': (8210, 2, 16395),
    'halo3': (8213, 7, 16395),
    'halo3odst': (8213, 7, 16395),
}


class TextWriter:
    def __init__(self, stream, quoted=False, decimal_places=None):
        self.stream, self.quoted = stream, quoted
        self.decimal_places = decimal_places
        precision = '%.10g' if decimal_places is None else f'%.{decimal_places}f'
        self.vector_formats = tuple('\t'.join([precision] * size) + '\n' for size in range(10))

    def line(self, value):
        if isinstance(value, str):
            if self.quoted:
                value = f'"{value}"'
            elif not value.strip():
                value = '<none>'
        self.stream.write(str(value) + '\n')

    def vector(self, values):
        values = tuple(values)
        if len(values) < len(self.vector_formats):
            self.stream.write(self.vector_formats[len(values)] % values)
        else:
            precision = '.10g' if self.decimal_places is None else f'.{self.decimal_places}f'
            self.stream.write('\t'.join(format(float(v), precision) for v in values) + '\n')

    def transform(self, value):
        self.vector(value.rotation)
        self.vector(value.translation)


def halo1_overlay_rotation(reference, rotation):
    """Convert reference*delta poses to the delta*reference poses H1 Tool expects.

    Inputs and result use the file's XYZW quaternion convention.
    """
    def multiply(a, b):
        x, y, z, w = a
        X, Y, Z, W = b
        return (w*X + x*W + y*Z - z*Y,
                w*Y - x*Z + y*W + z*X,
                w*Z + x*Y - y*X + z*W,
                w*W - x*X - y*Y - z*Z)
    norm = sum(v*v for v in reference)
    inverse = tuple((-v if i < 3 else v) / norm for i, v in enumerate(reference))
    return multiply(multiply(inverse, rotation), reference)


def halo1_overlay_pose(pose):
    """Adapt native reference*delta rotations to H1's delta*reference convention.

    Do this on import, so authored and imported actions share one convention
    and the JMO exporter can serialize their evaluated poses directly.
    """
    reference = pose['leading_frame']
    frames = []
    for frame in pose['frames']:
        if len(frame) != len(reference):
            raise ExportCancelled('H1 overlay reference and frame node counts differ')
        frames.append([
            (*node[:3], *halo1_overlay_rotation(base[3:7], node[3:7]), node[7])
            for base, node in zip(reference, frame)
        ])
    return {**pose, 'frames': frames}


def legacy_bone_order(parents):
    """Order names by hierarchy depth, then alphabetically, independent of Blender order."""
    depths = {}

    def depth(name):
        if name not in depths:
            parent = parents[name]
            depths[name] = depth(parent) + 1 if parent in parents else 0
        return depths[name]

    return sorted(parents, key=lambda name: (depth(name), name))


def hierarchy_children(nodes, halo1=False, maya_order=False):
    children = {}
    for index, node in enumerate(nodes):
        children.setdefault(node.parent, []).append(index)
    if halo1:
        # H1 defaults to reverse alphabetical traversal. Maya ordering
        # optionally prioritizes thighs and clavicles on biped skeletons.
        for parent, indices in children.items():
            indices.sort(key=lambda i: nodes[i].name, reverse=True)
            if maya_order and parent != -1:
                name = nodes[parent].name.lower()
                priority = 'thigh' if 'pelvis' in name else 'clavicle' if 'spine1' in name else None
                if priority:
                    indices.sort(key=lambda i: priority not in nodes[i].name.lower())
    return children


def hierarchy(nodes, halo1=False, maya_order=False):
    children = hierarchy_children(nodes, halo1, maya_order)
    result = [replace(n, child=-1, sibling=-1) for n in nodes]
    for parent, indices in children.items():
        if parent != -1:
            result[parent].child = indices[0]
        for first, second in zip(indices, indices[1:]):
            result[first].sibling = second
    return result


def node_checksum(nodes, halo1=False, maya_order=False):
    """Halo's ordered hierarchy hash, with 32-bit rotation at each branch."""
    def rotate(value, count):
        return ((value << count) | (value >> (32 - count))) & 0xffffffff
    children = hierarchy_children(nodes, halo1, maya_order)
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


def write_jms(asset, stream, *, maya_order=False):
    """Write the game-selected H1, H2 or H3 dialect, without mutating the asset."""
    v = asset.version
    if v not in range(8197, 8214):
        raise ExportCancelled(f'Unsupported JMS output version {v}')
    nodes = hierarchy(asset.nodes, halo1=v < 8205, maya_order=maya_order)
    w = TextWriter(stream)
    w.line(v)
    if v < 8205:
        if asset.shapes or asset.constraints or (v < 8201 and (asset.xrefs or asset.instances)):
            raise ExportCancelled(f'JMS {v} cannot represent these physics or instance records')
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
        if 8202 <= v <= 8204:
            w.line(m.texture or '<none>')
        w.line(m.definition or '<none>')
    w.line(len(asset.markers))
    for m in asset.markers:
        w.line(m.name)
        if 8198 <= v < 8205:
            w.line(m.region)
        w.line(m.parent)
        w.transform(m.transform)
        if v >= 8200:
            w.vector((m.radius,))
    if v >= 8201:
        w.line(len(asset.xrefs))
        for path, name in asset.xrefs:
            w.line(path)
            if v >= 8208:
                w.line(name)
        w.line(len(asset.instances))
        for name, uid, xref, transform in asset.instances:
            for value in ((name, uid, xref) if v >= 8203 else (name, xref)):
                w.line(value)
            w.transform(transform)
    if v < 8205:
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
            max_influences = 4 if v == 8204 else 2
            if len(weights) > max_influences:
                raise ExportCancelled(f'JMS {v} supports at most {max_influences} influences per vertex')
            weights += [(-1, 0)] * (max_influences - len(weights))
            if v == 8197:
                w.line(vertex.region)
            w.line(weights[0][0])
            if v == 8204:
                w.vector((weights[0][1],))
            w.vector(vertex.position)
            w.vector(vertex.normal)
            w.line(weights[1][0])
            w.vector((weights[1][1],))
            if v == 8204:
                for index, weight in weights[2:]:
                    w.line(index)
                    w.vector((weight,))
            for index in range(4 if v >= 8202 else 1):
                w.vector(vertex.uvs[index][:2] if index < len(vertex.uvs) else (0, 0))
            if v >= 8199:
                w.line(0)
    w.line(len(asset.triangles))
    for t in asset.triangles:
        if 8198 <= v < 8205:
            w.line(t.region)
        w.line(t.material)
        for i in t.vertices:
            w.line(i)
    if v >= 8206:
        for kind in ('sphere', 'box', 'pill', 'convex'):
            shapes = [s for s in asset.shapes if s.kind == kind]
            w.line(len(shapes))
            for s in shapes:
                for value in ((s.name, s.parent, s.material) if v >= 8207 else (s.name, s.parent)):
                    w.line(value)
                w.transform(s.transform)
                if s.dimensions:
                    w.vector(s.dimensions)
                if kind == 'convex':
                    w.line(len(s.vertices))
                    for p in s.vertices:
                        w.vector(p)
        for kind in ('ragdoll', 'hinge', 'car_wheel', 'point_to_point', 'prismatic'):
            if v < 8210 and kind in {'car_wheel', 'point_to_point', 'prismatic'}:
                if any(c.kind == kind for c in asset.constraints):
                    raise ExportCancelled(f'JMS {v} cannot represent {kind} constraints')
                continue
            constraints = [c for c in asset.constraints if c.kind == kind]
            w.line(len(constraints))
            for c in constraints:
                for value in (c.name, c.parent, c.child):
                    w.line(value)
                w.transform(c.parent_transform)
                w.transform(c.child_transform)
                w.vector(c.limits[:6] if kind == 'ragdoll' and v < 8213 else c.limits)
        if v >= 8209:
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


def write_ass(asset, stream, *, decimal_places=None):
    if asset.version not in range(1, 8):
        raise ExportCancelled(f'Unsupported ASS output version {asset.version}')
    w = TextWriter(stream, quoted=True, decimal_places=decimal_places)
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
        elif g.kind == 'GENERIC_LIGHT':
            if g.light is None:
                raise ExportCancelled('ASS generic light geometry has no light data')
            light = g.light
            w.line(light.kind)
            w.vector(light.color)
            for value in (
                    light.intensity, light.hotspot, light.falloff,
                    light.near_enabled, light.near_start, light.near_end,
                    light.far_enabled, light.far_start, light.far_end,
                    light.shape, light.aspect):
                w.line(value)
        else:
            raise ExportCancelled(f'Unsupported ASS output geometry {g.kind}')
    w.line(len(asset.instances))
    for i in asset.instances:
        for value in (i.geometry, i.name, i.unique_id, i.parent, i.inheritance):
            w.line(value)
        for transform in (i.local, i.pivot):
            w.transform(transform)
            w.vector(transform.scale if asset.version == 1 else (transform.scale[0],))
        for bone in i.bones:
            w.line(bone)
