"""Practical H1 decal previews with independent, reusable placement controls."""
from dataclasses import dataclass, replace
from math import asin, atan2, cos, isfinite, pi, sin

from .backend import TagDocument, read_only_tags


def placement_rotation(yaw, pitch):
    """Scenario bytes: full yaw, half pitch; projection points along local +X."""
    yaw, pitch = int(yaw) * pi / 127, int(pitch) * pi / 254
    cy, sy = cos(yaw / 2), sin(yaw / 2)
    cp, sp = cos(pitch / 2), sin(pitch / 2)
    return sy * sp, -cy * sp, sy * cp, cy * cp


@dataclass(frozen=True)
class DecalPreview:
    # Tag units and bitmap coordinates (V increases downwards).
    extent: tuple[float, float, float, float]
    uv_bounds: tuple[float, float, float, float] = (0., 1., 0., 1.)
    bitmap_index: int = 0
    sequence_index: int = -1
    sprite_index: int = -1
    no_random_rotation: bool = False
    snap_to_axis: bool = False


def preview_bounds(radius, width, height, sprite=None, preserve_aspect=False):
    if sprite is None:
        aspect = height / width if preserve_aspect and width > 0 else 1.
        return DecalPreview((-radius, radius, -radius * aspect, radius * aspect))
    left, right, top, bottom, rx, ry = sprite
    # Registration is relative to the cropped sprite, not the whole atlas.
    # Normalise its furthest extent to the preview radius. Compiled maximum
    # sprite extent and runtime randomness are deliberately not reproduced.
    x0, x1 = -rx * width, (right - left - rx) * width
    y0, y1 = -(bottom - top - ry) * height, ry * height
    extent = max(abs(x0), abs(x1), abs(y0), abs(y1))
    scale = radius / extent if extent > 0 else 1.
    # Sample texel centres at the cropped edges rather than filtering an
    # adjacent packed sprite into the preview.
    du = min(.5 / width, (right - left) / 2)
    dv = min(.5 / height, (bottom - top) / 2)
    return DecalPreview(tuple(v * scale for v in (x0, x1, y0, y1)),
                        (left + du, right - du, top + dv, bottom - dv))


def read_preview(document):
    root = document.tag.root()
    appearance = document.required_field(root, 'appearance').as_struct()
    radius = document.value(appearance, 'radius')
    radius = max(abs(float(radius.lower)), abs(float(radius.upper))) or .05
    properties = document.required_field(root, 'properties').as_struct()
    flags = document.required_field(properties, 'flags')
    preserve_aspect = flags.get_flag('preserve aspect')
    no_random_rotation = flags.get_flag('no random rotation')
    snap_to_axis = flags.get_flag('editor snap to axis')

    def with_flags(preview):
        return replace(preview, no_random_rotation=no_random_rotation, snap_to_axis=snap_to_axis)

    shader = document.required_field(root, 'shader').as_struct()
    bitmap = TagDocument.reference(document, shader, 'map')
    if bitmap is None:
        return with_flags(preview_bounds(radius, 1, 1))
    with read_only_tags(), TagDocument(bitmap.Filename, tags_root=document.tags_root, game='halo1',
                                      definitions=document.definitions, must_exist=True) as tag:
        bitmap_root = tag.tag.root()
        bitmaps = list(tag.block(bitmap_root, 'bitmaps'))
        if not bitmaps:
            return with_flags(preview_bounds(radius, 1, 1))
        for si, sequence in enumerate(tag.block(bitmap_root, 'sequences')):
            for fi, sprite in enumerate(tag.block(sequence, 'sprites')):
                bi = int(tag.value(sprite, 'bitmap index'))
                if not 0 <= bi < len(bitmaps):
                    continue
                width, height = (int(tag.value(bitmaps[bi], key)) for key in ('width', 'height'))
                reg = tag.value(sprite, 'registration point')
                bounds = tuple(float(tag.value(sprite, k)) for k in ('left', 'right', 'top', 'bottom'))
                if width <= 0 or height <= 0 or bounds[1] <= bounds[0] or bounds[3] <= bounds[2]:
                    continue
                preview = preview_bounds(radius, width, height, (*bounds, reg.x, reg.y), preserve_aspect)
                return with_flags(DecalPreview(preview.extent, preview.uv_bounds, bi, si, fi))
        width, height = (int(tag.value(bitmaps[0], key)) for key in ('width', 'height'))
        return with_flags(preview_bounds(radius, width, height, preserve_aspect=preserve_aspect))


