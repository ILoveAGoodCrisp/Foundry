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

from pathlib import Path
import bpy
from ..managed_blam.scenario_structure_bsp import ScenarioStructureBspTag
from .. import utils

class BlamPrefab:
    def __init__(self, ob, bsp=None, scale=None, rotation=None):
        nwo = ob.nwo
        self.name = ob.name
        self.bsp = bsp
        self.reference = nwo.marker_game_instance_tag_name
        self.scale = str(max(ob.scale[0], ob.scale[1], ob.scale[2]))
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
    return [ob for ob in context.scene.objects if utils.is_marker(ob) and ob.nwo.exportable and ob.nwo.marker_type == '_connected_geometry_marker_type_game_instance' and ob.nwo.marker_game_instance_tag_name.lower().endswith(".prefab")]

def export_prefabs():
    asset_path, asset_name = utils.get_asset_info()
    prefabs = [BlamPrefab(ob, utils.true_region(ob.nwo)) for ob in gather_prefabs(bpy.context)]
    bsps = [r.name for r in bpy.context.scene.nwo.regions_table if r.name.lower() != 'shared']
    structure_bsp_paths = [str(Path(asset_path, f'{asset_name}_{b}.scenario_structure_bsp')) for b in bsps]
    for idx, bsp_path in enumerate(structure_bsp_paths):
        b = bsps[idx]
        prefabs_list = [prefab for prefab in prefabs if prefab.bsp == b]
        with ScenarioStructureBspTag(path=bsp_path) as bsp: bsp.write_prefabs(prefabs_list)