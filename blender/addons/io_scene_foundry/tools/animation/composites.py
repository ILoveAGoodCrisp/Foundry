

from math import degrees, radians
from pathlib import Path
from typing import cast
import bpy

from ...props.scene import NWO_AnimationBlendAxisItems, NWO_AnimationCompositesItems, NWO_AnimationDeadZonesItems, NWO_AnimationGroupItems, NWO_AnimationLeavesItems, NWO_AnimationPhaseSetsItems, NWO_AnimationSubBlendAxisItems
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
    
    mode: bpy.props.EnumProperty(
        name="Mode",
        description="The mode the object must be in to use this animation. Use 'any' for all modes. Other valid inputs include but are not limited to: 'crouch' when a unit is crouching, 'combat' when a unit is in combat, 'sprint' when a unit is sprinting. Modes can also refer to vehicle seats. For example an animation for a unit driving a warthog would use 'warthog_d'. For more information refer to existing model_animation_graph tags. Can be empty",
        items=[
            ('combat', 'combat', ""),
            ('crouch', 'crouch', ""),
            ('sprint', 'sprint', ""),
        ]
    )

    weapon_class: bpy.props.StringProperty(
        name="Weapon Class",
        default="any",
        description="The weapon class this unit must be holding to use this animation. Weapon class is defined per weapon in .weapon tags (under Group WEAPON > weapon labels). Can be empty",
    )
    state: bpy.props.EnumProperty(
        name="State",
        description="Animation state. You can rename this after creating the composite if you would like a state not listed below",
        items=[
            ("locomote", "locomote", ""),
            ("aim_locomote_up", "aim_locomote_up", ""),
            ("turn_left_composite", "turn_left_composite", ""),
            ("turn_right_composite", "turn_right_composite", ""),
            ("jump", "jump", ""),
        ]
    )
    
    use_preset: bpy.props.BoolProperty(
        name="Use Preset",
        default=True,
        description="Adds default fields for the selected state"
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
        if self.use_preset:
            match self.state:
                case 'locomote':
                    if self.mode == 'sprint':
                        self.preset_sprint(entry)
                    else:
                        self.preset_locomote(entry)
                case 'aim_locomote_up':
                    if self.mode == 'crouch':
                        self.preset_crouch_aim(entry)
                    else:
                        self.preset_aim_locomote_up(entry)
                case 'turn_left_composite':
                    self.preset_turn_left(entry)
                case 'turn_right_composite':
                    self.preset_turn_right(entry)
                case 'jump':
                    self.preset_jump(entry)
            
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
        col.prop(self, "use_preset")
        
    def preset_jump(self, composite: NWO_AnimationCompositesItems):
        composite.timing_source = f"{self.mode} {self.weapon_class} jump_forward_long"
        
        vertical_blend_axis = cast(NWO_AnimationBlendAxisItems, composite.blend_axis.add())
        vertical_blend_axis.adjusted = 'on_start'
        
        horizontal_blend_axis = cast(NWO_AnimationBlendAxisItems, composite.blend_axis.add())
        horizontal_blend_axis.adjusted = 'on_start'
        
        jump_phase_set = cast(NWO_AnimationPhaseSetsItems, horizontal_blend_axis.phase_sets.add())
        jump_phase_set.name = "jump"
        jump_phase_set.key_primary_keyframe = True
        jump_phase_set.key_tertiary_keyframe = True
        
        jump_phase_set.leaves.add().animation = f"{self.mode} {self.weapon_class} jump_forward_long"
        jump_phase_set.leaves.add().animation = f"{self.mode} {self.weapon_class} jump_forward_short"
        jump_phase_set.leaves.add().animation = f"{self.mode} {self.weapon_class} jump_up_long"
        jump_phase_set.leaves.add().animation = f"{self.mode} {self.weapon_class} jump_up_short"
        jump_phase_set.leaves.add().animation = f"{self.mode} {self.weapon_class} jump_down_long"
        jump_phase_set.leaves.add().animation = f"{self.mode} {self.weapon_class} jump_down_short"
        
        horizontal_blend_axis.leaves.add().animation = f"{self.mode} {self.weapon_class} jump_down_forward"
        horizontal_blend_axis.leaves.add().animation = f"{self.mode} {self.weapon_class} jump_up_forward"
        horizontal_blend_axis.leaves.add().animation = f"{self.mode} {self.weapon_class} jump_short"
        horizontal_blend_axis.leaves.add().animation = f"{self.mode} {self.weapon_class} jump_up"
        horizontal_blend_axis.leaves.add().animation = f"{self.mode} {self.weapon_class} jump_down"
        
        
    def preset_turn_left(self, composite: NWO_AnimationCompositesItems):
        composite.timing_source = f"{self.mode} {self.weapon_class} turn_left"
        
        turn_blend_axis = cast(NWO_AnimationBlendAxisItems, composite.blend_axis.add())
        turn_blend_axis.name = "turn_rate"
        turn_blend_axis.animation_source_bounds_manual = True
        turn_blend_axis.animation_source_bounds = 0, 360
        turn_blend_axis.animation_source_limit = 45
        turn_blend_axis.runtime_source_bounds_manual = True
        turn_blend_axis.runtime_source_bounds = 0, 360
        turn_blend_axis.runtime_source_clamped = False
        
        turn_blend_axis.leaves.add().animation = f"{self.mode} {self.weapon_class} turn_left"
        turn_blend_axis.leaves.add().animation = f"{self.mode} {self.weapon_class} turn_left_slow"
        turn_blend_axis.leaves.add().animation = f"{self.mode} {self.weapon_class} turn_left_fast"
        
    def preset_turn_right(self, composite: NWO_AnimationCompositesItems):
        composite.timing_source = f"{self.mode} {self.weapon_class} turn_right"
        
        turn_blend_axis = cast(NWO_AnimationBlendAxisItems, composite.blend_axis.add())
        turn_blend_axis.name = "turn_rate"
        turn_blend_axis.animation_source_bounds_manual = True
        turn_blend_axis.animation_source_bounds = 0, 360
        turn_blend_axis.animation_source_limit = 45
        turn_blend_axis.runtime_source_bounds_manual = True
        turn_blend_axis.runtime_source_bounds = 0, 360
        turn_blend_axis.runtime_source_clamped = False
        
        turn_blend_axis.leaves.add().animation = f"{self.mode} {self.weapon_class} turn_right"
        turn_blend_axis.leaves.add().animation = f"{self.mode} {self.weapon_class} turn_right_slow"
        turn_blend_axis.leaves.add().animation = f"{self.mode} {self.weapon_class} turn_right_fast"
        
    def preset_crouch_aim(self, composite: NWO_AnimationCompositesItems):
        composite.timing_source = f"{self.mode} {self.weapon_class} aim_locomote_run_front_up"
        composite.overlay = True
        
        angle_blend_axis = cast(NWO_AnimationBlendAxisItems, composite.blend_axis.add())
        angle_blend_axis.name = "movement_angles"
        angle_blend_axis.animation_source_bounds_manual = True
        angle_blend_axis.animation_source_bounds = 0, 360
        angle_blend_axis.animation_source_limit = 45
        angle_blend_axis.runtime_source_bounds_manual = True
        angle_blend_axis.runtime_source_bounds = 0, 360
        angle_blend_axis.runtime_source_clamped = False
        
        run_front_up = cast(NWO_AnimationLeavesItems, angle_blend_axis.leaves.add())
        run_front_up.animation = f"{self.mode} {self.weapon_class} aim_locomote_run_front_up"
        run_front_up.uses_move_speed = True
        run_front_up.move_speed = 0.9
        run_front_up.uses_move_angle = True
        run_front_up.move_angle = 0
        
        run_left_up = cast(NWO_AnimationLeavesItems, angle_blend_axis.leaves.add())
        run_left_up.animation = f"{self.mode} {self.weapon_class} aim_locomote_run_left_up"
        run_left_up.uses_move_speed = True
        run_left_up.move_speed = 0.9
        run_left_up.uses_move_angle = True
        run_left_up.move_angle = radians(90)
        
        run_back_up = cast(NWO_AnimationLeavesItems, angle_blend_axis.leaves.add())
        run_back_up.animation = f"{self.mode} {self.weapon_class} aim_locomote_run_back_up"
        run_back_up.uses_move_speed = True
        run_back_up.move_speed = 0.9
        run_back_up.uses_move_angle = True
        run_back_up.move_angle = radians(180)
        
        run_right_up = cast(NWO_AnimationLeavesItems, angle_blend_axis.leaves.add())
        run_right_up.animation = f"{self.mode} {self.weapon_class} aim_locomote_run_right_up"
        run_right_up.uses_move_speed = True
        run_right_up.move_speed = 0.9
        run_right_up.uses_move_angle = True
        run_right_up.move_angle = radians(270)
        
        run_360_up = cast(NWO_AnimationLeavesItems, angle_blend_axis.leaves.add())
        run_360_up.animation = f"{self.mode} {self.weapon_class} aim_locomote_run_front_up"
        run_360_up.uses_move_speed = True
        run_360_up.move_speed = 0.9
        run_360_up.uses_move_angle = True
        run_360_up.move_angle = radians(360)
        
    def preset_aim_locomote_up(self, composite: NWO_AnimationCompositesItems):
        composite.timing_source = f"{self.mode} {self.weapon_class} aim_locomote_run_front_up"
        composite.overlay = True
        
        angle_blend_axis = cast(NWO_AnimationBlendAxisItems, composite.blend_axis.add())
        angle_blend_axis.name = "movement_angles"
        angle_blend_axis.animation_source_bounds_manual = True
        angle_blend_axis.animation_source_bounds = 0, 360
        angle_blend_axis.animation_source_limit = 45
        angle_blend_axis.runtime_source_bounds_manual = True
        angle_blend_axis.runtime_source_bounds = 0, 360
        angle_blend_axis.runtime_source_clamped = False
        
        speed_blend_axis = cast(NWO_AnimationSubBlendAxisItems, angle_blend_axis.blend_axis.add())
        speed_blend_axis.name = "movement_speed"
        speed_blend_axis.animation_source_bounds_manual = True
        speed_blend_axis.animation_source_bounds = 0, 1
        speed_blend_axis.runtime_source_bounds_manual = True
        speed_blend_axis.runtime_source_bounds = 0, 1
        speed_blend_axis.runtime_source_clamped = True
        
        walk_front_up = cast(NWO_AnimationLeavesItems, speed_blend_axis.leaves.add())
        walk_front_up.animation = f"{self.mode} {self.weapon_class} aim_locomote_walk_front_up"
        walk_front_up.uses_move_speed = True
        walk_front_up.move_speed = 0.5
        walk_front_up.uses_move_angle = True
        walk_front_up.move_angle = 0
        
        run_front_up = cast(NWO_AnimationLeavesItems, speed_blend_axis.leaves.add())
        run_front_up.animation = f"{self.mode} {self.weapon_class} aim_locomote_run_front_up"
        run_front_up.uses_move_speed = True
        run_front_up.move_speed = 0.9
        run_front_up.uses_move_angle = True
        run_front_up.move_angle = 0
        
        walk_left_up = cast(NWO_AnimationLeavesItems, speed_blend_axis.leaves.add())
        walk_left_up.animation = f"{self.mode} {self.weapon_class} aim_locomote_walk_left_up"
        walk_left_up.uses_move_speed = True
        walk_left_up.move_speed = 0.5
        walk_left_up.uses_move_angle = True
        walk_left_up.move_angle = radians(90)
        
        run_left_up = cast(NWO_AnimationLeavesItems, speed_blend_axis.leaves.add())
        run_left_up.animation = f"{self.mode} {self.weapon_class} aim_locomote_run_left_up"
        run_left_up.uses_move_speed = True
        run_left_up.move_speed = 0.9
        run_left_up.uses_move_angle = True
        run_left_up.move_angle = radians(90)
        
        walk_back_up = cast(NWO_AnimationLeavesItems, speed_blend_axis.leaves.add())
        walk_back_up.animation = f"{self.mode} {self.weapon_class} aim_locomote_walk_back_up"
        walk_back_up.uses_move_speed = True
        walk_back_up.move_speed = 0.5
        walk_back_up.uses_move_angle = True
        walk_back_up.move_angle = radians(180)
        
        run_back_up = cast(NWO_AnimationLeavesItems, speed_blend_axis.leaves.add())
        run_back_up.animation = f"{self.mode} {self.weapon_class} aim_locomote_run_back_up"
        run_back_up.uses_move_speed = True
        run_back_up.move_speed = 0.9
        run_back_up.uses_move_angle = True
        run_back_up.move_angle = radians(180)
        
        walk_right_up = cast(NWO_AnimationLeavesItems, speed_blend_axis.leaves.add())
        walk_right_up.animation = f"{self.mode} {self.weapon_class} aim_locomote_walk_right_up"
        walk_right_up.uses_move_speed = True
        walk_right_up.move_speed = 0.5
        walk_right_up.uses_move_angle = True
        walk_right_up.move_angle = radians(270)
        
        run_right_up = cast(NWO_AnimationLeavesItems, speed_blend_axis.leaves.add())
        run_right_up.animation = f"{self.mode} {self.weapon_class} aim_locomote_run_right_up"
        run_right_up.uses_move_speed = True
        run_right_up.move_speed = 0.9
        run_right_up.uses_move_angle = True
        run_right_up.move_angle = radians(270)
        
        walk_360_up = cast(NWO_AnimationLeavesItems, speed_blend_axis.leaves.add())
        walk_360_up.animation = f"{self.mode} {self.weapon_class} aim_locomote_walk_front_up"
        walk_360_up.uses_move_speed = True
        walk_360_up.move_speed = 0.5
        walk_360_up.uses_move_angle = True
        walk_360_up.move_angle = radians(360)
        
        run_360_up = cast(NWO_AnimationLeavesItems, speed_blend_axis.leaves.add())
        run_360_up.animation = f"{self.mode} {self.weapon_class} aim_locomote_run_front_up"
        run_360_up.uses_move_speed = True
        run_360_up.move_speed = 0.9
        run_360_up.uses_move_angle = True
        run_360_up.move_angle = radians(360)
        
    def preset_sprint(self, composite: NWO_AnimationCompositesItems):
        composite.timing_source = f"sprint {self.weapon_class} move_front_fast"
        
        speed_blend_axis = cast(NWO_AnimationBlendAxisItems, composite.blend_axis.add())
        speed_blend_axis.name = "movement_speed"
        speed_blend_axis.animation_source_bounds_manual = True
        speed_blend_axis.animation_source_bounds = 0, 1
        speed_blend_axis.runtime_source_bounds_manual = True
        speed_blend_axis.runtime_source_bounds = 0, 1
        speed_blend_axis.runtime_source_clamped = True
        
        speed_blend_axis.leaves.add().animation = f"sprint {self.weapon_class} move_front_fast"
        speed_blend_axis.leaves.add().animation = f"sprint {self.weapon_class} move_front_fast"
        
    def preset_locomote(self, composite: NWO_AnimationCompositesItems):
        composite.timing_source = f"{self.mode} {self.weapon_class} locomote_run_front"
        angle_blend_axis = cast(NWO_AnimationBlendAxisItems, composite.blend_axis.add())
        angle_blend_axis.name = "movement_angles"
        angle_blend_axis.animation_source_bounds_manual = True
        angle_blend_axis.animation_source_bounds = 0, 360
        angle_blend_axis.animation_source_limit = 45
        angle_blend_axis.runtime_source_bounds_manual = True
        angle_blend_axis.runtime_source_bounds = 0, 360
        angle_blend_axis.runtime_source_clamped = False
        
        dead_zone_0 = cast(NWO_AnimationDeadZonesItems, angle_blend_axis.dead_zones.add())
        dead_zone_0.name = "deadzone0"
        dead_zone_0.bounds = 45, 90
        dead_zone_0.rate = 90
        
        dead_zone_1 = cast(NWO_AnimationDeadZonesItems, angle_blend_axis.dead_zones.add())
        dead_zone_1.name = "deadzone1"
        dead_zone_1.bounds = 225, 270
        dead_zone_1.rate = 90
        
        speed_blend_axis = cast(NWO_AnimationSubBlendAxisItems, angle_blend_axis.blend_axis.add())
        speed_blend_axis.name = "movement_speed"
        speed_blend_axis.runtime_source_bounds_manual = True
        speed_blend_axis.runtime_source_bounds = 0, 1
        speed_blend_axis.runtime_source_clamped = True
        
        group_0 = cast(NWO_AnimationGroupItems, speed_blend_axis.groups.add())
        group_0.name = "Front"
        group_0.uses_move_angle = True
        group_0.move_angle = 0
        group_0.leaves.add().animation = f"{self.mode} {self.weapon_class} locomote_walk_inplace"
        group_0.leaves.add().animation = f"{self.mode} {self.weapon_class} locomote_walkslow_front"
        group_0.leaves.add().animation = f"{self.mode} {self.weapon_class} locomote_walk_front"
        group_0.leaves.add().animation = f"{self.mode} {self.weapon_class} locomote_run_front"
        
        group_45 = cast(NWO_AnimationGroupItems, speed_blend_axis.groups.add())
        group_45.name = "Front Left"
        group_45.uses_move_angle = True
        group_45.move_angle = radians(45)
        group_45.leaves.add().animation = f"{self.mode} {self.weapon_class} locomote_walk_inplace"
        group_45.leaves.add().animation = f"{self.mode} {self.weapon_class} locomote_walk_frontleft"
        group_45.leaves.add().animation = f"{self.mode} {self.weapon_class} locomote_run_frontleft"
        
        group_90 = cast(NWO_AnimationGroupItems, speed_blend_axis.groups.add())
        group_90.name = "Left"
        group_90.uses_move_angle = True
        group_90.move_angle = radians(90)
        group_90.leaves.add().animation = f"{self.mode} {self.weapon_class} locomote_walk_inplace"
        group_90.leaves.add().animation = f"{self.mode} {self.weapon_class} locomote_walk_left"
        group_90.leaves.add().animation = f"{self.mode} {self.weapon_class} locomote_run_left"
        
        group_135 = cast(NWO_AnimationGroupItems, speed_blend_axis.groups.add())
        group_135.name = "Back Left"
        group_135.uses_move_angle = True
        group_135.move_angle = radians(135)
        group_135.leaves.add().animation = f"{self.mode} {self.weapon_class} locomote_walk_inplace"
        group_135.leaves.add().animation = f"{self.mode} {self.weapon_class} locomote_walk_backleft"
        group_135.leaves.add().animation = f"{self.mode} {self.weapon_class} locomote_run_backleft"
        
        group_180 = cast(NWO_AnimationGroupItems, speed_blend_axis.groups.add())
        group_180.name = "Back"
        group_180.uses_move_angle = True
        group_180.move_angle = radians(180)
        group_180.leaves.add().animation = f"{self.mode} {self.weapon_class} locomote_walk_inplace"
        group_180.leaves.add().animation = f"{self.mode} {self.weapon_class} locomote_walk_back"
        group_180.leaves.add().animation = f"{self.mode} {self.weapon_class} locomote_run_back"
        
        group_225 = cast(NWO_AnimationGroupItems, speed_blend_axis.groups.add())
        group_225.name = "Back Right"
        group_225.uses_move_angle = True
        group_225.move_angle = radians(225)
        group_225.leaves.add().animation = f"{self.mode} {self.weapon_class} locomote_walk_inplace"
        group_225.leaves.add().animation = f"{self.mode} {self.weapon_class} locomote_walk_backright"
        group_225.leaves.add().animation = f"{self.mode} {self.weapon_class} locomote_run_backright"
        
        group_270 = cast(NWO_AnimationGroupItems, speed_blend_axis.groups.add())
        group_270.name = "Right"
        group_270.uses_move_angle = True
        group_270.move_angle = radians(270)
        group_270.leaves.add().animation = f"{self.mode} {self.weapon_class} locomote_walk_inplace"
        group_270.leaves.add().animation = f"{self.mode} {self.weapon_class} locomote_walk_right"
        group_270.leaves.add().animation = f"{self.mode} {self.weapon_class} locomote_run_right"
        
        group_315 = cast(NWO_AnimationGroupItems, speed_blend_axis.groups.add())
        group_315.name = "Front Right"
        group_315.uses_move_angle = True
        group_315.move_angle = radians(315)
        group_315.leaves.add().animation = f"{self.mode} {self.weapon_class} locomote_walk_inplace"
        group_315.leaves.add().animation = f"{self.mode} {self.weapon_class} locomote_walk_frontright"
        group_315.leaves.add().animation = f"{self.mode} {self.weapon_class} locomote_run_frontright"
        
        group_360 = cast(NWO_AnimationGroupItems, speed_blend_axis.groups.add())
        group_360.name = "360 Front"
        group_360.uses_move_angle = True
        group_360.move_angle = radians(360)
        group_360.leaves.add().animation = f"{self.mode} {self.weapon_class} locomote_walk_inplace"
        group_360.leaves.add().animation = f"{self.mode} {self.weapon_class} locomote_walkslow_front"
        group_360.leaves.add().animation = f"{self.mode} {self.weapon_class} locomote_walk_front"
        group_360.leaves.add().animation = f"{self.mode} {self.weapon_class} locomote_run_front"
    
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
    def __init__(self, data: NWO_AnimationCompositesItems):
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
                
        ET.SubElement(element_blend_axis, "animation", source=animation_source_name, bounds=self.two_vector_string(blend_axis.animation_source_bounds) if blend_axis.animation_source_bounds_manual else "auto", limit=str(int(blend_axis.animation_source_limit)))
        ET.SubElement(element_blend_axis, "runtime", source=runtime_source_name, bounds=self.two_vector_string(blend_axis.runtime_source_bounds) if blend_axis.runtime_source_bounds_manual else "auto", clamped=str(blend_axis.runtime_source_clamped).lower())
        if blend_axis.adjusted != "none":
            ET.SubElement(element_blend_axis, "adjustment", rate=blend_axis.adjusted)
            
        for dead_zone in blend_axis.dead_zones:
            ET.SubElement(element_blend_axis, "dead_zone", bounds=self.two_vector_string(dead_zone.bounds), rate=str(int(dead_zone.rate)))
        
        for leaf in blend_axis.leaves:
            self.write_leaf_entry(element_blend_axis, leaf)
        
        for phase_set in blend_axis.phase_sets:
            self.write_phase_set_entry(element_blend_axis, phase_set)
            
        for group in blend_axis.groups:
            self.write_group_entry(element_blend_axis, group)
        
        if hasattr(blend_axis, "blend_axis"):
            for sub_blend_axis in blend_axis.blend_axis:
                self.write_blend_axis_entry(element_blend_axis, sub_blend_axis)
            
    def write_phase_set_entry(self, element_blend_axis, phase_set):
        element_phase_set = ET.SubElement(element_blend_axis, "phase_set", name=phase_set.name)
        for k in keys:
            if getattr(phase_set, f"key_{k}"):
                ET.SubElement(element_phase_set, "sync", key=k.replace("_", " "))
                
        for leaf in phase_set.leaves:
            self.write_leaf_entry(element_phase_set, leaf)
            
    def write_group_entry(self, element_blend_axis, group):
        props = {}
        if group.uses_move_speed:
            props["get_move_speed"] = str(round(group.move_speed, 1))
        if group.uses_move_angle:
            props["get_move_angle"] = str(int(round(degrees(group.move_angle), 0)))
            
        element_group = ET.SubElement(element_blend_axis, "group", props)
            
        for leaf in group.leaves:
            self.write_leaf_entry(element_group, leaf)
            
    def write_leaf_entry(self, element, leaf):
        props = {"source": utils.space_partition(leaf.animation.replace(":", " "), True)}
        if leaf.uses_move_speed:
            props["get_move_speed"] = str(round(leaf.move_speed, 1))
        if leaf.uses_move_angle:
            props["get_move_angle"] = str(int(round(degrees(leaf.move_angle), 0)))
        ET.SubElement(element, "leaf", props)
    
    @staticmethod
    def two_vector_string(vector):
        return f"{str(int(vector[0]))},{str(int(vector[1]))}"