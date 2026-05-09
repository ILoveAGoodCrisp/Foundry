

import math
import os
import time
from typing import cast
import bpy
from mathutils import Euler, Matrix, Quaternion
from ... import utils

list_source_bones = []
list_root_bones = []

turn_rots = {
    "turn_left": (0, 90),
    "turn_left_slow": (0, 45),
    "turn_left_fast": (0, 360),
    "turn_right": (0, -90),
    "turn_right_slow": (0, -45),
    "turn_right_fast": (0, -360),
}

last_source_bone = ""
last_root_bone = ""

class NWO_OT_MovementDataToPedestal(bpy.types.Operator):
    bl_idname = "nwo.movement_data_transfer"
    bl_label = "Movement Data Transfer"
    bl_description = "Transfers the movement data of the source bone to the given root bone for the current or all animations. The type of movement transfered depends on the animation movement type"
    bl_options = {"UNDO", "REGISTER"}
    
    @classmethod
    def poll(cls, context):
        return utils.get_scene_props().animations
    
    def items_list_source_bones(self, context):
        return list_source_bones
    
    def items_list_root_bones(self, context):
        return list_root_bones
    
    source_bone: bpy.props.EnumProperty(
        name="Source Bone",
        options={'SKIP_SAVE'},
        description="The source bone that holds the movement to transfer. In the case of a legacy halo character animation this is usually the pelvis",
        items=items_list_source_bones,
    )
    
    root_bone: bpy.props.EnumProperty(
        name="Root Bone",
        options={'SKIP_SAVE'},
        description="The root bone that movement data should be transferred to. This will be the pedestal bone",
        items=items_list_root_bones,
    )
    
    all_animations: bpy.props.BoolProperty(
        name="All Animations",
        description="This operator will run on all animations instead of the currently active one"
    )
    
    include_no_movement: bpy.props.BoolProperty(
        name="Include All Base Animations",
        default=False,
        description="Transfers movement data for no movement base animations. These will be treated as if they have XY yaw movement by default; this will be overridden if the movement data type is set to manual"
    )
    
    movement_type: bpy.props.EnumProperty(
        name="Type",
        description="Determines what transforms are moved from the source bone to the root bone",
        items=[
            ('AUTOMATIC', "Automatic", "Movement type used accounts for the animation movement data type"),
            ('MANUAL', "Manual", "Define the exact type of transforms to move"),
            ('POSE', "Pose", "Uses the root bones current transform and updates keyframes such that the visual animation of the source bone is unchanged"),
            ('ANIMATION', "Animation", "Uses the root bones transform at either the start or end of the specified animation and updates keyframes such that the visual animation of the source bone is unchanged"),
            ('RESET', "Reset", "Resets the root bone to its rest position and updates keyframes such that the visual animation of the source bone is unchanged")
        ]
    )
    
    animation: bpy.props.StringProperty(
        name="Animation",
    )
    
    pose_type: bpy.props.EnumProperty(
        name="Pose Type",
        items=[
            ('CURRENT', 'Current Pose', "Use the current pose as the fixed location of the root bone"),
            ('ANIMATED', "Keyframed Poses", "Use each frame's pose"),
        ]
    )
    
    start_end: bpy.props.EnumProperty(
        name="Frame",
        items=[
            ('START', "Start", "Get the root position from start frame"),
            ('END', "End", "Get the root position from end frame"),
            ('ALL', "All", "Get the root position from every frame"),
        ]
    )
    
    use_x_loc: bpy.props.BoolProperty(
        name="Forward",
        default=True,
        description=""
    )
    use_y_loc: bpy.props.BoolProperty(
        name="Side to Side",
        default=True,
        description=""
    )
    use_z_loc: bpy.props.BoolProperty(
        name="Vertical",
        description=""
    )
    use_x_rot: bpy.props.BoolProperty(
        name="X Rotation",
        description=""
    )
    use_y_rot: bpy.props.BoolProperty(
        name="Y Rotation",
        description=""
    )
    use_z_rot: bpy.props.BoolProperty(
        name="Z Rotation",
        default=True,
        description=""
    )
    use_x_scale: bpy.props.BoolProperty(
        name="X Scale",
        description=""
    )
    use_y_scale: bpy.props.BoolProperty(
        name="Y Scale",
        description=""
    )
    use_z_scale: bpy.props.BoolProperty(
        name="Z Scale",
        description=""
    )
    relative_to_root_start: bpy.props.BoolProperty(
        name="Keep Root Start In Place",
        description="Frame 1 keeps the root bone's existing transform. Later frames receive the selected source transform deltas, and the source bone is counter-keyed so the visible animation stays the same",
        default=True,
    )
    
    relative: bpy.props.BoolProperty(
        name="Relative Source Transforms",
        description="Source positions are tested relative to the root bone (so we'll get the source bone transforms as if they had no parent), otherwise get their final transforms. Toggle this if you're getting weird results!",
        default=False,
    )
    
    def find_armature_ob(self, context):
        ob = None
        if context.object and context.object.type == "ARMATURE":
            ob = context.object
        else:
            ob = utils.get_rig(context)
            
        if ob is None:
            self.report({'WARNING'}, "No armature in scene")
            return {'CANCELLED'}
        
        
        global list_root_bones
        list_root_bones = []
        for bone in ob.pose.bones:
            if not bone.parent:
                list_root_bones.append((bone.name, bone.name, ""))
                
        global list_source_bones
        list_source_bones = []
        for bone in ob.pose.bones:
            if bone.parent:
                list_source_bones.append((bone.name, bone.name, ""))
                
        list_source_bones.sort(key=lambda x: "aim" in x[0]) # so aim pitch / aim_yaw don't get sorted first
                
        self.ob = ob
    
    def invoke(self, context, event):
        self.find_armature_ob(context)
        for bone in self.ob.pose.bones:
            if bone.name == last_source_bone:
                self.source_bone = last_source_bone
            elif bone.name == last_root_bone:
                self.root_bone = last_root_bone
                
        return context.window_manager.invoke_props_dialog(self, width=600)
    
    def draw(self, context):
        layout = cast(bpy.types.UILayout, self.layout)
        layout.use_property_split = True
        layout.prop(self, "source_bone")
        layout.prop(self, "root_bone")
        layout.prop(self, "all_animations")
        layout.prop(self, "relative")
        layout.prop(self, "relative_to_root_start")
        layout.prop(self, "movement_type", expand=True)
        if self.movement_type == 'MANUAL':
            layout.prop(self, "use_x_loc")
            layout.prop(self, "use_y_loc")
            layout.prop(self, "use_z_loc")
            layout.prop(self, "use_x_rot")
            layout.prop(self, "use_y_rot")
            layout.prop(self, "use_z_rot")
            layout.prop(self, "use_x_scale")
            layout.prop(self, "use_y_scale")
            layout.prop(self, "use_z_scale")
        elif self.movement_type == 'ANIMATION':
            layout.prop_search(self, "animation", utils.get_scene_props(), "animations", icon='ANIM')
            layout.prop(self, "start_end", expand=True)
        elif self.movement_type == 'AUTOMATIC':
            layout.prop(self, "include_no_movement")
        elif self.movement_type == 'POSE':
            layout.prop(self, "pose_type", expand=True)
        
    def has_movement_data(self, animation) -> bool:
        if animation.animation_type not in {'base', 'world'}:
            return False
        none_movement = animation.animation_movement_data == "none"
        if none_movement:
            if not self.include_no_movement:
                return False
            state = utils.space_partition(animation.name.replace(":", " "), True).lower()
            return state not in {'idle', 'takeoff'}
        
        return True
    
    def execute(self, context):
        global last_source_bone
        global last_root_bone
        last_source_bone = self.source_bone
        last_root_bone = self.root_bone
        
        scene_nwo = utils.get_scene_props()
        if not scene_nwo.animations:
            self.report({'WARNING'}, "No animations in scene")
            return {'CANCELLED'}
        
        if not self.all_animations and scene_nwo.active_animation_index == -1:
            self.report({'WARNING'}, "No active animation")
            return {'CANCELLED'}
        
        self.find_armature_ob(context)
        
        current_frame = context.scene.frame_current
        current_animation_index = scene_nwo.active_animation_index
        current_animation = scene_nwo.animations[scene_nwo.active_animation_index]
        current_pose = self.ob.data.pose_position
        current_object = context.object
        current_mode = context.mode
        
        settings_dict = {}
        root_matrix = None
        if self.movement_type == 'MANUAL':
            settings_dict["use_x_loc"] = self.use_x_loc
            settings_dict["use_y_loc"] = self.use_y_loc
            settings_dict["use_z_loc"] = self.use_z_loc
            settings_dict["use_x_rot"] = self.use_x_rot
            settings_dict["use_y_rot"] = self.use_y_rot
            settings_dict["use_z_rot"] = self.use_z_rot
            settings_dict["use_x_scale"] = self.use_x_scale
            settings_dict["use_y_scale"] = self.use_y_scale
            settings_dict["use_z_scale"] = self.use_z_scale
        elif self.movement_type == 'POSE':
            if self.pose_type == 'CURRENT':
                root_matrix = self.ob.pose.bones[self.root_bone].matrix.copy()
            else:
                root_matrix = get_bone_matrices(context, current_animation_index, current_animation, self.ob.pose.bones[self.root_bone])
        elif self.movement_type == 'RESET':
            root_matrix = Matrix.Identity(4)
        elif self.movement_type == 'ANIMATION':
            if not self.animation:
                self.report({'WARNING'}, "No animation specified")
                return {'CANCELLED'}
            for idx, animation in enumerate(scene_nwo.animations):
                if animation.name == self.animation:
                    scene_nwo.active_animation_index = idx
                    if self.start_end == 'START':
                        context.scene.frame_set(animation.frame_start)
                        root_matrix = self.ob.pose.bones[self.root_bone].matrix.copy()
                    elif self.start_end == 'END':
                        context.scene.frame_set(animation.frame_end)
                        root_matrix = self.ob.pose.bones[self.root_bone].matrix.copy()
                    else:
                        root_matrix = get_bone_matrices(context, idx, animation, self.ob.pose.bones[self.root_bone], current_animation.frame_end + 1 - current_animation.frame_start)
                    break
                
            scene_nwo.active_animation_index = current_animation_index
            context.scene.frame_set(current_frame)
        
        if not self.all_animations and not self.has_movement_data(current_animation) and not settings_dict and root_matrix is None:
            self.report({'WARNING'}, "Active animation has no movement data")
            return {'CANCELLED'}

        utils.set_object_mode(context)
        utils.set_active_object(self.ob)
        
        if self.all_animations:
            os.system("cls")
            start = time.perf_counter()
            scene_nwo_export = utils.get_export_props()
            if scene_nwo_export.show_output:
                bpy.ops.wm.console_toggle()  # toggle the console so users can see progress of export
                scene_nwo_export.show_output = False
                
            export_title = f"►►► MOVEMENT DATA TRANSFER ◄◄◄\n"
            print(export_title)
        
        source_bone_anim_matrices = {}
        source_bone = self.ob.pose.bones[self.source_bone]
        
        if not self.relative:
            if self.all_animations:
                print("Getting existing source bone poses")
                for i in range(len(scene_nwo.animations)):
                    animation = scene_nwo.animations[i]
                    print(f"--- {animation.name}")
                    source_bone_anim_matrices[i] = get_bone_matrices(context, i, animation, source_bone)
            else:
                print(f"Getting existing source bone poses for {current_animation.name}")
                source_bone_anim_matrices[current_animation_index] = get_bone_matrices(context, current_animation_index, current_animation, source_bone)
        
        self.ob.data.pose_position = 'REST'
        context.view_layer.update()
        root_rest_matrix = self.ob.pose.bones[self.root_bone].matrix.copy()
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        self.ob.data.edit_bones[self.source_bone].parent = None
        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
        self.ob.data.pose_position = 'POSE'
        context.view_layer.update()
        
        if self.movement_type == 'RESET':
            root_matrix = root_rest_matrix
            
        if self.relative:
            if self.all_animations:
                print("Getting existing source bone poses")
                for i in range(len(scene_nwo.animations)):
                    animation = scene_nwo.animations[i]
                    print(f"--- {animation.name}")
                    source_bone_anim_matrices[i] = get_bone_matrices(context, i, animation, source_bone)
            else:
                print(f"Getting existing source bone poses for {current_animation.name}")
                source_bone_anim_matrices[current_animation_index] = get_bone_matrices(context, current_animation_index, current_animation, source_bone)

        if self.all_animations:
            print("Calculating new root movement for all animations")
            for idx, animation in enumerate(scene_nwo.animations):
                if root_matrix is not None or settings_dict or self.has_movement_data(animation):
                    print(f"--- {animation.name}")
                    transfer_movement(context, animation, idx, self.ob, self.source_bone, self.root_bone, root_rest_matrix, root_matrix, settings_dict, source_bone_anim_matrices.get(idx), self.relative_to_root_start)
        else:
            print(f"Calculating new root movement for {current_animation.name}")
            transfer_movement(context, current_animation, current_animation_index, self.ob, self.source_bone, self.root_bone, root_rest_matrix, root_matrix, settings_dict, source_bone_anim_matrices.get(current_animation_index), self.relative_to_root_start)
            
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        self.ob.data.edit_bones[self.source_bone].parent = self.ob.data.edit_bones[self.root_bone]
        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
        
        print(f"\nSetting new source bone keyframes")
        for idx, source_bone_matrices in source_bone_anim_matrices.items():
            animation = scene_nwo.animations[idx]
            print(f"--- {animation.name}")
            fix_source_movement(context, animation, idx, self.ob, self.source_bone, source_bone_matrices)
        
        self.ob.data.pose_position = current_pose
        scene_nwo.active_animation_index = current_animation_index
        context.scene.frame_set(current_frame)
        context.view_layer.objects.active = current_object
        utils.restore_mode(current_mode)
        
        if self.all_animations:
            print("\n-----------------------------------------------------------------------")
            print(f"Completed in {utils.human_time(time.perf_counter() - start, True)}")
            print("-----------------------------------------------------------------------\n")
        
        return {'FINISHED'}
    
