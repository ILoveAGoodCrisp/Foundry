from pathlib import Path
import time
import bpy
from math import tau
from mathutils import Matrix, Quaternion, Vector
import numpy as np
import types

from ..tags.decorator_set import DecoratorSetTag

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
DECORATOR_ATTR_SOURCE = "decorator_source"

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
        return tag_path.is_absolute() and tag_path.is_file() and tag_path.suffix.lower() in {'.decorator_set', '.detail_object_collection'}
    
    
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
        return (utils.valid_nwo_asset(context) and context.scene.nwo.asset_type == 'scenario'
                and context.scene.nwo.decorators_from_blender)

    def execute(self, context):
        current_selection = context.selected_objects[:]
        current_object = context.object
        try:
            count = export_decorators(utils.is_corinth(context))
        except Exception as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        for ob in current_selection:
            ob.select_set(True)
        context.view_layer.objects.active = current_object
        self.report({'INFO'}, f'Exported {count} decorator placements')
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
    return nwo.marker_type == '_connected_geometry_marker_type_decorator'

def _decorator_cloud_marker_data(ob):
    tag_path = ob.get(DECORATOR_TAG_PROP) or ob.nwo.marker_game_instance_tag_name
    variant = ob.get(DECORATOR_VARIANT_PROP) or ob.nwo.marker_game_instance_tag_variant_name
    return tag_path, variant

def _is_decorator_cloud(ob):
    if not (ob and ob.type == 'MESH' and ob.get(DECORATOR_CLOUD_PROP)):
        return False
    
    tag_path, _ = _decorator_cloud_marker_data(ob)
    return isinstance(tag_path, str) and tag_path.lower().endswith((".decorator_set", ".detail_object_collection"))

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
                if not utils.ignore_for_export_fast(original, collection_map, parent):
                    proxies.extend(_decorator_cloud_proxies(original, inst.matrix_world))
                continue
            # Geometry Nodes emits preview instances for these same placements.
            # Their per-point settings are already read from the authored cloud.
            if original.get(DECORATOR_INSTANCE_SOURCE_PROP):
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
    sources = _color_attribute(mesh, DECORATOR_ATTR_SOURCE, (-1, ob.nwo.detail_object_sprite_index,
        ob.nwo.decorator_permutation_index, ob.nwo.decorator_cluster_index))
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
        nwo.scenario_child_scenario = ob.nwo.scenario_child_scenario
        nwo.marker_decorator_tag_name = tag_path
        nwo.marker_game_instance_tag_variant_name = variant
        nwo.decorator_type_index = ob.nwo.decorator_type_index
        nwo.detail_object_sprite_index, nwo.decorator_permutation_index, nwo.decorator_cluster_index = (round(float(v)) for v in sources[idx][1:])
        nwo.region_name = utils.true_region(ob.nwo)
        nwo.region_name_locked = ""
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
    if instance_collection is None and not _decorator_cloud_marker_data(ob)[0].endswith('.detail_object_collection'):
        raise ValueError(f"Decorator cloud {ob.name} has no instanced collection source")
    
    collection = collection or (ob.users_collection[0] if ob.users_collection else bpy.context.scene.collection)
    mesh = ob.data
    created = []
    for proxy in _decorator_cloud_proxies(ob, Matrix.Identity(4)):
        new_ob = bpy.data.objects.new(proxy.name, None)
        new_ob.empty_display_type = 'ARROWS'
        new_ob.matrix_world = proxy.matrix_world
        if instance_collection is not None:
            new_ob.instance_type = 'COLLECTION'
            new_ob.instance_collection = instance_collection
        new_ob.nwo.marker_type = '_connected_geometry_marker_type_decorator'
        new_ob.nwo.marker_game_instance_tag_name = proxy.nwo.marker_game_instance_tag_name
        new_ob.nwo.marker_game_instance_tag_variant_name = proxy.nwo.marker_game_instance_tag_variant_name
        new_ob.nwo.marker_instance = True
        new_ob.nwo.scenario_child_scenario = proxy.nwo.scenario_child_scenario
        new_ob.nwo.decorator_motion_scale = proxy.nwo.decorator_motion_scale
        new_ob.nwo.decorator_ground_tint = proxy.nwo.decorator_ground_tint
        new_ob.nwo.decorator_tint = proxy.nwo.decorator_tint
        for name in ('region_name', 'decorator_type_index', 'detail_object_sprite_index', 'decorator_permutation_index', 'decorator_cluster_index'):
            setattr(new_ob.nwo, name, getattr(proxy.nwo, name))
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

def export_decorators(corinth, decorator_objects = None):
    scene_nwo = utils.get_scene_props()
    if not scene_nwo.decorators_from_blender:
        return 0
    scenario_path = utils.get_asset_tag(".scenario", True)
    context = bpy.context
    if decorator_objects is None:
        decorator_objects = gather_decorators(context)

    game = utils.get_project(scene_nwo.scene_project).game
    from .scenario.targets import scenario_targets
    default_child = scene_nwo.decorators_from_blender_child_scenario if corinth else ''
    count = 0
    with scenario_targets(decorator_objects, scenario_path=scenario_path, tags_root=utils.get_tags_path(),
            game=game, default_child=default_child, include_existing_children=True) as targets:
        if game == 'halo1':
            # H1 detail instances live in shared BSP tags. Write each BSP once,
            # with one consistent palette across the parent and child scenarios.
            parent = targets[0][0]
            count = export_detail_objects(parent, decorator_objects)
            palette = parent.block(parent.tag.root(), 'detail object collection palette')
            for child, _ in targets[1:]:
                child.block(child.tag.root(), 'detail object collection palette').clear()
                for i in range(len(palette)):
                    child.block(child.tag.root(), 'detail object collection palette').paste(i, palette.snapshot(i))
                child.tag_has_changes = True
            return count
        for scenario, objects in targets:
            count += _export_decorators_to_scenario(scenario, objects)
    return count