def fixed_preview_axes(direction, normal, snap_to_axis=False):
    """H1's no-random-rotation texture basis, in tag space (Y increases up).

    Match decal_new_from_collision's signed dominant-axis selection and its
    surface-parallel fallback. Scenario yaw/pitch remain projection angles.
    """
    from mathutils import Vector

    if normal.dot(direction) >= -1e-4:
        return None

    def dominant_axis(vector):
        # H1 breaks equal magnitudes in favour of Z, then Y, then X.
        index = max(range(3), key=lambda i: (abs(vector[i]), i))
        axis = Vector((0, 0, 0))
        axis[index] = 1 if vector[index] > 0 else -1
        return axis

    if snap_to_axis:
        axis = (dominant_axis(direction) - normal).normalized()
        tangent = normal.cross(axis)
        bitangent = normal.cross(tangent)
        if tangent.length_squared < 1e-4 or bitangent.length_squared < 1e-4:
            parallel = direction - normal * direction.dot(normal)
            axis = dominant_axis(parallel)
            axis += normal if axis.dot(normal) > 0 else -normal
            tangent = normal.cross(axis.normalized())
    else:
        tangent = normal.cross(direction)
    if tangent.length_squared < 1e-12:
        return None  # Stable existing preview for a degenerate fixed basis.
    tangent.normalize()
    bitangent = normal.cross(tangent).normalized()
    # Engine forward=-bitangent, left=-tangent. Its extent Y is bitmap-down;
    # preview vertices and UVs use Y up, so negate the engine's left axis.
    return -bitangent, tangent


def projection_bvh(objects):
    """Build in imported world space; prefer untouched collision when available."""
    from mathutils.bvhtree import BVHTree
    candidates = [ob for ob in objects if ob.type == 'MESH' and ob.data.nwo.mesh_type in {
        '_connected_geometry_mesh_type_structure', '_connected_geometry_mesh_type_collision'}]
    collision = [ob for ob in candidates if ob.data.nwo.mesh_type == '_connected_geometry_mesh_type_collision']
    candidates = collision or candidates
    vertices, faces = [], []
    for ob in candidates:
        base = len(vertices)
        vertices.extend(ob.matrix_world @ vertex.co for vertex in ob.data.vertices)
        faces.extend(tuple(base + v for v in face.vertices) for face in ob.data.polygons)
    return BVHTree.FromPolygons(vertices, faces) if faces else None


