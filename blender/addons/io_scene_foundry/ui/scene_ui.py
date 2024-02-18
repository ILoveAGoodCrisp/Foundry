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

import os

from ..icons import get_icon_id, get_icon_id_in_directory
from ..utils.nwo_utils import (
    get_asset_info,
    get_data_path,
    get_prefs,
    is_corinth,
    os_sep_partition,
    valid_nwo_asset,
)
from .templates import NWO_PropPanel, NWO_Op
import bpy
from bpy.props import BoolProperty, StringProperty
from bpy.types import Context, OperatorProperties, UIList, Menu

class NWO_RegionsContextMenu(Menu):
    bl_label = "Regions Context Menu"
    bl_idname = "NWO_MT_RegionsContext"

    @classmethod
    def poll(self, context):
        return context.scene.nwo.regions_table
    
    def draw(self, context):
        pass

class NWO_PermutationsContextMenu(Menu):
    bl_label = "Permutations Context Menu"
    bl_idname = "NWO_MT_PermutationsContext"

    @classmethod
    def poll(self, context):
        return context.scene.nwo.permutations_table
    
    def draw(self, context):
        pass

class NWO_UL_Regions(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if item:
            row = layout.row()
            row.alignment = 'LEFT'
            # row.operator("nwo.region_rename", text=item.name, emboss=False, icon_value=get_icon_id("region"))
            row.prop(item, 'name', text='', emboss=False, icon_value=get_icon_id("region"))
            row = layout.row(align=True)
            row.alignment = 'RIGHT'
            row.prop(item, "hidden", text="", icon='HIDE_ON' if item.hidden else 'HIDE_OFF', emboss=False)
            row.prop(item, "hide_select", text="", icon='RESTRICT_SELECT_ON' if item.hide_select else 'RESTRICT_SELECT_OFF', emboss=False)
            if data.asset_type in ('MODEL', 'SKY'):
                row.prop(item, "active", text="", icon='CHECKBOX_HLT' if item.active else 'CHECKBOX_DEHLT', emboss=False)
        else:
            layout.label(text="", translate=False, icon_value=icon)

class NWO_UL_Permutations(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if item:
            row = layout.row()
            row.alignment = 'LEFT'
            # row.operator("nwo.permutation_rename", text=item.name, emboss=False, icon_value=get_icon_id("permutation"))
            row.prop(item, 'name', text='', emboss=False, icon_value=get_icon_id("permutation"))
            row = layout.row(align=True)
            row.alignment = 'RIGHT'
            row.prop(item, "hidden", text="", icon='HIDE_ON' if item.hidden else 'HIDE_OFF', emboss=False)
            row.prop(item, "hide_select", text="", icon='RESTRICT_SELECT_ON' if item.hide_select else 'RESTRICT_SELECT_OFF', emboss=False)
        else:
            layout.label(text="", translate=False, icon_value=icon)

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

    work_dir: BoolProperty(
        description="Set whether blend file should be saved to a work directory within the asset folder"
    )
    
    selected_only: BoolProperty(
        name="From Selection Only",
        description="Creates a new asset using only the currently selected objects"
    )

    asset_name: StringProperty()
    filename: StringProperty()

    def execute(self, context):
        data_dir = get_data_path()
        scene = context.scene
        nwo_scene = scene.nwo
        if self.filename:
            asset_name = self.filename
            asset_folder = self.filepath
            if asset_name == os_sep_partition(os.path.dirname(self.filepath).strip(os.sep), True):
                asset_folder = os.path.dirname(self.filepath)
        elif self.filepath.startswith(data_dir) and self.filepath != data_dir:
            asset_name = os_sep_partition(self.filepath.strip(os.sep), True)
            asset_folder = self.filepath
        else:
            asset_name = "new_asset"
            asset_folder = os.path.join(data_dir, "new_asset")

        # check folder location valid
        if not asset_folder.lower().startswith(data_dir):
            # try to fix it...
            # test if path equal to another project path
            for p in get_prefs().projects:
                path_data = os.path.join(p.project_path, "data" + os.sep).lower()
                if asset_folder.lower().startswith(path_data):
                    asset_folder = asset_folder.lower().replace(path_data, data_dir)
                    break
            else:
                self.report(
                    {"WARNING"},
                    f"Invalid asset location. Please ensure your file is saved to your {nwo_scene.scene_project} data directory",
                )
                return {"CANCELLED"}

        if not os.path.exists(asset_folder):
            os.makedirs(asset_folder, True)

        sidecar_path_full = os.path.join(asset_folder, asset_name + ".sidecar.xml")
        if not os.path.exists(sidecar_path_full):
            with open(sidecar_path_full, 'x') as _:
                pass
            
        scene.nwo_halo_launcher.sidecar_path = sidecar_path_full.replace(
            data_dir, ""
        )

        if self.work_dir:
            blend_save_path = os.path.join(
                asset_folder, "models", "work", asset_name + ".blend"
            )
            os.makedirs(os.path.dirname(blend_save_path), True)
        else:
            blend_save_path = os.path.join(asset_folder, asset_name + ".blend")
            
        context.scene.render.fps = 30
        
        if self.selected_only:
            [bpy.data.objects.remove(ob) for ob in bpy.data.objects if not ob.select_get()]

        bpy.ops.wm.save_as_mainfile(filepath=blend_save_path)

        self.report(
            {"INFO"},
            f"Created new {nwo_scene.asset_type.title()} asset for {nwo_scene.scene_project}. Asset Name = {asset_name}",
        )
        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        nwo_asset = scene.nwo
        flow = layout.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=True,
        )
        col = flow.column()
        projects = get_prefs().projects
        for p in projects:
            if p.name == nwo_asset.scene_project:
                thumbnail = os.path.join(p.project_path, p.project_image_path)
                if os.path.exists(thumbnail):
                    icon_id = get_icon_id_in_directory(thumbnail)
                elif p.project_remote_server_name == "bngtoolsql":
                    icon_id = get_icon_id("halo_reach")
                elif p.project_remote_server_name == "metawins":
                    icon_id = get_icon_id("halo_4")
                elif p.project_remote_server_name == "episql.343i.selfhost.corp.microsoft.com":
                    icon_id = get_icon_id("halo_2amp")
                else:
                    icon_id = get_icon_id("tag_test")
                col.menu("NWO_MT_ProjectChooserDisallowNew", text=nwo_asset.scene_project, icon_value=icon_id)
                break
        else:
            if projects:
                col.menu("NWO_MT_ProjectChooserDisallowNew", text="Choose Project", icon_value=get_icon_id("tag_test"))
            else:
                col.operator("nwo.project_add", text="Choose Project", icon_value=get_icon_id("tag_test")).set_scene_project = True
        col.separator()
        col.prop(nwo_asset, "asset_type", text="")
        col.scale_y = 1.25
        col.separator()
        col.prop(self, "work_dir", text="Save to work directory")
        col.separator()
        col.prop(self, "selected_only")
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
            if is_corinth(context):
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
        self.filepath = get_data_path()
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
    
class NWO_UL_IKChain(bpy.types.UIList):
    # Called for each drawn item.
    def draw_item(self, context, layout: bpy.types.UILayout, data, item, icon, active_data, active_propname, index, flt_flag):
        layout.alignment = 'LEFT'
        layout.prop(item, 'name', text='', emboss=False)
        if item.start_node and item.effector_node:
            layout.label(text=f'{item.start_node} >>> {item.effector_node}', icon='CON_SPLINEIK')
        else:
            layout.label(text='IK Chain Bones Not Set', icon='ERROR')
        # row.prop_search(item, 'start_node', data.main_armature.data, 'bones', text='')
        # row.prop_search(item, 'effector_node', data.main_armature.data, 'bones', text='')
        
class NWO_AddIKChain(bpy.types.Operator):
    bl_options = {'REGISTER', 'UNDO'}
    bl_idname = 'nwo.add_ik_chain'
    bl_label = "Add"
    bl_description = "Add a new Game IK Chain"
    
    @classmethod
    def poll(cls, context):
        return context.scene.nwo.main_armature

    def execute(self, context):
        nwo = context.scene.nwo
        chain = nwo.ik_chains.add()
        nwo.ik_chains_active_index = len(nwo.ik_chains) - 1
        chain.name = f"ik_chain_{len(nwo.ik_chains)}"
        context.area.tag_redraw()
        return {'FINISHED'}
    
class NWO_RemoveIKChain(bpy.types.Operator):
    bl_idname = "nwo.remove_ik_chain"
    bl_label = "Remove"
    bl_description = "Remove an IK Chain from the list."
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return context.scene.nwo.ik_chains and context.scene.nwo.ik_chains_active_index > -1

    def execute(self, context):
        nwo = context.scene.nwo
        index = nwo.ik_chains_active_index
        nwo.ik_chains.remove(index)
        if nwo.ik_chains_active_index > len(nwo.ik_chains) - 1:
            nwo.ik_chains_active_index -= 1
        context.area.tag_redraw()
        return {"FINISHED"}
    
class NWO_MoveIKChain(bpy.types.Operator):
    bl_idname = "nwo.move_ik_chain"
    bl_label = "Move"
    bl_description = "Moves the IK Chain up/down the list"
    bl_options = {"UNDO"}
    
    direction: bpy.props.StringProperty()

    def execute(self, context):
        nwo = context.scene.nwo
        chains = nwo.ik_chains
        delta = {"down": 1, "up": -1,}[self.direction]
        current_index = nwo.ik_chains_active_index
        to_index = (current_index + delta) % len(chains)
        chains.move(current_index, to_index)
        nwo.ik_chains_active_index = to_index
        context.area.tag_redraw()
        return {'FINISHED'}
    
class NWO_UL_ObjectControls(bpy.types.UIList):
    def draw_item(self, context, layout: bpy.types.UILayout, data, item, icon, active_data, active_propname, index, flt_flag):
        layout.label(text=item.ob.name, icon='OBJECT_DATA')
        layout.operator("nwo.remove_object_control", text='', icon='X', emboss=False).given_index = index
        
class NWO_OT_RemoveObjectControl(bpy.types.Operator):
    bl_idname = "nwo.remove_object_control"
    bl_label = "Remove Highlighted Object"
    bl_description = "Removes the highlighted object from the object controls list"
    bl_options = {"UNDO"}
    
    given_index: bpy.props.IntProperty(default=-1, options={'SKIP_SAVE'})
    
    def execute(self, context):
        nwo = context.scene.nwo
        if self.given_index > -1:
            index = self.given_index
        else:
            index = nwo.object_controls_active_index
        nwo.object_controls.remove(index)
        if nwo.object_controls_active_index > len(nwo.object_controls) - 1:
            nwo.object_controls_active_index -= 1
        context.area.tag_redraw()
            
        return {'FINISHED'}
    
class NWO_OT_BatchAddObjectControls(bpy.types.Operator):
    bl_idname = "nwo.batch_add_object_controls"
    bl_label = "Add Selected Objects"
    bl_description = "Adds selected objects to the object controls list"
    bl_options = {"UNDO"}

    def execute(self, context):
        scene_nwo = context.scene.nwo
        object_controls = scene_nwo.object_controls
        current_control_objects = [control.ob for control in object_controls]
        armatures = [scene_nwo.main_armature, scene_nwo.support_armature_a, scene_nwo.support_armature_b, scene_nwo.support_armature_c]
        valid_control_objects = [ob for ob in context.selected_objects if ob not in armatures and ob not in current_control_objects]
        for ob in valid_control_objects:
            object_controls.add().ob = ob
            
        return {"FINISHED"}
    
class NWO_OT_BatchRemoveObjectControls(bpy.types.Operator):
    bl_idname = "nwo.batch_remove_object_controls"
    bl_label = "Remove Selected Objects"
    bl_description = "Removes selected objects from the object controls list"
    bl_options = {"UNDO"}

    def execute(self, context):
        scene_nwo = context.scene.nwo
        object_controls = scene_nwo.object_controls
        selected_objects = context.selected_objects
        controls_to_remove = []
        for idx, control in enumerate(object_controls):
            if control.ob in selected_objects:
                controls_to_remove.append(idx)
        
        controls_to_remove.reverse()
        
        while controls_to_remove:
            object_controls.remove(controls_to_remove[0])
            controls_to_remove.pop(0)
            
        return {"FINISHED"}
    
class NWO_OT_SelectObjectControl(bpy.types.Operator):
    bl_idname = "nwo.select_object_control"
    bl_label = "Select"
    
    select: BoolProperty(default=True)

    def execute(self, context):
        scene_nwo = context.scene.nwo
        ob: bpy.types.Object = scene_nwo.object_controls[scene_nwo.object_controls_active_index].ob
        if not ob.visible_get():
            self.report({'WARNING'}, f"{ob.name} is hidden")
            return {'CANCELLED'}
        
        ob.select_set(self.select)
        # context.view_layer.objects.active = ob
        return {"FINISHED"}
    
    @classmethod
    def description(cls, context: Context, properties: OperatorProperties) -> str:
        if properties.select:
            return 'Select highlighted control object'
        else:
            return 'Deselect highlighted control object'
        
class NWO_OT_ClearAsset(bpy.types.Operator):
    bl_idname = "nwo.clear_asset"
    bl_label = "Unlink Asset"
    bl_description = "Unlinks the Asset from this blend"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return valid_nwo_asset()

    def execute(self, context):
        nwo = context.scene.nwo_halo_launcher
        _, asset_name = get_asset_info(nwo.sidecar_path)
        nwo.sidecar_path = ""
        self.report({'INFO'}, f"Asset [{asset_name}] unlinked from file")
        return {"FINISHED"}
    
    def invoke(self, context: bpy.types.Context, event):
        return context.window_manager.invoke_confirm(self, event)
