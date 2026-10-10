"""Scene convention conversion and independent selected-object transforms."""
import bpy

from .. import utils
from ..coordinate_system import CoordinateSystem, FORWARD_ITEMS
from ..scene_conversion import collect_objects, convert_scene, isolate_scope


class NWO_ScaleScene(bpy.types.Operator):
    bl_idname = "nwo.scale_scene"
    bl_label = "Convert Scene Coordinates"
    bl_description = "Convert the active scene and its referenced collections while preserving in-game placement"
    bl_options = {"REGISTER", "UNDO"}

    scale: bpy.props.EnumProperty(
        name="Destination Scale", options={'SKIP_SAVE'}, default='blender',
        items=[('blender', 'Blender Scale', 'One scene unit represents one meter'),
               ('max', 'Halo Scale', 'One scene unit represents 0.03048 meters')],
    )
    forward: bpy.props.EnumProperty(
        name="Destination Forward", options={'SKIP_SAVE'}, default='y-', items=FORWARD_ITEMS,
    )

    def execute(self, context):
        old_mode = context.mode
        utils.set_object_mode(context)
        try:
            changed = convert_scene(context, CoordinateSystem(self.scale, self.forward))
        finally:
            if context.object and old_mode in {'EDIT_MESH', 'EDIT_ARMATURE', 'POSE'}:
                bpy.ops.object.mode_set(mode='POSE' if old_mode == 'POSE' else 'EDIT')
        self.report({'INFO'}, "Scene coordinates converted" if changed else "Scene already uses this convention")
        return {'FINISHED'}

    def invoke(self, context, event):
        self.scale = context.scene.nwo.scale
        self.forward = context.scene.nwo.forward_direction
        return context.window_manager.invoke_props_dialog(self, width=420)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        current = CoordinateSystem.from_scene(context.scene.nwo)
        label = 'Blender Scale' if current.scale == 'blender' else 'Halo Scale'
        forward = dict((item[0], item[1]) for item in FORWARD_ITEMS)[current.forward]
        layout.label(text=f"Current: {label}, {forward} forward, Z up")
        layout.prop(self, 'scale')
        layout.prop(self, 'forward')
        factor, angle = current.conversion_to(CoordinateSystem(self.scale, self.forward))
        layout.label(text=f"Scale factor: {factor:.6g}   Rotation: {angle * 180 / 3.141592653589793:.0f}°")
        layout.label(text="Converts this scene, referenced collections and animations.")
        layout.label(text="Preserves in-game placement and keeps other scenes unchanged.")


class NWO_TransformSelected(bpy.types.Operator):
    bl_idname = "nwo.transform_selected"
    bl_label = "Transform Selected Objects"
    bl_description = "Resize or rotate selected objects around the world origin without changing the scene convention"
    bl_options = {"REGISTER", "UNDO"}

    scale_factor: bpy.props.FloatProperty(name="Scale Factor", default=1., min=0.000001,
        description="Uniform object scale around the world origin")
    rotation: bpy.props.FloatProperty(name="Z Rotation", default=0., subtype='ANGLE')

    @classmethod
    def poll(cls, context):
        return bool(context.selected_objects) and context.mode == 'OBJECT'

    def execute(self, context):
        if self.scale_factor == 1. and self.rotation == 0.:
            return {'FINISHED'}
        selected, active = list(context.selected_objects), context.view_layer.objects.active
        descendants = set(selected)
        while True:
            expanded = descendants | {ob for ob in collect_objects(context.scene) if ob.parent in descendants}
            if expanded == descendants:
                break
            descendants = expanded
        _, mapping = isolate_scope(context.scene, descendants, copy_data=False)
        utils.deselect_all_objects()
        selected = [mapping.get(ob, ob) for ob in selected]
        for ob in selected:
            ob.select_set(True)
        context.view_layer.objects.active = mapping.get(active, active)
        auto_key = context.scene.tool_settings.use_keyframe_insert_auto
        context.scene.tool_settings.use_keyframe_insert_auto = False
        try:
            if self.scale_factor != 1.:
                bpy.ops.transform.resize(value=(self.scale_factor,) * 3, orient_type='GLOBAL',
                                         center_override=(0., 0., 0.))
            if self.rotation:
                bpy.ops.transform.rotate(value=self.rotation, orient_axis='Z', orient_type='GLOBAL',
                                         center_override=(0., 0., 0.))
        finally:
            context.scene.tool_settings.use_keyframe_insert_auto = auto_key
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.prop(self, 'scale_factor')
        self.layout.prop(self, 'rotation')
        self.layout.label(text="Applies an object transform to the current pose.")
        self.layout.label(text="The scene convention stays unchanged.")
