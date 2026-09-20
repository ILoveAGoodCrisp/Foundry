from pathlib import Path
import time
import bpy
from math import tau
from mathutils import Matrix, Quaternion, Vector
import numpy as np
import types

from ..managed_blam.decorator_set import DecoratorSetTag

from ..tags.scenario import ScenarioMetadataTag
from .. import utils

DECORATOR_CLOUD_PROP = "nwo_decorator_placement_cloud"
DECORATOR_INSTANCE_SOURCE_PROP = "nwo_decorator_instance_source"
DECORATOR_TAG_PROP = "nwo_decorator_tag"
DECORATOR_VARIANT_PROP = "nwo_decorator_variant"
DECORATOR_ATTR_NORMAL = "normal"
DECORATOR_ATTR_INFO = "decorator_info"
DECORATOR_ATTR_SCALE = "decorator_scale"
DECORATOR_ATTR_TINT = "decorator_tint"

class NWO_OT_GetDecoratorTypes(bpy.types.Operator):
    bl_idname = "nwo.get_decorator_types"
    bl_label = "Get Decorator Types"
    bl_description = "Returns a list of decorator types"
    bl_options = {"UNDO", "REGISTER"}
    
    @classmethod
    def poll(cls, context):
        if context.object is None:
            return False
        if not context.object.nwo.marker_game_instance_tag_name.strip():
            return False
        
        if not utils.current_project_valid():
            return False
        
        tag_path = Path(utils.get_tags_path(), utils.relative_path(context.object.nwo.marker_game_instance_tag_name))
        return tag_path.is_absolute() and tag_path.exists() and tag_path.is_file() and tag_path.suffix.lower() == ".decorator_set"
    
    
    def type_items(self, context):
        with DecoratorSetTag(path=context.object.nwo.marker_game_instance_tag_name) as decorator:
            decorator_type_items = decorator.get_decorator_types()
            if not decorator_type_items:
                return [("default", "default", "")]
            
        items = []
        for v in decorator_type_items:
            items.append((v.decorator_type_name, v.decorator_type_name, ""))

        return items
    
    decorator_type: bpy.props.EnumProperty(
        name="Decorator Type",
        items=type_items,
    )
    
    def execute(self, context):
        nwo = context.object.nwo
        if str(Path(utils.get_tags_path(), nwo.marker_game_instance_tag_name)):
            nwo.marker_game_instance_tag_variant_name = self.decorator_type
            return {'FINISHED'}
        
        self.report({'ERROR'}, "Tag does not exist. Cannot find decorator types")
        return {"FINISHED"}
    
class NWO_OT_ExportDecorators(bpy.types.Operator):
    bl_idname = "nwo.export_decorators"
    bl_label = "Export Decorators"
    bl_description = "Exports all decorators"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return utils.valid_nwo_asset(context)

    def execute(self, context):
        current_selection = context.selected_objects[:]
        current_object = context.object
        export_decorators(utils.is_corinth(context))
        for ob in current_selection:
            ob.select_set(True)
        context.view_layer.objects.active = current_object
        return {"FINISHED"}

class NWO_OT_DecoratorCloudToInstances(bpy.types.Operator):
    bl_idname = "nwo.decorator_cloud_to_instances"
    bl_label = "Realize Decorator Cloud"
    bl_description = "Converts selected decorator placement clouds into editable collection-instance empties"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return any(_is_decorator_cloud(ob) for ob in context.selected_objects)

    def execute(self, context):
        selected = context.selected_objects[:]
        for ob in selected:
            ob.select_set(False)

        created = []
        for ob in selected:
            if _is_decorator_cloud(ob):
                created.extend(decorator_cloud_to_instances(ob, remove_cloud=True))

        for ob in created:
            ob.select_set(True)
        if created:
            context.view_layer.objects.active = created[0]

        self.report({'INFO'}, f"Created {len(created)} decorator instances")
        return {'FINISHED'}