def create_preview(placement, preview, material, collection, scenario_path, bvh=None, *, tags_root=None):
    import bpy
    from mathutils import Matrix, Quaternion, Vector
    from .. import import_transform

    control = bpy.data.objects.new(f'{placement.name} placement', None)
    control.empty_display_type = 'ARROWS'
    control.empty_display_size = import_transform.distance(.025)
    rotation = Quaternion((placement.rotation[3], *placement.rotation[:3]))
    control.matrix_world = import_transform.object_matrix(
        Matrix.LocRotScale(Vector(placement.position) * 100, rotation, Vector.Fill(3, 1)))
    control['halo1_decal_placement'] = True
    control['halo1_source_scenario'] = str(scenario_path)
    control['halo1_source_decal'] = placement.definition or ''
    if tags_root is not None:
        control['halo1_source_tags_root'] = str(tags_root)
    control['halo1_source_palette_index'] = placement.palette_index
    control['halo1_source_placement_index'] = placement.source_index
    collection.objects.link(control)

    origin = control.matrix_world.translation.copy()
    direction = control.matrix_world.to_3x3() @ Vector((1, 0, 0))
    direction.normalize()
    normal, point = -direction, origin.copy()
    fitted = False
    if bvh is not None:
        start = origin - direction * import_transform.distance(.1)
        hit, hit_normal, _, _ = bvh.ray_cast(start, direction, import_transform.distance(1.1))
        if hit is not None:
            point, normal, fitted = hit, hit_normal, True
            if normal.dot(direction) > 0:
                normal = -normal
    normal.normalize()
    horizontal = control.matrix_world.to_3x3() @ Vector((0, -1, 0))
    horizontal -= normal * horizontal.dot(normal)
    if horizontal.length < 1e-6:
        horizontal = normal.cross(Vector((0, 0, 1)))
    if horizontal.length < 1e-6:
        horizontal = normal.cross(Vector((0, 1, 0)))
    horizontal.normalize()
    vertical = normal.cross(horizontal).normalized()
    if preview.no_random_rotation:
        # Axis snapping is in Halo coordinates, before the scene forward-axis
        # conversion. Keep the raw rotation on the exportable parent control.
        tag_to_world = import_transform.rotation_matrix().to_3x3()
        world_to_tag = tag_to_world.inverted()
        axes = fixed_preview_axes(world_to_tag @ direction, world_to_tag @ normal, preview.snap_to_axis)
        if axes is not None:
            horizontal, vertical = (tag_to_world @ axis for axis in axes)
    point += normal * import_transform.distance(.0001)
    to_control = control.matrix_world.inverted_safe()
    x0, x1, y0, y1 = preview.extent
    vertices = [to_control @ (point + horizontal * import_transform.distance(x)
                              + vertical * import_transform.distance(y))
                for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
    mesh = bpy.data.meshes.new(placement.name)
    mesh.from_pydata(vertices, [], [(0, 1, 2, 3)])
    uv = mesh.uv_layers.new(name='UVMap0')
    left, right, top, bottom = preview.uv_bounds
    for loop, value in zip(uv.data, ((left, 1 - bottom), (right, 1 - bottom),
                                   (right, 1 - top), (left, 1 - top))):
        loop.uv = value
    if material is not None:
        mesh.materials.append(material)
    ob = bpy.data.objects.new(f'{placement.name} preview', mesh)
    ob.parent = control
    ob.matrix_basis = Matrix.Identity(4)
    ob['halo1_decal_preview'] = True
    ob['halo1_decal_surface_fitted'] = fitted
    collection.objects.link(ob)
    return control, ob


def placement_values(control):
    """Recover edited scenario placement values from the control, not its mesh.

    Positions and angles come from the current control transform. Preview
    fitting and mesh edits never affect this placement.
    """
    from mathutils import Matrix, Quaternion, Vector
    from .. import import_transform
    world_to_tag = import_transform.transform_matrix(Matrix.Scale(100, 4)).inverted_safe()
    position = world_to_tag @ control.matrix_world.translation
    direction = import_transform.rotation_matrix().inverted().to_3x3() @ (
        control.matrix_world.to_3x3() @ Vector((1, 0, 0)))
    if not all(isfinite(v) for v in direction) or direction.length_squared < 1e-12:
        raise ValueError(f'{control.name}: the decal control has an invalid projection direction')
    direction.normalize()
    yaw = max(-127, min(127, round(atan2(direction.y, direction.x) * 127 / pi)))
    pitch = max(-127, min(127, round(asin(max(-1., min(1., direction.z))) * 254 / pi)))
    return dict(position=tuple(position), yaw=yaw, pitch=pitch,
                palette_index=int(control['halo1_source_palette_index']),
                source_index=int(control['halo1_source_placement_index']),
                definition=str(control['halo1_source_decal']))
