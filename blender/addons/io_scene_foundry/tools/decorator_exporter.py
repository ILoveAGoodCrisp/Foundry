from pathlib import Path
import struct
import time
import bpy
from mathutils import Matrix, Quaternion, Vector
import numpy as np
import types

from ..constants import WU_SCALAR

from ..managed_blam.decorator_set import DecoratorSetTag

from ..managed_blam.scenario import (
    DECORATOR_ATTR_GROUND_TINT,
    DECORATOR_ATTR_MOTION_SCALE,
    DECORATOR_ATTR_ROTATION,
    DECORATOR_ATTR_ROTATION_W,
    DECORATOR_ATTR_SCALE,
    DECORATOR_ATTR_TINT,
    DECORATOR_CLOUD_PROP,
    ScenarioTag,
)
from .. import utils

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

def gather_decorators(context):
    print("--- Start decorator gather")
    start = time.perf_counter()

    def is_decorator_instance(nwo):
        return nwo.marker_type == '_connected_geometry_marker_type_game_instance' and nwo.marker_game_instance_tag_name.lower().endswith(".decorator_set")

    def is_decorator_cloud(ob):
        return ob.type == 'MESH' and ob.get(DECORATOR_CLOUD_PROP) and ob.nwo.marker_game_instance_tag_name.lower().endswith(".decorator_set")
    
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

            if is_decorator_cloud(original):
                proxies.extend(_decorator_cloud_proxies(original, inst.matrix_world))
                continue
            
            if not (original.type == 'EMPTY' and is_decorator_instance(nwo)):
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

def _float_attribute(mesh, name, default):
    count = len(mesh.vertices)
    attr = mesh.attributes.get(name)
    if attr is None:
        return np.full(count, default, dtype=np.float32)
    
    values = np.empty(count, dtype=np.float32)
    attr.data.foreach_get("value", values)
    return values

def _vector_attribute(mesh, name, default):
    count = len(mesh.vertices)
    attr = mesh.attributes.get(name)
    if attr is None:
        return np.tile(np.asarray(default, dtype=np.float32), (count, 1))
    
    values = np.empty(count * 3, dtype=np.float32)
    attr.data.foreach_get("vector", values)
    return values.reshape(count, 3)

def _decorator_cloud_proxies(ob, matrix_world):
    mesh = ob.data
    count = len(mesh.vertices)
    if count == 0:
        return []
    
    coords = np.empty(count * 3, dtype=np.float32)
    mesh.vertices.foreach_get("co", coords)
    coords = coords.reshape(count, 3)
    rotations = _vector_attribute(mesh, DECORATOR_ATTR_ROTATION, (0.0, 0.0, 0.0))
    rotation_w = _float_attribute(mesh, DECORATOR_ATTR_ROTATION_W, 1.0)
    scales = _float_attribute(mesh, DECORATOR_ATTR_SCALE, 1.0)
    motion_scales = _float_attribute(mesh, DECORATOR_ATTR_MOTION_SCALE, ob.nwo.decorator_motion_scale)
    ground_tints = _float_attribute(mesh, DECORATOR_ATTR_GROUND_TINT, ob.nwo.decorator_ground_tint)
    tints = _vector_attribute(mesh, DECORATOR_ATTR_TINT, ob.nwo.decorator_tint)
    
    proxies = []
    for idx in range(count):
        nwo = types.SimpleNamespace()
        nwo.marker_game_instance_tag_name = ob.nwo.marker_game_instance_tag_name
        nwo.marker_game_instance_tag_variant_name = ob.nwo.marker_game_instance_tag_variant_name
        nwo.decorator_motion_scale = float(motion_scales[idx])
        nwo.decorator_ground_tint = float(ground_tints[idx])
        nwo.decorator_tint = tuple(float(v) for v in tints[idx])

        proxy = types.SimpleNamespace()
        proxy.name = f"{ob.name}:{idx}"
        proxy.type = 'EMPTY'
        proxy.nwo = nwo
        proxy.matrix_world = matrix_world @ Matrix.LocRotScale(
            Vector(coords[idx]),
            Quaternion((float(rotation_w[idx]), float(rotations[idx][0]), float(rotations[idx][1]), float(rotations[idx][2]))),
            Vector.Fill(3, float(scales[idx])),
        )
        proxies.append(proxy)
    
    return proxies

def _placement_field_offsets(element):
    offsets = {}
    offset = 0
    for field in element.Fields:
        offsets[field.FieldName] = offset
        offset += int(field.Size)
        
    return offsets, offset

def _serialized_block_with_payload(template, count, payload):
    data = bytearray(template)
    lbgt = data.rfind(b"lbgt")
    dtpc = data.rfind(b"dtpc", 0, lbgt)
    if lbgt == -1 or dtpc == -1:
        raise ValueError("Serialized decorator placement block does not contain expected chunks")
    
    values_start = lbgt + 20
    data = data[:values_start] + payload + data[values_start:]
    struct.pack_into("<I", data, 8, len(data) - 12)
    struct.pack_into("<I", data, dtpc + 8, len(data) - dtpc - 12)
    struct.pack_into("<I", data, lbgt + 8, len(payload) + 8)
    struct.pack_into("<I", data, lbgt + 12, count)
    return bytes(data)

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

