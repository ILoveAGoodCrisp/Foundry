import bpy

class LockChildBoneTransforms(bpy.types.Operator):
    bl_options = {'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return context.mode == 'POSE' and context.selected_pose_bones
    
    def main(self, context: bpy.types.Context):
        self.bone_constraints = {}
        bone_selection = set(context.selected_pose_bones)
        for bone in bone_selection:
            for child_bone in bone.children:
                if child_bone in bone_selection:
                    continue
                ob = bpy.data.objects.new("temp_bone_constraint_object", object_data=None)
                ob.matrix_world = context.object.matrix_world @ child_bone.matrix
                con = child_bone.constraints.new(type='COPY_TRANSFORMS')
                con.target = ob
                self.bone_constraints[child_bone] = con
        
        context.window_manager.modal_handler_add(self)
    
    def modal(self, context, event):
        if event.type in {'LEFTMOUSE', 'RET'}:
            for bone, con in self.bone_constraints.items():
                ob = con.target
                with bpy.context.temp_override(active_pose_bone=bone):
                    bpy.ops.constraint.apply(constraint=con.name, owner='BONE')
                bpy.data.objects.remove(ob)
            return {'FINISHED'}
        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            for bone, con in self.bone_constraints.items():
                bpy.data.objects.remove(con.target)
                bone.constraints.remove(con)
            return {'CANCELLED'}

        return {'PASS_THROUGH'}
    
    def cancel(self, context):
        for bone, con in self.bone_constraints.items():
            bpy.data.objects.remove(con.target)
            bone.constraints.remove(con)

class NWO_OT_LockChildBoneLocation(LockChildBoneTransforms):
    bl_idname = "nwo.translate_bone_without_children"
    bl_label = "Translate Without Children"
    bl_description = "Translates the current pose bone selection without affecting bone children"

    def execute(self, context):
        self.main(context)
        bpy.ops.transform.translate('INVOKE_DEFAULT')
        return {'RUNNING_MODAL'}
    
class NWO_OT_LockChildBoneRotation(LockChildBoneTransforms):
    bl_idname = "nwo.rotate_bone_without_children"
    bl_label = "Rotate Without Children"
    bl_description = "Rotates the current pose bone selection without affecting bone children"

    def execute(self, context):
        self.main(context)
        bpy.ops.transform.rotate('INVOKE_DEFAULT')
        return {'RUNNING_MODAL'}
    
class NWO_OT_LockChildBoneScale(LockChildBoneTransforms):
    bl_idname = "nwo.resize_bone_without_children"
    bl_label = "Resize Without Children"
    bl_description = "Scales the current pose bone selection without affecting bone children"

    def execute(self, context):
        self.main(context)
        bpy.ops.transform.resize('INVOKE_DEFAULT')
        return {'RUNNING_MODAL'}
    
