from collections import defaultdict
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
        
        bpy.ops.wm.save_mainfile(compress=context.preferences.filepaths.use_file_compression)
        bpy.ops.wm.open_mainfile(filepath=fp)
        return {"FINISHED"}
    
class NWO_OT_FileAggregate(bpy.types.Operator):
    bl_idname = "nwo.file_aggregate"
    bl_label = "File Aggregate"
    bl_description = "Moves Region/Permutation/BSP/Layer linked collections into this file"
    bl_options = {"UNDO"}
    
    use_layers: bpy.props.BoolProperty(
        name="Aggregate from Layers",
        description="Aggregates files from layer collections instead of BSP collections"
    )
    
    @classmethod
    def poll(cls, context):
        return utils.valid_nwo_asset(context) and utils.nwo_asset_type() in ('model', 'scenario', 'sky')
    
    def execute(self, context):
        if self.use_layers:
            bsp_or_layer = 'permutation'
        else:
            bsp_or_layer = 'region'
        
        print("Mapping Collections")
        collections = create_parent_mapping(context)
        
        bsp_collection_parents = defaultdict(set)
        coll_names = []
        to_remove_collections = set()

        for coll in collections.keys():
            if coll.nwo.type != bsp_or_layer or not coll.library:
                continue
            to_remove_collections.add(coll)
            to_remove_collections.update(coll.children_recursive)
            coll_name = coll.name
            coll_names.append(coll_name)

            path = utils.resolve_relative_blend(coll.library.filepath)
            if path and Path(path).exists():
                for parent in collections[coll]:
                    bsp_collection_parents[path].add((coll_name, parent))

        # Unlink old collection
        print(f"Unlinking collections")
        bpy.data.batch_remove(to_remove_collections)
        
        with bpy.data.libraries.load(path) as (data_from, data_to):
            data_to.collections = [coll_names]

        print("Appending collections to file")
        for path, coll_info in bsp_collection_parents.items():
            for coll_name, parent in coll_info:
                print(f"Appending {coll_name}")
                with bpy.data.libraries.load(path) as (data_from, data_to):
                    data_to.collections = [coll_name]
                
                new_coll = bpy.data.collections.get(coll_name)
                
                if new_coll is not None:
                    if parent is None:
                        context.scene.collection.children.link(new_coll)
                    else:
                        parent.children.link(new_coll)
        
        self.report({'INFO'}, "File Aggregate Complete")
        return {"FINISHED"}
    
    def invoke(self, context, _):
        self.use_layers = utils.get_scene_props().last_bsp_split_was_layer
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        self.layout.prop(self, "use_layers")
        

class NWO_OT_FileSplit(bpy.types.Operator):
    bl_idname = "nwo.file_split"
    bl_label = "File Split"
    bl_description = "Moves Region/Permutation/BSP/Layer Collections into their own blends, linking them to this one"
    bl_options = {"UNDO"}
    
    use_layers: bpy.props.BoolProperty(
        name="Split to Layers",
        description="Splits files into layer/permutation collections instead of BSP/Region collections"
    )

    @classmethod
    def poll(cls, context):
        return utils.valid_nwo_asset(context) and utils.nwo_asset_type() in ('model', 'scenario', 'sky')

    def execute(self, context):
        
        if self.use_layers:
            bsp_or_layer = 'permutation'
            dir = Path(utils.get_asset_path_full(), "layers" if utils.nwo_asset_type() == 'scenario' else 'regions')
            utils.get_scene_props().last_bsp_split_was_layer = True
        else:
            bsp_or_layer = 'region'
            dir = Path(utils.get_asset_path_full(), "bsps" if utils.nwo_asset_type() == 'scenario' else 'permutations')
            utils.get_scene_props().last_bsp_split_was_layer = False
        
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
        
        bsp_or_layer = 'permutation' if self.use_layers else 'region'
        
        file_map = defaultdict(set)

        for coll in collections.keys():
            if coll.nwo.type != bsp_or_layer or coll.library:
                continue
            to_remove_collections.add(coll)
            to_remove_collections.update(coll.children_recursive)
            coll_name = coll.name
            bsp_collection_parent_names[coll_name] = {None if parent is None else parent.name for parent in collections[coll]}
            coll_names.append(coll_name)
            print(f"Exporting collection: {coll_name}")
            
            if self.use_layers:
                # region = get_parent_region(collections, parent)
                path = Path(dir, coll.nwo.permutation).with_suffix(".blend")
            else:
                path = Path(dir, coll.nwo.region).with_suffix(".blend")
                
            if path.exists():
                path.unlink()
            paths.append(path)
            
            file_map[path].add(coll)
            coll_objects.update(coll.all_objects)

        for path, colls in file_map.items():
            temp_scene = context.scene.copy()
            for c in temp_scene.collection.children:
                temp_scene.collection.children.unlink(c)
                
            for coll in colls:
                temp_scene.collection.children.link(coll)
            temp_scene.nwo.is_child_asset = True
            temp_scene.nwo.parent_asset = relative_original
            
            bpy.data.libraries.write(
                str(path),
                {temp_scene},
                compress=context.preferences.filepaths.use_file_compression,
            )
            
            bpy.data.scenes.remove(temp_scene)

        print(f"Unlinking collections")
        bpy.data.batch_remove(coll_objects)
        bpy.data.batch_remove(to_remove_collections)

        for name, path in zip(coll_names, paths):
            print(f"Linking {name} from {path}")
            with bpy.data.libraries.load(str(path), link=True, relative=True) as (data_from, data_to):
                data_to.collections = [name]

        for coll_name, parent_names in bsp_collection_parent_names.items():
            for parent_name in parent_names:
                if parent_name is not None:
                    bpy.data.collections[parent_name].children.link(bpy.data.collections[coll_name])
                else:
                    bpy.context.scene.collection.children.link(bpy.data.collections[coll_name])

        # bpy.ops.wm.save_mainfile()
        print("Purging old data")
        bpy.data.orphans_purge(do_recursive=True)
        self.report({'INFO'}, "File Split Complete")
        return {"FINISHED"}
    
    def invoke(self, context, _):
        self.use_layers = utils.get_scene_props().last_bsp_split_was_layer
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        self.layout.prop(self, "use_layers")
    
def create_parent_mapping(context):
    collection_map: dict[bpy.types.Collection, set[bpy.types.Collection | None]] = defaultdict(set)
    for collection in context.scene.collection.children:
        recursive_parent_mapper(collection, collection_map, None)
            
    return collection_map

def recursive_parent_mapper(collection: bpy.types.Collection, collection_map: dict[bpy.types.Collection, set[bpy.types.Collection | None]], parent_collection: bpy.types.Collection | None):
    collection_map[collection].add(parent_collection)
    for child in collection.children:
        recursive_parent_mapper(child, collection_map, collection)
        
def get_parent_region(collections, parent):
    if parent is None:
        return ""
    
    if parent.nwo.region:
        print(parent, parent.nwo.region)
        return f"{parent.nwo.region}_"

    regions = {get_parent_region(collections, collection_parent) for collection_parent in collections[parent]}
    regions.discard("")
    if len(regions) == 1:
        return regions.pop()

    return ""
