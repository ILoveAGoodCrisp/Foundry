

from pathlib import Path
import bpy
import os
from ..utils import get_project_path, get_scene_props, get_tags_path, is_corinth, os_sep_partition, redraw_area

global_items = {}
cinematic_event_props = ("sound_tag", "female_sound_tag", "effect")
scene_props = ('template_render_model', 'template_collision_model', 'template_physics_model', 'template_model_animation_graph', 'parent_animation_graph', 'render_model_path', 
               'template_model', 'template_biped', 'template_crate', 'template_creature', 'template_device_control', 'template_device_dispenser', 'template_device_machine',
               'template_device_terminal', 'template_effect_scenery', 'template_equipment', 'template_giant', 'template_scenery', 'template_vehicle', 'template_weapon', 'template_scenario', 'cinematic_scenario', 'animation_cmd_path')

event_data_props = 'event_sound_tag', 'event_effect_tag', 'event_model'

class NWO_GetTagsList(bpy.types.Operator):
    bl_label = ""
    bl_idname = 'nwo.get_tags_list'
    bl_property = "tag_list"
    bl_description = "Returns a searchable list of valid tags"
    bl_options = {"UNDO"}

    def tag_list_items(self, context):
        global global_items
        if global_items.get(self.list_type, 0):
            return global_items[self.list_type]
        else:
            global_items[self.list_type] = []

        tags_dir = get_tags_path()
        ext_list = extensions_from_type(self.list_type)
        tags = walk_tags_dir(tags_dir, ext_list)
        for t in tags:
            if type(self.list_type) == str:
                display = f"{Path(Path(t).parent.name, Path(t).name)}"
            else:
                display = str(Path(t).name)
                
            if len(display) > 35:
                global_items[self.list_type].append((t, f"...{display[-35:]}", ""))
            else:
                global_items[self.list_type].append((t, display, ""))

        return global_items[self.list_type]

    tag_list: bpy.props.EnumProperty(
        name="Tags",
        items=tag_list_items,
    )

    # comma delimited
    list_type: bpy.props.StringProperty()
    
    def execute(self, context):
        scene_nwo = get_scene_props()
        if self.list_type in scene_props:
            nwo = scene_nwo
        elif self.list_type == 'shader_path':
            nwo = context.object.active_material.nwo
        elif self.list_type.startswith('light'):
            nwo = context.object.data.nwo
        elif self.list_type in cinematic_event_props:
            nwo = scene_nwo.cinematic_events[scene_nwo.active_cinematic_event_index]
        elif self.list_type in event_data_props:
            animation = scene_nwo.animations[scene_nwo.active_animation_index]
            event = animation.animation_events[animation.active_animation_event_index]
            nwo = event.event_data[event.active_event_data_index]
        else:
            nwo = context.object.nwo
        setattr(nwo, self.list_type, self.tag_list)
        redraw_area(context, 'VIEW_3D')
        return {'FINISHED'}
    
    def invoke(self, context, event):
        wm = context.window_manager
        wm.invoke_search_popup(self)
        return {"FINISHED"}
    