def get_bone_matrices(context: bpy.types.Context, animation_index: int, animation, bone: bpy.types.PoseBone, frame_count=None):
    scene_nwo = utils.get_scene_props()
    scene_nwo.active_animation_index = animation_index
    scene = context.scene
    bone_matrices = []
    for i in range(animation.frame_start, animation.frame_end + 1):
        scene.frame_set(i)
        bone_matrices.append(bone.matrix.copy())
        
    if frame_count is not None and len(bone_matrices) != frame_count:
        if frame_count > len(bone_matrices):
            return bone_matrices + [bone_matrices[-1]] * (frame_count - len(bone_matrices))
        else:
            return bone_matrices[:frame_count - 1]
        
    return bone_matrices
    
def fix_source_movement(context: bpy.types.Context, animation, animation_index: int, ob: bpy.types.Object, source_bone_name: str, source_bone_matrices: list[Matrix]):
    scene_nwo = utils.get_scene_props()
    scene_nwo.active_animation_index = animation_index
    source_bone = ob.pose.bones[source_bone_name]
    for idx, i in enumerate(range(animation.frame_start, animation.frame_end + 1)):
        context.scene.frame_set(i)
        source_bone.matrix = source_bone_matrices[idx]
        context.view_layer.update()
        source_bone.keyframe_insert(data_path='location', frame=i, options={'INSERTKEY_VISUAL'})
        source_bone.keyframe_insert(data_path='rotation_quaternion', frame=i, options={'INSERTKEY_VISUAL'})
        source_bone.keyframe_insert(data_path='scale', frame=i, options={'INSERTKEY_VISUAL'})
        

