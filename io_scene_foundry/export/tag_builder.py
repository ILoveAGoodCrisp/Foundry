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
    get_data_path,
    get_tags_path,
    is_corinth,
    print_warning,
    run_tool,
    run_tool_sidecar,
    copy_file,
)

def set_template(scene_nwo, tags_dir, new_tag_path_name, tag_type):
    if tag_type == 'model' or getattr(scene_nwo, 'output_' + tag_type):
        relative_path = getattr(scene_nwo, 'template_' + tag_type)
        expected_asset_path = new_tag_path_name + tag_type
        if relative_path and not os.path.exists(expected_asset_path):
            full_path = tags_dir + relative_path
            if os.path.exists(full_path):
                copy_file(full_path, expected_asset_path)
                print(f'- Loaded {tag_type} tag template')
            else:
                print_warning(f'Tried to set up template for {tag_type} tag but given template tag [{full_path}] does not exist')

def setup_template_tags(scene_nwo, tags_dir, tag_path, is_corinth):
    new_tag_path_name = tag_path + '.'
    set_template(scene_nwo, tags_dir, new_tag_path_name, 'model')
    set_template(scene_nwo, tags_dir, new_tag_path_name, 'biped')
    set_template(scene_nwo, tags_dir, new_tag_path_name, 'crate')
    set_template(scene_nwo, tags_dir, new_tag_path_name, 'creature')
    set_template(scene_nwo, tags_dir, new_tag_path_name, 'device_control')
    if is_corinth:
        set_template(scene_nwo, tags_dir, new_tag_path_name, 'device_dispenser')
    set_template(scene_nwo, tags_dir, new_tag_path_name, 'device_machine')
    set_template(scene_nwo, tags_dir, new_tag_path_name, 'device_terminal')
    set_template(scene_nwo, tags_dir, new_tag_path_name, 'effect_scenery')
    set_template(scene_nwo, tags_dir, new_tag_path_name, 'equipment')
    set_template(scene_nwo, tags_dir, new_tag_path_name, 'giant')
    set_template(scene_nwo, tags_dir, new_tag_path_name, 'scenery')
    set_template(scene_nwo, tags_dir, new_tag_path_name, 'vehicle')
    set_template(scene_nwo, tags_dir, new_tag_path_name, 'weapon')


def build_tags(asset_type, sidecar_path, asset_path, asset_name, scene_nwo_export, scene_nwo, model_lighting, selected_bsps):
    print("\n\nBuilding Tags")
    print("-----------------------------------------------------------------------\n")
    tags_dir = get_tags_path()
    data_dir = get_data_path()
    tag_folder_path = asset_path.replace(data_dir, tags_dir)
    tag_path = os.path.join(tag_folder_path, asset_name)
    if asset_type == 'MODEL':
        setup_template_tags(scene_nwo, tags_dir, tag_path, is_corinth())
    faux_process = None
    if model_lighting:
        faux_process = run_tool(
            [
                "import",
                sidecar_path.replace(
                    f"{asset_name}.sidecar.xml", f"{asset_name}_lighting.sidecar.xml"
                ),
                "preserve_namespaces",
                "force",
            ],
            True,
            True,
        )
    failed = run_tool_sidecar(
        [
            "import",
            sidecar_path,
            *get_import_flags(
                asset_name,
                selected_bsps,
                scene_nwo_export.import_force,
                scene_nwo_export.import_draft,
                scene_nwo_export.import_seam_debug,
                scene_nwo_export.import_skip_instances,
                scene_nwo_export.import_decompose_instances,
                scene_nwo_export.import_suppress_errors,
                scene_nwo_export.import_lighting,
                scene_nwo_export.import_meta_only,
                scene_nwo_export.import_disable_hulls,
                scene_nwo_export.import_disable_collision,
                scene_nwo_export.import_no_pca,
                scene_nwo_export.import_force_animations,
            ),
        ],
        asset_path,
    )
    if asset_type == "FP ANIMATION":
        cull_unused_tags(sidecar_path.rpartition("\\")[0], asset_name)

    if faux_process is not None:
        faux_process.wait()
        scenario = f"{tag_path}.scenario"
        bsp = f"{tag_path}.scenario_structure_bsp"
        seams = f"{tag_path}.structure_seams"
        try:
            if os.path.exists(scenario):
                os.remove(scenario)
            if os.path.exists(bsp):
                os.remove(bsp)
            if os.path.exists(seams):
                os.remove(seams)
        except:
            print_warning("Failed to remove unused lightmap tags")

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
    asset_name,
    selected_bsps,
    flag_import_force,
    flag_import_draft,
    flag_import_seam_debug,
    flag_import_skip_instances,
    flag_import_decompose_instances,
    flag_import_suppress_errors,
    import_lighting,
    import_meta_only,
    import_disable_hulls,
    import_disable_collision,
    import_no_pca,
    import_force_animations,
):
    flags = []
    if flag_import_force:
        flags.append("force")
    if flag_import_skip_instances:
        flags.append("skip_instances")
    if is_corinth():
        flags.append("preserve_namespaces")
        if import_lighting:
            flags.append("lighting")
        if import_meta_only:
            flags.append("meta_only")
        if import_disable_hulls:
            flags.append("disable_hulls")
        if import_disable_collision:
            flags.append("no_collision")
        if import_no_pca:
            flags.append("no_pca")
        if import_force_animations:
            flags.append("force_errors")
    else:
        if flag_import_draft:
            flags.append("draft")
        if flag_import_seam_debug:
            flags.append("seam_debug")
        if flag_import_decompose_instances:
            flags.append("decompose_instances")
        if flag_import_suppress_errors:
            flags.append("suppress_errors_to_vrml")

    if selected_bsps:
        for bsp in selected_bsps:
            flags.append(f"{asset_name}_{bsp}")

    return flags