def extensions_from_type(list_type):
    match list_type:
        case "marker_game_instance_tag_name":
            return (".crate", ".scenery", ".effect_scenery", ".device_control", ".device_machine", ".device_terminal",
                        ".device_dispenser", ".biped", ".creature", ".giant", ".vehicle", ".weapon", ".equipment",
                        ".prefab", ".light", ".cheap_light", ".leaf", ".decorator_set")
        case 'marker_looping_effect':
            return (".effect")
        case 'marker_light_cone_tag':
            return (".light_cone")
        case 'marker_light_cone_curve':
            return (".curve_scalar")
        case 'fog_appearance_tag':
            return (".planar_fog_parameters")
        case 'light_tag_override':
            return (".light")
        case 'light_shader_reference':
            return (".render_method_definition")
        case 'light_gel_reference':
            return (".bitmap")
        case 'light_lens_flare_reference':
            return (".lens_flare")
        case 'template_render_model':
            return (".render_model")
        case 'template_collision_model':
            return (".collision_model")
        case 'template_model_animation_graph':
            return (".model_animation_graph")
        case 'parent_animation_graph':
            return (".model_animation_graph")
        case 'template_physics_model':
            return (".physics_model")
        case 'fp_model_path':
            return (".render_model")
        case 'gun_model_path':
            return (".render_model")
        case 'render_model_path':
            return (".render_model")
        case 'shader_path':
            return (".material", '.shader', '.shader_cortana', '.shader_custom', '.shader_decal', '.shader_foliage', '.shader_fur', '.shader_fur_stencil', '.shader_glass', '.shader_halogram', '.shader_mux', '.shader_mux_material', '.shader_screen', '.shader_skin', '.shader_terrain', 'shader_water')
        case 'template_model':
            return (".model")
        case 'template_biped':
            return (".biped")
        case 'template_crate':
            return ('.crate')
        case 'template_creature':
            return ('.creature')
        case 'template_device_control':
            return ('.device_control')
        case 'template_device_dispenser':
            return ('.device_dispenser')
        case 'template_device_machine':
            return ('.device_machine')
        case 'template_device_terminal':
            return ('.device_terminal')
        case 'template_effect_scenery':
            return ('.effect_scenery')
        case 'template_equipment':
            return ('.equipment')
        case 'template_giant':
            return ('.giant')
        case 'template_scenery':
            return ('.scenery')
        case 'template_vehicle':
            return ('.vehicle')
        case 'template_weapon':
            return ('.weapon')
        case 'template_weapon':
            return ('.weapon')
        case 'template_scenario':
            return ('.scenario')
        case 'cinematic_object':
            return (".crate", ".scenery", ".effect_scenery", ".device_control", ".device_machine", ".device_terminal",
                        ".device_dispenser", ".biped", ".creature", ".giant", ".vehicle", ".weapon", ".equipment")
        case 'cinematic_scenario':
            return (".scenario")
        case 'animation_cmd_path':
            return (".model_animation_graph")
        case 'sound_tag':
            return (".sound")
        case 'female_sound_tag':
            return (".sound")
        case 'effect':
            return (".effect")
        case 'event_sound_tag':
            return (".sound")
        case 'event_effect_tag':
            return (".effect")
        case 'event_model':
            return (".model")
        
def walk_tags_dir(tags_dir, ext_list):
    tags_set = set()
    fav_tags = set()
    # Display the favorite tags first, so grab these
    if is_corinth():
        fav_tags_file = os.path.join(get_project_path(), "FavoriteTags.txt")
        if os.path.exists(fav_tags_file):
            with open(fav_tags_file, "r") as file:
                for line in file:
                    l = line.strip("\n ")
                    if l and not l.startswith(";") and l.endswith(ext_list):
                        fav_tags.add(l)

    for root, dirs, files in os.walk(tags_dir):
        for file in files:
            if file.endswith(ext_list):
                relative_path = str(Path(root, file).relative_to(tags_dir))
                if relative_path not in fav_tags:
                    tags_set.add(relative_path)

    tags_sorted = sorted(tags_set, key=lambda x: os_sep_partition(x, True))
    tags = [t for t in fav_tags]
    tags.extend(tags_sorted)
    return tags

