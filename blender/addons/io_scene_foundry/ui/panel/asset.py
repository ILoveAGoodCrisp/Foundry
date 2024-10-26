"""UI for the asset editor sub-panel"""

import bpy
from ... import utils

class NWO_UL_SceneProps_SharedAssets(bpy.types.UIList):
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


class NWO_SceneProps_SharedAssets(bpy.types.Panel):
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


class NWO_List_Add_Shared_Asset(bpy.types.Operator):
    """Add an Item to the UIList"""

    bl_idname = "nwo_shared_asset.list_add"
    bl_label = "Add"
    bl_description = "Add a new shared asset (sidecar) to the list."
    filename_ext = ""
    bl_options = {"REGISTER", "UNDO"}

    filter_glob: bpy.props.StringProperty(
        default="*.xml",
        options={"HIDDEN"},
    )

    filepath: bpy.props.StringProperty(
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
        path = path.replace(utils.get_data_path(), "")
        scene_nwo.shared_assets[-1].shared_asset_path = path
        scene_nwo.shared_assets_index = len(scene_nwo.shared_assets) - 1
        context.area.tag_redraw()
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)

        return {"RUNNING_MODAL"}


class NWO_List_Remove_Shared_Asset(bpy.types.Operator):
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
    
class NWO_UL_ObjectControls(bpy.types.UIList):
    def draw_item(self, context, layout: bpy.types.UILayout, data, item, icon, active_data, active_propname, index, flt_flag):
        if item.ob:
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
    
    select: bpy.props.BoolProperty(default=True)

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
    def description(cls, context, properties) -> str:
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
    
class NWO_OT_LinkArmatures(bpy.types.Operator):
    bl_idname = "nwo.link_armatures"
    bl_label = "Link Armatures"
    bl_description = "Links a support armature to the main armature by assinging the parent bone and adding child of constraints"
    bl_options = {"UNDO"}
    
    support_arm: bpy.props.IntProperty(options={'HIDDEN'})
    
    parent_bone: bpy.props.StringProperty(
        name="Parent Bone",
        description="Bone from the main armature which acts as the parent of all root bones in the support armature"
    )
    
    @classmethod
    def poll(cls, context):
        return context.scene.nwo.main_armature
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        self.layout.prop_search(self, 'parent_bone', context.scene.nwo.main_armature.pose, 'bones')

    def execute(self, context):
        scene_nwo = context.scene.nwo
        main_armature = scene_nwo.main_armature

        support_armature = None
        parent_bone = main_armature.pose.bones.get(self.parent_bone)
        field_prop_name = ""
        match self.support_arm:
            case 0:
                support_armature = scene_nwo.support_armature_a
                field_prop_name = "support_armature_a_parent_bone"
            case 1:
                support_armature = scene_nwo.support_armature_b
                field_prop_name = "support_armature_b_parent_bone"
            case 2:
                support_armature = scene_nwo.support_armature_c
                field_prop_name = "support_armature_c_parent_bone"
                
        if support_armature is None:
            self.report({'WARNING'}, "Support armature is None")
            return {'CANCELLED'}
        
        elif parent_bone is None:
            self.report({'WARNING'}, f"Parent Bone not found in {main_armature}")
            return {'CANCELLED'}
        
        def has_child_of_constraint(pbone: bpy.types.PoseBone):
            for con in pbone.constraints:
                con: bpy.types.Constraint
                if con.type == 'CHILD_OF':
                    return True
                
            return False
        
        main_posed = main_armature.data.pose_position == 'POSE'
        support_posed = support_armature.data.pose_position == 'POSE'
        
        if main_posed:
            main_armature.data.pose_position = 'REST'
        if support_posed:
            support_armature.data.pose_position = 'REST'
            
        if main_posed or support_posed:
            context.view_layer.update()
        
        for pbone in support_armature.pose.bones:
            pbone: bpy.types.PoseBone
            if pbone.parent or has_child_of_constraint(pbone):
                continue
            constraint = pbone.constraints.new('CHILD_OF')
            constraint.target = main_armature
            constraint.subtarget = parent_bone.name
            constraint.inverse_matrix = (main_armature.matrix_world @ parent_bone.matrix).inverted()
            
        if main_posed:
            main_armature.data.pose_position = 'POSE'
        if support_posed:
            support_armature.data.pose_position = 'POSE'
            
        setattr(scene_nwo, field_prop_name, parent_bone.name)  
            
        return {"FINISHED"}