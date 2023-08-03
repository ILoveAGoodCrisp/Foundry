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

import os

from ..icons import get_icon_id
from ..utils.nwo_utils import (
    dot_partition,
    formalise_game_version,
    get_data_path,
    get_tags_path,
    managed_blam_active,
    valid_nwo_asset,
)
from .templates import NWO_Op_Path, NWO_PropPanel, NWO_Op
import bpy
from bpy.props import BoolProperty, StringProperty
from bpy.types import UIList, Panel


class NWO_SceneProps(Panel):
    bl_label = "Halo Scene"
    bl_idname = "NWO_PT_ScenePropertiesPanel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        scene_nwo = scene.nwo
        scene_nwo = context.scene.nwo
        mb_active = managed_blam_active()
        flow = layout.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=False,
        )
        if mb_active:
            flow.enabled = False
        row = flow.row()
        row.prop(scene_nwo, "game_version", text="")
        row.scale_y = 1.5
        flow = layout.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=False,
        )
        col = flow.column()
        if mb_active or scene_nwo.mb_startup:
            col.prop(scene_nwo, "mb_startup")
        col.separator()
        col = col.row()
        col.scale_y = 1.5
        if not valid_nwo_asset(context):
            col.operator("nwo.make_asset")
        if mb_active:
            col.label(text="ManagedBlam Active")
        elif os.path.exists(os.path.join(bpy.app.tempdir, "blam_new.txt")):
            col.label(text="Blender Restart Required for ManagedBlam")
        else:
            col.operator("managed_blam.init", text="Initialize ManagedBlam")

        flow = layout.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=False,
        )
        col = flow.column(heading="Asset Type")
        col.scale_y = 1.5
        col.prop(scene_nwo, "asset_type", text="")
        col1 = col.column(heading="Default Mesh Type")
        col1.prop(scene_nwo, "default_mesh_type_ui", text="")
        col2 = col.column(heading="Model Forward")
        if scene_nwo.asset_type in ("MODEL", "FP ANIMATION"):
            col2.prop(scene_nwo, "forward_direction", text="")
        if scene_nwo.asset_type == "MODEL":
            col.label(text="Output Tags")
            row = layout.grid_flow(
                row_major=True,
                columns=0,
                even_columns=True,
                even_rows=True,
                align=True,
            )
            row.scale_x = 1.3
            row.scale_y = 1.3

            row.prop(
                scene_nwo,
                "output_crate",
                text="",
                icon_value=get_icon_id("crate"),
            )
            row.prop(
                scene_nwo,
                "output_scenery",
                text="",
                icon_value=get_icon_id("scenery"),
            )
            row.prop(
                scene_nwo,
                "output_effect_scenery",
                text="",
                icon_value=get_icon_id("effect_scenery"),
            )

            row.prop(
                scene_nwo,
                "output_device_control",
                text="",
                icon_value=get_icon_id("device_control"),
            )
            row.prop(
                scene_nwo,
                "output_device_machine",
                text="",
                icon_value=get_icon_id("device_machine"),
            )
            row.prop(
                scene_nwo,
                "output_device_terminal",
                text="",
                icon_value=get_icon_id("device_terminal"),
            )
            if context.scene.nwo.game_version in ("h4", "h2a"):
                row.prop(
                    scene_nwo,
                    "output_device_dispenser",
                    text="",
                    icon_value=get_icon_id("device_dispenser"),
                )

            row.prop(
                scene_nwo,
                "output_biped",
                text="",
                icon_value=get_icon_id("biped"),
            )
            row.prop(
                scene_nwo,
                "output_creature",
                text="",
                icon_value=get_icon_id("creature"),
            )
            row.prop(
                scene_nwo,
                "output_giant",
                text="",
                icon_value=get_icon_id("giant"),
            )

            row.prop(
                scene_nwo,
                "output_vehicle",
                text="",
                icon_value=get_icon_id("vehicle"),
            )
            row.prop(
                scene_nwo,
                "output_weapon",
                text="",
                icon_value=get_icon_id("weapon"),
            )
            row.prop(
                scene_nwo,
                "output_equipment",
                text="",
                icon_value=get_icon_id("equipment"),
            )


