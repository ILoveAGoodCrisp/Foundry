# ##### BEGIN MIT LICENSE BLOCK #####
#
# MIT License
#
# Copyright (c) 2024 Crisp
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

def create_collections(context, ops, data, coll_type, coll_name, move_objects):
    selected_collection = context.collection
    if coll_name.strip() == "":
        coll_name = "default"
    coll_name = coll_name.lower()[:128]
    # iterates through the selected objects and applies the chosen collection type
    full_name = get_full_name(coll_type, coll_name)
    collection_index = get_coll_if_exists(data, full_name)
    if move_objects:
        if collection_index == -1:
            ops.object.move_to_collection(
                collection_index=0, is_new=True, new_collection_name=full_name
            )
        else:
            for ob in context.selected_objects:
                for coll in ob.users_collection:
                    coll.objects.unlink(ob)
                data.collections[collection_index].objects.link(ob)

        new_collection = bpy.data.collections[full_name]
    else:
        new_collection = bpy.data.collections.new(full_name)
        if selected_collection:
            selected_collection.children.link(new_collection)
        else:
            context.scene.collection.children.link(new_collection)

    new_collection.nwo.type = coll_type
    if coll_type == 'region':
        regions = context.scene.nwo.regions_table
        new_collection.nwo.region = coll_name
        if coll_name not in [r.name for r in regions]:
            new_region = regions.add()
            new_region.old = coll_name
            new_region.name = coll_name


    elif coll_type == 'permutation':
        permutations = context.scene.nwo.permutations_table
        new_collection.nwo.permutation = coll_name
        if coll_name not in [p.name for p in permutations]:
            new_perm = permutations.add()
            new_perm.old = coll_name
            new_perm.name = coll_name

    return {"FINISHED"}


def get_coll_if_exists(data, full_name):
    collection_index = -1
    if len(data.collections) > 0:
        all_collections = data.collections
        for index, c in enumerate(all_collections):
            if c.name.replace(" ", "") == full_name.replace(" ", ""):
                collection_index = index
                break

    return collection_index


def get_full_name(coll_type, coll_name):
    prefix = ""
    asset_type = bpy.context.scene.nwo.asset_type
    match coll_type:
        case "exclude":
            prefix = "exclude::"
        case "region":
            if asset_type in ("scenario", "prefab"):
                prefix = "bsp::"
            else:
                prefix = "region::"
        case _:
            if bpy.context.scene.nwo.asset_type in ("scenario", "prefab"):
                prefix = "layer::"
            else:
                prefix = "permutation::"

    if not coll_name:
        coll_name = "default"
        
    full_name_base = f"{prefix}{coll_name}"
    full_name = full_name_base

    # check if a collection by this name already exists, if so rename.
    duplicate = 1
    for c in bpy.data.collections:
        if max(c.name.rpartition(".")[0], c.name) == full_name:
            full_name = f"{full_name_base}.{duplicate:03d}"
            duplicate += 1

    return full_name

class NWO_CollectionManager_Create(bpy.types.Operator):
    bl_idname = "nwo.collection_create"
    bl_label = "New Halo Collection"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Creates a Halo collection with the specified name and type"

    def type_items(self, context):
        items = []
        r_name = "Region"
        p_name = "Permutation"
        if context.scene.nwo.asset_type == "scenario":
            r_name = "BSP"
            p_name = "Layer"

        items.append(("region", r_name, ""))
        items.append(("permutation", p_name, ""))
        items.append(("exclude", "Exclude", ""))

        return items

    type: bpy.props.EnumProperty(
        name="Collection Type",
        items=type_items,
        )
    
    name : bpy.props.StringProperty()

    def execute(self, context):
        from .collection_manager import create_collections

        return create_collections(
            context,
            bpy.ops,
            bpy.data,
            self.type,
            self.name,
            False
        )
    
    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.prop(self, "type", text="Type", expand=True)
        row = layout.row()
        row.activate_init = True
        row.prop(self, "name", text="Name")
        
class NWO_CollectionManager_CreateMove(NWO_CollectionManager_Create):
    bl_idname = "nwo.collection_create_move"
    bl_label = "Move to Halo Collection"
    bl_description = "Creates a Halo collection with the specified name and type. Adds all currently selected objects to it"

    def execute(self, context):
        from .collection_manager import create_collections

        return create_collections(
            context,
            bpy.ops,
            bpy.data,
            self.type,
            self.name,
            True,
        )
