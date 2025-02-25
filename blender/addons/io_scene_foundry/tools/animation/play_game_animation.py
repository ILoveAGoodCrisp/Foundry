from pathlib import Path
import bpy

from ...managed_blam.animation import AnimationTag
from ... import utils

animation_names = None
last_graph_path = None

def anim_play_cmd_to_clipboard(animation_name: str, graph_path="", scenery=False, loop=False, object_expression="(player_get 0)") -> str:
    if scenery:
        command = "scenery_animation_start"
    else:
        command = "custom_animation"
    if loop:
        command += "_loop"
    
    command += f" {object_expression} "
    
    command += graph_path
        
    command += f' {animation_name.strip().lower().replace(" ", ":")}'
    
    if not scenery:
        command += f" 0"
        
    utils.copy_to_clipboard(command)
    return command


class NWO_OT_AnimationNameSearch(bpy.types.Operator):
    bl_idname = 'nwo.animation_name_search'
    bl_label = "Search Animation Names"
    bl_property = "selected_animation_name"
    bl_description = "Returns a searchable list of animation names"
    bl_options = {"REGISTER", "UNDO"}
    
    @classmethod
    def poll(cls, context):
        return context.scene.nwo.animations or Path(utils.get_tags_path(), utils.relative_path(context.scene.nwo.animation_cmd_path)).exists()
    
    def animation_name_items(self, context):
        if animation_names:
            return animation_names
        else:
            return [("none", "No Animations in Graph", "")]

    selected_animation_name: bpy.props.EnumProperty(
        name="Animation Name",
        items=animation_name_items,
    )
    
    area: bpy.props.StringProperty()
    
    def execute(self, context):
        context.scene.nwo.animation_cmd_name = self.selected_animation_name
        utils.redraw_area(context, 'VIEW_3D')
        return {'FINISHED'}
    
    def invoke(self, context, event):
        global animation_names
        global last_graph_path
        nwo = context.scene.nwo
        path = utils.relative_path(nwo.animation_cmd_path)
        using_asset_path = False
        if not nwo.animation_cmd_path and utils.valid_nwo_asset(context):
            asset_path = Path(utils.get_asset_path())
            asset_name = asset_path.name
            path = str(Path(asset_path, asset_name))
            using_asset_path = True
            
        if animation_names is None or last_graph_path != path:
            last_graph_path = path
            if using_asset_path:
                if nwo.animations:
                    animation_names = [(a.name, a.name, "") for a in nwo.animations]
                else:
                    animation_names = []
            else:
                with AnimationTag(path=path) as animation:
                    names = animation.get_animation_names()
                    animation_names = [(n, n, "") for n in names]
            
        wm = context.window_manager
        wm.invoke_search_popup(self)
        return {"FINISHED"}

class NWO_OT_PlayGameAnimation(bpy.types.Operator):
    bl_idname = "nwo.play_game_animation"
    bl_label = "Copy Play Animation Command"
    bl_description = "Copies to the clipboard the command to play the selected animation on the given object"
    bl_options = {"REGISTER"}

    def execute(self, context):
        nwo = context.scene.nwo
        anim_name = nwo.animation_cmd_name.strip()
        if not anim_name:
            if nwo.animations and nwo.active_animation_index != -1:
                anim_name = nwo.animations[nwo.active_animation_index].name
            else:
                self.report({'WARNING'}, "No Animation name specified")
                return {'CANCELLED'}
            
        expression = "(player_get 0)"
        if nwo.animation_cmd_object_type != 'player' and nwo.animation_cmd_expression:
            expression = nwo.animation_cmd_expression
        
        path = utils.relative_path(nwo.animation_cmd_path)
        if not nwo.animation_cmd_path and utils.valid_nwo_asset(context):
            asset_path = Path(utils.get_asset_path())
            asset_name = asset_path.name
            path = str(Path(asset_path, f"{asset_name}.model_animation_graph"))
            
        if not path.strip(". "):
            # See if we can get the graph from the armature
            ob = utils.get_rig_prioritize_active(context)
            if ob is None or not ob.nwo.node_order_source:
                self.report({'WARNING'}, f"No graph path specified")
                return {'CANCELLED'}
    
            path = str(Path(utils.relative_path(ob.nwo.node_order_source)).with_suffix(".model_animation_graph"))

        
        full_path = Path(utils.get_tags_path(), path)
        if not (full_path.exists() and full_path.is_absolute()):
            self.report({'WARNING'}, f"Graph path does not exist: {full_path}")
            return {'CANCELLED'}
        
        command = anim_play_cmd_to_clipboard(anim_name, graph_path=path, scenery=nwo.animation_cmd_object_type == 'scenery', loop=nwo.animation_cmd_loop, object_expression=expression)
        self.report({'INFO'}, f"Copied to clipboard: {command}")
        return {"FINISHED"}