class NWO_SetUnitScale(NWO_Op):
    """Sets up the scene for Halo: Sets the unit scale to match Halo's and sets the frame rate to 30fps"""

    bl_idname = "nwo.set_unit_scale"
    bl_label = "Set Halo Scene"

    scale: bpy.props.FloatProperty()

    @classmethod
    def poll(self, context):
        return context.scene

    def execute(self, context):
        # Set the frame rate to 30
        if self.scale != 1.0:
            context.scene.render.fps = 30
        # define the Halo scale
        # Apply scale to clipping in all windows if halo_scale has not already been set
        current_scale = context.scene.unit_settings.scale_length
        scale_ratio = current_scale / self.scale
        for workspace in bpy.data.workspaces:
            for screen in workspace.screens:
                for area in screen.areas:
                    if area.type == "VIEW_3D":
                        for space in area.spaces:
                            if space.type == "VIEW_3D":
                                space.clip_start = space.clip_start * scale_ratio
                                space.clip_end = space.clip_end * scale_ratio
        # Set halo scale
        context.scene.unit_settings.scale_length = self.scale
        return {"FINISHED"}


class NWO_AssetMaker(NWO_Op):
    """Creates an asset"""

    bl_idname = "nwo.make_asset"
    bl_label = "Create New Asset"

    @classmethod
    def poll(self, context):
        return context.scene

    filter_glob: StringProperty(
        default="",
        options={"HIDDEN"},
    )

    use_filter_folder: BoolProperty(default=True)

    filepath: StringProperty(
        name="asset_path",
        description="Set the location of your asset",
        subtype="FILE_PATH",
    )

    asset_name: StringProperty(default="new_asset")

    work_dir: BoolProperty(
        description="Set whether blend file should be saved to a work directory within the asset folder"
    )

    managed_blam: BoolProperty(
        description="Blender Scene will initialize ManagedBlam on startup",
        default=False,
    )

    def execute(self, context):
        scene = context.scene
        nwo_scene = scene.nwo
        nwo_asset = scene.nwo
        asset_name = self.filepath.rpartition(os.sep)[2]
        asset_name_clean = dot_partition(asset_name)
        if asset_name_clean == "":
            asset_name_clean = "new_asset"
        # check folder location valid
        if not self.filepath.startswith(get_data_path()):
            # try to fix it...
            prefs = context.preferences.addons["io_scene_foundry"].preferences
            if self.filepath.startswith(prefs.hrek_path):
                self.filepath = self.filepath.replace(
                    os.path.join(prefs.hrek_path, "data" + os.sep),
                    get_data_path(),
                )
            elif self.filepath.startswith(prefs.h4ek_path):
                self.filepath = self.filepath.replace(
                    os.path.join(prefs.h4ek_path, "data" + os.sep),
                    get_data_path(),
                )
            elif self.filepath.startswith(prefs.h2aek_path):
                self.filepath = self.filepath.replace(
                    os.path.join(prefs.h2aek_path, "data" + os.sep),
                    get_data_path(),
                )
            else:
                self.report(
                    {"INFO"},
                    f"Invalid asset location. Please ensure your file is saved to your data {formalise_game_version(nwo_scene.game_version)} directory",
                )
                return {"CANCELLED"}

        if not os.path.exists(self.filepath):
            os.makedirs(self.filepath, True)

        sidecar_path_full = os.path.join(
            self.filepath, asset_name_clean + ".sidecar.xml"
        )
        open(sidecar_path_full, "x")
        scene.nwo_halo_launcher.sidecar_path = sidecar_path_full.replace(
            get_data_path(), ""
        )

        if self.work_dir:
            blend_save_path = os.path.join(
                self.filepath, "models", "work", asset_name_clean + ".blend"
            )
            os.makedirs(os.path.dirname(blend_save_path), True)
        else:
            blend_save_path = os.path.join(self.filepath, asset_name_clean + ".blend")

        bpy.ops.wm.save_as_mainfile(filepath=blend_save_path)

        if self.managed_blam:
            bpy.ops.managed_blam.init()
            nwo_scene.mb_startup = True

        self.report(
            {"INFO"},
            f"Created new {nwo_asset.asset_type.title()} asset for {formalise_game_version(nwo_scene.game_version)}",
        )
        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        nwo_scene = scene.nwo
        nwo_asset = scene.nwo
        flow = layout.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=True,
        )
        col = flow.column(heading="Asset Settings")
        col.prop(nwo_scene, "game_version", expand=True)
        col.separator()
        col.prop(nwo_asset, "asset_type", text="")
        col.scale_y = 1.25
        col.separator()
        col.prop(self, "work_dir", text="Save to work directory")
        col.prop(self, "managed_blam", text="Enable ManagedBlam")
        if nwo_asset.asset_type == "MODEL":
            col.separator()
            col.label(text="Output Tags")
            flow = col.grid_flow(
                row_major=True,
                columns=0,
                even_columns=True,
                even_rows=False,
                align=True,
            )
            flow.scale_x = 1
            flow.scale_y = 1.25
            flow.prop(
                nwo_asset,
                "output_crate",
                # text="",
                icon_value=get_icon_id("crate"),
            )
            flow.prop(
                nwo_asset,
                "output_scenery",
                # text="",
                icon_value=get_icon_id("scenery"),
            )
            flow.prop(
                nwo_asset,
                "output_effect_scenery",
                text="Effect",
                icon_value=get_icon_id("effect_scenery"),
            )

            flow.prop(
                nwo_asset,
                "output_device_control",
                text="Control",
                icon_value=get_icon_id("device_control"),
            )
            flow.prop(
                nwo_asset,
                "output_device_machine",
                text="Machine",
                icon_value=get_icon_id("device_machine"),
            )
            flow.prop(
                nwo_asset,
                "output_device_terminal",
                text="Terminal",
                icon_value=get_icon_id("device_terminal"),
            )
            if context.scene.nwo.game_version in ("h4", "h2a"):
                flow.prop(
                    nwo_asset,
                    "output_device_dispenser",
                    text="Dispenser",
                    icon_value=get_icon_id("device_dispenser"),
                )

            flow.prop(
                nwo_asset,
                "output_biped",
                # text="",
                icon_value=get_icon_id("biped"),
            )
            flow.prop(
                nwo_asset,
                "output_creature",
                # text="",
                icon_value=get_icon_id("creature"),
            )
            flow.prop(
                nwo_asset,
                "output_giant",
                # text="",
                icon_value=get_icon_id("giant"),
            )

            flow.prop(
                nwo_asset,
                "output_vehicle",
                # text="",
                icon_value=get_icon_id("vehicle"),
            )
            flow.prop(
                nwo_asset,
                "output_weapon",
                # text="",
                icon_value=get_icon_id("weapon"),
            )
            flow.prop(
                nwo_asset,
                "output_equipment",
                # text="",
                icon_value=get_icon_id("equipment"),
            )

    def invoke(self, context, event):
        self.filepath = get_data_path() + self.asset_name
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class NWO_UL_SceneProps_SharedAssets(UIList):
    use_name_reverse: bpy.props.BoolProperty(
        name="Reverse Name",
        default=False,
        options=set(),
        description="Reverse name sort order",
    )

    use_order_name: bpy.props.BoolProperty(
        name="Name",
        default=False,
        options=set(),
        description="Sort groups by their name (case-insensitive)",
    )

    filter_string: bpy.props.StringProperty(
        name="filter_string", default="", description="Filter string for name"
    )

    filter_invert: bpy.props.BoolProperty(
        name="Invert",
        default=False,
        options=set(),
        description="Invert Filter",
    )

    def filter_items(self, context, data, property):
        items = getattr(data, property)
        if not len(items):
            return [], []

        if self.filter_string:
            flt_flags = bpy.types.UI_UL_list.filter_items_by_name(
                self.filter_string,
                self.bitflag_filter_item,
                items,
                propname="name",
                reverse=self.filter_invert,
            )
        else:
            flt_flags = [self.bitflag_filter_item] * len(items)

        if self.use_order_name:
            flt_neworder = bpy.types.UI_UL_list.sort_items_by_name(items, "name")
            if self.use_name_reverse:
                flt_neworder.reverse()
        else:
            flt_neworder = []

        return flt_flags, flt_neworder

    def draw_filter(self, context, layout):
        row = layout.row(align=True)
        row.prop(self, "filter_string", text="Filter", icon="VIEWZOOM")
        row.prop(self, "filter_invert", text="", icon="ARROW_LEFTRIGHT")

        row = layout.row(align=True)
        row.label(text="Order by:")
        row.prop(self, "use_order_name", toggle=True)

        icon = "TRIA_UP" if self.use_name_reverse else "TRIA_DOWN"
        row.prop(self, "use_name_reverse", text="", icon=icon)

    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname
    ):
        scene = context.scene
        scene_nwo = scene.nwo
        if self.layout_type in {"DEFAULT", "COMPACT"}:
            if scene:
                layout.label(text=item.shared_asset_name, icon="BOOKMARKS")
            else:
                layout.label(text="")
        elif self.layout_type == "GRID":
            layout.alignment = "CENTER"
            layout.label(text="", icon_value=icon)


