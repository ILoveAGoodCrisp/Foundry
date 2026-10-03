"""Halo 1 BSP auxiliary geometry and surface annotations."""
import bmesh
import bpy
import numpy as np
import json
from itertools import combinations
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

from .. import import_transform, utils
from ..tools.append_foundry_materials import ensure_special_material
from ..tools.materials import sky as sky_material_definition, seamsealer
from .connected_geometry import StructureMarker
from .backend import TagDocument


def attach_source_attributes(mesh, record):
    """Keep compiled provenance in preservation imports without altering it."""
    source = record.halo1_source
    if not source:
        return
    point_keys = ('vertex_index', 'vertex_lightmap', 'vertex_material')
    face_keys = ('surface', 'lightmap', 'material', 'bitmap', 'collision_surface', 'collision_bsp')
    for domain, keys in (('POINT', point_keys), ('FACE', face_keys)):
        for key in keys:
            if key not in source:
                continue
            attribute = mesh.attributes.new(f'halo1_source_{key}', 'INT', domain)
            if len(attribute.data) != len(source[key]):
                raise ValueError(f'{mesh.name}: compiled {key} count changed during import')
            attribute.data.foreach_set('value', source[key])
    loop_indices = np.empty(len(mesh.loops), dtype=np.int32)
    mesh.loops.foreach_get('vertex_index', loop_indices)
    for key in ('tangents', 'binormals', 'lightmap_normals'):
        values = getattr(record, key)
        if not values:
            continue
        attribute = mesh.attributes.new(f'halo1_source_{key}', 'FLOAT_VECTOR', 'CORNER')
        attribute.data.foreach_set('vector', np.asarray(values, dtype=np.float32)[loop_indices].ravel())
    for key in ('spans', 'cluster_memberships', 'rings'):
        if key in source:
            mesh[f'halo1_source_{key}'] = json.dumps(source[key], separators=(',', ':'))
    mesh['halo1_source_tag'] = source['tag_path']
    mesh['halo1_source_lightmap_bitmap'] = source.get('lightmap_bitmap', '')
    mesh['halo1_preserved'] = True


def material(name):
    return bpy.data.materials.get(name) or bpy.data.materials.new(name)


def plane_values(plane):
    return plane.i, plane.j, plane.k, plane.d


def shader_alpha_tested(shader):
    """Read the shader checkbox, not radiosity's unrelated transparent-lit flag."""
    field = shader.tag.root().field('properties')
    properties = field.as_struct() if field is not None else None
    if properties is None:
        return False
    for name in ('flags', 'shader transparent glass flags'):
        flags = properties.field(name)
        if flags is not None:
            try:
                return flags.get_flag('alpha tested')
            except KeyError:
                pass
    return False


def apply_shader_transparency(tag, objects):
    """Assign per-face transparency from H1 BSP material shaders, once per path."""
    cache, seen = {}, set()
    for ob in objects:
        if ob.type != 'MESH' or ob.data in seen:
            continue
        mesh = ob.data
        seen.add(mesh)
        transparent_slots = set()
        for index, mat in enumerate(mesh.materials):
            path = mat.nwo.shader_path if mat is not None else ''
            if not path:
                continue
            key = path.replace('/', '\\').casefold()
            if key not in cache:
                cache[key] = False
                try:
                    with TagDocument(path, tags_root=tag.tags_root, game='halo1',
                                     definitions=tag.definitions, must_exist=True) as shader:
                        cache[key] = shader_alpha_tested(shader)
                except OSError as error:
                    utils.print_warning(f'Cannot read H1 shader transparency for {path}: {error}')
            if cache[key]:
                transparent_slots.add(index)
        mask = np.array([f.material_index in transparent_slots for f in mesh.polygons], dtype=bool)
        if mask.any():
            prop = utils.add_face_prop(mesh, 'transparent', mask)
            prop.transparent = True
            utils.calc_face_prop_counts(mesh)