def _safe_scale_ratio(value: float, base: float) -> float:
    if abs(base) < 1e-8:
        return 1.0
    return value / base


def _movement_channel_masks(animation, custom_settings: dict, root_matrix: Matrix | list[Matrix] | None):
    """Returns (use_loc, use_rot, use_scale, special_turn, final_token)."""
    use_root_transform = root_matrix is not None
    special_turn = False
    final_token = ""

    if custom_settings:
        return (
            (
                custom_settings.get("use_x_loc", False),
                custom_settings.get("use_y_loc", False),
                custom_settings.get("use_z_loc", False),
            ),
            (
                custom_settings.get("use_x_rot", False),
                custom_settings.get("use_y_rot", False),
                custom_settings.get("use_z_rot", False),
            ),
            (
                custom_settings.get("use_x_scale", False),
                custom_settings.get("use_y_scale", False),
                custom_settings.get("use_z_scale", False),
            ),
            False,
            final_token,
        )

    if use_root_transform:
        return (True, True, True), (True, True, True), (True, True, True), False, final_token

    movement = animation.animation_movement_data
    if animation.animation_type == 'world':
        return (True, True, True), (True, True, True), (False, False, False), False, final_token

    if movement == "none":
        return (True, True, False), (False, False, True), (False, False, False), False, final_token

    horizontal = "xy" in movement
    vertical = "z" in movement
    yaw = "yaw" in movement
    full = movement == "full"

    if yaw:
        final_token = animation.name.rpartition(" ")[2].lower()
        if turn_rots.get(final_token) is not None:
            special_turn = True
            yaw = False

    use_loc = (horizontal or full, horizontal or full, vertical or full)
    use_rot = (full, full, yaw or full)
    use_scale = (False, False, False)
    return use_loc, use_rot, use_scale, special_turn, final_token