class NWO_SceneProps_SharedAssets(NWO_PropPanel):
    bl_label = "Shared Assets"
    bl_idname = "NWO_PT_GameVersionPanel_SharedAssets"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_parent_id = "NWO_PT_ScenePropertiesPanel"

    @classmethod
    def poll(cls, context):
        return False  # hiding this menu until it actually does something

    def draw(self, context):
        scene = context.scene
        scene_nwo = scene.nwo
        layout = self.layout

        layout.template_list(
            "NWO_UL_SceneProps_SharedAssets",
            "",
            scene_nwo,
            "shared_assets",
            scene_nwo,
            "shared_assets_index",
        )
        # layout.template_list("NWO_UL_SceneProps_SharedAssets", "compact", scene_nwo, "shared_assets", scene_nwo, "shared_assets_index", type='COMPACT') # not needed

        row = layout.row()
        col = row.column(align=True)
        col.operator("nwo_shared_asset.list_add", text="Add")
        col = row.column(align=True)
        col.operator("nwo_shared_asset.list_remove", text="Remove")

        if len(scene_nwo.shared_assets) > 0:
            item = scene_nwo.shared_assets[scene_nwo.shared_assets_index]
            row = layout.row()
            # row.prop(item, "shared_asset_name", text='Asset Name') # debug only
            row.prop(item, "shared_asset_path", text="Path")
            row = layout.row()
            row.prop(item, "shared_asset_type", text="Type")


