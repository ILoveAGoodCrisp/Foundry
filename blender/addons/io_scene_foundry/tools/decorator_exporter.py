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
            decorator_type_items = decorator.get_type_names()
            if not decorator_type_items:
                return [("default", "default", "")]
            
        items = []
        for v in decorator_type_items:
            items.append((v, v, ""))

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
    
import bpy
import time
from mathutils import Matrix

def gather_decorators(context):
    print("--- Start decorator gather (depsgraph, proxy objects)")
    start = time.perf_counter()

    def matches_nwo(obj):
        try:
            mt = obj.nwo.marker_type
            name = obj.nwo.marker_game_instance_tag_name
            ign = obj.nwo.ignore_for_export
        except Exception:
            return False
        if mt != '_connected_geometry_marker_type_game_instance':
            return False
        if not (isinstance(name, str) and name.lower().endswith(".decorator_set")):
            return False
        if getattr(obj.nwo, "ignore_for_export", False):
            return False
        return True

    depsgraph = context.evaluated_depsgraph_get()
    proxies = []
    temp_objects = set()

    for inst in depsgraph.object_instances:
        eval_obj = inst.instance_object
        if eval_obj is None:
            continue

        inst_mat = inst.matrix_world.copy()

        src = bpy.data.objects.get(eval_obj.name, None)
        if src is None:
            src = eval_obj

        if src.type == 'EMPTY' and matches_nwo(src):
            proxy = types.SimpleNamespace()
            proxy.name = src.name
            proxy.type = 'EMPTY'
            proxy.nwo = src.nwo
            proxy.matrix_world = inst_mat
            proxies.append(proxy)

    print("--- Gathered decorators in: {:.3f}s".format(time.perf_counter() - start))
    return proxies, temp_objects
    
def export_decorators(corinth, decorator_objects = None):
    scenario_path = utils.get_asset_tag(".scenario", True)
    if corinth and bpy.context.scene.nwo.decorators_from_blender_child_scenario.strip():
        scenario_path = str(Path(scenario_path).with_name(bpy.context.scene.nwo.decorators_from_blender_child_scenario).with_suffix(".scenario"))
    
    tags_dir = utils.get_tags_path()
    context = bpy.context
    temp_objects=set()
    if decorator_objects is None:
        decorator_objects, temp_objects = gather_decorators(context)
    
    decorator_sets = {}
    for ob in decorator_objects:
        decorator_sets.setdefault(utils.relative_path(ob.nwo.marker_game_instance_tag_name.lower()), []).append(ob)
    
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
        
        for key, value in decorator_sets.items():
            path = utils.relative_path(ob.nwo.marker_game_instance_tag_name)
            if path and Path(tags_dir, path).exists():
                with DecoratorSetTag(path=path) as decorator_set:
                    decorator_types = decorator_set.get_type_names()
                element = sets_block.AddElement()
                element.SelectField("Reference:decorator set").Path = scenario._TagPath_from_string(key)
                placements = element.SelectField("Block:placements")
                for ob in value:
                    placement = placements.AddElement()
                    matrix = utils.halo_transform_matrix(ob.matrix_world)
                    placement.SelectField("position").Data = matrix.translation
                    q = matrix.to_quaternion()
                    placement.SelectField("rotation").Data = q[1], q[2], q[3], q[0]
                    placement.SelectField("scale").Data = max(matrix.to_scale().to_tuple()) / WU_SCALAR
                    
                    if ob.nwo.marker_game_instance_tag_variant_name.strip():
                        for idx, dec_type in enumerate(decorator_types):
                            if ob.nwo.marker_game_instance_tag_variant_name.lower() == dec_type.lower():
                                placement.SelectField("type index").Data = idx
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
        
    if temp_objects:
        bpy.data.batch_remove(temp_objects)
                            
                    