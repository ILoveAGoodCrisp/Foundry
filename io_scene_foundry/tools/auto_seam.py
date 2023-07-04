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
import bmesh

from io_scene_foundry.utils.nwo_utils import set_active_object, true_bsp


def auto_seam(context):
    structure_obs = []
    seam_obs = []
    export_obs = context.view_layer.objects
    for ob in export_obs:
        set_active_object(ob)
        ob.select_set(True)
        if (
            ob.nwo.export_this
            and ob.nwo.mesh_type_ui == "_connected_geometry_mesh_type_seam"
        ):
            seam_obs.append(ob)
        if (
            ob.nwo.export_this
            and ob.nwo.mesh_type_ui == "_connected_geometry_mesh_type_structure"
        ):
            structure_obs.append(ob)

        ob.select_set(False)

    for ob in seam_obs:
        ob.select_set(True)
    bpy.ops.object.delete()

    ignore_verts = []
    for ob in structure_obs:
        print(ob.name)
        ob_mat = ob.matrix_world
        # don't need to test a single mesh twice, so remove it from export_objects
        # structure_obs.remove(ob)
        # get the true locations of ob verts
        me = ob.data
        verts = [ob_mat @ v.co for v in me.vertices]
        # test against all other structure meshes
        for test_ob in structure_obs:
            # don't test structure meshes in own bsp
            if true_bsp(test_ob.nwo) == true_bsp(ob.nwo):
                continue
            test_ob_mat = test_ob.matrix_world
            # get test ob verts
            test_me = test_ob.data
            test_verts = [test_ob_mat @ v.co for v in test_me.vertices]

            # check for matching vert coords
            matching_verts = []
            for v in verts:
                for test_v in test_verts:
                    if v == test_v:
                        matching_verts.append(v)
                        break

            # check if at least 3 verts match (i.e. we can make a face out of them)
            if len(matching_verts) > 2 and matching_verts not in ignore_verts:
                # remove these verts from the pool obs are allowed to check from
                ignore_verts.append(matching_verts)
                # set 3D cursor to bsp median point
                set_active_object(ob)
                ob.select_set(True)
                bpy.ops.object.mode_set(mode="EDIT", toggle=False)
                bpy.ops.mesh.select_all(action="SELECT")
                bpy.ops.view3d.snap_cursor_to_selected()
                bpy.ops.object.mode_set(mode="OBJECT", toggle=False)
                ob.select_set(False)
                # make new seam object
                ob_nwo = ob.nwo
                test_ob_nwo = test_ob.nwo
                facing_bsp = ob_nwo.bsp_name_ui
                backfacing_bsp = test_ob_nwo.bsp_name_ui
                facing_perm = ob_nwo.permutation_name_ui
                # backfacing_perm = test_ob_nwo.permutation_name
                # create the new mesh
                seam_data = bpy.data.meshes.new("seam")
                seam_data.from_pydata(matching_verts, [], [])
                seam_data.update()
                # create face
                bm = bmesh.new()
                bm.from_mesh(seam_data)
                bmesh.ops.contextual_create(bm, geom=bm.verts)
                # bmesh.ops.triangulate(bm, faces=bm.faces)
                bm.to_mesh(seam_data)
                bm.free()
                # make a new object, apply halo props and link to the scene
                seam = bpy.data.objects.new(
                    f"seam({facing_bsp}:{backfacing_bsp})", seam_data
                )
                seam_nwo = seam.nwo
                seam_nwo.permutation_name_ui = facing_perm
                seam_nwo.seam_back_ui = backfacing_bsp
                seam_nwo.mesh_type_ui = "_connected_geometry_mesh_type_seam"
                context.scene.collection.objects.link(seam)
                set_active_object(seam)
                seam.select_set(True)
                bpy.ops.object.origin_set(type="ORIGIN_CURSOR", center="MEDIAN")
                bpy.ops.object.mode_set(mode="EDIT", toggle=False)
                bpy.ops.mesh.select_all(action="SELECT")
                bpy.ops.mesh.normals_make_consistent(inside=True)
                bpy.ops.object.mode_set(mode="OBJECT", toggle=False)
                seam.select_set(False)
                # now make the new seam to be flipped
                # flipped_seam_data = seam_data.copy()
                # flipped_seam = seam.copy()
                # flipped_seam.data = flipped_seam_data
                # flipped_seam.name = f"seam({backfacing_bsp}:{facing_bsp})"
                # flipped_seam_nwo = flipped_seam.nwo
                # flipped_seam_nwo.bsp_name = backfacing_bsp
                # flipped_seam_nwo.permutation_name = backfacing_perm
                # flipped_seam_nwo.mesh_type = (
                #     "_connected_geometry_mesh_type_seam"
                # )
                # context.scene.collection.objects.link(flipped_seam)
                # # use bmesh to flip normals of backfacing seam
                # bm = bmesh.new()
                # bm.from_mesh(flipped_seam_data)
                # bmesh.ops.reverse_faces(bm, faces=bm.faces)
                # bm.to_mesh(flipped_seam_data)
                # flipped_seam_data.update()
                # bm.free()

    return {"FINISHED"}