def _export_decorators_to_scenario(scenario, decorator_objects):
    game = scenario.game
    
    from ..tags.scenario import ScenarioDecoratorPlacement, ScenarioDecoratorSet
    from ..tags.scenario_decorators import replace_decorators
    decorator_sets = {}
    MAX_PLACEMENTS_PER_SET = 262_144
    for ob in decorator_objects:
        tag_path = utils.relative_path(ob.nwo.marker_decorator_tag_name)
        index = 0

        while True:
            values = decorator_sets.setdefault((tag_path, index), [])
            if len(values) < MAX_PLACEMENTS_PER_SET:
                values.append(ob)
                break
            index += 1

    records = []
    for (path, _), objects in decorator_sets.items():
        with DecoratorSetTag(path=path) as definition:
            types = definition.get_decorator_types()
            types_by_name = _decorator_type_indices(types)
            types_by_index = {item.decorator_type_index: item.decorator_type_name.lower() for item in types}
        placements = []
        for ob in objects:
            variant = ob.nwo.marker_game_instance_tag_variant_name.strip().lower()
            if not types_by_name or variant and variant not in types_by_name:
                raise ValueError(f'{ob.name}: invalid decorator type {variant!r}')
            type_index = types_by_name[variant] if variant else next(iter(types_by_name.values()))
            imported_index = ob.nwo.decorator_type_index
            if variant and types_by_index.get(imported_index) == variant:
                type_index = imported_index
            matrix = utils.halo_transforms_matrix(ob.matrix_world)
            q = matrix.to_quaternion()
            placements.append(ScenarioDecoratorPlacement(tuple(matrix.translation), (q.x, q.y, q.z, q.w),
                max(ob.matrix_world.to_scale()), type_index,
                _byte_value(ob.nwo.decorator_motion_scale * 255), _byte_value(ob.nwo.decorator_ground_tint * 255),
                tuple(utils.linear_to_srgb(c) for c in ob.nwo.decorator_tint),
                ob.nwo.decorator_permutation_index, ob.nwo.decorator_cluster_index))
        records.append(ScenarioDecoratorSet(path, Path(path).stem, tuple(placements)))

    print("--- Writing decorators to Tag")
    start = time.perf_counter()
    replace_decorators(scenario, records)
    if game == 'halo2' and records:
        utils.print_warning('Halo 2 decorator source placements exported. Rebuild decorator caches in Sapien (decorator_rebuild_all).')
    print("--- Completed decorators tag write in", utils.human_time(time.perf_counter() - start, True))
    return sum(len(record.placements) for record in records)


def export_detail_objects(scenario_path, objects):
    from contextlib import nullcontext
    from ..tags.halo1_detail_objects import DetailObjectPlacement, replace_detail_objects
    from ..tags.scenario import ScenarioDocument
    tags_root = utils.get_tags_path()
    document = nullcontext(scenario_path) if isinstance(scenario_path, ScenarioDocument) else ScenarioDocument(scenario_path, tags_root=tags_root, game='halo1', must_exist=True)
    with document as scenario:
        if scenario.read_only:
            raise RuntimeError('Cannot export detail objects during a read-only tag operation')
        bsps = [scenario.reference(row, 'structure bsp') for row in scenario.block(scenario.tag.root(), 'structure bsps')]
        placements = []
        type_cache = {}
        for ob in objects:
            path = utils.relative_path(ob.nwo.marker_decorator_tag_name)
            if path not in type_cache:
                with DecoratorSetTag(path=path) as collection:
                    type_cache[path] = _decorator_type_indices(collection.get_decorator_types())
            variant = ob.nwo.marker_game_instance_tag_variant_name.strip().lower()
            types = type_cache[path]
            if not types or variant and variant not in types:
                raise ValueError(f'{ob.name}: invalid detail object type {variant!r}')
            type_index = types[variant] if variant else next(iter(types.values()))
            region = utils.true_region(ob.nwo)
            bsp_index = next((i for i, ref in enumerate(bsps) if ref is not None and ref.ShortName == region), 0 if len(bsps) == 1 else -1)
            if bsp_index < 0:
                raise ValueError(f'{ob.name}: select the BSP for this detail object')
            color = [max(0, min(255, round(utils.linear_to_srgb(c) * 255))) for c in ob.nwo.decorator_tint]
            packed_color = (color[0] >> 3) << 11 | (color[1] >> 2) << 5 | color[2] >> 3
            placements.append(DetailObjectPlacement(path, tuple(utils.halo_transforms_matrix(ob.matrix_world).translation),
                type_index, ob.nwo.detail_object_sprite_index, packed_color, bsp_index))
        replace_detail_objects(scenario, placements)
    return len(placements)
                            
                    
