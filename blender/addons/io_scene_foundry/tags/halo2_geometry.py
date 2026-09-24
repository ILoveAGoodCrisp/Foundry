"""Resolve H2 render-leaf references to the surface mappings used by H3.

References name an index-buffer offset and a BSP3D node, NOT a collision
surface. The parallel collision leaf supplies BSP2D trees for that node's
plane. Only those trees' surfaces may own the referenced render triangle.
"""
from collections import defaultdict
from math import isclose

from .classic_geometry import _area, _subtract
from .prefab import StructureBspSurfaceMapping


def _strip_faces(doc, section, mesh):
    """Keep original strip offsets while accounting for skipped degenerates.

    The native scene expands triangles, so neither strip offsets nor lightmap
    triangle indices can be used directly as Blender polygon indices.
    """
    vertices = [tuple(doc.value(v, 'position').to_array())
                for v in doc.block(section, 'raw vertices')]
    indices = [int(doc.value(i, 'index')) & 0xffff
               for i in doc.block(section, 'strip indices')]
    offsets = {}
    face = 0
    for part in doc.block(section, 'parts'):
        start = int(doc.value(part, 'strip start index')) & 0xffff
        count = int(doc.value(part, 'strip length')) & 0xffff
        triangle_list = part.field('flags').get_flag('override triangle list')
        if start + count > len(indices):
            raise ValueError('Halo 2 render part has an invalid strip range')
        for offset in range(start, start + count - 2, 3 if triangle_list else 1):
            tri = indices[offset:offset + 3]
            if len(set(tri)) != 3 or 0xffff in tri:
                continue
            if any(i >= len(vertices) for i in tri):
                raise ValueError('Halo 2 render strip vertex is out of range')
            # Validate native decoding order before consuming authoritative IDs.
            native = mesh.indices[face * 3:face * 3 + 3]
            if len(native) != 3 or not all(any(
                    all(isclose(a, b, rel_tol=1e-6, abs_tol=1e-5) for a, b in zip(vertices[i], mesh.positions[j]))
                    for j in native) for i in tri):
                raise ValueError(f'Halo 2 native mesh {mesh.index} triangle {face} does not match strip offset {offset}')
            offsets[offset] = face
            face += 1
    if face * 3 != len(mesh.indices):
        raise ValueError('Halo 2 native triangle count does not match the source strips')
    return offsets


def surface_mappings(doc, owner, collision, meshes, sections, *, leaves_name='leaves'):
    """Return detached collision data and explicit (triangle, section) pairs."""
    record = doc._collision_bsp(collision, large=False, label='Halo 2 collision')
    render_leaves = doc.block(owner, leaves_name)
    collision_leaves = doc.block(collision, 'leaves')
    references = doc.block(owner, 'surface references')
    nodes = doc.block(collision, 'bsp3d nodes')
    planes = doc.block(collision, 'planes')
    refs2d = doc.block(collision, 'bsp2d references')
    nodes2d = doc.block(collision, 'bsp2d nodes')
    if len(render_leaves) != len(collision_leaves):
        raise ValueError('Halo 2 render and collision leaf counts differ')
    strip_faces = {index: _strip_faces(doc, sections[index], mesh) for index, mesh in meshes.items()}
    strip_counts = {index: len(doc.block(section, 'strip indices')) for index, section in sections.items()}
    surface_sets = {}

    def surfaces_for_node(root):
        root &= 0xffff
        if root in surface_sets:
            return surface_sets[root]
        pending, visited, result = [root], set(), set()
        while pending:
            node = pending.pop()
            if node == 0xffff or node in visited:
                continue
            visited.add(node)
            if node & 0x8000:
                index = node & 0x7fff
                if index >= len(record.surfaces):
                    raise ValueError('Halo 2 BSP2D surface is out of range')
                result.add(index)
            else:
                if node >= len(nodes2d):
                    raise ValueError('Halo 2 BSP2D node is out of range')
                pending.extend(int(doc.value(nodes2d[node], side)) & 0xffff
                               for side in ('left child', 'right child'))
        surface_sets[root] = result
        return result

    mappings = [set() for _ in record.surfaces]
    tested = set()
    for leaf_index, leaf in enumerate(render_leaves):
        section = int(doc.value(leaf, 'cluster')) if leaves_name == 'leaves' else next(iter(meshes), -1)
        if section not in meshes:
            continue
        first = int(doc.value(leaf, 'first surface reference index'))
        count = int(doc.value(leaf, 'surface reference count')) & 0xffff
        if first < 0 or first + count > len(references):
            if not count:
                continue
            raise ValueError('Halo 2 render leaf has an invalid surface reference range')
        collision_leaf = collision_leaves[leaf_index]
        first2d = int(doc.value(collision_leaf, 'first bsp2d reference')) & 0xffff
        count2d = int(doc.value(collision_leaf, 'bsp2d reference count')) & 0xff
        if count2d and first2d + count2d > len(refs2d):
            raise ValueError('Halo 2 collision leaf has an invalid BSP2D range')
        by_plane = defaultdict(set)
        for i in range(first2d, first2d + count2d):
            ref = refs2d[i]
            by_plane[int(doc.value(ref, 'plane')) & 0x7fff].update(
                surfaces_for_node(int(doc.value(ref, 'bsp2d node'))))
        for i in range(first, first + count):
            ref = references[i]
            node_index = int(doc.value(ref, 'bsp node index'))
            if node_index == -1:
                continue  # Explicitly not attached to a collision splitter.
            if not 0 <= node_index < len(nodes):
                raise ValueError('Halo 2 surface reference BSP3D node is out of range')
            raw = nodes[node_index].raw_bytes
            if len(raw) != 8:
                raise ValueError('Unsupported Halo 2 packed BSP3D node')
            plane_index = int.from_bytes(raw[:2], 'little') & 0x7fff
            if plane_index >= len(planes):
                raise ValueError('Halo 2 BSP3D plane is out of range')
            offset = int(doc.value(ref, 'strip index')) & 0xffff
            if offset + 2 >= strip_counts[section]:
                raise ValueError('Halo 2 surface reference strip offset is out of range')
            face = strip_faces[section].get(offset)
            if face is None:
                continue  # Degenerate strip connector, not an emitted triangle.
            value = doc.value(planes[plane_index], 'plane')
            plane = (value.i, value.j, value.k, value.d)
            drop = max(range(3), key=lambda axis: abs(plane[axis]))
            axes = [axis for axis in range(3) if axis != drop]
            mesh = meshes[section]
            triangle = [tuple(mesh.positions[v][a] for a in axes)
                        for v in mesh.indices[face * 3:face * 3 + 3]]
            for surface in by_plane[plane_index]:
                key = (section, face, surface)
                if key in tested or record.surfaces[surface].invalid:
                    continue
                tested.add(key)
                polygon = [tuple(record.vertices[v][a] for a in axes) for v in record.polygons[surface]]
                # BSP leaves/planes identify the candidates. The projected
                # intersection selects the owning surface within that leaf;
                # no normal/plane-distance heuristic overrides the tag links.
                _, intersection = _subtract(triangle, polygon)
                if intersection and _area(intersection) > max(1e-12, _area(triangle) * 1e-7):
                    mappings[surface].add((face, section))
    return record, [StructureBspSurfaceMapping(i, (), tuple(sorted(pairs)))
                    for i, pairs in enumerate(mappings)]