def fog_geometry(vertices, face):
    """Avoid thin ears when tessellating compiled H1 fog outlines.

    Compiled boundaries contain almost-collinear clipping vertices. Blender's
    ngon tessellation can make slivers from these, causing H1 Tool to generate
    an extra fog plane and fail during PVS construction. A center fan retains
    every boundary vertex without those ears. Only use it when the center is
    strictly inside every oriented edge; otherwise preserve the input polygon.
    """
    if len(face) <= 3:
        return vertices, [face]
    points = np.asarray([vertices[i] for i in face], dtype=np.float64)
    center = points.mean(axis=0)
    relative = points - center
    edges = np.roll(points, -1, axis=0) - points
    normal = np.cross(relative, np.roll(relative, -1, axis=0)).sum(axis=0)
    length = np.linalg.norm(normal)
    if length <= 1e-12:
        return vertices, [face]
    normal /= length
    if (np.max(np.abs(relative @ normal)) > 0.0001 or
            np.any(np.cross(edges, center - points) @ normal <= 1e-12)):
        return vertices, [face]
    center_index = len(vertices)
    return [*vertices, tuple(center)], [
        [a, b, center_index] for a, b in zip(face, face[1:] + face[:1])]


def weather_vertices(planes):
    """Intersect inward weather planes in double precision before building a hull."""
    planes = np.asarray(planes, dtype=np.float64)
    if len(planes) < 4:
        return []
    normals, distances = planes[:, :3], planes[:, 3]
    vertices = []
    for indices in combinations(range(len(planes)), 3):
        matrix = normals[list(indices)]
        if abs(np.linalg.det(matrix)) < 1e-10:
            continue
        point = np.linalg.solve(matrix, distances[list(indices)])
        if np.any(normals @ point < distances - 1e-7):
            continue
        if not any(np.linalg.norm(point - existing) <= 0.0001 for existing in vertices):
            vertices.append(point)
    # Redundant, almost parallel planes also introduce points along an edge,
    # rather than at its endpoints. Remove those before float32 hull creation.
    # Recheck every removed point against surviving segments to bound drift.
    def on_segment(point, points):
        for a, b in combinations(points, 2):
            delta = b - a
            fraction = float((point - a) @ delta) / float(delta @ delta)
            if (0 < fraction < 1 and
                    np.linalg.norm(point - a - fraction*delta) <= 0.0001):
                return True
        return False

    remaining, removed = list(vertices), []
    for point in vertices:
        if len(remaining) <= 4:
            break
        candidates = [other for other in remaining if other is not point]
        if all(on_segment(old, candidates) for old in [point, *removed]):
            remaining = candidates
            removed.append(point)
    return remaining


def collision_point_is_solid(tag):
    """Classify tag-space points without confusing unknown leaves with solid."""
    from .collision_solid import CollisionSolidQuery
    bsps = list(tag.block(tag.tag.root(), 'collision bsp'))
    if not bsps:
        return lambda point: False
    bsp = bsps[0]
    planes = [plane_values(tag.value(p, 'plane')) for p in tag.block(bsp, 'planes')]
    nodes = [tuple(int(tag.value(n, field)) for field in ('plane', 'back child', 'front child'))
             for n in tag.block(bsp, 'bsp3d nodes')]

    # H1 render leaves reference the collision tree's empty leaves. Do not use
    # this correspondence for a malformed or mismatched block.
    leaves = [int(tag.value(leaf, 'cluster')) for leaf in tag.block(tag.tag.root(), 'leaves')]
    if len(leaves) != len(list(tag.block(bsp, 'leaves'))):
        leaves = ()
    return CollisionSolidQuery(planes, nodes, leaves)


