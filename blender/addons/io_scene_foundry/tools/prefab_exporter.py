

from pathlib import Path
import time
import bpy
from ..managed_blam.scenario_structure_bsp import ScenarioStructureBspTag
from .. import utils

class BlamPrefab:
    def __init__(self, ob, bsp=None, scale=None, rotation=None):
        nwo = ob.nwo
        self.name = ob.name
        self.bsp = bsp
        self.reference = nwo.marker_game_instance_tag_name
        matrix = ob.matrix_world
        mscale = matrix.to_scale()
        self.scale = str(max(mscale[0], mscale[1], mscale[2]))
        matrix = utils.halo_transforms(ob, scale, rotation, True)
        matrix_3x3 = matrix.to_3x3().normalized()
        # forward = -matrix_3x3.col[1]
        # self.forward = [str(n) for n in forward]
        # left_matrix = matrix_3x3.col[0]
        # self.left = [str(n) for n in left_matrix]
        # self.up = [str(n) for n in matrix_3x3.col[2]]
        # self.position = [str(n) for n in matrix.translation]
        # self.props = nwo
        forward = matrix_3x3.col[0]
        left_matrix = matrix_3x3.col[1]
        up_matrix = matrix_3x3.col[2]
        self.forward = [str(n) for n in forward]
        self.left = [str(n) for n in left_matrix]
        self.up = [str(n) for n in up_matrix]
        self.position = [str(n) for n in matrix.translation]
        self.props = nwo
    
class NWO_OT_ExportPrefabs(bpy.types.Operator):
    bl_idname = "nwo.export_prefabs"
    bl_label = "Export Prefabs"
    bl_description = "Exports all blender prefabs to their respective structure bsp tags"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return utils.valid_nwo_asset(context) and context.scene.nwo.asset_type == 'scenario' and utils.is_corinth(context)

    def execute(self, context):
        export_prefabs()
        return {"FINISHED"}
    
def gather_prefabs(context):
    print("--- Start prefab gather")
    start = time.perf_counter()

    def is_prefab_instance(nwo):
        return nwo.marker_type == '_connected_geometry_marker_type_game_instance' and nwo.marker_game_instance_tag_name.lower().endswith(".prefab")
    
    collection_map = utils.create_parent_mapping(context)
    proxies = {}
    with utils.DepsgraphRead():
        depsgraph = context.evaluated_depsgraph_get()

        for inst in depsgraph.object_instances:
            ob = inst.object.original
            nwo = ob.nwo
            
            if not (ob.type == 'EMPTY' and is_prefab_instance(nwo)):
                continue

            if utils.ignore_for_export_fast(ob, collection_map):
                continue
            
            export_collection = nwo.export_collection
            has_export_collection = bool(nwo.export_collection)
            if has_export_collection:
                if collection_map[export_collection].non_export:
                    continue

            proxy = utils.ExportObject()
            proxy.name = ob.name
            proxy.type = ob.type
            proxy.nwo = nwo
            proxy.matrix_world = inst.matrix_world.copy()
            if has_export_collection:
                proxies[proxy] = collection_map[export_collection].region
            else:
                proxies[proxy] = nwo.region_name

    print(len(proxies), "prefabs found")
    print("--- Gathered prefabs in: {:.3f}s".format(time.perf_counter() - start))
        
    return proxies

def export_prefabs():
    asset_path = utils.get_asset_path()
    prefabs = [BlamPrefab(ob, region) for ob, region in gather_prefabs(bpy.context).items()]
    bsps = [r.name for r in bpy.context.scene.nwo.regions_table if r.name.lower() != 'shared']
    structure_bsp_paths = [str(Path(asset_path, f'{b}.scenario_structure_bsp')) for b in bsps]
    for idx, bsp_path in enumerate(structure_bsp_paths):
        b = bsps[idx]
        prefabs_list = [prefab for prefab in prefabs if prefab.bsp == b]
        with ScenarioStructureBspTag(path=bsp_path) as bsp: bsp.write_prefabs(prefabs_list)