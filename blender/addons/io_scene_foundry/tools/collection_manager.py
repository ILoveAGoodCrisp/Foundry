

import bpy

from ..utils import get_scene_props

def create_collections(context, ops, data, coll_type, coll_name, move_objects):
    selected_collection = context.collection
    if coll_name.strip() == "":
        coll_name = "default"
    coll_name = coll_name.lower()[:128]
    # iterates through the selected objects and applies the chosen collection type
    full_name = get_full_name(coll_type, coll_name)
    collection_index = get_coll_if_exists(data, full_name)
    if move_objects:
        # Outliner selections are independent of the viewport selection and can
        # include collections or other IDs as well as objects.
        if context.area and context.area.type == 'OUTLINER':
            objects = [item for item in context.selected_ids if isinstance(item, bpy.types.Object)]
        else:
            objects = list(context.selected_objects)

        if collection_index == -1:
            new_collection = data.collections.new(full_name)
            context.scene.collection.children.link(new_collection)
        else:
            new_collection = data.collections[collection_index]

        for ob in objects:
            # Link first so an object never temporarily loses every collection.
            if ob.name not in new_collection.objects:
                new_collection.objects.link(ob)
            for coll in tuple(ob.users_collection):
                if coll != new_collection:
                    coll.objects.unlink(ob)
    else:
        new_collection = bpy.data.collections.new(full_name)
        if selected_collection:
            selected_collection.children.link(new_collection)
        else:
            context.scene.collection.children.link(new_collection)

    new_collection.nwo.type = coll_type
    scene_nwo = get_scene_props()
    if coll_type == 'region':
        regions = scene_nwo.regions_table
        new_collection.nwo.region = coll_name
        if coll_name not in [r.name for r in regions]:
            new_region = regions.add()
            new_region.old = coll_name
            new_region.name = coll_name


    elif coll_type == 'permutation':
        permutations = scene_nwo.permutations_table
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
    asset_type = get_scene_props().asset_type

    if not coll_name:
        coll_name = "default"
        
    full_name_base = coll_name
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
        if get_scene_props().asset_type == "scenario":
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
