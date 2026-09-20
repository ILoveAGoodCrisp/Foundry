

from math import isfinite, radians
from pathlib import Path
from typing import cast
import bpy
from mathutils import Matrix
import numpy as np

from ..constants import VALID_MESHES

from .backend import TagDocument
from .blender import BlenderTag
from .. import utils
from .. import import_transform

POLYART_SCALE_FROM = 0.001
POLYART_SCALE_TO = 1000
POLYART_POSITION_SCALE = POLYART_SCALE_FROM * 100
POLYART_MAX_VERTEX_INDEX = 32767
POLYART_DEFAULT_PLACEMENT = (57.355, 32.262, 0.1, 10000.0, (0.0, 0.0, -43.914))
        
def decode_triangle_strip(indices):
    tris = []
    for i in range(len(indices) - 2):
        a, b, c = indices[i], indices[i + 1], indices[i + 2]

        if a == b or b == c or a == c:
            continue

        if i % 2 == 0:
            tris.append((a, b, c))
        else:
            tris.append((b, a, c))
    return tris

def encode_triangle_strip(triangles):
    if not triangles:
        return []

    strips = []
    prev_last = None

    for tri in triangles:
        a, b, c = tri

        if not strips:
            strips.extend([a, b, c])
        else:
            raw_triangle = (a, b, c) if (len(strips) + 2) % 2 == 0 else (b, a, c)
            if prev_last is not None:
                strips.extend([prev_last, raw_triangle[0]])
            strips.extend(raw_triangle)
        prev_last = c

    return strips


def _float_to_short(value: float, label: str) -> int:
    value = float(value)
    if not isfinite(value):
        raise RuntimeError(f"Polyart {label} contains a non-finite value")
    if abs(value) > np.finfo(np.float16).max:
        raise RuntimeError(f"Polyart {label} value {value:g} exceeds the half-float range")
    return int(np.asarray([value], dtype=np.float16).view(np.int16)[0])


def _vertex_alpha(mesh: bpy.types.Mesh, vertex_index: int, loop_index: int, polygon_index: int) -> float:
    color_attributes = getattr(mesh, "color_attributes", None)
    if color_attributes is None:
        return 1.0

    attribute = color_attributes.get("Color") or color_attributes.active_color
    if attribute is None or not attribute.data:
        return 1.0

    match attribute.domain:
        case 'POINT':
            index = vertex_index
        case 'CORNER':
            index = loop_index
        case 'FACE':
            index = polygon_index
        case _:
            return 1.0

    color = attribute.data[index].color
    return float(color[3]) if len(color) > 3 else 1.0


def _object_region(original: bpy.types.Object, instancer_parent: bpy.types.Object | None,
                   collection_map, valid_regions: set[str], default_region: str) -> tuple[str, str | None]:
    collection_region = ""
    collection_owner = instancer_parent or original
    export_collection = collection_owner.nwo.export_collection
    if export_collection:
        collection = collection_map.get(export_collection)
        if collection is not None:
            collection_region = collection.region or ""

    requested_region = collection_region or original.nwo.region_name or default_region
    if requested_region in valid_regions:
        return requested_region, None

    return default_region, (
        f"Object [{original.name}] has region [{requested_region}] which is not present in the regions table. "
        f"Setting region to: {default_region}"
    )


