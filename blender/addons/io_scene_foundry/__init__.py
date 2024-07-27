from pathlib import Path
import bpy
from bpy.app.handlers import persistent
from .tools.light_exporter import export_lights
from .tools.prefab_exporter import export_prefabs
from . import managed_blam

old_snapshot = {}
old_x = None

old_node_dict = {}

from .utils import (
    get_project_path,
)

from . import tools
from . import ui
from . import export
from . import keymap
from . import icons
from . import preferences

modules = [
    preferences,
    tools,
    ui,
    export,
    keymap,
    icons,
]

version = "1.0.0"

def msgbus_callback(context):
    try:
        ob = context.object
        if context.object:
            highlight = ob.data.nwo.highlight
            if highlight and context.mode == "EDIT_MESH":
                bpy.ops.nwo.face_layer_color_all(enable_highlight=highlight)
    except:
        pass

def subscribe(owner):
    subscribe_to = bpy.types.Object, "mode"
    bpy.msgbus.subscribe_rna(
        key=subscribe_to,
        owner=owner,
        args=(bpy.context,),
        notify=msgbus_callback,
        options={
            "PERSISTENT",
        },
    )

@persistent
def load_set_output_state(dummy):
    bpy.context.scene.nwo_export.show_output = utils.foundry_output_state

@persistent
def load_handler(dummy):
    context = bpy.context
    context.scene.nwo.export_in_progress = False
    context.scene.nwo.camera_sync_active = False
    # Add projects
    projects = utils.setup_projects_list()
    blend_path = bpy.data.filepath
    project_names = [p.name for p in projects]
    if projects and (not context.scene.nwo.scene_project or context.scene.nwo.scene_project not in project_names):
        for p in projects:
            if Path(blend_path).is_relative_to(p.project_path):
                context.scene.nwo.scene_project = p.name
                break
        else:
            context.scene.nwo.scene_project = projects[0].name

    # Handle old scenes with aleady existing regions/perms/global materials
    # update_tables_from_objects(context)

    # Add default sets if needed
    scene_nwo = context.scene.nwo
    if not scene_nwo.regions_table:
        default_region = scene_nwo.regions_table.add()
        default_region.old = "default"
        default_region.name = "default"

    if not scene_nwo.permutations_table:
        default_permutation = scene_nwo.permutations_table.add()
        default_permutation.old = "default"
        default_permutation.name = "default"
        
    if not scene_nwo.zone_sets and not scene_nwo.user_removed_all_zone_set:
        all_zone_set = scene_nwo.zone_sets.add()
        all_zone_set.name = "all"
        
    # prefs = get_prefs()
    # if prefs.poop_default:
    #     scene_nwo.default_mesh_type_ui = '_connected_geometry_mesh_type_poop'
    
    if not bpy.app.background:
        # Set game version from file
        proxy_left_active = context.scene.nwo.instance_proxy_running
        if proxy_left_active:
            for ob in context.view_layer.objects:
                if ob.nwo.proxy_parent:
                    utils.unlink(ob)

            context.scene.nwo.instance_proxy_running = False

        context.scene.nwo.instance_proxy_running = False
        # set output to on
        # context.scene.nwo_export.show_output = True

        # create warning if current project is incompatible with loaded managedblam.dll
        mb_path = managed_blam.mb_path
        if mb_path:
            if not str(mb_path).startswith(str(get_project_path())):
                utils.restart_blender()

        # like and subscribe
        subscription_owner = object()
        subscribe(subscription_owner)
        
        # Validate Managedblam
        try:
            project_path = Path(get_project_path())
            if not project_path.exists():
                print(f"Project path does not exist: {str(project_path)}")
                managed_blam.mb_operational = False
                return
            mb_path = Path(project_path, "bin", "managedblam")
            if not mb_path:
                print(f"Managedblam.dll does not exist: {str(mb_path)}")
                managed_blam.mb_operational = False
                return
            managed_blam.mb_operational = True
        except:
            pass
        
@persistent
def save_object_positions_to_tags(dummy):
    if bpy.context and bpy.context.scene:
        nwo = bpy.context.scene.nwo
        asset_type = nwo.asset_type
        if not utils.valid_nwo_asset(): return
        if nwo.prefabs_export_on_save and asset_type == 'scenario' and utils.is_corinth():
            print("Exporting Prefabs")
            export_prefabs()
        if nwo.lights_export_on_save and asset_type == 'scenario':
            print("Exporting Lights")
            export_lights()
            
def register():
    bpy.app.handlers.load_post.append(load_handler)
    bpy.app.handlers.load_post.append(load_set_output_state)
    bpy.app.handlers.save_post.append(save_object_positions_to_tags)
    # bpy.app.handlers.undo_post.append(get_temp_settings)
    for module in modules:
        module.register()
    icons.icons_activate()

def unregister():
    bpy.app.handlers.save_post.remove(save_object_positions_to_tags)
    bpy.app.handlers.load_post.remove(load_handler)
    bpy.app.handlers.load_post.remove(load_set_output_state)
    # bpy.app.handlers.undo_post.remove(get_temp_settings)
    for module in reversed(modules):
        module.unregister()