class NWO_TagExplore(bpy.types.Operator):
    bl_label = "Select Tag"
    bl_idname = 'nwo.tag_explore'
    bl_options = {'UNDO'}
    bl_property = "prop"
    bl_description = 'Opens a file explorer dialog filtered for valid tags'

    filter_glob: bpy.props.StringProperty(
        default="*",
        options={"HIDDEN", "SKIP_SAVE"},
    )

    filepath: bpy.props.StringProperty(
        name="path", description="Set the path to the tag", subtype="FILE_PATH"
    )

    prop: bpy.props.StringProperty()

    def execute(self, context):
        scene_nwo = get_scene_props()
        if self.prop in scene_props:
            nwo = scene_nwo
        elif self.prop == 'shader_path':
            nwo = context.object.active_material.nwo
        elif self.prop.startswith('light'):
            nwo = context.object.data.nwo
        elif self.prop in cinematic_event_props:
            nwo = scene_nwo.cinematic_events[scene_nwo.active_cinematic_event_index]
        elif self.prop in event_data_props:
            animation = scene_nwo.animations[scene_nwo.active_animation_index]
            event = animation.animation_events[animation.active_animation_event_index]
            nwo = event.event_data[event.active_event_data_index]
        else:
            nwo = context.object.nwo
        setattr(nwo, self.prop, self.filepath)
        return {"FINISHED"}

    def invoke(self, context, event):
        self.filepath = get_tags_path() + os.sep
        self.filter_glob = get_glob_from_prop(self.prop)
        context.window_manager.fileselect_add(self)

        return {"RUNNING_MODAL"}
    
    def draw(self, context):
        pass
    
def get_glob_from_prop(prop):
    match prop:
        case 'marker_game_instance_tag_name':
            return "*.biped;*.crate;*.creature;*.device_*;*.effect_sc*;*.equipment;*.giant;*.scenery;*.vehicle;*.weapon;*.prefab;*.cheap_light;*.light;dec*_set"
        case 'fog_appearance_tag':
            return "*.pl*parameters"
        case 'marker_looping_effect':
            return "*.effect"
        case 'marker_light_cone_tag':
            return "*.light_cone"
        case 'marker_light_cone_curve':
            return "*.curve_scalar"
        case 'light_tag_override':
            return "*.light"
        case 'light_shader_reference':
            return "*.re*definition"
        case 'light_gel_reference':
            return "*.bitmap"
        case 'light_lens_flare_reference':
            return "*.lens_flare"
        case 'template_render_model':
            return "*.render_model"
        case 'template_collision_model':
            return "*.collision_mo*"
        case 'template_model_animation_graph':
            return "*.model_*_graph"
        case 'parent_animation_graph':
            return "*.model_*_graph"
        case 'template_physics_model':
            return "*.physics_model"
        case 'render_model_path':
            return "*.render_model"
        case 'shader_path':
            return "*.material;*.shade*"
        case 'template_model':
            return "*.model"
        case 'template_biped':
            return "*.biped"
        case 'template_crate':
            return '*.crate'
        case 'template_creature':
            return '*.creature'
        case 'template_device_control':
            return '*.device_con*'
        case 'template_device_dispenser':
            return '*.device_d*'
        case 'template_device_machine':
            return '*.device_ma*'
        case 'template_device_terminal':
            return '*.device_te*'
        case 'template_effect_scenery':
            return '*.effect_sc*'
        case 'template_equipment':
            return '*.equipment'
        case 'template_giant':
            return '*.giant'
        case 'template_scenery':
            return '*.scenery'
        case 'template_vehicle':
            return '*.vehicle'
        case 'template_weapon':
            return '*.weapon'
        case 'template_scenario':
            return '*.scenario'
        case 'cinematic_object':
            return "*.biped;*.crate;*.creature;*.device_*;*.effect_sc*;*.equipment;*.giant;*.scenery;*.vehicle;*.weapon"
        case 'cinematic_scenario':
            return '*.scenario'
        case 'animation_cmd_path':
            return "*.model_*_graph"
        case 'sound_tag':
            return "*.sound"
        case 'female_sound_tag':
            return "*.sound"
        case 'effect':
            return "*.effect"
        case 'event_sound_tag':
            return "*.sound"
        case 'event_effect_tag':
            return "*.effect"
        case 'event_model':
            return "*.model"
        case _:
            return "*"