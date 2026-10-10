"""Read H1 compiled render streams without routing them through lossy JMS.

Structured fields use the native tag API; vertex data remains little endian.
Source surface IDs refer to the BSP's global triangle table, not collision
surfaces. Cluster ownership is many-to-many and is retained separately.
"""
from __future__ import annotations

import numpy as np


def packed_vectors(values):
    values = np.asarray(values, dtype=np.uint32)
    components = []
    for shift, width in ((0, 11), (11, 11), (22, 10)):
        mask = (1 << width) - 1
        signed = ((values >> shift) & mask).astype(np.int32)
        signed = np.where(signed & (1 << (width - 1)), signed - (1 << width), signed)
        components.append((signed * 2.0 + 1.0) / mask)
    return np.column_stack(components)


def vertex_streams(uncompressed, compressed, rendered_count, lighting_count, label):
    """Prefer complete floats, then complete packed data; never silently trim."""
    nr, nl = rendered_count, lighting_count
    if nr < 0 or nl not in (0, nr):
        raise ValueError(f'{label}: invalid rendered/lighting vertex counts {nr}/{nl}')
    if len(uncompressed) >= nr * 56 + nl * 20:
        render = np.frombuffer(uncompressed, dtype='<f4', count=nr * 14).reshape(nr, 14)
        lighting = np.frombuffer(uncompressed, dtype='<f4', count=nl * 5,
                                 offset=nr * 56).reshape(nl, 5)
        streams = dict(positions=render[:, :3], normals=render[:, 3:6],
                       binormals=render[:, 6:9], tangents=render[:, 9:12],
                       texcoords=render[:, 12:14], lightmap_normals=lighting[:, :3],
                       lightmap_texcoords=lighting[:, 3:5], encoding='uncompressed')
    elif len(compressed) >= nr * 32 + nl * 8:
        render_type = np.dtype([('position', '<f4', 3), ('normal', '<u4'),
                                ('binormal', '<u4'), ('tangent', '<u4'), ('uv', '<f4', 2)])
        light_type = np.dtype([('normal', '<u4'), ('uv', '<i2', 2)])
        render = np.frombuffer(compressed, dtype=render_type, count=nr)
        lighting = np.frombuffer(compressed, dtype=light_type, count=nl, offset=nr * 32)
        streams = dict(positions=render['position'], normals=packed_vectors(render['normal']),
                       binormals=packed_vectors(render['binormal']),
                       tangents=packed_vectors(render['tangent']), texcoords=render['uv'],
                       lightmap_normals=packed_vectors(lighting['normal']),
                       lightmap_texcoords=(lighting['uv'].astype(float) * 2 + 1) / 65535,
                       encoding='compressed')
    else:
        raise ValueError(f'{label}: incomplete vertex streams; need {nr * 56 + nl * 20} '
                         f'uncompressed or {nr * 32 + nl * 8} compressed bytes, got '
                         f'{len(uncompressed)}/{len(compressed)}')
    for name, values in streams.items():
        if name != 'encoding' and not np.isfinite(values).all():
            raise ValueError(f'{label}: non-finite {name}')
    if not nl:
        streams['lightmap_texcoords'] = np.zeros((nr, 2))
        streams['lightmap_normals'] = np.zeros((nr, 3))
    streams['has_lightmap_uvs'] = bool(nl)
    return streams


