
from pathlib import Path
import bpy

from ... import utils
import xml.etree.cElementTree as ET
import xml.dom.minidom

keys = ("primary_keyframe",
        "secondary_keyframe",
        "tertiary_keyframe",
        "left_foot",
        "right_foot",
        "body_impact",
        "left_foot_lock",
        "left_foot_unlock",
        "right_foot_lock",
        "right_foot_unlock",
        "blend_range_marker",
        "stride_expansion",
        "stride_contraction",
        "ragdoll_keyframe",
        "drop_weapon_keyframe",
        "match_a",
        "match_b",
        "match_c",
        "match_d",
        "jetpack_closed",
        "jetpack_open",
        "sound_event",
        "effect_event",
        )

# class NWO_UL_AnimationComposites(bpy.types.UIList):
#     def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
#         if item:
#             # row.alignment = 'LEFT'
#             layout.prop(item, 'name', emboss=False, text="", icon_value=get_icon_id("animation_composite"))
#         else:
#             layout.label(text="", translate=False, icon_value=icon)
    
# class NWO_OT_AnimationCompositeRemove(bpy.types.Operator):
#     bl_label = "Remove Composite Animation"
#     bl_idname = "nwo.animation_composite_remove"
#     bl_options = {'UNDO'}

#     def execute(self, context):
#         nwo = context.scene.nwo
#         table = nwo.animation_composites
#         table.remove(nwo.animation_composites_active_index)
#         if nwo.animation_composites_active_index > len(table) - 1:
#             nwo.animation_composites_active_index -= 1
#         context.area.tag_redraw()
#         return {'FINISHED'}
    
# class NWO_OT_AnimationCompositeMove(bpy.types.Operator):
#     bl_label = "Move Composite Animation"
#     bl_idname = "nwo.animation_composite_move"
#     bl_options = {'UNDO'}
    
#     direction: bpy.props.StringProperty()

#     def execute(self, context):
#         nwo = context.scene.nwo
#         table = nwo.animation_composites
#         delta = {"down": 1, "up": -1,}[self.direction]
#         current_index = nwo.animation_composites_active_index
#         to_index = (current_index + delta) % len(table)
#         table.move(current_index, to_index)
#         nwo.animation_composites_active_index = to_index
#         context.area.tag_redraw()
#         return {'FINISHED'}
            