def _decorator_placement_dtype(offsets, element_size):
    fields = (
        ("position", "position", ("<f4", (3,))),
        ("type_index", "type index", "u1"),
        ("motion_scale", "motion scale", "u1"),
        ("ground_tint", "ground tint", "u1"),
        ("rotation", "rotation", ("<f4", (4,))),
        ("scale", "scale", "<f4"),
        ("tint_color", "tint color", ("<f4", (3,))),
        ("bsp_index", "bsp index", "<i4"),
        ("cluster_index", "cluster index", "<i2"),
    )
    missing = [field_name for _, field_name, _ in fields if field_name not in offsets]
    if missing:
        raise ValueError(f"Decorator placement block is missing fields: {', '.join(missing)}")
    
    names = [name for name, _, _ in fields]
    formats = [fmt for _, _, fmt in fields]
    field_offsets = [offsets[field_name] for _, field_name, _ in fields]
    if "cluster decorator set index" in offsets:
        names.append("cluster_decorator_set_index")
        formats.append("<i2")
        field_offsets.append(offsets["cluster decorator set index"])
    
    return np.dtype({
        "names": names,
        "formats": formats,
        "offsets": field_offsets,
        "itemsize": element_size,
    })

def _build_decorator_placement_payload(decorator_objects, decorator_types, corinth, offsets, element_size):
    payload = bytearray(element_size * len(decorator_objects))
    if not decorator_objects:
        return payload
    
    rows = np.ndarray(len(decorator_objects), dtype=_decorator_placement_dtype(offsets, element_size), buffer=payload)
    rows["bsp_index"] = -1
    rows["cluster_index"] = -1
    if corinth and "cluster_decorator_set_index" in rows.dtype.names:
        rows["cluster_decorator_set_index"] = -1
    
    type_indices = _decorator_type_indices(decorator_types)
    for idx, ob in enumerate(decorator_objects):
        matrix = utils.halo_transforms_matrix(ob.matrix_world)
        rows["position"][idx] = tuple(matrix.translation)
        q = matrix.to_quaternion()
        rows["rotation"][idx] = q[1], q[2], q[3], q[0]
        rows["scale"][idx] = max(ob.matrix_world.to_scale().to_tuple())
        
        variant = ob.nwo.marker_game_instance_tag_variant_name.strip().lower()
        if variant:
            rows["type_index"][idx] = type_indices.get(variant, 0) & 0xFF
        
        rows["motion_scale"][idx] = _decorator_byte_value(ob.nwo.decorator_motion_scale * 255, corinth)
        rows["ground_tint"][idx] = _decorator_byte_value(ob.nwo.decorator_ground_tint * 255, corinth)
        rows["tint_color"][idx] = tuple(utils.linear_to_srgb(ob.nwo.decorator_tint[i]) for i in range(3))
        
    return payload

def _write_decorator_placements_serialized(placements, decorator_objects, decorator_types, corinth):
    placements.RemoveAllElements()
    if not decorator_objects:
        return
    
    template_element = placements.AddElement()
    offsets, element_size = _placement_field_offsets(template_element)
    placements.RemoveAllElements()
    
    payload = _build_decorator_placement_payload(decorator_objects, decorator_types, corinth, offsets, element_size)
    serialized = _serialized_block_with_payload(bytes(placements.Serialize()), len(decorator_objects), payload)
    placements.Deserialize(serialized)

def _write_decorator_placements_elementwise(placements, decorator_objects, decorator_types, corinth):
    placements.RemoveAllElements()
    type_indices = _decorator_type_indices(decorator_types)
    for ob in decorator_objects:
        placement = placements.AddElement()
        matrix = utils.halo_transforms_matrix(ob.matrix_world)
        placement.SelectField("position").Data = matrix.translation
        q = matrix.to_quaternion()
        placement.SelectField("rotation").Data = q[1], q[2], q[3], q[0]
        placement.SelectField("scale").Data = max(ob.matrix_world.to_scale().to_tuple())
        
        variant = ob.nwo.marker_game_instance_tag_variant_name.strip().lower()
        if variant:
            placement.SelectField("type index").Data = type_indices.get(variant, 0)
        
        motion_scale = int(ob.nwo.decorator_motion_scale * 255)
        ground_tint = int(ob.nwo.decorator_ground_tint * 255)
                
        if not corinth:
            motion_scale = utils.signed_int8(motion_scale)
            ground_tint = utils.signed_int8(ground_tint)
            
        placement.SelectField("motion scale").Data = motion_scale
        placement.SelectField("ground tint").Data = ground_tint
        
        placement.SelectField("tint color").Data = [utils.linear_to_srgb(c) for c in ob.nwo.decorator_tint]
        
        placement.SelectField("bsp index").Data = -1
        placement.SelectField("cluster index").Data = -1
        if corinth:
            placement.SelectField("cluster decorator set index").Data = -1
    
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
    with ScenarioTag(path=scenario_path) as scenario:
        decorator_block = scenario.tag.SelectField("Block:decorators")
        if decorator_block.Elements.Count < 1:
            set_element = decorator_block.AddElement()
        else:
            set_element = decorator_block.Elements[0]
            
        sets_block = set_element.SelectField("Block:sets")
        sets_block.RemoveAllElements()
        # print("Max sets size", sets_block.MaximumElementCount)
        
        for key, value in decorator_sets.items():
            path = key[0]
            if path and Path(tags_dir, path).exists():
                with DecoratorSetTag(path=path) as decorator_set:
                    decorator_types = decorator_set.get_decorator_types()
                    decorator_path = decorator_set.tag_path
                element = sets_block.AddElement()
                element.SelectField("Reference:decorator set").Path = decorator_path
                placements = element.SelectField("Block:placements")
                # print("Max placements size", placements.MaximumElementCount)
                try:
                    _write_decorator_placements_serialized(placements, value, decorator_types, corinth)
                except Exception as error:
                    print(f"Serialized decorator write failed for {path}, using element writes: {error}")
                    _write_decorator_placements_elementwise(placements, value, decorator_types, corinth)
                
                    
        scenario.tag_has_changes = True
    print("--- Completed decorators tag write in", utils.human_time(time.perf_counter() - start, True))
                            
                    
