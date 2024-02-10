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

from io_scene_foundry.utils.nwo_utils import all_prefixes


def CopyProps(report, template, targets):
    # Apply prefixes from template object
    template_name = template.name
    template_prefix = ""
    for prefix in all_prefixes:
        if template_name.startswith(prefix):
            template_prefix = prefix
    for ob in targets:
        if ob != template:
            target_name = ob.name
            for prefix in all_prefixes:
                target_name = target_name.replace(prefix, "")

            target_name = template_prefix + target_name
            ob.name = target_name

    # Apply halo properties to target objects
    template_props = template.nwo
    target_count = 0
    for ob in targets:
        if ob != template:
            target_count += 1
            target_props = ob.nwo

            target_props.object_type_items_all = template_props.object_type_items_all

    report(
        {"INFO"},
        f"Copied properties from {template_name} to {target_count} target objects",
    )
    return {"FINISHED"}