def collect_polyart_meshes(context: bpy.types.Context):
    """Build one quantized, unified mesh per Foundry region."""
    scene_nwo = utils.get_scene_props()
    regions = [entry.name for entry in scene_nwo.regions_table]
    if not regions:
        regions = ["default"]
    default_region = regions[0]
    valid_regions = set(regions)

    vertices_by_region = {region: [] for region in regions}
    triangles_by_region = {region: [] for region in regions}
    vertex_maps = {region: {} for region in regions}
    warnings = []
    warnings_seen = set()

    collection_map = utils.create_parent_mapping(context)
    depsgraph = context.evaluated_depsgraph_get()
    inverse_rotation = import_transform.rotation_matrix(scene_nwo).inverted()
    scene_scale = import_transform.scale_factor(scene_nwo)

    for instance in depsgraph.object_instances:
        evaluated_object = instance.object
        original = evaluated_object.original
        instancer_parent = original

        if instance.is_instance:
            evaluated_object = instance.instance_object
            original = evaluated_object.original
            instancer_parent = instance.parent
        elif original.is_instancer and original.instance_collection and original.instance_collection.all_objects and not original.nwo.marker_instance:
            continue

        if original.type not in VALID_MESHES:
            continue
        if utils.ignore_for_export_fast(original, collection_map, instancer_parent):
            continue

        region, warning = _object_region(original, instancer_parent, collection_map, valid_regions, default_region)
        if warning is not None and warning not in warnings_seen:
            warnings_seen.add(warning)
            warnings.append(warning)

        use_original_mesh = (
            original.type == 'MESH' and not evaluated_object.modifiers and original.data.shape_keys is None
        )
        mesh = original.data if use_original_mesh else evaluated_object.to_mesh(
            preserve_all_data_layers=True, depsgraph=depsgraph)
        if mesh is None:
            continue

        try:
            mesh.calc_loop_triangles()
            uv_layer = mesh.uv_layers.get("UVMap0") or mesh.uv_layers.active
            if uv_layer is None:
                warning = f"Object [{original.name}] has no UV map. Polyart UVs default to (0, 0)"
                if warning not in warnings_seen:
                    warnings_seen.add(warning)
                    warnings.append(warning)

            matrix_world = instance.matrix_world.copy() if instance.is_instance else original.matrix_world.copy()
            object_to_tag = inverse_rotation @ matrix_world
            reverse_winding = matrix_world.to_3x3().determinant() < 0
            region_vertices = vertices_by_region[region]
            region_triangles = triangles_by_region[region]
            vertex_map = vertex_maps[region]

            for loop_triangle in mesh.loop_triangles:
                loop_indices = list(loop_triangle.loops)
                if reverse_winding:
                    loop_indices[1], loop_indices[2] = loop_indices[2], loop_indices[1]

                triangle = []
                for loop_index in loop_indices:
                    loop = mesh.loops[loop_index]
                    tag_position = (object_to_tag @ mesh.vertices[loop.vertex_index].co) / scene_scale / POLYART_POSITION_SCALE
                    uv = uv_layer.data[loop_index].uv if uv_layer is not None else (0.0, 0.0)
                    alpha = _vertex_alpha(mesh, loop.vertex_index, loop_index, loop_triangle.polygon_index)

                    encoded = (
                        _float_to_short(tag_position.x, "position x"),
                        _float_to_short(tag_position.y, "position y"),
                        _float_to_short(tag_position.z, "position z"),
                        _float_to_short(alpha, "alpha"),
                        _float_to_short(uv[0], "UV u"),
                        _float_to_short(uv[1], "UV v"),
                    )
                    vertex_index = vertex_map.get(encoded)
                    if vertex_index is None:
                        vertex_index = len(region_vertices)
                        if vertex_index > POLYART_MAX_VERTEX_INDEX:
                            raise RuntimeError(
                                f"Polyart region [{region}] exceeds {POLYART_MAX_VERTEX_INDEX + 1} unique vertices"
                            )
                        vertex_map[encoded] = vertex_index
                        region_vertices.append(encoded)
                    triangle.append(vertex_index)

                if len(set(triangle)) == 3:
                    region_triangles.append(tuple(triangle))
        finally:
            if not use_original_mesh:
                evaluated_object.to_mesh_clear()

    return {
        region: (vertices_by_region[region], triangles_by_region[region])
        for region in regions
        if triangles_by_region[region]
    }, warnings