def cluster_sky_lookup(tag):
    """Locate a point through the collision BSP; render leaves share its indices."""
    root = tag.tag.root()
    skies = [int(tag.value(c, 'sky')) for c in tag.block(root, 'clusters')]
    leaves = [int(tag.value(leaf, 'cluster')) for leaf in tag.block(root, 'leaves')]
    bsps = list(tag.block(root, 'collision bsp'))
    if not bsps:
        return lambda point: skies[0] if len(skies) == 1 else None
    bsp = bsps[0]
    planes = [plane_values(tag.value(p, 'plane')) for p in tag.block(bsp, 'planes')]
    nodes = [tuple(int(tag.value(n, field)) for field in ('plane', 'back child', 'front child'))
             for n in tag.block(bsp, 'bsp3d nodes')]

    def lookup(point):
        index = 0
        for _ in range(len(nodes) + 1):
            index &= 0xffffffff
            if index == 0xffffffff:
                return None  # Solid space.
            if index & 0x80000000:
                leaf = index & 0x7fffffff
                cluster = leaves[leaf] if leaf < len(leaves) else -1
                return skies[cluster] if 0 <= cluster < len(skies) else None
            if index >= len(nodes):
                return None
            plane_index, back, front = nodes[index]
            if not 0 <= plane_index < len(planes):
                return None
            x, y, z, distance = planes[plane_index]
            index = front if x*point.x + y*point.y + z*point.z >= distance else back
        return None
    return lookup


def replace_collision_only(objects, tag=None):
    """Use each collision shell face's adjacent cluster to select its material."""
    lookup = cluster_sky_lookup(tag) if tag is not None else lambda point: 0
    to_tag = import_transform.transform_matrix(Matrix.Scale(100, 4)).inverted_safe() if tag is not None else Matrix.Identity(4)
    unresolved = 0
    for ob in objects:
        if ob.type != 'MESH':
            continue
        mesh = ob.data
        local_to_tag = to_tag @ ob.matrix_world
        for index in reversed(range(len(mesh.nwo.face_props))):
            prop = mesh.nwo.face_props[index]
            if prop.type != 'face_mode' or prop.face_mode != 'collision_only':
                continue
            attribute = mesh.attributes.get(prop.attribute_name)
            if attribute is None:
                continue
            mask = np.empty(len(mesh.polygons), dtype=np.int32)
            attribute.data.foreach_get('value', mask)
            for face in mesh.polygons:
                if mask[face.index]:
                    # The native decoder uses an untextured "default" slot
                    # for material-less shell surfaces. Other unmatched
                    # collision faces (ramps, covers, player blockers) must
                    # retain both their shader and Collision Only property.
                    source_material = (mesh.materials[face.material_index]
                                       if mesh.materials else None)
                    if source_material is not None and (
                            source_material.nwo.shader_path or
                            source_material.name.split('.')[0] != 'default'):
                        continue
                    points = [local_to_tag @ mesh.vertices[v].co for v in face.vertices]
                    center = sum(points, Vector()) / len(points)
                    normal = (points[1] - points[0]).cross(points[2] - points[0]).normalized()
                    # Probe off the boundary into the adjacent non-solid leaf.
                    sky_index = lookup(center + normal * 0.00025)
                    if sky_index is None:
                        sky_index = lookup(center - normal * 0.00025)
                    if sky_index is None:
                        sky_index = lookup(center)
                    if sky_index is None:
                        unresolved += 1
                    definition = seamsealer if sky_index == -1 else sky_material_definition
                    mat = ensure_special_material(definition)
                    slot = next((i for i, existing in enumerate(mesh.materials) if existing == mat), None)
                    if slot is None:
                        slot = len(mesh.materials)
                        mesh.materials.append(mat)
                    face.material_index = slot
                    mask[face.index] = 0
            if mask.any():
                attribute.data.foreach_set('value', mask)
            else:
                mesh.attributes.remove(attribute)
                mesh.nwo.face_props.remove(index)
        utils.calc_face_prop_counts(mesh)
    # if unresolved:
    #     utils.print_warning(f'Could not resolve clusters for {unresolved} H1 shell faces; kept +sky fallback')