def _compose_selected_delta_matrix(
    source_matrix: Matrix,
    source_start_matrix: Matrix,
    root_start_matrix: Matrix,
    use_loc: tuple[bool, bool, bool],
    use_rot: tuple[bool, bool, bool],
    use_scale: tuple[bool, bool, bool],
) -> Matrix:
    """
    Builds a new root matrix where frame 1 is root_start_matrix, and later frames
    are driven by the source bone while preserving the frame-1 source->root offset.

    Important matrix order:
        root frame N = source frame N @ inverse(source frame 1) @ root frame 1

    This means the root starts exactly where it already was on frame 1, then follows
    the source/pelvis motion with the same initial offset, instead of applying a
    source delta in root-start space and drifting away from the source.

    Selected transform masks are then applied from that wanted follow matrix onto the
    root's frame-1 matrix, so disabled channels remain unchanged.
    """
    wanted_follow_matrix = source_matrix @ source_start_matrix.inverted_safe() @ root_start_matrix
    return _compose_selected_absolute_matrix(
        root_start_matrix,
        wanted_follow_matrix,
        use_loc,
        use_rot,
        use_scale,
    )


def _compose_selected_absolute_matrix(
    existing_matrix: Matrix,
    incoming_matrix: Matrix,
    use_loc: tuple[bool, bool, bool],
    use_rot: tuple[bool, bool, bool],
    use_scale: tuple[bool, bool, bool],
) -> Matrix:
    existing_loc, existing_rot, existing_scale = existing_matrix.decompose()
    incoming_loc, incoming_rot, incoming_scale = incoming_matrix.decompose()

    loc = existing_loc.copy()
    for axis, use_axis in enumerate(use_loc):
        if use_axis:
            loc[axis] = incoming_loc[axis]

    if all(use_rot):
        rot = incoming_rot
    elif any(use_rot):
        euler_order = existing_rot.to_euler().order
        existing_euler = existing_rot.to_euler(euler_order)
        incoming_euler = incoming_rot.to_euler(euler_order)
        for axis, use_axis in enumerate(use_rot):
            if use_axis:
                existing_euler[axis] = incoming_euler[axis]
        rot = existing_euler.to_quaternion()
    else:
        rot = existing_rot

    scale = existing_scale.copy()
    for axis, use_axis in enumerate(use_scale):
        if use_axis:
            scale[axis] = incoming_scale[axis]

    return Matrix.LocRotScale(loc, rot, scale)