class NWO_List_Add_Shared_Asset(NWO_Op):
    """Add an Item to the UIList"""

    bl_idname = "nwo_shared_asset.list_add"
    bl_label = "Add"
    bl_description = "Add a new shared asset (sidecar) to the list."
    filename_ext = ""
    bl_options = {"REGISTER", "UNDO"}

    filter_glob: StringProperty(
        default="*.xml",
        options={"HIDDEN"},
    )

    filepath: StringProperty(
        name="Sidecar",
        description="Set path for the Sidecar file",
        subtype="FILE_PATH",
    )

    @classmethod
    def poll(cls, context):
        return context.scene

    def execute(self, context):
        scene = context.scene
        scene_nwo = scene.nwo
        scene_nwo.shared_assets.add()

        path = self.filepath
        path = path.replace(get_data_path(), "")
        scene_nwo.shared_assets[-1].shared_asset_path = path
        scene_nwo.shared_assets_index = len(scene_nwo.shared_assets) - 1
        context.area.tag_redraw()
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)

        return {"RUNNING_MODAL"}


class NWO_List_Remove_Shared_Asset(NWO_Op):
    """Remove an Item from the UIList"""

    bl_idname = "nwo_shared_asset.list_remove"
    bl_label = "Remove"
    bl_description = "Remove a shared asset (sidecar) from the list."
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        scene_nwo = scene.nwo
        return context.scene and len(scene_nwo.shared_assets) > 0

    def execute(self, context):
        scene = context.scene
        scene_nwo = scene.nwo
        index = scene_nwo.shared_assets_index
        scene_nwo.shared_assets.remove(index)
        return {"FINISHED"}
    
class NWO_RenderPath(NWO_Op_Path):
    bl_idname = "nwo.render_path"
    bl_description = "Set the path to a render model tag"

    def __init__(self):
        self.tag_path_field = bpy.context.scene.nwo.render_model_path

    def execute(self, context):
        context.scene.nwo.render_model_path = self.filepath
        return {"FINISHED"}
    
class NWO_CollisionPath(NWO_Op_Path):
    bl_idname = "nwo.collision_path"
    bl_description = "Set the path to a collision model tag"

    def __init__(self):
        self.tag_path_field = bpy.context.scene.nwo.collision_model_path

    def execute(self, context):
        context.scene.nwo.collision_model_path = self.filepath
        return {"FINISHED"}
    
class NWO_PhysicsPath(NWO_Op_Path):
    bl_idname = "nwo.physics_path"
    bl_description = "Set the path to a physics model tag"

    def __init__(self):
        self.tag_path_field = bpy.context.scene.nwo.physics_model_path

    def execute(self, context):
        context.scene.nwo.physics_model_path = self.filepath
        return {"FINISHED"}
    
class NWO_AnimationPath(NWO_Op_Path):
    bl_idname = "nwo.animation_path"
    bl_description = "Set the path to a model animation graph tag"

    def __init__(self):
        self.tag_path_field = bpy.context.scene.nwo.animation_graph_path

    def execute(self, context):
        context.scene.nwo.animation_graph_path = self.filepath
        return {"FINISHED"}
    
class NWO_FPModelPath(NWO_Op_Path):
    bl_idname = "nwo.fp_model_path"
    bl_description = "Set the path to the FP render model tag"

    def __init__(self):
        self.tag_path_field = bpy.context.scene.nwo.animation_graph_path

    def execute(self, context):
        context.scene.nwo.animation_graph_path = self.filepath
        return {"FINISHED"}
    
class NWO_GunModelPath(NWO_Op_Path):
    bl_idname = "nwo.gun_model_path"
    bl_description = "Set the path to the Gun render model tag"

    def __init__(self):
        self.tag_path_field = bpy.context.scene.nwo.animation_graph_path

    def execute(self, context):
        context.scene.nwo.animation_graph_path = self.filepath
        return {"FINISHED"}