def _is_decorator_instance(nwo):
    return nwo.marker_type == '_connected_geometry_marker_type_game_instance' and nwo.marker_game_instance_tag_name.lower().endswith(".decorator_set")

def _decorator_cloud_marker_data(ob):
    tag_path = ob.get(DECORATOR_TAG_PROP) or ob.nwo.marker_game_instance_tag_name
    variant = ob.get(DECORATOR_VARIANT_PROP) or ob.nwo.marker_game_instance_tag_variant_name
    return tag_path, variant

def _is_decorator_cloud(ob):
    if not (ob and ob.type == 'MESH' and ob.get(DECORATOR_CLOUD_PROP)):
        return False
    
    tag_path, _ = _decorator_cloud_marker_data(ob)
    return isinstance(tag_path, str) and tag_path.lower().endswith(".decorator_set")

def gather_decorators(context):
    print("--- Start decorator gather")
    start = time.perf_counter()
    
    collection_map = utils.create_parent_mapping(context)
    proxies = []
    with utils.DepsgraphRead():
        depsgraph = context.evaluated_depsgraph_get()

        for inst in depsgraph.object_instances:
            obj = inst.object
            original = obj.original
            nwo = original.nwo
            parent = original
            
            if inst.is_instance:
                obj = inst.instance_object
                original = obj.original
                nwo = original.nwo
                parent = inst.parent

            if _is_decorator_cloud(original):
                proxies.extend(_decorator_cloud_proxies(original, inst.matrix_world))
                continue
            
            if not (original.type == 'EMPTY' and _is_decorator_instance(nwo)):
                continue
            
            if utils.ignore_for_export_fast(original, collection_map, parent):
                continue

            proxy = types.SimpleNamespace()
            proxy.name = original.name
            proxy.type = 'EMPTY'
            proxy.nwo = nwo
            proxy.matrix_world = inst.matrix_world.copy()
            proxies.append(proxy)

    print(len(proxies), "decorators found")
    print("--- Gathered decorators in: {:.3f}s".format(time.perf_counter() - start))
        
    return proxies

def _vector_attribute(mesh, name, default):
    count = len(mesh.vertices)
    attr = mesh.attributes.get(name)
    if attr is None:
        return np.tile(np.asarray(default, dtype=np.float32), (count, 1))
    
    values = np.empty(count * 3, dtype=np.float32)
    attr.data.foreach_get("vector", values)
    return values.reshape(count, 3)

def _color_attribute(mesh, name, default):
    count = len(mesh.vertices)
    attr = mesh.attributes.get(name)
    if attr is None:
        return np.tile(np.asarray(default, dtype=np.float32), (count, 1))
    
    values = np.empty(count * 4, dtype=np.float32)
    attr.data.foreach_get("color", values)
    return values.reshape(count, 4)

def _decorator_rotation_from_normal(normal, rotation):
    if normal.z < -0.999999:
        align = Quaternion((0.0, 1.0, 0.0, 0.0))
    else:
        align = Quaternion((1.0 + normal.z, -normal.y, normal.x, 0.0))
        align.normalize()
    
    return align @ Quaternion((0.0, 0.0, 1.0), float(rotation) * tau)