def _insert_selected_root_keyframes(
    root_bone: bpy.types.PoseBone,
    frame: int,
    use_loc: tuple[bool, bool, bool],
    use_rot: tuple[bool, bool, bool],
    use_scale: tuple[bool, bool, bool],
):
    if any(use_loc):
        root_bone.keyframe_insert(data_path='location', frame=frame, options={'INSERTKEY_VISUAL'})
    if any(use_rot):
        root_bone.keyframe_insert(data_path='rotation_quaternion', frame=frame, options={'INSERTKEY_VISUAL'})
    if any(use_scale):
        root_bone.keyframe_insert(data_path='scale', frame=frame, options={'INSERTKEY_VISUAL'})


def transfer_movement(
    context: bpy.types.Context,
    animation,
    animation_index: int,
    ob: bpy.types.Object,
    source_bone_name: str,
    root_bone_name: str,
    root_rest_matrix: Matrix,
    root_matrix: Matrix | list[Matrix] | None,
    custom_settings: dict = {},
    source_bone_matrices: list[Matrix] | None = None,
    relative_to_root_start: bool = True,
):
    scene_nwo = utils.get_scene_props()
    scene_nwo.active_animation_index = animation_index
    scene = context.scene

    root_bone = ob.pose.bones[root_bone_name]
    root_bone: bpy.types.PoseBone

    use_loc, use_rot, use_scale, special_turn, final_token = _movement_channel_masks(animation, custom_settings, root_matrix)
    use_root_transform = root_matrix is not None

    # New path: root frame 1 remains where it already is. Later frames receive the
    # selected source deltas. The source bone is restored/counter-keyed later by
    # fix_source_movement(), so the visible skeleton animation stays the same.
    if relative_to_root_start and source_bone_matrices:
        scene.frame_set(animation.frame_start)
        context.view_layer.update()
        root_start_matrix = root_bone.matrix.copy()
        source_start_matrix = source_bone_matrices[0].copy()

        for idx, frame in enumerate(range(animation.frame_start, animation.frame_end + 1)):
            scene.frame_set(frame)
            source_matrix = source_bone_matrices[min(idx, len(source_bone_matrices) - 1)]
            root_bone.matrix = _compose_selected_delta_matrix(
                source_matrix,
                source_start_matrix,
                root_start_matrix,
                use_loc,
                use_rot,
                use_scale,
            )
            context.view_layer.update()
            _insert_selected_root_keyframes(root_bone, frame, use_loc, use_rot, use_scale)
        return

    # Original absolute/special-turn behaviour below.
    if not custom_settings and not use_root_transform and special_turn:
        root_rest_rot = root_rest_matrix.to_euler()
        turn_start, turn_end = turn_rots.get(final_token)
        scene.frame_set(animation.frame_start)
        euler_rot = Euler((0, 0, math.radians(turn_start)))
        euler_rot.rotate(root_rest_rot)
        loc, _, sca = root_bone.matrix.decompose()
        root_bone.matrix = Matrix.LocRotScale(loc, euler_rot, sca)
        root_bone.keyframe_insert(data_path='rotation_quaternion', frame=animation.frame_start, options={'INSERTKEY_VISUAL'})
        scene.frame_set(animation.frame_end)
        euler_rot = Euler((0, 0, math.radians(turn_end)))
        euler_rot.rotate(root_rest_rot)
        loc, _, sca = root_bone.matrix.decompose()
        root_bone.matrix = Matrix.LocRotScale(loc, euler_rot, sca)
        root_bone.keyframe_insert(data_path='rotation_quaternion', frame=animation.frame_end, options={'INSERTKEY_VISUAL'})

        for i in range(animation.frame_start, animation.frame_end + 1):
            scene.frame_set(i)
            root_bone.keyframe_insert(data_path='rotation_quaternion', frame=i, options={'INSERTKEY_VISUAL'})
        return

    if use_root_transform:
        if isinstance(root_matrix, Matrix):
            for frame in range(animation.frame_start, animation.frame_end + 1):
                scene.frame_set(frame)
                root_bone.matrix = _compose_selected_absolute_matrix(root_bone.matrix.copy(), root_matrix, use_loc, use_rot, use_scale)
                context.view_layer.update()
                _insert_selected_root_keyframes(root_bone, frame, use_loc, use_rot, use_scale)
        else:
            for idx, frame in enumerate(range(animation.frame_start, animation.frame_end + 1)):
                scene.frame_set(frame)
                root_bone.matrix = _compose_selected_absolute_matrix(root_bone.matrix.copy(), root_matrix[idx], use_loc, use_rot, use_scale)
                context.view_layer.update()
                _insert_selected_root_keyframes(root_bone, frame, use_loc, use_rot, use_scale)
        return

    con_rot = None
    con_loc = None
    con_limit_rot = None
    con_limit_loc = None

    if custom_settings:
        con_rot = root_bone.constraints.new(type='COPY_ROTATION')
        con_rot.target = ob
        con_rot.subtarget = source_bone_name
        con_rot.target_space = 'LOCAL_OWNER_ORIENT'
        con_rot.owner_space = 'LOCAL'

        con_loc = root_bone.constraints.new(type='COPY_LOCATION')
        con_loc.target = ob
        con_loc.subtarget = source_bone_name
        con_loc.target_space = 'LOCAL_OWNER_ORIENT'
        con_loc.owner_space = 'LOCAL'

        con_limit_rot = root_bone.constraints.new(type='LIMIT_ROTATION')
        con_limit_rot.use_limit_x = not custom_settings.get("use_x_rot")
        con_limit_rot.use_limit_y = not custom_settings.get("use_y_rot")
        con_limit_rot.use_limit_z = not custom_settings.get("use_z_rot")
        con_limit_rot.owner_space = 'LOCAL'

        con_limit_loc = root_bone.constraints.new(type='LIMIT_LOCATION')
        con_limit_loc.use_min_x = not custom_settings.get("use_x_loc")
        con_limit_loc.use_max_x = not custom_settings.get("use_x_loc")
        con_limit_loc.use_min_y = not custom_settings.get("use_y_loc")
        con_limit_loc.use_max_y = not custom_settings.get("use_y_loc")
        con_limit_loc.use_min_z = not custom_settings.get("use_z_loc")
        con_limit_loc.use_max_z = not custom_settings.get("use_z_loc")
        con_limit_loc.owner_space = 'LOCAL'
    else:
        if any(use_rot):
            con_rot = root_bone.constraints.new(type='COPY_ROTATION')
            con_rot.target = ob
            con_rot.subtarget = source_bone_name
            con_rot.target_space = 'LOCAL_OWNER_ORIENT'
            con_rot.owner_space = 'LOCAL'

            if use_rot != (True, True, True):
                con_limit_rot = root_bone.constraints.new(type='LIMIT_ROTATION')
                con_limit_rot.use_limit_x = not use_rot[0]
                con_limit_rot.use_limit_y = not use_rot[1]
                con_limit_rot.use_limit_z = not use_rot[2]
                con_limit_rot.owner_space = 'LOCAL'

        if any(use_loc):
            con_loc = root_bone.constraints.new(type='COPY_LOCATION')
            con_loc.target = ob
            con_loc.subtarget = source_bone_name
            con_loc.target_space = 'LOCAL_OWNER_ORIENT'
            con_loc.owner_space = 'LOCAL'

            if use_loc != (True, True, True):
                con_limit_loc = root_bone.constraints.new(type='LIMIT_LOCATION')
                con_limit_loc.use_min_x = not use_loc[0]
                con_limit_loc.use_max_x = not use_loc[0]
                con_limit_loc.use_min_y = not use_loc[1]
                con_limit_loc.use_max_y = not use_loc[1]
                con_limit_loc.use_min_z = not use_loc[2]
                con_limit_loc.use_max_z = not use_loc[2]
                con_limit_loc.owner_space = 'LOCAL'

    for frame in range(animation.frame_start, animation.frame_end + 1):
        scene.frame_set(frame)
        context.view_layer.update()
        _insert_selected_root_keyframes(root_bone, frame, use_loc, use_rot, use_scale)

    if con_loc is not None:
        root_bone.constraints.remove(con_loc)
        if con_limit_loc is not None:
            root_bone.constraints.remove(con_limit_loc)
    if con_rot is not None:
        root_bone.constraints.remove(con_rot)
        if con_limit_rot is not None:
            root_bone.constraints.remove(con_limit_rot)

