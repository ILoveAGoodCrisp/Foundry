

def export(export_op):
    export_op("INVOKE_DEFAULT")
    return {"FINISHED"}

def export_quick(export_op):
    export_op()
    return {"FINISHED"}
