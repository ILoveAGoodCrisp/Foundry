from pathlib import Path
import addon_utils
from bpy.app.handlers import persistent
import bpy

from .tools.light_exporter import export_lights
from .tools.prefab_exporter import export_prefabs
from .tools.decorator_exporter import export_decorators

from . import managed_blam
from . import utils

load_handler_complete = False

def msgbus_callback(context):
    try:
        ob = context.object
        if context.object:
            highlight = ob.data.nwo.highlight
            if highlight and context.mode == "EDIT_MESH":
                bpy.ops.nwo.face_attribute_color_all(enable_highlight=highlight)
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
    utils.get_export_props().show_output = utils.foundry_output_state
    
@persistent
def import_handler(import_context):
    # Handles adding region / permutations to the scene and setting up instance proxies

    proxies = []
    for item in import_context.import_items:
        id = item.id
        if id is None or id.id_type is None:
            continue
        match id.id_type:
            case 'OBJECT':
                if id.nwo.region_name:
                    utils.add_region(id.nwo.region_name)
                if id.nwo.permutation_name:
                    utils.add_permutation(id.nwo.permutation_name)
                
                if id.type == 'MESH':
                    for prop in id.data.nwo.face_props:
                        if prop.type == 'region':
                            if prop.region_name:
                                utils.add_region(prop.region_name)
                                
                    if id.nwo.proxy_type:
                        proxies.append(item.id)
                            
                    
            case 'COLLECTION':
                match id.nwo.type:
                    case 'region':
                        if id.nwo.region:
                            utils.add_region(id.nwo.region)
                    case 'permutation':
                        if id.nwo.permutation:
                            utils.add_permutation(id.nwo.permutation)
    
    if proxies:
        # proxy_scene = utils.get_foundry_storage_scene()
        for ob in proxies:
            utils.unlink(ob)
            # proxy_scene.collection.objects.link(ob)
    
@persistent
def load_handler(dummy):
    context = bpy.context
    
    nwo = utils.get_scene_props()
    
    if not nwo.is_main_scene:
        nwo.is_main_scene = True
    
    nwo.export_in_progress = False
    nwo.camera_sync_active = False
    # Add projects
    projects = utils.setup_projects_list()
    blend_path = bpy.data.filepath
    project_names = [p.name for p in projects]
    if projects and (not nwo.scene_project or nwo.scene_project not in project_names):
        if blend_path:
            for p in projects:
                if Path(blend_path).is_relative_to(p.project_path):
                    nwo.scene_project = p.name
                    break
            else:
                nwo.scene_project = projects[0].name
        else:
            nwo.scene_project = projects[0].name

    # Handle old scenes with aleady existing regions/perms/global materials
    # update_tables_from_objects(context)
    
    module_name = bpy.context.preferences.addons[__package__].module
    for m in addon_utils.modules():
        if m.__name__ == module_name:
            utils.module = m

    # Add default sets if needed
    if not nwo.regions_table:
        default_region = nwo.regions_table.add()
        default_region.old = "default"
        default_region.name = "default"

    if not nwo.permutations_table:
        default_permutation = nwo.permutations_table.add()
        default_permutation.old = "default"
        default_permutation.name = "default"
        
    if not nwo.cinematic_scenes:
        default_cin_scene = nwo.cinematic_scenes.add()
        default_cin_scene.name = "default"
        default_cin_scene.scene = nwo.id_data
        
    # if not scene_nwo.zone_sets and not scene_nwo.user_removed_all_zone_set:
    #     all_zone_set = scene_nwo.zone_sets.add()
    #     all_zone_set.name = "default"
        
    # prefs = get_prefs()
    # if prefs.poop_default:
    #     scene_nwo.default_mesh_type = '_connected_geometry_mesh_type_poop'
    
    if not bpy.app.background:
        # Set game version from file
        proxy_left_active = nwo.instance_proxy_running
        if proxy_left_active:
            for ob in context.view_layer.objects:
                if ob.nwo.proxy_type:
                    utils.unlink(ob)

            nwo.instance_proxy_running = False

        nwo.instance_proxy_running = False

        # create warning if current project is incompatible with loaded managedblam.dll
        mb_path = managed_blam.mb_path
        if mb_path:
            if not str(mb_path).startswith(str(utils.get_project_path())):
                if nwo.sidecar_path:
                    utils.restart_blender()
                else:
                    possible_project = utils.get_project_from_path(str(Path(mb_path).parent.parent))
                    if possible_project is not None:
                        nwo.scene_project = possible_project.name

        # like and subscribe
        subscription_owner = object()
        subscribe(subscription_owner)
        
        # Validate Managedblam
        try:
            project_path = Path(utils.get_project_path())
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
    
    # Ensure icons loaded
    from . import icons
    if icons.icons_active:
        icons.unregister()
    icons.register()
    if not icons.icons_active:
        icons.icons_activate()
    
    global load_handler_complete
    load_handler_complete = True
        
@persistent
def save_object_positions_to_tags(dummy):
    if bpy.context and bpy.context.scene:
        nwo = utils.get_scene_props()
        asset_type = nwo.asset_type
        if not utils.valid_nwo_asset(): return
        if nwo.prefabs_export_on_save and asset_type == 'scenario' and utils.is_corinth():
            print("Exporting Prefabs")
            export_prefabs()
        if nwo.lights_export_on_save and asset_type == 'scenario':
            print("Exporting Lights")
            export_lights(*utils.get_asset_info())
        if nwo.decorators_export_on_save and asset_type == 'scenario' and nwo.decorators_from_blender:
            print("Exporting Decorators")
            export_decorators(utils.is_corinth(bpy.context))