

import bpy


def set_export(context, report, setting):
    if setting == "none":
        b_var = False
    else:
        b_var = True
    # get scene armature
    for ob in context.view_layer.objects:
        if ob.type == "ARMATURE" and not ob.name.startswith("+"):
            model_armature = ob
            break

    if setting == "active":
        for action in bpy.data.actions:
            action.nwo.export_this = False
        model_armature.animation_data.action.nwo.export_this = True
        report(
            {"INFO"},
            f"Enabled export only for {model_armature.animation_data.action.name}",
        )
    else:
        for action in bpy.data.actions:
            action.nwo.export_this = b_var
            if b_var:
                report({"INFO"}, "Enabled export for all animations")
            else:
                report({"INFO"}, "Disabled export for all animations")

    context.area

    return {"FINISHED"}
