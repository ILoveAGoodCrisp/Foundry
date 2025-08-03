from pathlib import Path
import bpy
from .. import utils

class NWO_OT_OpenLinkedFile(bpy.types.Operator):
    bl_idname = "nwo.open_linked_file"
    bl_label = "Open Linked File"
    bl_description = "Opens a linked file"
    bl_options = {"UNDO"}

class NWO_OT_FileSplit(bpy.types.Operator):
    bl_idname = "nwo.file_split"
    bl_label = "BSP File Split"
    bl_description = "Moves BSP Collections into their own blends, linking them to this one"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return utils.valid_nwo_asset(context) and utils.nwo_asset_type() == 'scenario'

    def execute(self, context):
        dir = Path(utils.get_asset_path_full(), "bsps")
        if not dir.exists():
            dir.mkdir(parents=True)

        original_file = bpy.data.filepath
        print("Mapping Collections")
        collections = create_parent_mapping(context)

        bsp_collection_parent_names = {}
        coll_objects = set()
        coll_names = []
        paths = []
        to_remove_collections = set()
        # Work on copies to avoid editing live data during export
        for coll in collections.keys():
            if coll.nwo.type != 'region':
                continue
            to_remove_collections.add(coll)
            to_remove_collections.update(coll.children_recursive)
            coll_name = coll.name
            parent = collections[coll]
            bsp_collection_parent_names[coll_name] = parent.name
            coll_names.append(coll_name)
            print(f"Exporting collection: {coll_name}")

            path = Path(dir, coll.nwo.region).with_suffix(".blend")
            if path.exists():
                path.unlink()
            paths.append(path)
            # Create temporary blend with just this collection
            temp_scene = context.scene.copy()
            for c in temp_scene.collection.children:
                temp_scene.collection.children.unlink(c)
            temp_scene.collection.children.link(coll)
            temp_scene.nwo.is_child_asset = True
            bpy.data.libraries.write(
                str(path),
                {temp_scene},
                compress=True,
            )
            
            bpy.data.scenes.remove(temp_scene)
            
            coll_objects.update(coll.all_objects)

        # Unlink old collection
        print(f"Unlinking collections")
        bpy.data.batch_remove(coll_objects)
        bpy.data.batch_remove(to_remove_collections)

        # Link back the collection
        for name, path in zip(coll_names, paths):
            print(f"Linking {name} from {path}")
            with bpy.data.libraries.load(str(path), link=True) as (data_from, data_to):
                data_to.collections = [name]

        for coll_name, parent_name in bsp_collection_parent_names.items():
            if parent_name is not None:
                bpy.data.collections[parent_name].children.link(bpy.data.collections[coll_name])
            else:
                bpy.context.scene.collection.children.link(bpy.data.collections[coll_name])

        # Save once at the end
        # bpy.ops.wm.save_mainfile()
        print("Purging old data")
        bpy.data.orphans_purge(do_recursive=True)
        return {"FINISHED"}
    
def create_parent_mapping(context):
    """Returns a dict of collections [key=collection, value=parent collection]"""
    collection_map: dict[bpy.types.Collection: bpy.types.Collection] = {}
    for collection in context.scene.collection.children:
        recursive_parent_mapper(collection, collection_map, None)
            
    return collection_map

def recursive_parent_mapper(collection: bpy.types.Collection, collection_map: list[bpy.types.Collection], parent_collection: bpy.types.Collection | None):
    collection_map[collection] = parent_collection
    for child in collection.children:
        recursive_parent_mapper(child, collection_map, collection)