class FCurveTransfer:
    source_fcurve: bpy.types.FCurve
    target_fcurve: bpy.types.FCurve
    
    def __init__(self, action: bpy.types.Action, source_bone: str, target_bone: str, source_channel: str, target_channel: str, slot_name: str) -> None:
        source_channel_array_index, source_channel_name = source_channel.split(':')
        target_channel_array_index, target_channel_name = target_channel.split(':')
        self.action = action
        self.fcurves = utils.get_fcurves(self.action, slot_name)
        self.source_bone = source_bone
        self.target_bone = target_bone
        self.source_channel = source_channel_name
        self.source_channel_index = int(source_channel_array_index)
        self.target_channel_index = int(target_channel_array_index)
        self.target_channel = target_channel_name
        self.source_fcurve = None
        self.target_fcurve = None
    
    def get_fcurves(self):
        source_data_path = f'pose.bones["{self.source_bone}"].{self.source_channel}'
        target_data_path = f'pose.bones["{self.target_bone}"].{self.target_channel}'
        for fc in self.fcurves:
            if fc.data_path == source_data_path and fc.array_index == self.source_channel_index:
                self.source_fcurve = fc
            elif fc.data_path == target_data_path and fc.array_index == self.target_channel_index:
                self.target_fcurve = fc
                
        if not self.source_fcurve:
            return
        
        if not self.target_fcurve:
            self.target_fcurve = self.fcurves.new(data_path=f'pose.bones["{self.target_bone}"].{self.target_channel}', index=self.target_channel_index)
            
    def transfer_data(self):
        source_coordinates = []
        for kfp in self.source_fcurve.keyframe_points:
            source_coordinates.append(kfp.co_ui[1])
            
        target_kfps = self.target_fcurve.keyframe_points
        for index, coordinates in enumerate(source_coordinates):
            target_kfps.insert(index, coordinates, options={'REPLACE'})
            
    def remove_source_fcurve(self):
        self.fcurves.remove(self.source_fcurve)
            
