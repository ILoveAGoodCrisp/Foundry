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

from math import degrees
from pathlib import Path
import bpy

from ...props.scene import NWO_AnimationCompositesItems
from ...icons import get_icon_id
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

class NWO_UL_AnimationComposites(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if item:
            # row.alignment = 'LEFT'
            layout.prop(item, 'name', emboss=False, text="", icon_value=get_icon_id("animation_composite"))
        else:
            layout.label(text="", translate=False, icon_value=icon)
            
class NWO_OT_AnimationCompositeAdd(bpy.types.Operator):
    bl_label = "Add Composite Animation"
    bl_idname = "nwo.animation_composite_add"
    bl_options = {'UNDO'}
    
    mode: bpy.props.StringProperty(
        name="Mode",
        description="The mode the object must be in to use this animation. Use 'any' for all modes. Other valid inputs inlcude but are not limited to: 'crouch' when a unit is crouching,  'combat' when a unit is in combat. Modes can also refer to vehicle seats. For example an animation for a unit driving a warthog would use 'warthog_d'. For more information refer to existing model_animation_graph tags. Can be empty",
    )

    weapon_class: bpy.props.StringProperty(
        name="Weapon Class",
        description="The weapon class this unit must be holding to use this animation. Weapon class is defined per weapon in .weapon tags (under Group WEAPON > weapon labels). Can be empty",
    )
    state: bpy.props.EnumProperty(
        name="State",
        items=[
            ("locomote", "locomote", ""),
            ("aim_locomote_up", "aim_locomote_up", ""),
            ("turn_left_composite", "turn_left_composite", ""),
            ("turn_right_composite", "turn_right_composite", ""),
            ("jump", "jump", ""),
        ]
    )
    
    def build_name(self):
        name = ""
        name += self.mode.strip() if self.mode.strip() else "any"
        name += " "
        name += self.weapon_class.strip() if self.weapon_class.strip() else "any"
        name += " "
        name += self.state
        return name

    def execute(self, context):
        nwo = context.scene.nwo
        table = nwo.animation_composites
        entry = table.add()
        entry.name = self.build_name()
        nwo.animation_composites_active_index = len(table) - 1
        context.area.tag_redraw()
        return {'FINISHED'}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.label(text="Animation Name")
        col = layout.column()
        col.use_property_split = True
        col.prop(self, "mode")
        col.prop(self, "weapon_class")
        col.prop(self, "state", text="State")
    
class NWO_OT_AnimationCompositeRemove(bpy.types.Operator):
    bl_label = "Remove Composite Animation"
    bl_idname = "nwo.animation_composite_remove"
    bl_options = {'UNDO'}

    def execute(self, context):
        nwo = context.scene.nwo
        table = nwo.animation_composites
        table.remove(nwo.animation_composites_active_index)
        if nwo.animation_composites_active_index > len(table) - 1:
            nwo.animation_composites_active_index -= 1
        context.area.tag_redraw()
        return {'FINISHED'}
    
class NWO_OT_AnimationCompositeMove(bpy.types.Operator):
    bl_label = "Move Composite Animation"
    bl_idname = "nwo.animation_composite_move"
    bl_options = {'UNDO'}
    
    direction: bpy.props.StringProperty()

    def execute(self, context):
        nwo = context.scene.nwo
        table = nwo.animation_composites
        delta = {"down": 1, "up": -1,}[self.direction]
        current_index = nwo.animation_composites_active_index
        to_index = (current_index + delta) % len(table)
        table.move(current_index, to_index)
        nwo.animation_composites_active_index = to_index
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
                animation_name = item.animation.nwo.name_override if item.animation.nwo.name_override.strip() else item.animation.name
            layout.label(text=animation_name, icon='ACTION')
        else:
            layout.label(text="", translate=False, icon_value=icon)
            
class NWO_OT_AnimationLeafAdd(bpy.types.Operator):
    bl_label = "Add Animation Source"
    bl_idname = "nwo.animation_leaf_add"
    bl_options = {'UNDO'}
    
    phase_set: bpy.props.BoolProperty(options={'SKIP_SAVE', 'HIDDEN'})
    
    def execute(self, context):
        composite = context.scene.nwo.animation_composites[context.scene.nwo.animation_composites_active_index]
        blend_axis = composite.blend_axis[composite.blend_axis_active_index]
        
        if self.phase_set:
            parent = blend_axis.phase_sets[blend_axis.phase_sets_active_index]
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

    def execute(self, context):
        composite = context.scene.nwo.animation_composites[context.scene.nwo.animation_composites_active_index]
        blend_axis = composite.blend_axis[composite.blend_axis_active_index]
        
        if self.phase_set:
            parent = blend_axis.phase_sets[blend_axis.phase_sets_active_index]
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

    def execute(self, context):
        composite = context.scene.nwo.animation_composites[context.scene.nwo.animation_composites_active_index]
        blend_axis = composite.blend_axis[composite.blend_axis_active_index]
        
        if self.phase_set:
            parent = blend_axis.phase_sets[blend_axis.phase_sets_active_index]
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
    def __init__(self, data: NWO_AnimationCompositesItems):
        self.data = data
        
    def build_xml(self):
        element_composite = ET.Element("composite")
        timing_action = self.data.timing_source
        timing_name = timing_action.nwo.name_override
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
        with open(full_path, "w") as xfile:
            xfile.write(
                part1
                + 'encoding="{}"?>'.format(m_encoding)
                + part2
            )
            
        return str(relative_path)
        
    def write_blend_axis_entry(self, element_composite, blend_axis):
        element_blend_axis = ET.SubElement(element_composite, "blend_axis", name=blend_axis.name)
        animation_source_name = ""
        runtime_source_name = ""
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
            case "vertical":
                animation_source_name = "translation_offset_z"
                runtime_source_name = "get_destination_vertical"
            case "horizontal":
                animation_source_name = "translation_offset_horizontal"
                runtime_source_name = "get_destination_forward"
                
        ET.SubElement(element_blend_axis, "animation", source=animation_source_name, bounds=self.two_vector_string(blend_axis.animation_source_bounds), limit=str(int(blend_axis.animation_source_limit)))
        ET.SubElement(element_blend_axis, "runtime", source=runtime_source_name, bounds=self.two_vector_string(blend_axis.runtime_source_bounds), clamped=str(blend_axis.runtime_source_clamped).lower())
        if blend_axis.adjusted != "none":
            ET.SubElement(element_blend_axis, "adjustment", rate=blend_axis.adjusted)
            
        for dead_zone in blend_axis.dead_zones:
            ET.SubElement(element_blend_axis, "dead_zone", bounds=self.two_vector_string(dead_zone.bounds), rate=str(int(dead_zone.rate)))
        
        for leaf in blend_axis.leaves:
            self.write_leaf_entry(element_blend_axis, leaf)
        
        for phase_set in blend_axis.phase_sets:
            self.write_phase_set_entry(element_blend_axis, phase_set)
            
    def write_phase_set_entry(self, element_blend_axis, phase_set):
        element_phase_set = ET.SubElement(element_blend_axis, "phase_set", name=phase_set.name)
        for k in keys:
            if getattr(phase_set, f"key_{k}"):
                ET.SubElement(element_phase_set, "sync", key=k.replace("_", " "))
                
        for leaf in phase_set.leaves:
            self.write_leaf_entry(element_phase_set, leaf)
            
    def write_leaf_entry(self, element, leaf):
        props = {"source": leaf.animation.nwo.name_override}
        if leaf.uses_move_speed:
            props["get_move_speed"] = str(round(leaf.move_speed, 1))
        if leaf.uses_move_angle:
            props["get_move_angle"] = str(int(degrees(leaf.move_angle)))
        ET.SubElement(element, "leaf", props)
    
    @staticmethod
    def two_vector_string(vector):
        return f"{str(int(vector[0]))},{str(int(vector[1]))}"