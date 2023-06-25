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

from ..utils.nwo_utils import (
    get_tags_path,
    not_bungie_game,
    run_tool_sidecar,
)


def import_sidecar(
    sidecar_type,
    sidecar_path,
    asset_path,
    asset_name,
    import_check,
    import_force,
    import_verbose,
    import_draft,
    import_seam_debug,
    import_skip_instances,
    import_decompose_instances,
    import_surpress_errors,
):
    print("\n\nBuilding Tags")
    print(
        "-------------------------------------------------------------------------\n"
    )
    # time.sleep(0.5)
    failed = run_tool_sidecar(
        [
            "import",
            sidecar_path,
            *get_import_flags(
                import_check,
                import_force,
                import_verbose,
                import_draft,
                import_seam_debug,
                import_skip_instances,
                import_decompose_instances,
                import_surpress_errors,
            ),
        ],
        asset_path
    )
    if sidecar_type == "FP ANIMATION":
        cull_unused_tags(sidecar_path.rpartition('\\')[0], asset_name)

    return failed


def cull_unused_tags(asset_path, asset_name):
    try:
        tag_path = os.path.join(get_tags_path() + asset_path, asset_name)
        scenery = f"{tag_path}.scenery"
        model = f"{tag_path}.model"
        render_model = f"{tag_path}.render_model"
        # remove the unused tags
        if os.path.exists(scenery):
            os.remove(scenery)
        if os.path.exists(model):
            os.remove(model)
        if os.path.exists(render_model):
            os.remove(render_model)

    except:
        print("Failed to remove unused tags")


def get_import_flags(
    flag_import_check,
    flag_import_force,
    flag_import_verbose,
    flag_import_draft,
    flag_import_seam_debug,
    flag_import_skip_instances,
    flag_import_decompose_instances,
    flag_import_surpress_errors,
):
    flags = []
    if flag_import_force:
        flags.append("force")
    if flag_import_skip_instances:
        flags.append("skip_instances")
    if not_bungie_game():
        flags.append("preserve_namespaces")
    else:
        if flag_import_check:
            flags.append("check")
        if flag_import_verbose:
            flags.append("verbose")
        if flag_import_draft:
            flags.append("draft")
        if flag_import_seam_debug:
            flags.append("seam_debug")
        if flag_import_decompose_instances:
            flags.append("decompose_instances")
        if flag_import_surpress_errors:
            flags.append("surpress_errors_to_vrml")

    return flags