class NWO_OT_FcurveTransfer(bpy.types.Operator):
    bl_idname = "nwo.fcurve_transfer"
    bl_label = "Motion Transfer"
    bl_description = "Transfers animation keyframes from one channel to another. For example transferring all motion on the Z location channel of bone A to the X location channel of bone B"
    bl_options = {"UNDO", "REGISTER"}
    
    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'ARMATURE'
    
    all_animations: bpy.props.BoolProperty(
        name="All Animations",
        description="Run this operator on all actions in the blend file. Disable to only run on the active animation",
    )
    
    remove_source_data: bpy.props.BoolProperty(
        name="Remove Source Channel",
        description="Removes all data from the source channel after transfer",
        default=True,
    )
    
    def list_bones(self, context):
        items = []
        arm = context.object
        for bone in arm.pose.bones:
            items.append((bone.name, bone.name, ""))
            
        return items
            
    def list_channels(self, context):
        items = [
            ("0:location", "X Location", ""),
            ("1:location", "Y Location", ""),
            ("2:location", "Z Location", ""),
            ("0:rotation_euler", "X Euler", ""),
            ("1:rotation_euler", "Y Euler", ""),
            ("2:rotation_euler", "Z Euler", ""),
            ("0:rotation_quaternion", "W Quaternion", ""),
            ("1:rotation_quaternion", "X Quaternion", ""),
            ("2:rotation_quaternion", "Y Quaternion", ""),
            ("3:rotation_quaternion", "Z Quaternion", ""),
            ("0:scale", "X Scale", ""),
            ("1:scale", "Y Scale", ""),
            ("2:scale", "Z Scale", ""),
        ]
        
        return items
    
    source_bone: bpy.props.EnumProperty(
        name="Source Bone",
        description="The bone to transfer data from",
        items=list_bones,
    )
    
    source_channel: bpy.props.EnumProperty(
        name="Source Channel",
        description="The name of the channel containing data. This data must exist",
        items=list_channels,
    )
    
    target_bone: bpy.props.EnumProperty(
        name="Target Bone",
        description="The bone to transfer data to",
        items=list_bones,
    )
    
    target_channel: bpy.props.EnumProperty(
        name="Target Channel",
        description="The name of the channel to receive data. This can be empty",
        items=list_channels,
    )

    def execute(self, context):
        scene_nwo = utils.get_scene_props()
        active_animation_index = scene_nwo.active_animation_index
        animation = scene_nwo.animations[active_animation_index]
        actions = []
        if self.all_animations:
            actions = set(bpy.data.actions)
        else:
            actions = {track.action for track in animation.action_tracks}
            
        armature = context.object
        if not armature.animation_data:
            armature.animation_data_create()
            
        slot_name = armature.animation_data.last_slot_identifier
            
        utils.clear_animation(animation)
        for action in actions:
            fcurve_transfer = FCurveTransfer(action, self.source_bone, self.target_bone, self.source_channel, self.target_channel, slot_name)
            fcurve_transfer.get_fcurves()
            if fcurve_transfer.source_fcurve:
                fcurve_transfer.transfer_data()
                if self.remove_source_data:
                    fcurve_transfer.remove_source_fcurve()
            else:
                self.report({'WARNING'}, f"Failed to find source fcurve on action {action.name}")
        
        scene_nwo.active_animation_index = active_animation_index
        return {"FINISHED"}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, "source_bone")
        layout.prop(self, "source_channel")
        layout.separator()
        layout.prop(self, "target_bone")
        layout.prop(self, "target_channel")
        layout.separator()
        layout.prop(self, "all_animations")
        layout.prop(self, "remove_source_data")
