
from pathlib import Path
import math
from copy import deepcopy
from itertools import combinations
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

AXIS_ANIMATION_SOURCES = {
    "movement_angles": "linear_movement_angle",
    "movement_speed": "linear_movement_speed",
    "turn_rate": "average_angular_rate",
    "turn_angle": "total_angular_offset",
    "vertical": "translation_offset_z",
    "horizontal": "translation_offset_horizontal",
    "aim_pitch": "none",
    "aim_yaw": "none",
    "aim_yaw_from_start": "none",
}

AXIS_RUNTIME_SOURCES = {
    "movement_angles": "get_move_angle",
    "movement_speed": "get_move_speed",
    "turn_rate": "get_turn_rate",
    "turn_angle": "get_turn_angle",
    "vertical": "get_destination_vertical",
    "horizontal": "get_destination_forward",
    "aim_pitch": "get_aim_pitch",
    "aim_yaw": "get_aim_yaw",
    "aim_yaw_from_start": "get_aim_yaw_from_start",
}

CYCLIC_ANGLE_SOURCES = {
    "linear_movement_angle",
    "total_angular_offset",
}


class NWO_UL_AnimationBlendAxis(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if item:
            # row.alignment = 'LEFT'
            layout.label(text=utils.formalise_string(item.name), icon='INDIRECT_ONLY_OFF')
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
            ("aim_pitch", "Aim Pitch", ""), # none get_aim_pitch
            ("aim_yaw", "Aim Yaw", ""), # none get_aim_yaw
            ("aim_yaw_from_start", "Aim Yaw From Start", ""), # none get_aim_yaw_from_start
        ]
    )
    
    def execute(self, context):
        scene_nwo = utils.get_scene_props()
        composite = scene_nwo.animations[scene_nwo.active_animation_index]
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
        scene_nwo = utils.get_scene_props()
        composite = scene_nwo.animations[scene_nwo.active_animation_index]
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
        scene_nwo = utils.get_scene_props()
        composite = scene_nwo.animations[scene_nwo.active_animation_index]
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
        scene_nwo = utils.get_scene_props()
        composite = scene_nwo.animations[scene_nwo.active_animation_index]
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
        scene_nwo = utils.get_scene_props()
        composite = scene_nwo.animations[scene_nwo.active_animation_index]
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
        scene_nwo = utils.get_scene_props()
        composite = scene_nwo.animations[scene_nwo.active_animation_index]
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
        scene_nwo = utils.get_scene_props()
        composite = scene_nwo.animations[scene_nwo.active_animation_index]
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
        scene_nwo = utils.get_scene_props()
        composite = scene_nwo.animations[scene_nwo.active_animation_index]
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
        scene_nwo = utils.get_scene_props()
        composite = scene_nwo.animations[scene_nwo.active_animation_index]
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
        scene_nwo = utils.get_scene_props()
        composite = scene_nwo.animations[scene_nwo.active_animation_index]
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
        scene_nwo = utils.get_scene_props()
        composite = scene_nwo.animations[scene_nwo.active_animation_index]
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
        scene_nwo = utils.get_scene_props()
        composite = scene_nwo.animations[scene_nwo.active_animation_index]
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
    
    def execute(self, context):
        scene_nwo = utils.get_scene_props()
        composite = scene_nwo.animations[scene_nwo.active_animation_index]
        blend_axis = composite.blend_axis[composite.blend_axis_active_index]
        
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

    def execute(self, context):
        scene_nwo = utils.get_scene_props()
        composite = scene_nwo.animations[scene_nwo.active_animation_index]
        blend_axis = composite.blend_axis[composite.blend_axis_active_index]
        
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

    def execute(self, context):
        scene_nwo = utils.get_scene_props()
        composite = scene_nwo.animations[scene_nwo.active_animation_index]
        blend_axis = composite.blend_axis[composite.blend_axis_active_index]
        
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
    def __init__(self, data, blend_axis_values=None):
        self.data = data
        self.blend_axis_values = blend_axis_values or {}
        self._missing_motion_warnings = set()
        self._automatic_value_ranges = {}
        
    def build_xml(self):
        if not self.data.timing_source.strip():
            raise RuntimeError(f"Composite [{self.data.name}]: select a timing source animation")
        self._automatic_value_ranges = self.automatic_value_ranges()
        element_composite = ET.Element("composite")
        ET.SubElement(element_composite, "timing", source=self.source_name(self.data.timing_source))
        
        parent_stack = []
        element_stack = []
        for idx, blend_axis in enumerate(self.data.blend_axis):
            rel = blend_axis.relationship

            if idx == 0 or rel == 'PARENT':
                parent_element = element_composite
                parent_stack = [blend_axis]
                element_stack = [element_composite]
            elif rel == 'CHILD':
                parent_element = element_stack[-1] if element_stack else element_composite
                parent_stack.append(blend_axis)
                element_stack.append(parent_element)
            elif rel == 'SIBLING':
                if len(parent_stack) > 1:
                    parent_stack.pop()
                    element_stack.pop()
                parent_element = element_stack[-1] if element_stack else element_composite
                parent_stack.append(blend_axis)
                element_stack.append(parent_element)

            element_stack[-1] = self.write_blend_axis_entry(blend_axis, element=parent_element, parent_stack=parent_stack)

        self.prepare_blend_space(element_composite)
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
        scene_nwo_export = utils.get_export_props()
        if not scene_nwo_export.debug_composites or not full_path.exists():
            with open(full_path, "w") as xfile:
                xfile.write(
                    part1
                    + 'encoding="{}"?>'.format(m_encoding)
                    + part2
                )
            
        return str(relative_path)

    def source_name(self, label):
        """Short names inherit composite scope; retain explicitly different scopes."""
        name = utils.AnimationName(label)
        composite = utils.AnimationName(self.data.name)
        if (name.valid and not name.custom and name.type == utils.AnimationStateType.ACTION
                and all(getattr(name, field) == getattr(composite, field)
                        for field in ('mode', 'weapon_class', 'weapon_type', 'set'))):
            return f'{name.state} {name.variant}' if name.variant else name.state
        return label.replace(':', ' ').strip()

    def prepare_blend_space(self, root):
        """Repair redundant movement dimensions in exported XML, then validate sets.

        Keep authored Blender data intact. Tool counts every axis and expects
        every leaf at the end of one axis chain, including leaves in phase sets.
        """
        def fail(message):
            raise RuntimeError(f"Composite [{self.data.name}]: {message}")

        axes = list(root.iter('blend_axis'))
        if not axes:
            fail('add at least one blend axis')
        parent = root
        for axis in axes:
            if parent.findall('blend_axis') != [axis]:
                fail('Tool requires a single chain of blend axes; use Child relationships')
            if parent is not root and (parent.findall('leaf') or parent.findall('phase_set')):
                fail('place all animations and phase sets on the innermost blend axis')
            parent = axis
        if len(axes) > 3:
            fail('the supplied Tool importer supports at most three blend axes')
        leaves = list(root.iter('leaf'))
        if not leaves:
            fail('no animation sources are configured')

        # A constant movement direction is not a blend dimension. Speed-only
        # forward locomotion must remain valid for old .blend files as well.
        for axis in sorted(axes, key=lambda item: item.find('animation').get('source') != 'linear_movement_angle'):
            source = axis.find('animation').get('source')
            if source not in {'linear_movement_angle', 'linear_movement_speed'} or len(axes) == 1:
                continue
            selection = axis.find('phase_select')
            if selection is not None and selection.get('priority') != 'current':
                continue  # Do not discard an explicitly authored selection policy.
            values = [leaf.get(source) for leaf in leaves]
            if any(value is None for value in values):
                continue  # Tool will measure unresolved motion from its animation data.
            values = [float(value) for value in values]
            if not all(math.isfinite(value) for value in values):
                fail(f'non-finite sample value on {axis.get("name")}')
            if max(values) - min(values) > 1e-6:
                continue
            if axis is axes[0] and any('bounds' in phase.attrib for phase in root.iter('phase_set')):
                continue  # Explicit set bounds belong to the original outer axis.
            owner = next(node for node in root.iter() if axis in list(node))
            position = list(owner).index(axis)
            owner.remove(axis)
            for child in list(axis):
                if child.tag in {'blend_axis', 'phase_set', 'leaf'}:
                    owner.insert(position, child)
                    position += 1
            for leaf in leaves:
                leaf.attrib.pop(source, None)
            axes.remove(axis)
            utils.print_warning(f"Composite [{self.data.name}]: omitted constant {axis.get('name')} axis from export")

        terminal = axes[-1]
        sets = terminal.findall('phase_set')
        loose = terminal.findall('leaf')
        if sets and loose:
            # Tool's sets use contiguous offsets. Mixing loose leaves with named
            # sets otherwise makes those offsets ambiguous.
            name = '__ungrouped'
            while any(phase.get('name') == name for phase in sets):
                name += '_'
            implicit = ET.SubElement(terminal, 'phase_set', name=name)
            for leaf in loose:
                terminal.remove(leaf)
                implicit.append(leaf)
            sets.append(implicit)
        populations = sets or [terminal]
        sources = [axis.find('animation').get('source') for axis in axes]
        for population in populations:
            label = population.get('name', 'animations')
            if 'bounds' in population.attrib:
                lo, hi = map(float, population.get('bounds').split(','))
                if not math.isfinite(lo) or not math.isfinite(hi) or hi < lo:
                    fail(f'phase set [{label}] needs finite, ordered set bounds')
            samples = []
            seen = set()
            for leaf in population.findall('leaf'):
                key = tuple(sorted(leaf.attrib.items()))
                if key in seen:
                    population.remove(leaf)
                else:
                    samples.append(leaf)
                    seen.add(key)
            if not samples:
                fail(f'phase set [{label}] has no animation sources')
            # A deliberate constant-pose speed blend can reference one clip at
            # two endpoints. This does not invent a different animation or gait.
            if len(axes) == 1 and sources == ['linear_movement_speed'] and len({leaf.get('source') for leaf in samples}) == 1:
                bounds = [float(value) for value in axes[0].find('animation').get('bounds').split(',')]
                if bounds[0] == bounds[1] and len(samples) == 1:
                    # Equal bounds mean automatic extents to Tool. A single
                    # speed sample needs a nonzero interval for the fallback.
                    bounds = [0.0, max(float(samples[0].get(sources[0], '1')), 1e-3)]
                    axes[0].find('animation').set('bounds', self.two_vector_string(bounds))
                if bounds[1] > bounds[0] and len(samples) == 1:
                    samples[0].set(sources[0], self.format_number(bounds[0]))
                    other = deepcopy(samples[0])
                    other.set(sources[0], self.format_number(bounds[1]))
                    population.append(other)
                    samples.append(other)
                    utils.print_warning(f"Composite [{self.data.name}]: using one clip at both speed endpoints; verify stride and playback in game")
            if len(samples) <= len(axes):
                fail(f'phase set [{label}] has {len(samples)} samples for {len(axes)} axes; needs at least {len(axes) + 1}')
            points = []
            for leaf in samples:
                point = []
                for axis, source in zip(axes, sources):
                    value = leaf.get(source if source != 'none' else axis.find('runtime').get('source'))
                    if value is None:
                        break
                    lo, hi = map(float, axis.find('animation').get('bounds').split(','))
                    value = float(value)
                    if not math.isfinite(value) or not math.isfinite(lo) or not math.isfinite(hi) or hi < lo:
                        fail(f'phase set [{label}] has invalid values or bounds on {axis.get("name")}')
                    point.append((value - lo) / (hi - lo) if hi != lo else value)
                if len(point) != len(axes):
                    break
                points.append(point)
            if len(points) != len(samples):
                utils.print_warning(f"Composite [{self.data.name}]: phase set [{label}] has unresolved motion values; Tool must validate its geometry")
                continue
            for i, point in enumerate(points):
                if any(max(abs(a-b) for a, b in zip(point, other)) < 1e-6 for other in points[:i]):
                    fail(f'phase set [{label}] contains duplicate sample coordinates')
            rows = [[a-b for a, b in zip(point, points[0])] for point in points[1:]]
            rank = 0
            for column in range(len(axes)):
                pivot = next((i for i in range(rank, len(rows)) if abs(rows[i][column]) > 1e-6), None)
                if pivot is None:
                    continue
                rows[rank], rows[pivot] = rows[pivot], rows[rank]
                scale = rows[rank][column]
                rows[rank] = [value / scale for value in rows[rank]]
                for i in range(rank + 1, len(rows)):
                    scale = rows[i][column]
                    rows[i] = [a - scale*b for a, b in zip(rows[i], rows[rank])]
                rank += 1
            if rank < len(axes):
                fail(f'phase set [{label}] samples only span {rank} dimensions for {len(axes)} axes; remove an unused axis or add suitable movement samples')
            if len(axes) == 2:
                limits = []
                for axis in axes:
                    node = axis.find('animation')
                    limit = float(node.get('limit', '0'))
                    lo, hi = map(float, node.get('bounds').split(','))
                    limits.append((limit / (hi - lo) if hi > lo else limit) if limit > 0 else math.inf)
                if any(math.isfinite(limit) for limit in limits):
                    # Full rank alone is insufficient: Tool's blend limits must
                    # allow a non-degenerate triangle at every sample. Converted
                    # diagonals often lie exactly between two cardinal samples.
                    def allowed(a, b):
                        return all(abs(x-y) <= limit + 1e-6 for x, y, limit in zip(a, b, limits))
                    for index, point in enumerate(points):
                        neighbors = [other for i, other in enumerate(points) if i != index and allowed(point, other)]
                        supported = False
                        for a, b in combinations(neighbors, 2):
                            area = (a[0]-point[0]) * (b[1]-point[1]) - (a[1]-point[1]) * (b[0]-point[0])
                            if abs(area) > 1e-6 and allowed(a, b):
                                supported = True
                                break
                        if not supported:
                            for axis, limit in zip(axes, limits):
                                if math.isfinite(limit):
                                    axis.find('animation').set('limit', '0')
                            utils.print_warning(
                                f'Composite [{self.data.name}]: phase set [{label}] blend limits leave '
                                f'[{samples[index].get("source")}] without a non-degenerate triangle. '
                                'Tool can hang on this layout. Exported finite Animation Source Limits '
                                'as 0 (unlimited); saved Blender settings are unchanged. Check blending '
                                'in game, or author a complete directional grid to retain finite limits.')
                            break

    def automatic_value_for_axis(self, animation_name, blend_axis):
        raw_value = self.raw_automatic_value_for_axis(animation_name, blend_axis.name)
        if raw_value is None:
            return None

        return self.normalise_value_for_axis(raw_value, blend_axis, True)

    def raw_automatic_value_for_axis(self, animation_name, axis_name):
        source = animation_source_from_name(axis_name)
        if source == "none":
            return 0.0

        motion_values = self.motion_values_for_animation(animation_name)
        if motion_values is None:
            return None

        if hasattr(motion_values, "get"):
            return motion_values.get(source)

        return getattr(motion_values, source, None)

    def automatic_value_ranges(self):
        ranges = {}
        for blend_axis, parent_stack in self.blend_axis_parent_stacks():
            self.collect_automatic_value_ranges(blend_axis, parent_stack, ranges)

        return ranges

    def collect_automatic_value_ranges(self, parent, parent_stack, ranges):
        for leaf in getattr(parent, "leaves", []):
            self.collect_leaf_automatic_value_ranges(leaf, parent_stack, ranges, parent)

        for phase_set in getattr(parent, "phase_sets", []):
            self.collect_automatic_value_ranges(phase_set, parent_stack, ranges)

        for group in getattr(parent, "groups", []):
            self.collect_automatic_value_ranges(group, parent_stack, ranges)

    def collect_leaf_automatic_value_ranges(self, leaf, parent_stack, ranges, parent=None):
        for idx, blend_axis in enumerate(parent_stack):
            if idx > 9 or getattr(leaf, f"manual_blend_axis_{idx}") or getattr(parent, f"manual_blend_axis_{idx}", False):
                continue

            source = animation_source_from_name(blend_axis.name)
            if source == "none":
                continue

            value = self.raw_automatic_value_for_axis(leaf.animation, blend_axis.name)
            if value is None:
                continue

            key = id(blend_axis)
            current = ranges.get(key)
            if current is None:
                ranges[key] = [value, value]
            else:
                current[0] = min(current[0], value)
                current[1] = max(current[1], value)

    def blend_axis_parent_stacks(self):
        parent_stack = []
        for idx, blend_axis in enumerate(self.data.blend_axis):
            rel = blend_axis.relationship

            if idx == 0 or rel == 'PARENT':
                parent_stack = [blend_axis]
            elif rel == 'CHILD':
                parent_stack.append(blend_axis)
            elif rel == 'SIBLING':
                if len(parent_stack) > 1:
                    parent_stack.pop()
                parent_stack.append(blend_axis)

            yield blend_axis, list(parent_stack)

    def motion_values_for_animation(self, animation_name):
        if not animation_name:
            return None

        for key in self.animation_name_keys(animation_name):
            motion_values = self.blend_axis_values.get(key)
            if motion_values is not None:
                return motion_values

        warning_key = animation_name.strip().lower()
        if warning_key and warning_key not in self._missing_motion_warnings:
            self._missing_motion_warnings.add(warning_key)
            utils.print_warning(
                f"Composite [{self.data.name}] could not precompute blend axis values for animation [{animation_name}]. "
                "Tool may calculate any missing leaf values."
            )

        return None

    @staticmethod
    def animation_name_keys(animation_name):
        names = (
            animation_name,
            animation_name.replace(":", " "),
            animation_name.replace(" ", ":"),
        )
        seen = set()
        for name in names:
            key = name.strip().lower()
            if key and key not in seen:
                seen.add(key)
                yield key
        
    def write_blend_axis_entry(self, blend_axis, element=None, parent_stack=[]):
        element_blend_axis = ET.SubElement(element, "blend_axis", name=blend_axis.name)
        animation_source_name = animation_source_from_name(blend_axis.name)
        runtime_source_name = runtime_source_from_name(blend_axis.name)
                
        ET.SubElement(
            element_blend_axis,
            "animation",
            source=animation_source_name,
            bounds=self.two_vector_string(self.animation_bounds_for_axis(blend_axis)),
            limit=self.format_number(blend_axis.animation_source_limit),
        )
        ET.SubElement(element_blend_axis, "runtime", source=runtime_source_name, bounds=self.two_vector_string(self.runtime_bounds_for_axis(blend_axis)), clamped=str(blend_axis.runtime_source_clamped).lower())
        if blend_axis.adjusted != "none":
            ET.SubElement(element_blend_axis, "adjustment", rate=blend_axis.adjusted)
        priority = getattr(blend_axis, 'phase_priority', 'default')
        if priority == 'default':
            legacy = {phase.priority for phase in blend_axis.phase_sets if phase.priority != 'default'}
            if len(legacy) > 1:
                raise RuntimeError(f"Composite [{self.data.name}]: conflicting legacy phase priorities; select one priority on the blend axis")
            priority = next(iter(legacy), 'current')
        ET.SubElement(element_blend_axis, 'phase_select', priority=priority)
            
        for dead_zone in blend_axis.dead_zones:
            ET.SubElement(element_blend_axis, "dead_zone", bounds=self.two_vector_string(dead_zone.bounds), rate=self.format_number(dead_zone.rate))
        
        emitted_leaf_values = {}
        for leaf in blend_axis.leaves:
            self.write_leaf_entry(element_blend_axis, leaf, parent_stack, emitted_leaf_values=emitted_leaf_values)
        
        phase_names = {phase.name for phase in blend_axis.phase_sets}
        for group in blend_axis.groups:
            if group.phase_set and group.phase_set not in phase_names:
                raise RuntimeError(f"Composite [{self.data.name}]: group [{group.name}] refers to missing phase set [{group.phase_set}]")
        for phase_set in blend_axis.phase_sets:
            groups = [group for group in blend_axis.groups if group.phase_set == phase_set.name]
            self.write_phase_set_entry(element_blend_axis, phase_set, parent_stack, groups)
            
        for group in blend_axis.groups:
            if not group.phase_set:
                self.write_group_entry(element_blend_axis, group, parent_stack, emitted_leaf_values)
            
        return element_blend_axis
            
    def write_phase_set_entry(self, element_blend_axis, phase_set, parent_stack, groups=()):
        element_phase_set = ET.SubElement(element_blend_axis, "phase_set", name=phase_set.name)
        if phase_set.timing_source:
            element_phase_set.set('timing', self.source_name(phase_set.timing_source))
        if phase_set.bounds_manual:
            element_phase_set.set('bounds', self.two_vector_string(phase_set.bounds))
        for k in keys:
            if getattr(phase_set, f"key_{k}"):
                ET.SubElement(element_phase_set, "sync", key=k.replace("_", " "))
                
        emitted_leaf_values = {}
        for leaf in phase_set.leaves:
            self.write_leaf_entry(element_phase_set, leaf, parent_stack, emitted_leaf_values=emitted_leaf_values)
        for group in groups:
            self.write_group_entry(element_phase_set, group, parent_stack, emitted_leaf_values)
            
    def write_group_entry(self, element_blend_axis, group, parent_stack, emitted_leaf_values=None):
        props = {}
        for idx, item in enumerate(parent_stack):
            if idx > 9:
                break
            if getattr(group, f"manual_blend_axis_{idx}"):
                value = self.normalise_value_for_axis(getattr(group, f"blend_axis_{idx}"), item, False)
                props[self.value_attribute_name(item.name, True)] = self.format_number(value)

        for leaf in group.leaves:
            self.write_leaf_entry(element_blend_axis, leaf, parent_stack, props, emitted_leaf_values)

    def write_leaf_entry(self, element, leaf, parent_stack, inherited_props=None, emitted_leaf_values=None):
        if not leaf.animation.strip():
            raise RuntimeError(f"Composite [{self.data.name}]: select an animation for every source")
        props = {"source": self.source_name(leaf.animation)}
        if inherited_props:
            props.update(inherited_props)

        for idx, item in enumerate(parent_stack):
            if idx > 9:
                break
            if getattr(leaf, f"manual_blend_axis_{idx}"):
                value = self.normalise_value_for_axis(getattr(leaf, f"blend_axis_{idx}"), item, False)
                attribute_name = self.value_attribute_name(item.name, True)
            elif self.has_inherited_value(props, item.name):
                continue
            else:
                value = self.automatic_value_for_axis(leaf.animation, item)
                attribute_name = self.value_attribute_name(item.name, False)

            if value is not None:
                props[attribute_name] = self.format_number(value)

        if emitted_leaf_values is not None:
            key = self.leaf_parameter_key(parent_stack, props)
            if key is not None:
                if key in emitted_leaf_values:
                    previous = emitted_leaf_values[key]
                    if previous != props['source']:
                        raise RuntimeError(f"Composite [{self.data.name}]: [{previous}] and [{props['source']}] have identical blend coordinates; choose one source or assign meaningful distinct values")
                    return
                emitted_leaf_values[key] = props['source']

        ET.SubElement(element, "leaf", props)

    def leaf_parameter_key(self, parent_stack, props):
        values = []
        for item in parent_stack:
            value = self.value_for_axis_from_props(item, props)
            if value is None:
                return None

            values.append(self.normalised_parameter_key_value(value, item))

        return tuple(values)

    def value_for_axis_from_props(self, blend_axis, props):
        for attribute_name in (
            self.value_attribute_name(blend_axis.name, True),
            self.value_attribute_name(blend_axis.name, False),
        ):
            if attribute_name in props:
                return props[attribute_name]

        return None

    def normalised_parameter_key_value(self, value, blend_axis):
        try:
            numeric = float(value)
        except ValueError:
            return str(value).strip().lower()

        bounds_min, bounds_max = self.animation_bounds_for_axis(blend_axis)
        if bounds_min != bounds_max:
            numeric = (numeric - bounds_min) / (bounds_max - bounds_min)

        return round(numeric, 6)
    
    @staticmethod
    def two_vector_string(vector):
        return f"{CompositeXML.format_number(vector[0])},{CompositeXML.format_number(vector[1])}"
    
    @staticmethod
    def format_number(value):
        numeric = float(value)
        if numeric.is_integer():
            return str(int(numeric))
        return f"{numeric:.6f}".rstrip("0").rstrip(".")

    def animation_bounds_for_axis(self, blend_axis):
        source = animation_source_from_name(blend_axis.name)
        if blend_axis.animation_source_bounds_manual:
            bounds = blend_axis.animation_source_bounds
            if source == "linear_movement_speed":
                return 0.0, float(bounds[1])

            return float(bounds[0]), float(bounds[1])

        if source == "linear_movement_speed":
            value_range = self._automatic_value_ranges.get(id(blend_axis))
            if value_range is not None:
                max_speed = max(float(value_range[1]), 0.0)
                if max_speed > 0.0:
                    return 0.0, max_speed

        return 0.0, 1.0

    def runtime_bounds_for_axis(self, blend_axis):
        if blend_axis.runtime_source_bounds_manual:
            bounds = blend_axis.runtime_source_bounds
            return float(bounds[0]), float(bounds[1])

        return self.animation_bounds_for_axis(blend_axis)

    def normalise_value_for_axis(self, value, blend_axis, automatic):
        source = animation_source_from_name(blend_axis.name)
        if source == "none":
            return 0.0

        numeric = float(value)
        if automatic and source == "linear_movement_speed":
            return numeric

        bounds_min, bounds_max = self.animation_bounds_for_axis(blend_axis)
        bounds_span = bounds_max - bounds_min

        if source in CYCLIC_ANGLE_SOURCES and abs(abs(bounds_span) - 360.0) < 1e-3:
            return self.wrap_value_to_bounds(numeric, bounds_min, bounds_max)

        if automatic:
            value_range = self._automatic_value_ranges.get(id(blend_axis))
            if value_range is not None:
                source_min, source_max = value_range
                if source_min != source_max and bounds_min != bounds_max:
                    return self.rescale_value(source_min, source_max, bounds_min, bounds_max, numeric)

                return bounds_min

        return numeric

    @staticmethod
    def rescale_value(source_min, source_max, target_min, target_max, value):
        t = (value - source_min) / (source_max - source_min)
        return target_min + t * (target_max - target_min)

    @staticmethod
    def wrap_value_to_bounds(value, bounds_min, bounds_max):
        span = bounds_max - bounds_min
        if span == 0.0:
            return bounds_min

        wrapped = ((value - bounds_min) % span) + bounds_min
        if wrapped == bounds_min and value != bounds_min:
            return bounds_max

        return wrapped

    @staticmethod
    def value_attribute_name(axis_name, manual):
        animation_source = animation_source_from_name(axis_name)
        if manual and animation_source == "none":
            return runtime_source_from_name(axis_name)

        return animation_source

    def has_inherited_value(self, props, axis_name):
        return (
            self.value_attribute_name(axis_name, True) in props
            or self.value_attribute_name(axis_name, False) in props
        )
    
    
def animation_source_from_name(name):
    return AXIS_ANIMATION_SOURCES.get(name, "function_unknown")


def runtime_source_from_name(name):
    return AXIS_RUNTIME_SOURCES.get(name, "function_unknown")


def function_from_name(name):
    return runtime_source_from_name(name)
            