class NWO_UL_AnimationSubBlendAxis(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if item:
            # row.alignment = 'LEFT'
            layout.prop(item, 'name', emboss=False, text="", icon='INDIRECT_ONLY_OFF')
        else:
            layout.label(text="", translate=False, icon_value=icon)
            
class NWO_OT_AnimationSubBlendAxisAdd(bpy.types.Operator):
    bl_label = "Add Blend Axis"
    bl_idname = "nwo.animation_sub_blend_axis_add"
    bl_options = {'UNDO'}
    
    blend_axis: bpy.props.EnumProperty(
        name="Blend Axis",
        items=[
            ("movement_angles", "Movement Angles", ""), # linear_movement_angle get_move_angle
            ("movement_speed", "Movement Speed", ""), # linear_movement_speed get_move_speed
            ("turn_rate", "Turn Rate", ""), # average_angular_rate get_turn_rate
            ("turn_angle", "Turn Angle", ""), # total_angular_offset get_turn_angle
            ("vertical", "Vertical", ""), # translation_offset_z get_destination_vertical
            ("horizontal", "Horizontal", ""), # translation_offset_horizontal get_destination_forward
        ]
    )
    
    def execute(self, context):
        composite = context.scene.nwo.animation_composites[context.scene.nwo.animation_composites_active_index]
        blend_axis = composite.blend_axis[composite.blend_axis_active_index]
        table = blend_axis.blend_axis
        entry = table.add()
        entry.name = self.blend_axis
        blend_axis.blend_axis_active_index = len(table) - 1
        context.area.tag_redraw()
        return {'FINISHED'}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        self.layout.prop(self, 'blend_axis')
        
class NWO_OT_AnimationSubBlendAxisRemove(bpy.types.Operator):
    bl_label = "Remove Blend Axis"
    bl_idname = "nwo.animation_sub_blend_axis_remove"
    bl_options = {'UNDO'}

    def execute(self, context):
        composite = context.scene.nwo.animation_composites[context.scene.nwo.animation_composites_active_index]
        blend_axis = composite.blend_axis[composite.blend_axis_active_index]
        table = blend_axis.blend_axis
        table.remove(blend_axis.blend_axis_active_index)
        if blend_axis.blend_axis_active_index > len(table) - 1:
            blend_axis.blend_axis_active_index -= 1
        context.area.tag_redraw()
        return {'FINISHED'}
    
class NWO_OT_AnimationSubBlendAxisMove(bpy.types.Operator):
    bl_label = "Move Blend Axis"
    bl_idname = "nwo.animation_sub_blend_axis_move"
    bl_options = {'UNDO'}
    
    direction: bpy.props.StringProperty()

    def execute(self, context):
        composite = context.scene.nwo.animation_composites[context.scene.nwo.animation_composites_active_index]
        blend_axis = composite.blend_axis[composite.blend_axis_active_index]
        table = blend_axis.blend_axis
        delta = {"down": 1, "up": -1,}[self.direction]
        current_index = blend_axis.blend_axis_active_index
        to_index = (current_index + delta) % len(table)
        table.move(current_index, to_index)
        blend_axis.blend_axis_active_index = to_index
        context.area.tag_redraw()
        return {'FINISHED'}
    
class NWO_UL_AnimationBlendAxis(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if item:
            # row.alignment = 'LEFT'
            layout.prop(item, 'name', emboss=False, text="", icon='INDIRECT_ONLY_OFF')
        else:
            layout.label(text="", translate=False, icon_value=icon)
            
class NWO_OT_AnimationBlendAxisAdd(bpy.types.Operator):
    bl_label = "Add Blend Axis"
    bl_idname = "nwo.animation_blend_axis_add"
    bl_options = {'UNDO'}
    
    blend_axis: bpy.props.EnumProperty(
        name="Blend Axis",
        items=[
            ("movement_angles", "Movement Angles", ""), # linear_movement_angle get_move_angle
            ("movement_speed", "Movement Speed", ""), # linear_movement_speed get_move_speed
            ("turn_rate", "Turn Rate", ""), # average_angular_rate get_turn_rate
            ("turn_angle", "Turn Angle", ""), # total_angular_offset get_turn_angle
            ("vertical", "Vertical", ""), # translation_offset_z get_destination_vertical
            ("horizontal", "Horizontal", ""), # translation_offset_horizontal get_destination_forward
        ]
    )
    
    def execute(self, context):
        composite = context.scene.nwo.animation_composites[context.scene.nwo.animation_composites_active_index]
        table = composite.blend_axis
        entry = table.add()
        entry.name = self.blend_axis
        composite.blend_axis_active_index = len(table) - 1
        context.area.tag_redraw()
        return {'FINISHED'}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        self.layout.prop(self, 'blend_axis')
        
class NWO_OT_AnimationBlendAxisRemove(bpy.types.Operator):
    bl_label = "Remove Blend Axis"
    bl_idname = "nwo.animation_blend_axis_remove"
    bl_options = {'UNDO'}

    def execute(self, context):
        composite = context.scene.nwo.animation_composites[context.scene.nwo.animation_composites_active_index]
        table = composite.blend_axis
        table.remove(composite.blend_axis_active_index)
        if composite.blend_axis_active_index > len(table) - 1:
            composite.blend_axis_active_index -= 1
        context.area.tag_redraw()
        return {'FINISHED'}
    
class NWO_OT_AnimationBlendAxisMove(bpy.types.Operator):
    bl_label = "Move Blend Axis"
    bl_idname = "nwo.animation_blend_axis_move"
    bl_options = {'UNDO'}
    
    direction: bpy.props.StringProperty()

    def execute(self, context):
        composite = context.scene.nwo.animation_composites[context.scene.nwo.animation_composites_active_index]
        table = composite.blend_axis
        delta = {"down": 1, "up": -1,}[self.direction]
        current_index = composite.blend_axis_active_index
        to_index = (current_index + delta) % len(table)
        table.move(current_index, to_index)
        composite.blend_axis_active_index = to_index
        context.area.tag_redraw()
        return {'FINISHED'}
    
class NWO_UL_AnimationDeadZone(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if item:
            layout.prop(item, 'name', emboss=False, text="", icon='CON_OBJECTSOLVER')
        else:
            layout.label(text="", translate=False, icon_value=icon)
            
class NWO_OT_AnimationDeadZoneAdd(bpy.types.Operator):
    bl_label = "Add Animation Set"
    bl_idname = "nwo.animation_dead_zone_add"
    bl_options = {'UNDO'}
    
    def execute(self, context):
        composite = context.scene.nwo.animation_composites[context.scene.nwo.animation_composites_active_index]
        blend_axis = composite.blend_axis[composite.blend_axis_active_index]
        table = blend_axis.dead_zones
        entry = table.add()
        blend_axis.dead_zones_active_index = len(table) - 1
        entry.name = f"dead_zone{blend_axis.dead_zones_active_index}"
        context.area.tag_redraw()
        return {'FINISHED'}
        
class NWO_OT_AnimationDeadZoneRemove(bpy.types.Operator):
    bl_label = "Remove Animation Set"
    bl_idname = "nwo.animation_dead_zone_remove"
    bl_options = {'UNDO'}

    def execute(self, context):
        composite = context.scene.nwo.animation_composites[context.scene.nwo.animation_composites_active_index]
        blend_axis = composite.blend_axis[composite.blend_axis_active_index]
        table = blend_axis.dead_zones
        table.remove(blend_axis.dead_zones_active_index)
        if blend_axis.dead_zones_active_index > len(table) - 1:
            blend_axis.dead_zones_active_index -= 1
        context.area.tag_redraw()
        return {'FINISHED'}
    
class NWO_OT_AnimationDeadZoneMove(bpy.types.Operator):
    bl_label = "Move Animation Set"
    bl_idname = "nwo.animation_dead_zone_move"
    bl_options = {'UNDO'}
    
    direction: bpy.props.StringProperty()

    def execute(self, context):
        composite = context.scene.nwo.animation_composites[context.scene.nwo.animation_composites_active_index]
        blend_axis = composite.blend_axis[composite.blend_axis_active_index]
        table = blend_axis.dead_zones
        delta = {"down": 1, "up": -1,}[self.direction]
        current_index = blend_axis.dead_zones_active_index
        to_index = (current_index + delta) % len(table)
        table.move(current_index, to_index)
        blend_axis.dead_zones_active_index = to_index
        context.area.tag_redraw()
        return {'FINISHED'}
    
class NWO_UL_AnimationGroup(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if item:
            layout.prop(item, 'name', emboss=False, text="", icon='GROUP_VERTEX')
        else:
            layout.label(text="", translate=False, icon_value=icon)
            
class NWO_OT_AnimationGroupAdd(bpy.types.Operator):
    bl_label = "Add Animation Group"
    bl_idname = "nwo.animation_group_add"
    bl_options = {'UNDO'}
    
    def execute(self, context):
        composite = context.scene.nwo.animation_composites[context.scene.nwo.animation_composites_active_index]
        blend_axis = composite.blend_axis[composite.blend_axis_active_index]
        table = blend_axis.groups
        entry = table.add()
        blend_axis.groups_active_index = len(table) - 1
        entry.name = f"group{blend_axis.groups_active_index}"
        context.area.tag_redraw()
        return {'FINISHED'}
        
class NWO_OT_AnimationGroupRemove(bpy.types.Operator):
    bl_label = "Remove Animation Group"
    bl_idname = "nwo.animation_group_remove"
    bl_options = {'UNDO'}

    def execute(self, context):
        composite = context.scene.nwo.animation_composites[context.scene.nwo.animation_composites_active_index]
        blend_axis = composite.blend_axis[composite.blend_axis_active_index]
        table = blend_axis.groups
        table.remove(blend_axis.groups_active_index)
        if blend_axis.groups_active_index > len(table) - 1:
            blend_axis.groups_active_index -= 1
        context.area.tag_redraw()
        return {'FINISHED'}
    
class NWO_OT_AnimationGroupMove(bpy.types.Operator):
    bl_label = "Move Animation Group"
    bl_idname = "nwo.animation_group_move"
    bl_options = {'UNDO'}
    
    direction: bpy.props.StringProperty()

    def execute(self, context):
        composite = context.scene.nwo.animation_composites[context.scene.nwo.animation_composites_active_index]
        blend_axis = composite.blend_axis[composite.blend_axis_active_index]
        table = blend_axis.groups
        delta = {"down": 1, "up": -1,}[self.direction]
        current_index = blend_axis.groups_active_index
        to_index = (current_index + delta) % len(table)
        table.move(current_index, to_index)
        blend_axis.groups_active_index = to_index
        context.area.tag_redraw()
        return {'FINISHED'}
    
class NWO_UL_AnimationPhaseSet(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if item:
            layout.prop(item, 'name', emboss=False, text="", icon='PRESET')
        else:
            layout.label(text="", translate=False, icon_value=icon)
            
class NWO_OT_AnimationPhaseSetAdd(bpy.types.Operator):
    bl_label = "Add Animation Set"
    bl_idname = "nwo.animation_phase_set_add"
    bl_options = {'UNDO'}
    
    def execute(self, context):
        composite = context.scene.nwo.animation_composites[context.scene.nwo.animation_composites_active_index]
        blend_axis = composite.blend_axis[composite.blend_axis_active_index]
        table = blend_axis.phase_sets
        entry = table.add()
        blend_axis.phase_sets_active_index = len(table) - 1
        entry.name = f"set{blend_axis.phase_sets_active_index}"
        context.area.tag_redraw()
        return {'FINISHED'}
        
class NWO_OT_AnimationPhaseSetRemove(bpy.types.Operator):
    bl_label = "Remove Animation Set"
    bl_idname = "nwo.animation_phase_set_remove"
    bl_options = {'UNDO'}

    def execute(self, context):
        composite = context.scene.nwo.animation_composites[context.scene.nwo.animation_composites_active_index]
        blend_axis = composite.blend_axis[composite.blend_axis_active_index]
        table = blend_axis.phase_sets
        table.remove(blend_axis.phase_sets_active_index)
        if blend_axis.phase_sets_active_index > len(table) - 1:
            blend_axis.phase_sets_active_index -= 1
        context.area.tag_redraw()
        return {'FINISHED'}
    
class NWO_OT_AnimationPhaseSetMove(bpy.types.Operator):
    bl_label = "Move Animation Set"
    bl_idname = "nwo.animation_phase_set_move"
    bl_options = {'UNDO'}
    
    direction: bpy.props.StringProperty()

    def execute(self, context):
        composite = context.scene.nwo.animation_composites[context.scene.nwo.animation_composites_active_index]
        blend_axis = composite.blend_axis[composite.blend_axis_active_index]
        table = blend_axis.phase_sets
        delta = {"down": 1, "up": -1,}[self.direction]
        current_index = blend_axis.phase_sets_active_index
        to_index = (current_index + delta) % len(table)
        table.move(current_index, to_index)
        blend_axis.phase_sets_active_index = to_index
        context.area.tag_redraw()
        return {'FINISHED'}
    
class NWO_UL_AnimationLeaf(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if item:
            animation_name = "None"
            if item.animation:
                animation_name = item.animation
            layout.label(text=animation_name, icon='ACTION')
        else:
            layout.label(text="", translate=False, icon_value=icon)
            
class NWO_OT_AnimationLeafAdd(bpy.types.Operator):
    bl_label = "Add Animation Source"
    bl_idname = "nwo.animation_leaf_add"
    bl_options = {'UNDO'}
    
    phase_set: bpy.props.BoolProperty(options={'SKIP_SAVE', 'HIDDEN'})
    group: bpy.props.BoolProperty(options={'SKIP_SAVE', 'HIDDEN'})
    sub_axis: bpy.props.BoolProperty(options={'SKIP_SAVE', 'HIDDEN'})
    
    def execute(self, context):
        composite = context.scene.nwo.animation_composites[context.scene.nwo.animation_composites_active_index]
        blend_axis = composite.blend_axis[composite.blend_axis_active_index]
        if self.sub_axis:
            blend_axis = blend_axis.blend_axis[blend_axis.blend_axis_active_index]
        
        if self.phase_set:
            parent = blend_axis.phase_sets[blend_axis.phase_sets_active_index]
        elif self.group:
            parent = blend_axis.groups[blend_axis.groups_active_index]
        else:
            parent = blend_axis
            
        parent.leaves.add()
        parent.leaves_active_index = len(parent.leaves) - 1
        context.area.tag_redraw()
        return {'FINISHED'}
        
class NWO_OT_AnimationLeafRemove(bpy.types.Operator):
    bl_label = "Remove Animation Source"
    bl_idname = "nwo.animation_leaf_remove"
    bl_options = {'UNDO'}
    
    phase_set: bpy.props.BoolProperty(options={'SKIP_SAVE', 'HIDDEN'})
    group: bpy.props.BoolProperty(options={'SKIP_SAVE', 'HIDDEN'})
    sub_axis: bpy.props.BoolProperty(options={'SKIP_SAVE', 'HIDDEN'})

    def execute(self, context):
        composite = context.scene.nwo.animation_composites[context.scene.nwo.animation_composites_active_index]
        blend_axis = composite.blend_axis[composite.blend_axis_active_index]
        if self.sub_axis:
            blend_axis = blend_axis.blend_axis[blend_axis.blend_axis_active_index]
        
        if self.phase_set:
            parent = blend_axis.phase_sets[blend_axis.phase_sets_active_index]
        elif self.group:
            parent = blend_axis.groups[blend_axis.groups_active_index]
        else:
            parent = blend_axis
            
        parent.leaves.remove(parent.leaves_active_index)
        if parent.leaves_active_index > len(parent.leaves) - 1:
            parent.leaves_active_index -= 1
        context.area.tag_redraw()
        return {'FINISHED'}
    
class NWO_OT_AnimationLeafMove(bpy.types.Operator):
    bl_label = "Move Animation Source"
    bl_idname = "nwo.animation_leaf_move"
    bl_options = {'UNDO'}
    
    direction: bpy.props.StringProperty()
    phase_set: bpy.props.BoolProperty(options={'SKIP_SAVE', 'HIDDEN'})
    group: bpy.props.BoolProperty(options={'SKIP_SAVE', 'HIDDEN'})
    sub_axis: bpy.props.BoolProperty(options={'SKIP_SAVE', 'HIDDEN'})

    def execute(self, context):
        composite = context.scene.nwo.animation_composites[context.scene.nwo.animation_composites_active_index]
        blend_axis = composite.blend_axis[composite.blend_axis_active_index]
        if self.sub_axis:
            blend_axis = blend_axis.blend_axis[blend_axis.blend_axis_active_index]
        
        if self.phase_set:
            parent = blend_axis.phase_sets[blend_axis.phase_sets_active_index]
        elif self.group:
            parent = blend_axis.groups[blend_axis.groups_active_index]
        else:
            parent = blend_axis
            
        delta = {"down": 1, "up": -1,}[self.direction]
        current_index = parent.leaves_active_index
        to_index = (current_index + delta) % len(parent.leaves)
        parent.leaves.move(current_index, to_index)
        parent.leaves_active_index = to_index
        context.area.tag_redraw()
        return {'FINISHED'}
    
class CompositeXML:
    def __init__(self, data):
        self.data = data
        
    def build_xml(self):
        element_composite = ET.Element("composite")
        timing_name = utils.space_partition(self.data.timing_source.replace(":", " "), True)
        ET.SubElement(element_composite, "timing", source=timing_name)
        for blend_axis in self.data.blend_axis:
            self.write_blend_axis_entry(element_composite, blend_axis)
            
        dom = xml.dom.minidom.parseString(ET.tostring(element_composite))
        xml_string = dom.toprettyxml(indent="  ")
        part1, part2 = xml_string.split("?>")
        m_encoding = "utf-8"
        asset_dir = utils.get_asset_path()
        composites_dir = Path(asset_dir, "animations", "composites")
        composites_dir_full_path = Path(utils.get_data_path(), composites_dir)
        if not composites_dir_full_path.exists():
            composites_dir_full_path.mkdir(parents=True, exist_ok=True)
        relative_path = Path(composites_dir, self.data.name.replace(" ", "_")).with_suffix(".composite.xml")
        full_path = Path(utils.get_data_path(), relative_path)
        if not bpy.context.scene.nwo.debug_composites or not full_path.exists():
            with open(full_path, "w") as xfile:
                xfile.write(
                    part1
                    + 'encoding="{}"?>'.format(m_encoding)
                    + part2
                )
            
        return str(relative_path)
        
    def write_blend_axis_entry(self, element_composite, blend_axis, parent_blend_axis=None):
        element_blend_axis = ET.SubElement(element_composite, "blend_axis", name=blend_axis.name)
        animation_source_name = ""
        runtime_source_name = ""
        parent_runtime_source_name = ""
        match blend_axis.name:
            case "movement_angles":
                animation_source_name = "linear_movement_angle"
                runtime_source_name = "get_move_angle"
            case "movement_speed":
                animation_source_name = "linear_movement_speed"
                runtime_source_name = "get_move_speed"
            case "turn_rate":
                animation_source_name = "average_angular_rate"
                runtime_source_name = "get_turn_rate"
            case "turn_angle":
                animation_source_name = "total_angular_offset"
                runtime_source_name = "get_turn_angle"
            case "vertical":
                animation_source_name = "translation_offset_z"
                runtime_source_name = "get_destination_vertical"
            case "horizontal":
                animation_source_name = "translation_offset_horizontal"
                runtime_source_name = "get_destination_forward"
                
        if parent_blend_axis:
            parent_runtime_source_name = function_from_name(parent_blend_axis.name)
                
        ET.SubElement(element_blend_axis, "animation", source=animation_source_name, bounds=self.two_vector_string(blend_axis.animation_source_bounds) if blend_axis.animation_source_bounds_manual else "auto", limit=str(int(blend_axis.animation_source_limit)))
        ET.SubElement(element_blend_axis, "runtime", source=runtime_source_name, bounds=self.two_vector_string(blend_axis.runtime_source_bounds) if blend_axis.runtime_source_bounds_manual else "auto", clamped=str(blend_axis.runtime_source_clamped).lower())
        if blend_axis.adjusted != "none":
            ET.SubElement(element_blend_axis, "adjustment", rate=blend_axis.adjusted)
            
        for dead_zone in blend_axis.dead_zones:
            ET.SubElement(element_blend_axis, "dead_zone", bounds=self.two_vector_string(dead_zone.bounds), rate=str(int(dead_zone.rate)))
        
        for leaf in blend_axis.leaves:
            self.write_leaf_entry(element_blend_axis, leaf, parent_runtime_source_name, runtime_source_name)
        
        for phase_set in blend_axis.phase_sets:
            self.write_phase_set_entry(element_blend_axis, phase_set)
            
        for group in blend_axis.groups:
            self.write_group_entry(element_blend_axis, group, parent_runtime_source_name, runtime_source_name)
        
        if hasattr(blend_axis, "blend_axis"):
            for sub_blend_axis in blend_axis.blend_axis:
                self.write_blend_axis_entry(element_blend_axis, sub_blend_axis, blend_axis)
            
    def write_phase_set_entry(self, element_blend_axis, phase_set):
        element_phase_set = ET.SubElement(element_blend_axis, "phase_set", name=phase_set.name)
        for k in keys:
            if getattr(phase_set, f"key_{k}"):
                ET.SubElement(element_phase_set, "sync", key=k.replace("_", " "))
                
        for leaf in phase_set.leaves:
            self.write_leaf_entry(element_phase_set, leaf)
            
    def write_group_entry(self, element_blend_axis, group, parent_function_name, function_name):
        props = {}
        if parent_function_name:
            if group.manual_blend_axis_1:
                props[parent_function_name] = str(round(group.blend_axis_1, 6))
            if group.manual_blend_axis_2:
                props[function_name] = str(round(group.blend_axis_2, 6))
        else:
            if group.manual_blend_axis_1:
                props[function_name] = str(round(group.blend_axis_1, 6))
            
        element_group = ET.SubElement(element_blend_axis, "group", props)
            
        for leaf in group.leaves:
            self.write_leaf_entry(element_group, leaf)
            
    def write_leaf_entry(self, element, leaf, parent_function_name, function_name):
        props = {"source": utils.space_partition(leaf.animation.replace(":", " "), True)}
        if parent_function_name:
            if leaf.manual_blend_axis_1:
                props[parent_function_name] = str(round(leaf.blend_axis_1, 6))
            if leaf.manual_blend_axis_2:
                props[function_name] = str(round(leaf.blend_axis_2, 6))
        else:
            if leaf.manual_blend_axis_1:
                props[function_name] = str(round(leaf.blend_axis_1, 6))
                
        ET.SubElement(element, "leaf", props)
    
    @staticmethod
    def two_vector_string(vector):
        return f"{str(int(vector[0]))},{str(int(vector[1]))}"
    
    
def function_from_name(name):
    match name:
        case 'movement_angles':
            return "get_move_angle"
        case 'movement_speed':
            return "get_move_speed"
        case 'turn_rate':
            return "get_turn_rate"
        case 'turn_angle':
            return "get_turn_angle"
        case 'vertical':
            return "get_destination_vertical"
        case 'horizontal':
            return "get_destination_forward"
            
    return "function_unknown"
            