def export_polyart(context: bpy.types.Context, asset_path: str | Path):
    """Write a polyart_asset tag for every Foundry region containing geometry."""
    if not utils.is_corinth(context):
        raise RuntimeError("Polyart assets are only supported by Halo 4 and Halo 2 Anniversary Multiplayer")

    hidden_objects = {}
    for ob in context.view_layer.objects:
        hidden = ob.hide_get()
        viewport_hidden = ob.hide_viewport
        if hidden or viewport_hidden:
            hidden_objects[ob] = hidden, viewport_hidden
            if hidden:
                ob.hide_set(False)
            if viewport_hidden:
                ob.hide_viewport = False

    try:
        if hidden_objects:
            context.view_layer.update()
        meshes, warnings = collect_polyart_meshes(context)
    finally:
        for ob, (hidden, viewport_hidden) in hidden_objects.items():
            if hidden:
                ob.hide_set(True)
            if viewport_hidden:
                ob.hide_viewport = True
        if hidden_objects:
            context.view_layer.update()
    for warning in warnings:
        utils.print_warning(warning)

    if not meshes:
        raise RuntimeError("No exportable Polyart mesh geometry was found")

    relative_asset_path = Path(utils.relative_path(asset_path))
    tag_directory = Path(utils.get_tags_path(), relative_asset_path)
    tag_directory.mkdir(parents=True, exist_ok=True)

    safe_names = {}
    written = []
    for region, (vertices, triangles) in meshes.items():
        tag_name = utils.clean_text(region, replace_spaces=True)
        other_region = safe_names.get(tag_name.lower())
        if other_region is not None:
            raise RuntimeError(
                f"Polyart regions [{other_region}] and [{region}] resolve to the same tag name [{tag_name}]"
            )
        safe_names[tag_name.lower()] = region

        tag_path = Path(relative_asset_path, tag_name)
        with PolyArtTag(path=tag_path) as polyart:
            polyart.from_blender(vertices, triangles)
            written.append(polyart.tag_path.RelativePathWithExtension)
            print(
                f"--- Wrote Polyart tag [{region}]: {len(vertices)} vertices, "
                f"{len(triangles)} triangles -> {polyart.tag_path.RelativePathWithExtension}"
            )

    return written



