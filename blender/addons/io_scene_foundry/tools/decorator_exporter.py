from pathlib import Path
import time
import bpy
import types

from ..constants import WU_SCALAR

from ..managed_blam.decorator_set import DecoratorSetTag

from ..managed_blam.scenario import ScenarioTag
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
    
    collection_map = utils.create_parent_mapping(context)
    proxies = []
    with utils.DepsgraphRead():
        depsgraph = context.evaluated_depsgraph_get()

        for inst in depsgraph.object_instances:
            obj = inst.object
            original = obj.original
            nwo = original.nwo
            
            if inst.is_instance:
                obj = inst.instance_object
                original = obj.original
                nwo = original.nwo
            
            if not (original.type == 'EMPTY' and is_decorator_instance(nwo)):
                continue
            
            
            if utils.ignore_for_export_fast(original, collection_map, obj):
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
                for ob in value:
                    placement = placements.AddElement()
                    matrix = utils.halo_transforms_matrix(ob.matrix_world)
                    placement.SelectField("position").Data = matrix.translation
                    q = matrix.to_quaternion()
                    placement.SelectField("rotation").Data = q[1], q[2], q[3], q[0]
                    placement.SelectField("scale").Data = max(ob.matrix_world.to_scale().to_tuple())
                    
                    if ob.nwo.marker_game_instance_tag_variant_name.strip():
                        for dec_type in decorator_types:
                            if ob.nwo.marker_game_instance_tag_variant_name.lower() == dec_type.decorator_type_name:
                                placement.SelectField("type index").Data = dec_type.decorator_type_index
                                break
                            
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
                    
                    
        scenario.tag_has_changes = True
    print("--- Completed decorators tag write in", utils.human_time(time.perf_counter() - start, True))
                            
                    