def apply_collision_surface_flags(tag, objects):
    """Transfer explicit H1 collision flags to the final imported faces."""
    root = tag.tag.root()
    indices = {int(tag.value(entry, 'collision surface index'))
               for entry in tag.block(root, 'breakable surfaces')}
    bsps = list(tag.block(root, 'collision bsp'))
    if not bsps:
        if indices:
            utils.print_warning('H1 breakable surfaces reference a missing collision BSP')
        return
    bsp = bsps[0]
    vertices = [Vector(tag.value(v, 'point').to_array()) * 100
                for v in tag.block(bsp, 'vertices')]
    transform = import_transform.transform_matrix(Matrix.Identity(4))
    vertices = [transform @ v for v in vertices]
    edges = list(tag.block(bsp, 'edges'))
    surfaces = list(tag.block(bsp, 'surfaces'))
    polygons = {'face_sides': [], 'ladder': [], 'breakable': [], 'invisible': []}
    for index in sorted(indices - set(range(len(surfaces)))):
        utils.print_warning(f'H1 breakable collision surface {index} is out of range')
    for index, surface in enumerate(surfaces):
        flags = tag.required_field(surface, 'flags')
        enabled = {
            'face_sides': flags.get_flag('two sided'),
            'ladder': flags.get_flag('climbable'),
            'breakable': flags.get_flag('breakable') or index in indices,
            'invisible': flags.get_flag('invisible'),
        }
        if not any(enabled.values()):
            continue
        first = int(tag.value(surfaces[index], 'first edge')) & 0xffff
        current, visited, polygon = first, set(), []
        while current not in visited and 0 <= current < len(edges):
            visited.add(current)
            edge = edges[current]
            if (int(tag.value(edge, 'left surface')) & 0xffff) == index:
                vertex, following = 'start vertex', 'forward edge'
            elif (int(tag.value(edge, 'right surface')) & 0xffff) == index:
                vertex, following = 'end vertex', 'reverse edge'
            else:
                break
            polygon.append(int(tag.value(edge, vertex)) & 0xffff)
            current = int(tag.value(edge, following)) & 0xffff
            if current == first:
                break
        if current != first or len(polygon) < 3 or any(v >= len(vertices) for v in polygon):
            utils.print_warning(f'H1 collision surface {index} has an invalid edge loop')
            continue
        for name, active in enabled.items():
            if active:
                polygons[name].append(polygon)
    trees = {name: BVHTree.FromPolygons(vertices, faces) for name, faces in polygons.items() if faces}
    if not trees:
        return
    tolerance = 0.025 * import_transform.scale_factor()
    for ob in objects:
        if ob.type != 'MESH' or ob.data.nwo.mesh_type not in {
                '_connected_geometry_mesh_type_structure', '_connected_geometry_mesh_type_collision'}:
            continue
        mesh = ob.data
        masks = {name: np.zeros(len(mesh.polygons), dtype=np.int8) for name in trees}
        render_only = np.zeros(len(mesh.polygons), dtype=bool)
        for prop in mesh.nwo.face_props:
            if prop.type == 'face_mode' and prop.face_mode == 'render_only':
                attribute = mesh.attributes.get(prop.attribute_name)
                if attribute is not None:
                    render_only |= np.array([entry.value for entry in attribute.data], dtype=bool)
        for face in mesh.polygons:
            # The merge already established that these faces have no matching
            # collision surface. A nearby wall must not supply its flags.
            if render_only[face.index]:
                continue
            points = [ob.matrix_world @ mesh.vertices[v].co for v in face.vertices]
            points.append(sum(points, Vector()) / len(points))
            for name, tree in trees.items():
                if all((hit := tree.find_nearest(point))[0] is not None
                       and hit[3] <= tolerance for point in points):
                    masks[name][face.index] = 1
        # The compiled 'invisible' bit means large/sphere-only collision (*),
        # not ordinary non-rendering collision (@). It takes precedence over
        # modes inferred while matching render and collision geometry.
        sphere_only = masks.get('invisible')
        if sphere_only is not None and sphere_only.any():
            for prop in mesh.nwo.face_props:
                if prop.type == 'face_mode':
                    attribute = mesh.attributes.get(prop.attribute_name)
                    if attribute is not None:
                        values = np.array([v.value for v in attribute.data], dtype=np.int8)
                        values[sphere_only.astype(bool)] = 0
                        attribute.data.foreach_set('value', values)
            if 'breakable' in masks:
                masks['breakable'] &= ~sphere_only
        for name, mask in masks.items():
            if mask.any():
                prop = utils.add_face_prop(mesh, 'face_mode' if name in {'breakable', 'invisible'} else name,
                                           None if mask.all() else mask)
                if name == 'breakable':
                    prop.face_mode = 'breakable'
                elif name == 'invisible':
                    prop.face_mode = 'sphere_collision_only'
                elif name == 'face_sides':
                    prop.two_sided = True
        # H1 shell materials can carry explicit collision flags. The generic
        # cleanup otherwise clears every face property on '+' materials.
        utils.consolidate_face_attributes(mesh, preserve_special_faces=True)
        utils.calc_face_prop_counts(mesh)