class PolyArtTag(BlenderTag, TagDocument):
    tag_ext = 'polyart_asset'
    
    def __init__(self, path='', **kwargs):
        kwargs.setdefault('tag_must_exist', False)
        super().__init__(path, **kwargs)
        self.block_vertices = self.block(self.tag.root(), 'vertices')
        self.block_indices = self.block(self.tag.root(), 'indices')
        self.placement_data = self.block(self.tag.root(), 'placement data')

    def from_blender(self, vertices, triangles):
        indices = encode_triangle_strip(triangles)
        if len(vertices) > POLYART_MAX_VERTEX_INDEX + 1:
            raise RuntimeError(f"Polyart exceeds {POLYART_MAX_VERTEX_INDEX + 1} unique vertices")
        for vertex_index, vertex in enumerate(vertices):
            if len(vertex) != 6:
                raise RuntimeError(f"Polyart vertex {vertex_index} must contain position, alpha, and UV data")
            if any(value < -32768 or value > 32767 for value in vertex):
                raise RuntimeError(f"Polyart vertex {vertex_index} contains data outside the signed 16-bit range")
        for index in indices:
            if index < 0 or index >= len(vertices) or index > POLYART_MAX_VERTEX_INDEX:
                raise RuntimeError(f"Polyart index {index} is outside the vertex block")

        self.block_vertices.clear()
        for vertex in vertices:
            element = self.block_vertices[self.block_vertices.add()]
            for name, value in zip(('half x', 'half y', 'half z', 'half alpha', 'half u', 'half v'), vertex):
                self.required_field(element, name).set(int(value))

        self.block_indices.clear()
        for index in indices:
            self.required_field(self.block_indices[self.block_indices.add()], 'index').set(int(index))

        if not len(self.placement_data):
            horizontal_fov, vertical_fov, near, far, camera_position = POLYART_DEFAULT_PLACEMENT
            element = self.placement_data[self.placement_data.add()]
            self.required_field(element, 'horizontal fov').set(horizontal_fov)
            self.required_field(element, 'vertical fov').set(vertical_fov)
            self.required_field(element, 'near z plane distance').set(near)
            self.required_field(element, 'far z plane distance').set(far)
            field = self.required_field(element, 'camera position')
            field.set(type(field.value)(*camera_position))

        self.tag_has_changes = True
    
    
    def to_blender(self, collection=None):
        verts = []
        alphas = []
        uvs = []
        objects = []
        
        for element in self.block_vertices:
            vert_int16 = np.array([self.value(element, 'half x'), self.value(element, 'half y'), self.value(element, 'half z')], dtype=np.int16)
            vert_uint16 = vert_int16.view(np.uint16)
            verts.append(vert_uint16.view(np.float16).astype(np.float32) * POLYART_POSITION_SCALE)
            
            alpha_int16 = np.array([self.value(element, 'half alpha')], dtype=np.int16)
            alpha_uint16 = alpha_int16.view(np.uint16)
            alphas.append(alpha_uint16.view(np.float16)[0])
            
            uv_int16 = np.array([self.value(element, 'half u'), self.value(element, 'half v')], dtype=np.int16)
            uv_uint16 = uv_int16.view(np.uint16)
            uvs.append(uv_uint16.view(np.float16))
            
        indices = decode_triangle_strip([self.value(element, 'index') for element in self.block_indices])
            
        mesh = bpy.data.meshes.new(self.tag_path.ShortName)
        
        mesh.from_pydata(vertices=verts, edges=[], faces=indices)
        mesh.transform(import_transform.mesh_matrix())
        
        uv_layer = mesh.uv_layers.new(name="UVMap0", do_init=False)
        for face in mesh.polygons:
            for vert_idx, loop_idx in zip(face.vertices, face.loop_indices):
                uv_layer.data[loop_idx].uv = uvs[vert_idx]
                
        vcolor_attribute = mesh.color_attributes.new("Color", 'FLOAT_COLOR', 'POINT')
        rgba = np.repeat(np.array(alphas)[:, None], 4, axis=1)
        vcolor_attribute.data.foreach_set("color", rgba.ravel())

        
        mat = bpy.data.materials.get("polyart")
        if mat is None:
            mat = bpy.data.materials.new("polyart")
            tree = cast(bpy.types.NodeTree, mat.node_tree)
            tree.nodes.clear()
            node_attribute = tree.nodes.new(type="ShaderNodeAttribute")
            node_attribute.attribute_name = "Color"
            node_shader = tree.nodes.new(type='ShaderNodeBsdfPrincipled')
            tree.links.new(input=node_shader.inputs["Alpha"], output=node_attribute.outputs["Alpha"])
            node_output = tree.nodes.new(type='ShaderNodeOutputMaterial')
            tree.links.new(input=node_output.inputs[0], output=node_shader.outputs[0])
            mat.surface_render_method = 'BLENDED'
              
        mesh.materials.append(mat)
        ob = bpy.data.objects.new(mesh.name, mesh)
        ob.matrix_world = import_transform.rotation_matrix()
        
        if collection is None:
            bpy.context.scene.collection.objects.link(ob)
        else:
            collection.objects.link(ob)
            
        objects.append(ob)
            
        camera_ob = bpy.data.objects.get("polyart_camera")
        
        if camera_ob is None:
            for element in self.placement_data:
                camera = bpy.data.cameras.new("polyart_camera")
                camera.lens_unit = 'FOV'
                camera.angle = radians(45)
                camera.display_size = (camera.display_size / 0.03048) * import_transform.scale_factor()
                
                camera_ob = bpy.data.objects.new("polyart_camera", camera)
                camera_ob.matrix_world = import_transform.object_matrix(Matrix.Translation((0, 0, 5 / 0.03048)))
                if collection is None:
                    bpy.context.scene.collection.objects.link(camera_ob)
                else:
                    collection.objects.link(camera_ob)
                    
                objects.append(camera_ob)
            
        return objects
