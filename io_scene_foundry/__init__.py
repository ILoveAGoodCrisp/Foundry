# ##### BEGIN MIT LICENSE BLOCK #####
#
# MIT License
#
# Copyright (c) 2023 Crisp
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

# Don't edit the version or build version here or it will break CI
# Need to do this because of Blender parsing the plugin init code instead of actually executing it when getting bl_info

import ctypes
import bpy
from bpy.app.handlers import persistent

from io_scene_foundry.utils import nwo_globals

try:
    import clr
    nwo_globals.clr_installed = True
except:
    nwo_globals.clr_installed = False

from io_scene_foundry.utils.nwo_utils import (
    formalise_game_version,
    get_ek_path,
    valid_nwo_asset,
)

bl_info = {
    "name": "Foundry - Halo Blender Creation Kit",
    "author": "Crisp",
    "version": (343, 7, 343),
    "blender": (3, 6, 0),
    "location": "File > Export",
    "description": "Asset Exporter and Toolset for Halo Reach, Halo 4, and Halo 2 Aniversary Multiplayer: BUILD_VERSION_STR",
    "warning": "",
    "wiki_url": "https://c20.reclaimers.net/general/tools/foundry",
    "support": "COMMUNITY",
    "category": "Export",
}


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
    if not bpy.app.background:
        # Set game version from file
        context = bpy.context
        context.scene.nwo.game_version
        if not (context.scene.nwo.game_version_set or valid_nwo_asset(context)):
            context.scene.nwo.game_version = bpy.context.preferences.addons["io_scene_foundry"].preferences.default_game_version

        # set output to on
        # context.scene.nwo_export.show_output = True

        # run ManagedBlam on startup if enabled
        if context.scene.nwo.mb_startup:
            bpy.ops.managed_blam.init()

        # create warning if current game_version is incompatible with loaded managedblam.dll
        mb_path = nwo_globals.mb_path
        if mb_path:
            if not mb_path.startswith(get_ek_path()):
                game = formalise_game_version(context.scene.nwo.game_version)
                result = ctypes.windll.user32.MessageBoxW(
                    0,
                    f"{game} is incompatible with the loaded ManagedBlam version: {mb_path + '.dll'}. Please restart Blender or switch to a {game} asset.\n\nClose Blender?",
                    f"ManagedBlam / Game Mismatch",
                    4,
                )
                if result == 6:
                    bpy.ops.wm.quit_blender()

        # like and subscribe
        subscription_owner = object()
        subscribe(subscription_owner)

@persistent
def get_temp_settings(dummy):
    """Restores settings that the user created on export. Necesssary due to the way the exporter undos changes made during scene export"""
    scene = bpy.context.scene
    nwo = scene.nwo
    nwo_export = scene.nwo_export
    settings = nwo_globals.nwo_scene_settings
    if settings:
        scene.nwo_halo_launcher.sidecar_path = settings["sidecar_path"]
        nwo.game_version = settings["game_version"]
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

        nwo_globals.nwo_scene_settings.clear()


def fix_icons():
    icons.icons_activate()

def register():
    bpy.app.handlers.load_post.append(load_handler)
    bpy.app.handlers.load_post.append(load_set_output_state)
    bpy.app.handlers.undo_post.append(get_temp_settings)
    for module in modules:
        module.register()

    bpy.app.timers.register(fix_icons, first_interval=0.04, persistent=True)


def unregister():
    bpy.app.timers.unregister(fix_icons)
    bpy.app.handlers.load_post.remove(load_handler)
    bpy.app.handlers.load_post.append(load_set_output_state)
    bpy.app.handlers.undo_post.remove(get_temp_settings)
    for module in reversed(modules):
        module.unregister()


if __name__ == "__main__":
    register()