def create_helpers(tag, collection):
    objects = []
    root = tag.tag.root()
    helper_collections = {}

    def helper_collection(kind):
        if kind not in helper_collections:
            child = bpy.data.collections.new(f'{collection.name}_{kind}')
            collection.children.link(child)
            helper_collections[kind] = child
        return helper_collections[kind]

    def mesh_object(name, vertices, faces, mesh_type, mat):
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(vertices, [], faces)
        mesh.update()
        mesh.materials.append(material(mat))
        mesh.nwo.mesh_type = '_connected_geometry_mesh_type_' + mesh_type
        ob = bpy.data.objects.new(name, mesh)
        ob.matrix_world = import_transform.transform_matrix(Matrix.Scale(100, 4))
        ob.display_type = 'WIRE'
        ob.show_in_front = True
        kind = 'fog_planes' if mesh_type == 'planar_fog_volume' else 'weather_polyhedra'
        helper_collection(kind).objects.link(ob)
        objects.append(ob)
        return ob

    for index, fog in enumerate(tag.block(root, 'fog planes')):
        vertices = [Vector(tag.value(v, 'point').to_array()) for v in tag.block(fog, 'vertices')]
        if len(vertices) < 3:
            utils.print_warning(f'H1 fog plane {index} has fewer than three vertices')
            continue
        plane = plane_values(tag.value(fog, 'plane'))
        face = list(range(len(vertices)))
        normal = sum((vertices[i].cross(vertices[(i + 1) % len(vertices)])
                      for i in range(len(vertices))), Vector())
        if normal.dot(Vector(plane[:3])) < 0:
            face.reverse()
        vertices, faces = fog_geometry(vertices, face)
        ob = mesh_object(f'+fog_{index}', vertices, faces, 'planar_fog_volume', '+fog')
        ob['h1_front_region'] = int(tag.value(fog, 'front region'))
        ob['h1_plane'] = plane

    for index, weather in enumerate(tag.block(root, 'weather polyhedra')):
        planes = [plane_values(tag.value(p, 'plane')) for p in tag.block(weather, 'planes')]
        # H1 weather normals point inward (n.dot(p) >= d).
        vertices = weather_vertices(planes)
        if len(vertices) < 4:
            utils.print_warning(f'H1 weather polyhedron {index} does not enclose a volume')
            continue
        bm = bmesh.new()
        try:
            for v in vertices:
                bm.verts.new(v)
            # Several plane triples can describe the same corner. Float32
            # intersection noise otherwise turns these into tiny hull faces
            # which Tool rejects as degenerate weather geometry.
            bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=0.0001)
            if len(bm.verts) < 4:
                utils.print_warning(f'H1 weather polyhedron {index} does not enclose a volume')
                continue
            bmesh.ops.convex_hull(bm, input=list(bm.verts))
            bm.verts.index_update()
            ob = mesh_object(f'+weather_{index}', [tuple(v.co) for v in bm.verts],
                             [[v.index for v in f.verts] for f in bm.faces],
                             'weather_polyhedron', '+weather')
        finally:
            bm.free()
        ob['h1_bounding_sphere_center'] = tuple(tag.value(weather, 'bounding sphere center').to_array())
        ob['h1_bounding_sphere_radius'] = float(tag.value(weather, 'bounding sphere radius'))

    for record in tag.markers():
        ob = StructureMarker(record).to_object()
        helper_collection('markers').objects.link(ob)
        objects.append(ob)
    return objects
