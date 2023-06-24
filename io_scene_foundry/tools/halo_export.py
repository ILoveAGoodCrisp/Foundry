# ##### BEGIN MIT LICENSE BLOCK #####
#
# MIT License
#
# Copyright (c) 2023 Crisp
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

import os
import bpy


def export(export_op):
    export_op("INVOKE_DEFAULT")
    return {"FINISHED"}

def export_quick(
    export_op,
    report,
    export_gr2_files,
    export_all_bsps,
    export_all_perms,
    import_to_game,
    import_draft,
    lightmap_structure,
    lightmap_quality_h4,
    lightmap_region,
    lightmap_quality,
    lightmap_specific_bsp,
    lightmap_all_bsps,
    export_animations,
    export_skeleton,
    export_render,
    export_collision,
    export_physics,
    export_markers,
    export_structure,
    export_design,
):
    export_op(
        export_gr2_files=export_gr2_files,
        export_all_bsps=export_all_bsps,
        export_all_perms=export_all_perms,
        import_to_game=import_to_game,
        import_draft=import_draft,
        lightmap_structure=lightmap_structure,
        lightmap_quality_h4=lightmap_quality_h4,
        lightmap_region=lightmap_region,
        lightmap_quality=lightmap_quality,
        lightmap_specific_bsp=lightmap_specific_bsp,
        lightmap_all_bsps=lightmap_all_bsps,
        export_animations=export_animations,
        export_skeleton=export_skeleton,
        export_render=export_render,
        export_collision=export_collision,
        export_physics=export_physics,
        export_markers=export_markers,
        export_structure=export_structure,
        export_design=export_design,
        quick_export=True,
    )
    temp_report_path = os.path.join(bpy.app.tempdir, "foundry_export_report.txt")
    if os.path.exists(temp_report_path):
        with open(temp_report_path, "r") as temp_file:
            lines = temp_file.readlines()
            report_text = lines[0]
            report_type = lines[1]

        os.remove(temp_report_path)
        report({report_type}, report_text)

    else:
        report({"INFO"}, "Quick Export Complete")

    return {"FINISHED"}