def bsp_mappings(doc, meshes, instances):
    """Resolve native scene mesh IDs to cluster/instance mapping groups."""
    root = doc.tag.root()
    clusters = doc.block(root, 'clusters')
    cluster_instances = {i['name']: i for i in instances if i['mesh_type'] == 'render'
                         and i['name'].startswith('cluster_') and i['object_index'] >= 0}
    cluster_meshes, sections, source_ids = {}, {}, {}
    for index, cluster in enumerate(clusters):
        instance = cluster_instances.get(f'cluster_{index}')
        if instance is None:
            continue  # Empty clusters are omitted by the native extractor.
        source = instance['object_index']
        data = doc.block(cluster, 'cluster data')
        if not len(data):
            raise ValueError('Halo 2 cluster has no editable render data')
        cluster_meshes[index] = meshes[source]
        sections[index] = data[0].field('section').as_struct()
        source_ids[index] = source
    groups = []
    collisions = doc.block(root, 'collision bsp')
    if len(collisions) > 1:
        raise ValueError('Halo 2 BSP contains multiple structure collision trees')
    if len(collisions):
        record, mappings = surface_mappings(doc, root, collisions[0], cluster_meshes, sections)
        groups.append((record, mappings, source_ids, True))
    native_instances = [i for i in instances if i['mesh_type'] == 'render' and i['object_index'] >= 0
                        and i['object_index'] not in source_ids.values()]
    placements = list(doc.block(root, 'instanced geometry instances'))
    if len(native_instances) != len(placements):
        raise ValueError('Halo 2 native instance placements do not match tag placements')
    definitions = doc.block(root, 'instanced geometries definitions')
    seen = set()
    for native, placement in zip(native_instances, placements):
        definition_index = int(doc.value(placement, 'instance definition'))
        source = native['object_index']
        if (definition_index, source) in seen:
            continue
        seen.add((definition_index, source))
        if not 0 <= definition_index < len(definitions):
            raise ValueError('Halo 2 instance definition is out of range')
        definition = definitions[definition_index]
        info = definition.field('render info').as_struct()
        data = doc.block(info, 'render data')
        if not len(data):
            raise ValueError('Halo 2 instance has no editable render data')
        record, mappings = surface_mappings(
            doc, definition, definition.field('collision info').as_struct(),
            {0: meshes[source]}, {0: data[0].field('section').as_struct()}, leaves_name='render leaves')
        groups.append((record, mappings, {0: source}, False))
    return groups
