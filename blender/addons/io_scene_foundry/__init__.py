# ##### BEGIN MIT LICENSE BLOCK #####
#
# MIT License
#
# Copyright (c) 2024 Crisp
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# ##### END MIT LICENSE BLOCK #####

import atexit
from pathlib import Path
import bpy
from bpy.app.handlers import persistent
import os
import signal

from io_scene_foundry.managed_blam import blam
from io_scene_foundry.tools.light_exporter import export_lights_tasks
from io_scene_foundry.tools.prefab_exporter import export_prefabs_tasks
from io_scene_foundry.utils.nwo_utils import is_corinth, restart_blender, setup_projects_list, unlink, valid_nwo_asset
from io_scene_foundry.utils import nwo_globals

old_snapshot = {}
old_x = None

old_node_dict = {}

bl_info = {
    "name": "Foundry - Halo Blender Creation Kit",
    "author": "Crisp",
    "version": (343, 7, 343),
    "blender": (4, 1, 0),
    "location": "File > Export",
    "description": "Asset Exporter and Toolset for Halo Reach, Halo 4, and Halo 2 Anniversary Multiplayer: BUILD_VERSION_STR",
    "warning": "",
    "wiki_url": "https://c20.reclaimers.net/general/tools/foundry",
    "support": "COMMUNITY",
    "category": "Export",
}

def foundry_blam_cleanup():
    for p in nwo_globals.processes:
        os.kill(p.pid, signal.SIGTERM)

#check that version is 4.1.0 or greater
if bpy.app.version < (4, 1, 0):
    raise Warning("Blender version must be 4.1.0 or greater to use Foundry")
else:
    from io_scene_foundry.utils import nwo_globals

    from io_scene_foundry.utils.nwo_utils import (
        get_project_path,
    )

    from . import tools
    from . import ui
    from . import export
    from . import managed_blam
    from . import keymap
    from . import icons


    modules = [
        tools,
        ui,
        managed_blam,
        export,
        keymap,
        icons,
    ]

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
        bpy.context.scene.nwo_export.show_output = nwo_globals.foundry_output_state

    @persistent
    def load_handler(dummy):
        context = bpy.context
        context.scene.nwo.shader_sync_active = False
        context.scene.nwo.light_sync_active = False
        context.scene.nwo.export_in_progress = False
        atexit.register(foundry_blam_cleanup)
        # Add projects
        projects = setup_projects_list()
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
                        unlink(ob)

                context.scene.nwo.instance_proxy_running = False

            context.scene.nwo.instance_proxy_running = False
            # set output to on
            # context.scene.nwo_export.show_output = True

            # create warning if current project is incompatible with loaded managedblam.dll
            mb_path = nwo_globals.mb_path
            if mb_path:
                if not str(mb_path).startswith(str(get_project_path())):
                    restart_blender()

            # like and subscribe
            subscription_owner = object()
            subscribe(subscription_owner)
            
            # Validate Managedblam
            try:
                import clr
                nwo_globals.clr_installed = True
                project_path = Path(get_project_path())
                if not project_path.exists():
                    print(f"Project path does not exist: {str(project_path)}")
                    nwo_globals.mb_operational = False
                    return
                mb_path = Path(project_path, "bin", "managedblam")
                if not mb_path:
                    print(f"Managedblam.dll does not exist: {str(mb_path)}")
                    nwo_globals.mb_operational = False
                    return
                nwo_globals.mb_operational = True
            except:
                nwo_globals.clr_installed = False

    @persistent
    def get_temp_settings(dummy):
        """Restores settings that the user created on export. Necesssary due to the way the exporter undos changes made during scene export"""
        scene = bpy.context.scene
        nwo = scene.nwo
        nwo_export = scene.nwo_export
        settings = nwo_globals.nwo_scene_settings
        if settings:
            nwo.sidecar_path = settings["sidecar_path"]
            nwo.scene_project = settings["scene_project"]
            nwo.asset_type = settings["asset_type"]
            nwo.output_biped = settings["output_biped"]
            nwo.output_crate = settings["output_crate"]
            nwo.output_creature = settings["output_creature"]
            nwo.output_device_control = settings["output_device_control"]
            nwo.output_device_dispenser = settings["output_device_dispenser"]
            nwo.output_device_machine = settings["output_device_machine"]
            nwo.output_device_terminal = settings["output_device_terminal"]
            nwo.output_effect_scenery = settings["output_effect_scenery"]
            nwo.output_equipment = settings["output_equipment"]
            nwo.output_giant = settings["output_giant"]
            nwo.output_scenery = settings["output_scenery"]
            nwo.output_vehicle = settings["output_vehicle"]
            nwo.output_weapon = settings["output_weapon"]
            nwo_export.show_output = settings["show_output"]
            nwo_export.lightmap_all_bsps = settings["lightmap_all_bsps"]
            nwo_export.lightmap_quality = settings["lightmap_quality"]
            nwo_export.lightmap_quality_h4 = settings["lightmap_quality_h4"]
            nwo_export.lightmap_region = settings["lightmap_region"]
            nwo_export.lightmap_specific_bsp = settings["lightmap_specific_bsp"]
            nwo_export.lightmap_structure = settings["lightmap_structure"]
            nwo_export.import_force = settings["import_force"]
            nwo_export.import_draft = settings["import_draft"]
            nwo_export.import_seam_debug = settings["import_seam_debug"]
            nwo_export.import_skip_instances = settings["import_skip_instances"]
            nwo_export.import_decompose_instances = settings["import_decompose_instances"]
            nwo_export.import_suppress_errors = settings["import_suppress_errors"]
            nwo_export.import_lighting = settings["import_lighting"]
            nwo_export.import_meta_only = settings["import_meta_only"]
            nwo_export.import_disable_hulls = settings["import_disable_hulls"]
            nwo_export.import_disable_collision = settings["import_disable_collision"]
            nwo_export.import_no_pca = settings["import_no_pca"]
            nwo_export.import_force_animations = settings["import_force_animations"]
            nwo_export.fast_animation_export = settings["fast_animation_export"]
            nwo_export.fix_bone_rotations = settings["fix_bone_rotations"]

            if nwo.instance_proxy_running:
                nwo.instance_proxy_running = False
                for ob in bpy.context.view_layer.objects:
                    if ob.nwo.proxy_parent:
                        unlink(ob)

            nwo_globals.nwo_scene_settings.clear()
            
    @persistent
    def save_object_positions_to_tags(dummy):
        if bpy.context and bpy.context.scene:
            nwo = bpy.context.scene.nwo
            asset_type = nwo.asset_type
            if not valid_nwo_asset(): return
            managed_blam_tasks = []
            if nwo.prefabs_export_on_save and asset_type == 'scenario' and is_corinth():
                print("Exporting Prefabs")
                managed_blam_tasks.extend(export_prefabs_tasks())
            if nwo.lights_export_on_save and asset_type == 'scenario':
                print("Exporting Lights")
                managed_blam_tasks.extend(export_lights_tasks())
                
            # blam(managed_blam_tasks)

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


    if __name__ == "__main__":
        register()
