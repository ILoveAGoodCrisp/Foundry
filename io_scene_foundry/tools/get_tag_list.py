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

import bpy
import os
from io_scene_foundry.utils.nwo_utils import get_ek_path, get_tags_path, not_bungie_game, os_sep_partition

global_items = []

class NWO_GetTagsList(bpy.types.Operator):
    bl_idname = "nwo.get_tags_list"
    bl_label = "Get Tags"
    bl_property = "tag_list"
    bl_description = "Get a list of valid tags"
    bl_options = {"REGISTER", "UNDO"}

    def tag_list_items(self, context):
        global global_items
        if global_items:
            return global_items
        tags_dir = get_tags_path()
        ext_list = extensions_from_type(self.list_type)
        tags = walk_tags_dir(tags_dir, ext_list)
        for t in tags:
            global_items.append((t, os_sep_partition(t, True), ""))

        return global_items

    tag_list: bpy.props.EnumProperty(
        name="Tags",
        items=tag_list_items,
    )

    # comma delimited
    list_type: bpy.props.StringProperty()
    
    def execute(self, context):
        nwo = context.object.nwo
        nwo.marker_game_instance_tag_name_ui = self.tag_list
        return {'FINISHED'}
    
    def invoke(self, context, event):
        wm = context.window_manager
        wm.invoke_search_popup(self)
        return {"FINISHED"}
    
def extensions_from_type(list_type):
    match list_type:
        case "game_instance":
            return (".crate", ".scenery", ".effect_scenery", ".device_control", ".device_machine", ".device_terminal",
                        ".device_dispenser", ".biped", ".creature", ".giant", ".vehicle", ".weapon", ".equipment",
                        ".prefab", ".light", ".cheap_light", ".leaf", ".decorator_set")
        case _:
            return (".scenery")
        
def walk_tags_dir(tags_dir, ext_list):
    tags_set = set()
    fav_tags = set()
    # Display the favorite tags first, so grab these
    if not_bungie_game():
        fav_tags_file = os.path.join(get_ek_path(), "FavoriteTags.txt")
        if os.path.exists(fav_tags_file):
            with open(fav_tags_file, "r") as file:
                for line in file:
                    l = line.strip("\n ")
                    if l and not l.startswith(";") and l.endswith(ext_list):
                        fav_tags.add(l)

    for root, dirs, files in os.walk(tags_dir):
        for file in files:
            if file.endswith(ext_list):
                relative_path = os.path.join(root, file).replace(tags_dir, "")
                if relative_path not in fav_tags:
                    tags_set.add(relative_path)

    tags_sorted = sorted(tags_set, key=lambda x: os_sep_partition(x, True))
    tags = [t for t in fav_tags]
    tags.extend(tags_sorted)
    return tags