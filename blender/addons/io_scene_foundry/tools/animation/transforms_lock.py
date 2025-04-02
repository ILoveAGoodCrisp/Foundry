import bpy
from mathutils import Matrix

class NWO_OT_LockChildBoneTransforms(bpy.types.Operator):
    bl_idname = "nwo.lock_child_bone_transforms"
    bl_label = "Lock Child Bone Transforms"
    bl_description = "Locks the visual transforms of the children of the currently active pose bone"
    bl_options = {'REGISTER'}
    
    _timer = None

    @classmethod
    def poll(cls, context):
        return context.mode == 'POSE' and context.active_pose_bone

    def invoke(self, context, event):
        if context.scene.nwo.bone_transform_lock_active:
            context.scene.nwo.bone_transform_lock_active = False
            return {'FINISHED'}
        self.frame = context.scene.frame_current
        self.bone = context.active_pose_bone
        self.child_bones = {cb: cb.matrix.copy() for cb in self.bone.children}
        
        if not self.child_bones:
            self.report({'WARNING'}, f"Active bone [{self.bone.name}] has no children")
            context.scene.nwo.bone_transform_lock_active = False
            return {'FINISHED'}
        
        context.scene.nwo.bone_transform_lock_active = True
        self._timer = context.window_manager.event_timer_add(0.1, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        nwo = context.scene.nwo
        if not nwo.bone_transform_lock_active or context.active_pose_bone != self.bone:
            nwo.bone_transform_lock_active = False
            return {"CANCELLED"}
        
        if event.type == 'TIMER':
            for bone, matrix in self.child_bones.items():
                if nwo.lock_bone_loc and nwo.lock_bone_rot and nwo.lock_bone_sca:
                    bone.matrix = matrix
                else:
                    locked_loc, locked_rot, locked_sca = matrix.decompose()
                    loc, rot, sca = bone.matrix.decompose()
                    bone.matrix = Matrix.LocRotScale(locked_loc if nwo.lock_bone_loc else loc, locked_rot if nwo.lock_bone_rot else rot, locked_sca if nwo.lock_bone_sca else sca)

        return {'PASS_THROUGH'}
    
    def cancel(self, context):
        context.window_manager.event_timer_remove(self._timer)
        context.scene.nwo.bone_transform_lock_active = False