def render_scene(document, *, import_collision=True):
    """Return the classic scene contract with complete H1 render metadata.

    Uses the low-level native field API, so existing bundled wheels can expose
    both packed streams and full shader references without a native rebuild.
    """
    root = document.tag.root()
    surfaces = list(document.block(root, 'surfaces'))
    triangles = [tuple(int(document.value(s, f'vertex{i} index')) & 0xffff
                       for i in range(3)) for s in surfaces]
    memberships = [set() for _ in surfaces]
    references = list(document.block(root, 'leaf surfaces'))
    cluster_count = len(document.block(root, 'clusters'))
    for leaf_index, leaf in enumerate(document.block(root, 'leaves')):
        cluster = int(document.value(leaf, 'cluster'))
        first = int(document.value(leaf, 'surface references'))
        count = int(document.value(leaf, 'surface reference count'))
        if count == 0:
            continue
        if first < 0 or count < 0 or first + count > len(references):
            raise ValueError(f'{document.path}: leaf {leaf_index} has invalid surface references')
        if cluster == -1:
            continue
        if not 0 <= cluster < cluster_count:
            raise ValueError(f'{document.path}: leaf {leaf_index} has invalid cluster {cluster}')
        for reference in references[first:first + count]:
            surface = int(document.value(reference, 'surface'))
            if not 0 <= surface < len(surfaces):
                raise ValueError(f'{document.path}: leaf {leaf_index} references surface {surface}')
            memberships[surface].add(cluster)

    names, paths, slots = [], [], {}

    def slot(name, path):
        key = path.replace('/', '\\').casefold() if path else f'__missing__:{name}'
        if key not in slots:
            slots[key] = len(names)
            names.append(name)
            paths.append(path)
        return slots[key]

    mesh = {key: [] for key in ('positions', 'normals', 'binormals', 'tangents', 'texcoords',
                                'lightmap_normals', 'lightmap_texcoords', 'indices', 'parts')}
    source = {key: [] for key in ('vertex_index', 'vertex_lightmap', 'vertex_material',
                                  'surface', 'lightmap', 'material', 'bitmap', 'spans')}
    mesh['has_lightmap_uvs'] = False
    for li, lightmap in enumerate(document.block(root, 'lightmaps')):
        for mi, material in enumerate(document.block(lightmap, 'materials')):
            label = f'{document.path}: lightmap {li}, material {mi}'
            nr = int(document.value(document.required_field(material, 'rendered vertices').as_struct(), 'vertex count'))
            nl = int(document.value(document.required_field(material, 'lightmap vertices').as_struct(), 'vertex count'))
            streams = vertex_streams(document.required_field(material, 'uncompressed vertices').as_data(),
                                     document.required_field(material, 'compressed vertices').as_data(),
                                     nr, nl, label)
            base = len(mesh['positions'])
            for key in ('positions', 'normals', 'binormals', 'tangents', 'texcoords',
                        'lightmap_normals', 'lightmap_texcoords'):
                mesh[key].extend(streams[key].tolist())
            mesh['has_lightmap_uvs'] |= streams['has_lightmap_uvs']
            reference = document.reference(material, 'shader')
            path = reference.RelativePathWithExtension if reference else ''
            material_slot = slot(reference.ShortName if reference else 'default', path)
            first, count = (int(document.value(material, key)) for key in ('surfaces', 'surface count'))
            if first < 0 or count < 0 or first + count > len(triangles):
                raise ValueError(f'{label}: invalid surface span {first}+{count}')
            index_start = len(mesh['indices'])
            for si in range(first, first + count):
                if any(v >= nr for v in triangles[si]):
                    raise ValueError(f'{label}: surface {si} references a vertex outside 0..{nr - 1}')
                mesh['indices'].extend(base + v for v in triangles[si])
                for key, value in (('surface', si), ('lightmap', li), ('material', mi),
                                   ('bitmap', int(document.value(lightmap, 'bitmap')))):
                    source[key].append(value)
            mesh['parts'].append(dict(material_index=material_slot, index_start=index_start,
                                      index_count=count * 3, part_type=0))
            source['vertex_index'].extend(range(nr))
            source['vertex_lightmap'].extend([li] * nr)
            source['vertex_material'].extend([mi] * nr)
            source['spans'].append(dict(lightmap=li, material=mi, vertex_start=base,
                                        vertex_count=nr, lighting_count=nl, first_surface=first,
                                        surface_count=count, encoding=streams['encoding']))
    mesh['node_indices'] = [(-1, -1, -1, -1)] * len(mesh['positions'])
    mesh['node_weights'] = [(0., 0., 0., 0.)] * len(mesh['positions'])
    mesh['vertex_colors'] = [(0., 0., 0.)] * len(mesh['positions'])
    mesh['rigid_node_index'] = None
    source['cluster_memberships'] = [sorted(m) for m in memberships]
    source['lightmap_bitmap'] = ''
    reference = document.reference(root, 'lightmaps bitmap')
    if reference:
        source['lightmap_bitmap'] = reference.RelativePathWithExtension
    source['tag_path'] = str(document.path)
    mesh['halo1_source'] = source

    objects, instances = [mesh], [dict(object_index=0, name='render_geometry',
                                     rotation=(0., 0., 0., 1.), translation=(0., 0., 0.),
                                     scale=1., mesh_type='render', reference='')]
    if not import_collision:
        return dict(materials=names, material_paths=paths, objects=objects, instances=instances)
    # Collision indices belong to edge rings, not the render triangle table.
    collision_slots = [slot(reference.ShortName if reference else 'default',
                            reference.RelativePathWithExtension if reference else '')
                       for m in document.block(root, 'collision materials')
                       for reference in [document.reference(m, 'shader')]]
    collision = {key: [] for key in ('positions', 'normals', 'texcoords', 'indices', 'parts')}
    collision_source = dict(collision_surface=[], collision_bsp=[], rings=[], tag_path=str(document.path))
    for bi, bsp in enumerate(document.block(root, 'collision bsp')):
        vertices = [tuple(document.value(v, 'point').to_array()) for v in document.block(bsp, 'vertices')]
        planes = [document.value(p, 'plane') for p in document.block(bsp, 'planes')]
        if not np.isfinite(np.asarray(vertices)).all():
            raise ValueError(f'{document.path}: collision BSP {bi} has non-finite vertices')
        edges = [tuple(int(document.value(e, k)) for k in ('start vertex', 'end vertex',
                  'forward edge', 'reverse edge', 'left surface', 'right surface'))
                 for e in document.block(bsp, 'edges')]
        for si, surface in enumerate(document.block(bsp, 'surfaces')):
            label = f'{document.path}: collision BSP {bi}, surface {si}'
            first = current = int(document.value(surface, 'first edge'))
            visited, ring = set(), []
            while 0 <= current < len(edges) and current not in visited:
                visited.add(current)
                a, b, forward, reverse, left, right = edges[current]
                if left == si:
                    vertex, current = a, forward
                elif right == si:
                    vertex, current = b, reverse
                else:
                    break
                if not 0 <= vertex < len(vertices):
                    raise ValueError(f'{label}: invalid ring vertex {vertex}')
                ring.append(vertex)
                if current == first:
                    break
            if current != first or len(ring) < 3:
                raise ValueError(f'{label}: invalid collision edge ring')
            designation = int(document.value(surface, 'plane')) & 0xffffffff
            pi = designation & 0x7fffffff
            if pi >= len(planes):
                raise ValueError(f'{label}: invalid plane {pi}')
            plane = planes[pi]
            sign = -1 if designation & 0x80000000 else 1
            normal = tuple(sign * v for v in (plane.i, plane.j, plane.k))
            base = len(collision['positions'])
            collision['positions'].extend(vertices[v] for v in ring)
            collision['normals'].extend([normal] * len(ring))
            collision['texcoords'].extend([(0., 0.)] * len(ring))
            start = len(collision['indices'])
            for i in range(1, len(ring) - 1):
                collision['indices'].extend((base, base + i, base + i + 1))
                collision_source['collision_surface'].append(si)
                collision_source['collision_bsp'].append(bi)
            mi = int(document.value(surface, 'material'))
            if mi < -1 or mi >= len(collision_slots):
                raise ValueError(f'{label}: invalid material {mi}')
            material_slot = slot('default', '') if mi == -1 else collision_slots[mi]
            if collision['parts'] and collision['parts'][-1]['material_index'] == material_slot:
                collision['parts'][-1]['index_count'] += len(collision['indices']) - start
            else:
                collision['parts'].append(dict(material_index=material_slot, index_start=start,
                                              index_count=len(collision['indices']) - start, part_type=0))
            collision_source['rings'].append(dict(bsp=bi, surface=si, vertices=ring,
                                                  plane=designation, material=mi))
    if collision['indices']:
        count = len(collision['positions'])
        collision.update(node_indices=[(-1,) * 4] * count, node_weights=[(0.,) * 4] * count,
                         lightmap_texcoords=[(0., 0.)] * count, vertex_colors=[(0.,) * 3] * count,
                         rigid_node_index=None, halo1_source=collision_source)
        objects.append(collision)
        instances.append(dict(instances[0], object_index=1, name='@CollideOnly', mesh_type='collision'))
    return dict(materials=names, material_paths=paths, objects=objects, instances=instances)
