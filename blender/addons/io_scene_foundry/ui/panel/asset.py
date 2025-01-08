"""UI for the asset editor sub-panel"""

import os
from pathlib import Path
import bpy

from ...icons import get_icon_id
from ... import utils

import xml.etree.ElementTree as ET
    
class NWO_UL_ChildAsset(bpy.types.UIList):
    def draw_item(
        self,
        context,
        layout,
        data,
        item,
        icon,
        active_data,
        active_propname,
        index,
    ):
        name = item.asset_path
                
        layout.label(text=name, icon='FILE')
        layout.prop(item, "enabled", icon='CHECKBOX_HLT' if item.enabled else 'CHECKBOX_DEHLT', text="", emboss=False)
        
class NWO_OT_OpenChildAsset(bpy.types.Operator):
    bl_idname = "nwo.open_child_asset"
    bl_label = "Open Blend"
    bl_description = "Opens the source blend file for this asset"
    bl_options = {"UNDO"}
    
    @classmethod
    def poll(cls, context):
        return context.scene.nwo.child_assets and context.scene.nwo.active_child_asset_index > -1
    
    def execute(self, context):
        asset_path = Path(context.scene.nwo.child_assets[context.scene.nwo.active_child_asset_index].asset_path)
        full_path = Path(utils.get_data_path(), asset_path, f"{asset_path.name}.sidecar.xml")
        
        source_blend_element = None
        try:
            tree = ET.parse(full_path)
            root = tree.getroot()
            source_blend_element = root.find(".//SourceBlend")
        except:
            pass
        
        if source_blend_element is None:
            self.report({'WARNING'}, f"Failed to identify source blend file from {full_path}")
            return {'CANCELLED'}
        
        relative_blend_path = source_blend_element.text
        
        full_blend_path = Path(utils.get_data_path(), relative_blend_path)
        if not full_blend_path.exists():
            self.report({'WARNING'}, f"Source blend file does not exist: {full_blend_path}")
            return {'CANCELLED'}
        
        os.startfile(full_blend_path)
        
        return {'FINISHED'}
        
        
class NWO_OT_AddChildAsset(bpy.types.Operator):
    bl_idname = "nwo.add_child_asset"
    bl_label = "Add Child Asset"
    bl_description = "Adds a path to the sidecar which should contribute to this asset"
    bl_options = {"UNDO"}
    
    @classmethod
    def poll(cls, context):
        return context.scene and utils.get_prefs().projects
    
    filter_glob: bpy.props.StringProperty(
        default="*.sidecar.xml",
        options={"HIDDEN"},
    )

    use_filter_folder: bpy.props.BoolProperty(default=True)

    filepath: bpy.props.StringProperty(
        name="Sidecar Path",
        description="",
        subtype="FILE_PATH",
    )
    
    filename: bpy.props.StringProperty()

    def execute(self, context):
        scene_nwo = context.scene.nwo
        fp = Path(self.filepath)
        if fp.is_absolute() and fp.is_relative_to(utils.get_data_path()):
            relative_filepath = utils.relative_path(fp)
            if relative_filepath == context.scene.nwo.sidecar_path:
                self.report({'WARNING'}, f"Cannot add own asset sidecar")
                return {'CANCELLED'}
            child = scene_nwo.child_assets.add()
            child.asset_path = str(Path(relative_filepath).parent)
            scene_nwo.active_child_asset_index = len(scene_nwo.child_assets) - 1
        else:
            self.report({'WARNING'}, f"sidecar.xml path [{fp}] is not relative to current project data directory [{utils.get_data_path()}]. Cannot add child asset")
            return {'CANCELLED'}
        
        return {'FINISHED'}
    
    def invoke(self, context, _):
        self.filepath = utils.get_asset_path_full() + os.sep
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
    
class NWO_OT_RemoveChildAsset(bpy.types.Operator):
    bl_idname = "nwo.remove_child_asset"
    bl_label = "Remove"
    bl_description = "Remove a child asset from the list"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return context.scene.nwo.child_assets and context.scene.nwo.active_child_asset_index > -1

    def execute(self, context):
        nwo = context.scene.nwo
        index = nwo.active_child_asset_index
        nwo.child_assets.remove(index)
        if nwo.active_child_asset_index > len(nwo.child_assets) - 1:
            nwo.active_child_asset_index -= 1
        context.area.tag_redraw()
        return {"FINISHED"}
    
class NWO_OT_MoveChildAsset(bpy.types.Operator):
    bl_idname = "nwo.move_child_asset"
    bl_label = "Move"
    bl_description = "Moves the child asset up/down the list"
    bl_options = {"UNDO"}
    
    direction: bpy.props.StringProperty()

    def execute(self, context):
        nwo = context.scene.nwo
        assets = nwo.child_assets
        delta = {"down": 1, "up": -1,}[self.direction]
        current_index = nwo.active_child_asset_index
        to_index = (current_index + delta) % len(assets)
        assets.move(current_index, to_index)
        nwo.active_child_asset_index = to_index
        context.area.tag_redraw()
        return {'FINISHED'}
    
class NWO_UL_IKChain(bpy.types.UIList):
    # Called for each drawn item.
    def draw_item(self, context, layout: bpy.types.UILayout, data, item, icon, active_data, active_propname, index, flt_flag):
        layout.alignment = 'LEFT'
        layout.prop(item, 'name', text='', emboss=False, icon_value=get_icon_id("ik_chain"))
        if item.start_node and item.effector_node:
            layout.label(text=f'{item.start_node} >>> {item.effector_node}')
        else:
            layout.label(text='IK Chain Bones Not Set', icon='ERROR')
        # row.prop_search(item, 'start_node', data.main_armature.data, 'bones', text='')
        # row.prop_search(item, 'effector_node', data.main_armature.data, 'bones', text='')
        
class NWO_OT_AddIKChain(bpy.types.Operator):
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
    
class NWO_OT_RemoveIKChain(bpy.types.Operator):
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
    
class NWO_OT_MoveIKChain(bpy.types.Operator):
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
        
class NWO_OT_ClearAsset(bpy.types.Operator):
    bl_idname = "nwo.clear_asset"
    bl_label = "Unlink Asset"
    bl_description = "Unlinks the Asset from this blend"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return context.scene.nwo.sidecar_path

    def execute(self, context):
        nwo = context.scene.nwo
        _, asset_name = utils.get_asset_info(nwo.sidecar_path)
        nwo.sidecar_path = ""
        self.report({'INFO'}, f"Asset [{asset_name}] unlinked from file")
        return {"FINISHED"}
    
    def invoke(self, context: bpy.types.Context, event):
        return context.window_manager.invoke_confirm(self, event)
    
class NWO_OT_RegisterIcons(bpy.types.Operator):
    bl_idname = "nwo.register_icons"
    bl_label = "Reload Icons"
    bl_description = "Reloads the Foundry icons if any failed to load at startup"
    bl_options = {"UNDO"}

    def execute(self, context):
        from ... import icons
        if icons.icons_active:
            icons.unregister()
        icons.register()
        if not icons.icons_active:
            icons.icons_activate()
            
        return {"FINISHED"}