def _decorator_cloud_proxies(ob, matrix_world):
    mesh = ob.data
    count = len(mesh.vertices)
    if count == 0:
        return []
    
    coords = np.empty(count * 3, dtype=np.float32)
    mesh.vertices.foreach_get("co", coords)
    coords = coords.reshape(count, 3)
    normals = _vector_attribute(mesh, DECORATOR_ATTR_NORMAL, (0.0, 0.0, 1.0))
    info = _color_attribute(mesh, DECORATOR_ATTR_INFO, (0.0, ob.nwo.decorator_ground_tint, ob.nwo.decorator_motion_scale, 1.0))
    scales = _color_attribute(mesh, DECORATOR_ATTR_SCALE, (1.0, 1.0, 1.0, 1.0))
    tints = _color_attribute(mesh, DECORATOR_ATTR_TINT, (*ob.nwo.decorator_tint, 1.0))
    tag_path, variant = _decorator_cloud_marker_data(ob)
    
    proxies = []
    for idx in range(count):
        normal = Vector(normals[idx])
        if normal.length_squared < 0.000001:
            normal = Vector((0.0, 0.0, 1.0))
        else:
            normal.normalize()

        nwo = types.SimpleNamespace()
        nwo.marker_game_instance_tag_name = tag_path
        nwo.marker_game_instance_tag_variant_name = variant
        nwo.decorator_motion_scale = float(info[idx][2])
        nwo.decorator_ground_tint = float(info[idx][1])
        nwo.decorator_tint = tuple(float(v) for v in tints[idx][:3])

        proxy = types.SimpleNamespace()
        proxy.name = f"{ob.name}:{idx}"
        proxy.type = 'EMPTY'
        proxy.nwo = nwo
        proxy.matrix_world = matrix_world @ Matrix.LocRotScale(
            Vector(coords[idx]),
            _decorator_rotation_from_normal(normal, info[idx][0]),
            Vector.Fill(3, float(scales[idx][0])),
        )
        proxies.append(proxy)
    
    return proxies

def _decorator_cloud_instance_collection(ob):
    source_name = ob.get(DECORATOR_INSTANCE_SOURCE_PROP)
    source = bpy.data.objects.get(source_name) if isinstance(source_name, str) else None
    if source is None:
        source = bpy.data.objects.get(f"{ob.name}_instance_source")
    
    return source.instance_collection if source is not None else None, source

def decorator_cloud_to_instances(ob, collection=None, remove_cloud=False):
    instance_collection, source = _decorator_cloud_instance_collection(ob)
    if instance_collection is None:
        raise ValueError(f"Decorator cloud {ob.name} has no instanced collection source")
    
    collection = collection or (ob.users_collection[0] if ob.users_collection else bpy.context.scene.collection)
    mesh = ob.data
    created = []
    for proxy in _decorator_cloud_proxies(ob, Matrix.Identity(4)):
        new_ob = bpy.data.objects.new(proxy.name, None)
        new_ob.empty_display_type = 'ARROWS'
        new_ob.matrix_world = proxy.matrix_world
        new_ob.instance_type = 'COLLECTION'
        new_ob.instance_collection = instance_collection
        new_ob.nwo.marker_type = '_connected_geometry_marker_type_game_instance'
        new_ob.nwo.marker_game_instance_tag_name = proxy.nwo.marker_game_instance_tag_name
        new_ob.nwo.marker_game_instance_tag_variant_name = proxy.nwo.marker_game_instance_tag_variant_name
        new_ob.nwo.marker_instance = True
        new_ob.nwo.decorator_motion_scale = proxy.nwo.decorator_motion_scale
        new_ob.nwo.decorator_ground_tint = proxy.nwo.decorator_ground_tint
        new_ob.nwo.decorator_tint = proxy.nwo.decorator_tint
        collection.objects.link(new_ob)
        created.append(new_ob)
    
    if remove_cloud:
        bpy.data.objects.remove(ob, do_unlink=True)
        if source is not None:
            bpy.data.objects.remove(source, do_unlink=True)
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
    
    return created

def _decorator_type_indices(decorator_types):
    return {dec_type.decorator_type_name.lower(): dec_type.decorator_type_index for dec_type in decorator_types}

def _byte_value(value):
    return max(0, min(255, int(value)))

def _decorator_byte_value(value, corinth):
    value = _byte_value(value)
    if corinth:
        # Match ManagedBlam's CharInteger coercion in the old field-by-field writer.
        return min(value, 127)
    
    return value

