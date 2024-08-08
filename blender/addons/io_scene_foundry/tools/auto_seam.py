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
import bmesh
from ..tools.property_apply import apply_props_material

from ..utils import deselect_all_objects, export_objects_mesh_only, get_prefs, poll_ui, set_active_object, true_permutation, true_region

class NWO_AutoSeam(bpy.types.Operator):
    bl_idname = "nwo.auto_seam"
    bl_label = "Auto Seam"
    bl_options = {"UNDO"}
    bl_description = "Generates BSP seams. Requires there to be atleast 2 BSPs in the blend scene and that object mode is active"
    
    selected_only: bpy.props.BoolProperty(name='Selected Objects Only', description="Only create seams between objects in the current selection")
    
    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and poll_ui('scenario') and len(context.scene.nwo.regions_table) > 1

    def execute(self, context):
        return self.auto_seam(context)
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def auto_seam(self, context: bpy.types.Context):
        old_selection = [ob for ob in context.selected_objects if ob.nwo.mesh_type != '_connected_geometry_mesh_type_seam']
        old_active = context.object if context.object and context.object.nwo.mesh_type != '_connected_geometry_mesh_type_seam' else None
        old_3d_cursor_mat = context.scene.cursor.matrix
        apply_materials = get_prefs().apply_materials
        export_obs = export_objects_mesh_only()
        seam_obs = [ob for ob in export_obs if ob.data.nwo.mesh_type == "_connected_geometry_mesh_type_seam"]

        if self.selected_only:
            structure_obs = [ob for ob in export_obs if ob.data.nwo.mesh_type == "_connected_geometry_mesh_type_structure" and ob in context.selected_objects]
        else:
            structure_obs = [ob for ob in export_obs if ob.data.nwo.mesh_type == "_connected_geometry_mesh_type_structure"]

        deselect_all_objects()
        selected_regions = {true_region(structure.nwo) for structure in structure_obs}
        if len(selected_regions) <= 1:
            word = "selection" if self.selected_only else "scene"
            self.report({"WARNING"}, f"Only one structure bsp in {word}")
            return {"CANCELLED"}

        ignore_verts = set()
        seam_counter = 0
        overlapping_seams = 0
        matches = set()
        
        structure_obs_data = [(ob, ob.matrix_world, ob.data, [ob.matrix_world @ v.co for v in ob.data.vertices]) for ob in structure_obs]

        for ob, ob_mat, me, verts in structure_obs_data:
            for test_ob, test_ob_mat, test_me, test_verts in structure_obs_data:
                if ob == test_ob:
                    continue

                pair_key = frozenset({ob.name, test_ob.name})
                if pair_key in matches:
                    continue
                matches.add(pair_key)

                if true_region(test_ob.nwo) == true_region(ob.nwo):
                    continue

                matching_verts = [v.to_tuple() for v in verts if v in test_verts]
                if len(matching_verts) > 2 and frozenset(matching_verts) not in ignore_verts:
                    ignore_verts.add(frozenset(matching_verts))
                    set_active_object(ob)
                    ob.select_set(True)
                    bpy.ops.object.mode_set(mode='EDIT')
                    bpy.ops.mesh.select_all(action="SELECT")
                    bpy.ops.view3d.snap_cursor_to_selected()
                    bpy.ops.object.mode_set(mode='OBJECT')
                    ob.select_set(False)

                    ob_nwo = ob.nwo
                    test_ob_nwo = test_ob.nwo
                    facing_bsp = true_region(ob_nwo)
                    backfacing_bsp = true_region(test_ob_nwo)
                    facing_perm = true_permutation(ob_nwo)

                    seam_data = bpy.data.meshes.new("seam")
                    seam_data.from_pydata(matching_verts, [], [])
                    seam_data.update()

                    new_seam_found = False
                    for old_seam in seam_obs:
                        old_verts = sorted([old_seam.matrix_world @ v.co for v in old_seam.data.vertices])
                        new_verts = sorted([v for v in seam_data.vertices])
                        if old_verts == new_verts:
                            new_seam_found = True
                            overlapping_seams += 1
                            break
                    
                    if new_seam_found:
                        continue

                    bm = bmesh.new()
                    bm.from_mesh(seam_data)
                    old_verts = bm.verts
                    bmesh.ops.contextual_create(bm, geom=bm.verts)
                    bmesh.ops.inset_individual(bm, faces=bm.faces)
                    bm.to_mesh(seam_data)

                    seam = bpy.data.objects.new(f"seam({facing_bsp}:{backfacing_bsp})", seam_data)
                    seam.data.nwo.mesh_type = "_connected_geometry_mesh_type_seam"
                    seam.nwo.permutation_name = facing_perm
                    seam.nwo.region_name = facing_bsp
                    seam.nwo.seam_back = backfacing_bsp
                    context.scene.collection.objects.link(seam)

                    if apply_materials:
                        apply_props_material(seam, 'Seam')

                    set_active_object(seam)
                    seam.select_set(True)
                    bpy.ops.object.origin_set(type="ORIGIN_CURSOR", center="MEDIAN")
                    bpy.ops.object.mode_set(mode='EDIT')
                    bpy.ops.mesh.select_all(action="SELECT")
                    bpy.ops.mesh.normals_make_consistent(inside=True)
                    bpy.ops.mesh.remove_doubles()
                    bpy.ops.object.mode_set(mode='OBJECT')
                    seam.select_set(False)
                    seam_counter += 1

        for ob in old_selection:
            ob.select_set(True)
        if old_active is not None:
            set_active_object(old_active)
        context.scene.cursor.matrix = old_3d_cursor_mat

        if seam_counter:
            self.report({'INFO'}, f"Created {seam_counter} seam{'s' if seam_counter > 1 else ''}")
        elif overlapping_seams:
            self.report({'INFO'}, f'Seams already in place')
        else:
            self.report({'WARNING'}, f'Failed to create any seams. Ensure that structure objects between bsps have overlapping verts')
        
        return {"FINISHED"}

