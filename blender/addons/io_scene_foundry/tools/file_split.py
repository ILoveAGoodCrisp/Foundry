from pathlib import Path
import bpy
from .. import utils

class NWO_OT_OpenLinkedCollection(bpy.types.Operator):
    bl_idname = "nwo.open_linked_collection"
    bl_label = "Open Linked Collection"
    bl_description = "Opens the blend file for a linked collection"
    bl_options = {"UNDO"}
    
    @classmethod
    def poll(cls, context):
        return context.collection and context.collection.library
    
    def execute(self, context):
        
        fp = utils.resolve_relative_blend(context.collection.library.filepath)
        
        if not fp or not Path(fp).exists():
            self.report({'WARNING'}, f"Library filepath does not exist: {fp}")
            return {'CANCELLED'}
        
        bpy.ops.wm.save_mainfile()
        bpy.ops.wm.open_mainfile(filepath=fp)
        return {"FINISHED"}
    
class NWO_OT_FileAggregate(bpy.types.Operator):
    bl_idname = "nwo.file_aggregate"
    bl_label = "BSP File Aggregate"
    bl_description = "Moves linked BSP collections into this file"
    bl_options = {"UNDO"}
    
    @classmethod
    def poll(cls, context):
        return utils.valid_nwo_asset(context) and utils.nwo_asset_type() == 'scenario'
    
    def execute(self, context):
        print("Mapping Collections")
        collections = create_parent_mapping(context)
        
        bsp_collection_parents = {}
        coll_names = []
        to_remove_collections = set()

        for coll in collections.keys():
            if coll.nwo.type != 'region' or not coll.library:
                continue
            to_remove_collections.add(coll)
            to_remove_collections.update(coll.children_recursive)
            coll_name = coll.name
            parent = collections[coll]
            
            coll_names.append(coll_name)

            path = utils.resolve_relative_blend(coll.library.filepath)
            if path and Path(path).exists():
                bsp_collection_parents[path] = (coll_name, parent)

        # Unlink old collection
        print(f"Unlinking collections")
        bpy.data.batch_remove(to_remove_collections)

        print("Appending collections to file")
        for path, (coll_name, parent) in bsp_collection_parents.items():
            print(f"Appending {coll_name}")
            with bpy.data.libraries.load(path) as (data_from, data_to):
                data_to.collections = [coll_name]
                
            parent.children.link(bpy.data.collections[coll_name])
        
        self.report({'INFO'}, "File Aggregate Complete")
        return {"FINISHED"}
        

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
        relative_original = utils.relative_path(original_file)
        print("Mapping Collections")
        collections = create_parent_mapping(context)

        bsp_collection_parent_names = {}
        coll_objects = set()
        coll_names = []
        paths = []
        to_remove_collections = set()

        for coll in collections.keys():
            if coll.nwo.type != 'region' or coll.library:
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

            temp_scene = context.scene.copy()
            for c in temp_scene.collection.children:
                temp_scene.collection.children.unlink(c)
            temp_scene.collection.children.link(coll)
            temp_scene.nwo.is_child_asset = True
            temp_scene.nwo.parent_asset = relative_original
            bpy.data.libraries.write(
                str(path),
                {temp_scene},
                compress=True,
            )
            
            bpy.data.scenes.remove(temp_scene)
            
            coll_objects.update(coll.all_objects)
            
            # child_asset = context.scene.nwo.child_assets.add()
            # child_asset.asset_path = utils.relative_path(path)

        print(f"Unlinking collections")
        bpy.data.batch_remove(coll_objects)
        bpy.data.batch_remove(to_remove_collections)

        for name, path in zip(coll_names, paths):
            print(f"Linking {name} from {path}")
            with bpy.data.libraries.load(str(path), link=True, relative=True) as (data_from, data_to):
                data_to.collections = [name]

        for coll_name, parent_name in bsp_collection_parent_names.items():
            if parent_name is not None:
                bpy.data.collections[parent_name].children.link(bpy.data.collections[coll_name])
            else:
                bpy.context.scene.collection.children.link(bpy.data.collections[coll_name])

        # bpy.ops.wm.save_mainfile()
        print("Purging old data")
        bpy.data.orphans_purge(do_recursive=True)
        self.report({'INFO'}, "File Split Complete")
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