def _write_decorator_placements(scenario, placements, decorator_objects, decorator_types, corinth):
    placements.clear()
    type_indices = _decorator_type_indices(decorator_types)
    for ob in decorator_objects:
        index = placements.add()
        placement = placements[index]
        matrix = utils.halo_transforms_matrix(ob.matrix_world)
        position = scenario.required_field(placement, 'position')
        position.set(type(position.value)(*matrix.translation))
        q = matrix.to_quaternion()
        rotation = scenario.required_field(placement, 'rotation')
        rotation.set(type(rotation.value)(q[1], q[2], q[3], q[0]))
        scenario.required_field(placement, 'scale').set(max(ob.matrix_world.to_scale().to_tuple()))
        
        variant = ob.nwo.marker_game_instance_tag_variant_name.strip().lower()
        if variant:
            scenario.required_field(placement, 'type index').set(type_indices.get(variant, 0))
        
        motion_scale = _decorator_byte_value(ob.nwo.decorator_motion_scale * 255, corinth)
        ground_tint = _decorator_byte_value(ob.nwo.decorator_ground_tint * 255, corinth)
        if not corinth:
            motion_scale = utils.signed_int8(motion_scale)
            ground_tint = utils.signed_int8(ground_tint)
        scenario.required_field(placement, 'motion scale').set(motion_scale)
        scenario.required_field(placement, 'ground tint').set(ground_tint)
        tint = scenario.required_field(placement, 'tint color')
        tint.set(type(tint.value)(*(utils.linear_to_srgb(c) for c in ob.nwo.decorator_tint)))

        bsp = placement.field('bsp index') or placement.field('runtime bsp index')
        if bsp is not None:
            bsp.set(-1)
        scenario.required_field(placement, 'cluster index').set(-1)
        decorator_set_index = placement.field('cluster decorator set index')
        if decorator_set_index is not None:
            decorator_set_index.set(-1)
    scenario.tag_has_changes = True
    
def export_decorators(corinth, decorator_objects = None):
    scenario_path = utils.get_asset_tag(".scenario", True)
    scene_nwo = utils.get_scene_props()
    if corinth and scene_nwo.decorators_from_blender_child_scenario.strip():
        scenario_path = str(Path(scenario_path).with_name(scene_nwo.decorators_from_blender_child_scenario).with_suffix(".scenario"))
    
    tags_dir = utils.get_tags_path()
    context = bpy.context
    if decorator_objects is None:
        decorator_objects = gather_decorators(context)
    
    decorator_sets = {}
    MAX_SETS = 48
    MAX_PLACEMENTS_PER_SET = 262_144
    for ob in decorator_objects:
        tag_path = utils.relative_path(ob.nwo.marker_game_instance_tag_name.lower())
        index = 0

        while True:
            values = decorator_sets.setdefault((tag_path, index), [])
            if len(values) < MAX_PLACEMENTS_PER_SET:
                values.append(ob)
                break
            index += 1

            if len(decorator_sets) > MAX_SETS:
                for k in list(decorator_sets.keys())[:-MAX_SETS]:
                    del decorator_sets[k]
                    
    print("--- Writing decorators to Tag")
    start = time.perf_counter()
    with ScenarioMetadataTag(path=scenario_path) as scenario:
        root = scenario.tag.root()
        decorator_block = scenario.block(root, 'decorators')
        if not len(decorator_block):
            decorator_block.add()
            decorator_block = scenario.block(root, 'decorators')
        sets_block = scenario.block(decorator_block[0], 'sets')
        sets_block.clear()
        # print("Max sets size", sets_block.MaximumElementCount)
        
        for key, value in decorator_sets.items():
            path = key[0]
            if path and Path(tags_dir, path).exists():
                with DecoratorSetTag(path=path) as decorator_set:
                    decorator_types = decorator_set.get_decorator_types()
                    decorator_path = decorator_set.tag_path
                index = sets_block.add()
                element = sets_block[index]
                scenario.set_reference(element, 'decorator set', decorator_path)
                placements = scenario.block(element, 'placements')
                _write_decorator_placements(scenario, placements, value, decorator_types, corinth)
    print("--- Completed decorators tag write in", utils.human_time(time.perf_counter() - start, True))
                            
                    
