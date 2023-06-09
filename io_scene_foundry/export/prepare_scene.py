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

import bmesh
import bpy
from os import path
import csv
from math import radians
from mathutils import Matrix, Vector
import time

from io_scene_foundry.tools.shader_finder import find_shaders
from ..utils.nwo_utils import (
    bool_str,
    color_3p_str,
    color_4p_str,
    deselect_all_objects,
    disable_prints,
    dot_partition,
    enable_prints,
    jstr,
    layer_faces,
    print_warning,
    set_active_object,
    is_shader,
    get_tags_path,
    not_bungie_game,
    true_region,
    true_bsp,
    true_permutation,
    update_progress,
    valid_animation_types,
    vector_str,
)


#####################################################################################
#####################################################################################
# MAIN CLASS
class PrepareScene:
    def __init__(
        self,
        context,
        report,
        asset,
        sidecar_type,
        use_armature_deform_only,
        game_version,
        meshes_to_empties,
        export_animations,
        export_gr2_files,
        export_all_perms,
        export_all_bsps,
    ):
        # time it!
        start = time.perf_counter()

        h4 = game_version != "reach"

        # Exit local view. Must do this otherwise fbx export will fail.
        self.exit_local_view(context)
        # print("exit_local_view")

        # Force set object mode
        context.view_layer.update()
        self.set_object_mode(context)
        # print("set_object_mode")

        # Get the current set of selected objects. We need this so selected perms/bsps only functionality can be used
        objects_selection = context.selected_objects[:]

        deselect_all_objects()

        # Disable collections with the +exclude prefix. This way they are treated as if they are not part of the asset at all
        self.disable_excluded_collections(context)
        # print("disable_excluded_collections")

        # Unhide collections. Hidden collections will stop objects in the collection being exported. We only want this functionality if the collection is disabled
        self.unhide_collections(context)
        # print("unhide_collections")

        # make objects linked to scene real and local
        # Context override selection does not work here
        disable_prints()

        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.duplicates_make_real()
        bpy.ops.object.make_local(type="ALL")
        bpy.ops.object.select_all(action='DESELECT')

        enable_prints()

        context.view_layer.update()
        # print("make_local")

        # cast view_layer objects to variable
        all_obs = context.view_layer.objects

        # unlink non export objects
        non_export_obs = [
            ob
            for ob in all_obs
            if not ob.nwo.export_this
            or ob.type in ("LATTICE", "LIGHT_PROBE", "SPEAKER", "CAMERA")
            or (ob.type == "EMPTY" and ob.empty_display_type == "IMAGE")
        ]
        for ob in non_export_obs:
            self.unlink(ob)
        # print("unlink_obs")
        scenario_asset = sidecar_type == "SCENARIO"

        export_obs = context.view_layer.objects[:]
        scene_coll = context.scene.collection.objects
        # build proxy instances from structure
        if h4:
            proxy_owners = [
                ob
                for ob in export_obs
                if ob.nwo.mesh_type_ui
                == "_connected_geometry_mesh_type_structure"
                and ob.nwo.proxy_instance
            ]
            for ob in proxy_owners:
                proxy_instance = ob.copy()
                proxy_instance.name = f"{ob.name}(instance)"
                proxy_instance.nwo.mesh_type_ui = (
                    "_connected_geometry_mesh_type_poop"
                )
                scene_coll.link(proxy_instance)

            # print("structure_proxy")

        materials = bpy.data.materials

        if "Override" not in materials:
            override_mat = materials.new("Override")
        else:
            override_mat = materials.get("Override")

        # start the great loop!
        context.view_layer.update()
        export_obs = context.view_layer.objects[:]

        # establish region/global mats sets
        has_regions = sidecar_type in ("MODEL", "SKY")
        has_global_mats = sidecar_type in ("MODEL", "SCENARIO", "PREFAB")

        regions = {"default"}
        global_materials = {"default"}
        self.bsps = set()
        process = "Building Export Scene"
        update_progress(process, 0)
        len_export_obs = len(export_obs)
        for idx, ob in enumerate(export_obs):
            set_active_object(ob)
            ob.select_set(True)
            nwo = ob.nwo
            me = ob.data
            ob_type = ob.type
            is_mesh = ob_type == "MESH"
            is_mesh_loose = ob_type in (
                "MESH",
                "EMPTY",
                "CURVE",
                "META",
                "SURFACE",
                "FONT",
            )

            # export objects must be visible and selectable
            ob.hide_set(False)
            ob.hide_select = False

            # fix empty group names
            bsp_ui = nwo.bsp_name_ui
            bsp_ui = "default" if bsp_ui == "" else bsp_ui

            perm_ui = nwo.permutation_name_ui
            perm_ui = "default" if perm_ui == "" else perm_ui

            region_ui = nwo.region_name_ui
            region_ui = "default" if region_ui == "" else region_ui

            # cast ui props to export props
            nwo.permutation_name = true_permutation(nwo)
            if scenario_asset:
                nwo.bsp_name = true_bsp(nwo)

            self.set_object_type(ob, ob_type, nwo, is_mesh_loose)

            self.apply_object_mesh_marker_properties(
                ob, sidecar_type, not h4, nwo
            )

            # add region/global_mat to sets
            uses_global_mat = (
                has_global_mats
                and nwo.mesh_type
                in (
                    "_connected_geometry_mesh_type_collision",
                    "_connected_geometry_mesh_type_physics"
                    "_connected_geometry_mesh_type_poop",
                    "_connected_geometry_mesh_type_poop_collision",
                )
                or scenario_asset
                and not h4
                and nwo.mesh_type == "_connected_geometry_mesh_type_default"
            )
            uses_regions = has_regions and nwo.mesh_type in (
                "_connected_geometry_mesh_type_collision",
                "_connected_geometry_mesh_type_physics",
                "_connected_geometry_mesh_type_default",
            )

            if uses_regions:
                regions.add(nwo.region_name)

            if uses_global_mat:
                global_materials.add(nwo.face_global_material)

            if scenario_asset:
                self.bsps.add(nwo.bsp_name)

            if export_gr2_files:
                # fix meshes with missing UV maps
                if is_mesh:
                    uv_layers = me.uv_layers
                    if not uv_layers:
                        uv_layers.new(name="UVMap_0")

                    # print("uv fix")

                    # Add materials to all objects without one. No materials = unhappy Tool.exe
                    self.fix_materials(ob, me, materials, override_mat)
                    # print("fix_materials")

            ob.select_set(False)

            update_progress(process, idx / len_export_obs)

        update_progress(process, 1)

        # OB LOOP COMPLETE----------------------------------------------------------------------------------------------
        # --------------------------------------------------------------------------------------------------------------
        # print("ob_loop")

        # get selected perms and bsps for use later
        self.selected_perms = set()
        self.selected_bsps = set()

        sel_perms = export_all_perms == "selected"
        sel_bsps = export_all_bsps == "selected"

        if sel_perms or sel_bsps:
            for ob in objects_selection:
                nwo = ob.nwo

                if sel_perms:
                    self.selected_perms.add(nwo.permutation_name)

                if sel_bsps:
                    self.selected_bsps.add(nwo.bsp_name)

        # loop through each material to check if find_shaders is needed
        for mat in materials:
            mat_nwo = mat.nwo
            if mat_nwo.rendered and not mat_nwo.shader_path:
                find_shaders(materials, report)
                break

        # print("found_shaders")

        # get new export_obs
        context.view_layer.update()
        export_obs = context.view_layer.objects[:]

        # apply face layer properties
        self.apply_face_properties(context, export_obs, scene_coll, h4)
        # print("face_props_applied")

        # get new export_obs from split meshes
        context.view_layer.update()
        export_obs = context.view_layer.objects[:]

        if export_gr2_files:
            # poop proxy madness
            self.setup_poop_proxies(export_obs, h4)
            # print("poop_proxies")

            # get new proxy export_obs
            context.view_layer.update()
            export_obs = context.view_layer.objects[:]

            # Convert mesh markers to empty objects
            if meshes_to_empties:
                self.markerify(export_obs, scene_coll, context)
                # print("markifiy")

                # get new export_obs from deleted markers
                context.view_layer.update()
                export_obs = context.view_layer.objects[:]

            # remove meshes with zero faces
            self.cull_zero_face_meshes(export_obs)
            # print("cull_zero_face")

        # Establish a dictionary of scene regions. Used later in export_gr2 and build_sidecar
        regions = [region for region in regions if region]
        self.regions_dict = {
            region: str(idx) for idx, region in enumerate(regions)
        }

        # Establish a dictionary of scene global materials. Used later in export_gr2 and build_sidecar
        global_materials = [
            global_material
            for global_material in global_materials
            if global_material
        ]
        self.global_materials_dict = {
            global_material: str(idx)
            for idx, global_material in enumerate(global_materials)
            if global_material
        }

        # get all objects that we plan to export later
        self.halo_objects_init()
        self.halo_objects(sidecar_type, export_obs)
        # print("halo_objects")

        self.model_armature = None
        self.skeleton_bones = {}
        self.current_action = None

        if sidecar_type in ("MODEL", "SKY", "FP ANIMATION"):
            self.model_armature, using_auto_armature = self.get_scene_armature(
                export_obs, asset, scene_coll
            )

            if self.model_armature:
                if not using_auto_armature or sidecar_type != "FP ANIMATION":
                    # unlink any unparented objects from the scene
                    for ob in export_obs:
                        if ob is not self.model_armature and not ob.parent:
                            print_warning(
                                f"Ignoring {ob.name} because it is not parented to the scene armature"
                            )
                            self.unlink(ob)

                    context.view_layer.update()
                    export_obs = context.view_layer.objects[:]
                    self.fix_bad_parenting(self.model_armature, export_obs)

                # set bone names equal to their name overrides (if not blank)
                if export_gr2_files:
                    self.set_bone_names(self.model_armature.data.bones)

                self.skeleton_bones = self.get_bone_list(
                    self.model_armature, use_armature_deform_only, h4
                )  # return a list of bones attached to the model armature, ignoring control / non-deform bones
                if bpy.data.actions:
                    try:
                        self.current_action = self.get_current_action(
                            context, self.model_armature
                        )
                    except:
                        pass

        # print("armature")

        # Set timeline range for use during animation export
        self.timeline_start, self.timeline_end = self.set_timeline_range(
            context
        )

        # rotate the model armature if needed
        if export_gr2_files:
            self.fix_armature_rotation(
                self.model_armature,
                sidecar_type,
                context,
                export_animations,
                self.current_action,
                self.timeline_start,
                self.timeline_end,
            )

        # Set animation name overrides / fix them up for the exporter
        self.set_animation_overrides(self.model_armature, self.current_action)

        # get the max LOD count in the scene if we're exporting a decorator
        self.lod_count = self.get_decorator_lod_count(
            self.halo_objects, sidecar_type == "DECORATOR SET"
        )

        end = time.perf_counter()
        print(f"\nScene Prepared in {end - start} seconds")
        # time.sleep(3)

        # raise

    def auto_seam(self, context):
        structure_obs = [
            ob
            for ob in context.view_layer.objects
            if ob.type == "MESH"
            and ob.nwo.mesh_type == "_connected_geometry_mesh_type_default"
        ]
        ignore_verts = []
        for ob in structure_obs:
            ob_mat = ob.matrix_world
            # don't need to test a single mesh twice, so remove it from export_objects
            structure_obs.remove(ob)
            # get the true locations of ob verts
            me = ob.data
            verts = [ob_mat @ v.co for v in me.vertices]
            # test against all other structure meshes
            for test_ob in structure_obs:
                # don't test structure meshes in own bsp
                if test_ob.nwo.bsp_name == ob.nwo.bsp_name:
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
                if (
                    len(matching_verts) > 2
                    and matching_verts not in ignore_verts
                ):
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
                    facing_bsp = ob_nwo.bsp_name
                    backfacing_bsp = test_ob_nwo.bsp_name
                    facing_perm = ob_nwo.permutation_name
                    backfacing_perm = test_ob_nwo.permutation_name
                    # create the new mesh
                    seam_data = bpy.data.meshes.new("seam")
                    seam_data.from_pydata(matching_verts, [], [])
                    seam_data.update()
                    # create face and triangulate with bmesh
                    bm = bmesh.new()
                    bm.from_mesh(seam_data)
                    bmesh.ops.contextual_create(bm, geom=bm.verts)
                    bmesh.ops.triangulate(bm, faces=bm.faces)
                    bm.to_mesh(seam_data)
                    bm.free()
                    # make a new object, apply halo props and link to the scene
                    seam = bpy.data.objects.new(
                        f"seam({facing_bsp}:{backfacing_bsp})", seam_data
                    )
                    seam_nwo = seam.nwo
                    seam_nwo.bsp_name = facing_bsp
                    seam_nwo.permutation_name = facing_perm
                    seam_nwo.mesh_type = "_connected_geometry_mesh_type_seam"
                    context.scene.collection.objects.link(seam)
                    set_active_object(seam)
                    seam.select_set(True)
                    bpy.ops.object.origin_set(
                        type="ORIGIN_CURSOR", center="MEDIAN"
                    )
                    bpy.ops.object.mode_set(mode="EDIT", toggle=False)
                    bpy.ops.mesh.select_all(action="SELECT")
                    bpy.ops.mesh.normals_make_consistent(inside=True)
                    bpy.ops.object.mode_set(mode="OBJECT", toggle=False)
                    seam.select_set(False)
                    # now make the new seam to be flipped
                    flipped_seam_data = seam_data.copy()
                    flipped_seam = seam.copy()
                    flipped_seam.data = flipped_seam_data
                    flipped_seam.name = f"seam({backfacing_bsp}:{facing_bsp})"
                    flipped_seam_nwo = flipped_seam.nwo
                    flipped_seam_nwo.bsp_name = backfacing_bsp
                    flipped_seam_nwo.permutation_name = backfacing_perm
                    flipped_seam_nwo.mesh_type = (
                        "_connected_geometry_mesh_type_seam"
                    )
                    context.scene.collection.objects.link(flipped_seam)
                    # use bmesh to flip normals of backfacing seam
                    bm = bmesh.new()
                    bm.from_mesh(flipped_seam_data)
                    bmesh.ops.reverse_faces(bm, faces=bm.faces)
                    bm.to_mesh(flipped_seam_data)
                    flipped_seam_data.update()
                    bm.free()

    def unlink(self, ob):
        data_coll = bpy.data.collections
        for collection in data_coll:
            if collection in ob.users_collection:
                collection.objects.unlink(ob)

        scene_coll = bpy.context.scene.collection
        if scene_coll in ob.users_collection:
            scene_coll.objects.unlink(ob)

    def cull_zero_face_meshes(self, export_obs):
        for ob in export_obs:
            if ob.type == "MESH" and not ob.data.polygons:
                self.unlink(ob)

    # FACEMAP SPLIT

    def justify_face_split(self, layer_faces_dict, poly_count):
        """Checked whether we actually need to split this mesh up"""
        # check if face layers cover the whole mesh, if they do, we don't need to split the mesh
        for face_seq in layer_faces_dict.values():
            face_count = len(face_seq)
            if poly_count != face_count:
                return True

        return False

    def strip_render_only_faces(self, layer_faces_dict, bm):
        """Removes faces from a mesh that have the render only property"""
        # loop through each face layer and select non collision faces
        for layer, face_seq in layer_faces_dict.items():
            if (
                layer.face_mode_override
                and layer.face_mode_ui
                == "_connected_geometry_face_mode_render_only"
            ):
                bmesh.ops.delete(bm, geom=face_seq, context="FACES")

        return len(bm.faces)

    def recursive_layer_split(
        self,
        ob,
        me,
        face_layers,
        layer_faces_dict,
        h4,
        scene_coll,
        split_objects,
        bm,
    ):
        # faces_layer_dict = {faces: layer for layer, faces in layer_faces_dict.keys()}
        faces_layer_dict = {}
        for layer, face_seq in layer_faces_dict.items():
            fs = tuple(face_seq)
            if fs in faces_layer_dict.keys() and face_seq:
                faces_layer_dict[fs].append(layer)
            elif face_seq:
                faces_layer_dict[fs] = [layer]

        for face_seq in faces_layer_dict.keys():
            if len(faces_layer_dict.keys()) == 1:
                # delete faces from new mesh
                for face in bm.faces:
                    face.select = True if face in face_seq else False

                split_bm = bm.copy()
                # new_face_seq = [face for face in split_bm.faces if face not in face_seq]


                bmesh.ops.delete(
                    bm,
                    geom=[face for face in bm.faces if not face.select],
                    context="FACES",
                )

                bm.to_mesh(me)

                split_ob = ob.copy()

                split_ob.data = me.copy()
                split_me = split_ob.data


                bmesh.ops.delete(
                    split_bm,
                    geom=[face for face in split_bm.faces if face.select],
                    context="FACES",
                )

                split_bm.to_mesh(split_me)

                scene_coll.link(split_ob)

                for layer in faces_layer_dict[face_seq]:
                    self.face_prop_to_mesh_prop(ob.nwo, layer, h4)

                ob_name_suffix = str(
                    [layer.name for layer in faces_layer_dict[face_seq]]
                )
                ob.name = f"{ob.name}{ob_name_suffix}"
                split_objects.append(ob)

            elif face_seq:
                # delete faces from new mesh
                for face in bm.faces:
                    face.select = True if face in face_seq else False

                split_bm = bm.copy()
                # new_face_seq = [face for face in split_bm.faces if face not in face_seq]


                bmesh.ops.delete(
                    bm,
                    geom=[face for face in bm.faces if not face.select],
                    context="FACES",
                )

                bm.to_mesh(me)

                split_ob = ob.copy()

                split_ob.data = me.copy()
                split_me = split_ob.data


                bmesh.ops.delete(
                    split_bm,
                    geom=[face for face in split_bm.faces if face.select],
                    context="FACES",
                )

                split_bm.to_mesh(split_me)

                scene_coll.link(split_ob)

                new_layer_faces_dict = {
                    layer: layer_faces(
                        split_bm,
                        split_bm.faces.layers.int.get(layer.layer_name),
                    )
                    for layer in face_layers
                }

                self.recursive_layer_split(
                    split_ob,
                    split_me,
                    face_layers,
                    new_layer_faces_dict,
                    h4,
                    scene_coll,
                    split_objects,
                    split_bm,
                )

        return split_objects

    def split_to_layers(
        self, context, ob, ob_nwo, me, face_layers, scene_coll, h4, bm
    ):
        poly_count = len(bm.faces)
        layer_faces_dict = {
            layer: layer_faces(bm, bm.faces.layers.int.get(layer.layer_name))
            for layer in face_layers
        }

        collision_ob = None

        if self.justify_face_split(layer_faces_dict, poly_count):
            # if instance geometry, we need to fix the collision model (provided the user has not already defined one)
            if (
                ob_nwo.mesh_type == "_connected_geometry_mesh_type_poop"
                and not ob.nwo.poop_render_only
                and not h4
            ):  # don't do this for h4 as collision can be open
                # check for custom collision / physics
                if not ob.children:
                    collision_ob = ob.copy()
                    collision_ob.data = me.copy()
                    scene_coll.link(collision_ob)
                    # Remove render only property faces from coll mesh
                    coll_bm = bmesh.new()
                    coll_bm.from_mesh()
                    poly_count = self.strip_render_only_faces(
                        layer_faces_dict, coll_bm
                    )

                    collision_ob.name = f"{ob.name}(collision)"

                    collision_ob.parent = ob
                    collision_ob.matrix_world = ob.matrix_world
                    collision_ob.nwo.mesh_type = (
                        "_connected_geometry_mesh_type_poop_collision"
                    )

            normals_ob = ob.copy()
            normals_ob.data = me.copy()

            split_objects = self.recursive_layer_split(
                ob, me, face_layers, layer_faces_dict, h4, scene_coll, [ob], bm
            )
            for split_ob in split_objects:
                if split_ob.data.polygons:
                    # TODO only do data transfer for rendered geo
                    # set up data transfer modifier to retain normals
                    mod = split_ob.modifiers.new(
                        "HaloDataTransfer", "DATA_TRANSFER"
                    )
                    mod.object = normals_ob
                    mod.use_object_transform = False
                    mod.use_loop_data = True
                    mod.data_types_loops = {"CUSTOM_NORMAL"}
                    # if obj.data.face_props:
                    #     obj.name = f'{dot_partition(obj.name)}({obj.face_maps[0].name})'
                # make sure we're not parenting the collision to a zero face mesh
                elif collision_ob is not None and collision_ob.parent == ob:
                    collision_ob.parent = None
                    # can't have a free floating coll mesh in Reach, so we make it a poop and make it invisible
                    collision_ob_nwo = collision_ob.nwo
                    collision_ob_nwo.mesh_type = (
                        "_connected_geometry_mesh_type_poop"
                    )
                    collision_ob_nwo.face_mode = (
                        "_connected_geometry_face_mode_collision_only"
                    )
                    # collision_mesh.nwo.face_type = '_connected_geometry_face_type_seam_sealer'
                    collision_ob.matrix_world = ob.matrix_world

            return split_objects

        else:
            return context.selected_objects

    def create_adjacent_seam(self, ob, adjacent_bsp):
        facing_bsp = ob.nwo.bsp_name
        # triangulate first before copying
        me = ob.data
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
        bm.to_mesh(me)
        bm.free()
        # now make the new seam to be flipped
        flipped_seam = ob.copy()
        flipped_seam.data = ob.data.copy()
        bpy.context.scene.collection.objects.link(flipped_seam)
        flipped_seam_name = ob.name.rpartition("(")[0]
        flipped_seam.name = (
            flipped_seam_name + f"({adjacent_bsp}:{facing_bsp})"
        )
        flipped_seam.nwo.bsp_name = adjacent_bsp
        # use bmesh to flip normals
        bm = bmesh.new()
        me = flipped_seam.data
        bm.from_mesh(me)
        for f in bm.faces:
            f.normal_flip()
        bm.to_mesh(me)
        me.update()
        bm.free()

    def face_prop_to_mesh_prop(self, mesh_props, face_props, h4):
        # ignore unused face_prop items
        # run through each face prop and apply it to the mesh if override set
        # if face_props.seam_override and ob.nwo.mesh_type == '_connected_geometry_mesh_type_default':
        #     mesh_props.mesh_type = '_connected_geometry_mesh_type_seam'
        #     create_adjacent_seam(ob, face_props.seam_adjacent_bsp)

        # reset mesh props
        # first set the persistent mesh props, followed by the optional

        # set mesh props from face props
        if face_props.face_type_override:
            mesh_props.face_type = face_props.face_type_ui
            mesh_props.sky_permutation_index = str(
                face_props.sky_permutation_index_ui
            )
        if face_props.face_mode_override:
            mesh_props.face_mode = face_props.face_mode_ui
        if face_props.face_two_sided_override and face_props.face_two_sided_ui:
            mesh_props.face_sides = "_connected_geometry_face_sides_two_sided"
        if face_props.face_draw_distance_override:
            mesh_props.face_draw_distance = face_props.face_draw_distance_ui
        if face_props.texcoord_usage_override:
            mesh_props.texcoord_usage = face_props.texcoord_usage_ui
        if face_props.region_name_override:
            mesh_props.region_name = face_props.region_name_ui
        if face_props.face_global_material_override:
            mesh_props.face_global_material = (
                face_props.face_global_material_ui
            )
        if face_props.ladder_override:
            mesh_props.ladder = bool_str(face_props.ladder_ui)
        if face_props.slip_surface_override:
            mesh_props.slip_surface = bool_str(face_props.slip_surface_ui)
        if face_props.decal_offset_override:
            mesh_props.decal_offset = bool_str(face_props.decal_offset_ui)
        if face_props.group_transparents_by_plane_override:
            mesh_props.group_transparents_by_plane = bool_str(
                face_props.group_transparents_by_plane_ui
            )
        if face_props.no_shadow_override:
            mesh_props.no_shadow = bool_str(face_props.no_shadow_ui)
        if face_props.precise_position_override:
            mesh_props.precise_position = bool_str(
                face_props.precise_position_ui
            )
        if face_props.no_lightmap_override:
            mesh_props.no_lightmap = bool_str(face_props.no_lightmap_ui)
        if face_props.no_pvs_override:
            mesh_props.no_pvs = bool_str(face_props.no_pvs_ui)
        # lightmap props
        if face_props.lightmap_additive_transparency_override:
            mesh_props.lightmap_additive_transparency = jstr(
                face_props.lightmap_additive_transparency_ui
            )
            mesh_props.lightmap_additive_transparency_active = True
        if face_props.lightmap_resolution_scale_override:
            mesh_props.lightmap_resolution_scale = int(
                face_props.lightmap_resolution_scale_ui
            )
            mesh_props.lightmap_resolution_scale_active = True
        if face_props.lightmap_type_override:
            mesh_props.lightmap_type = face_props.lightmap_type_ui
            mesh_props.lightmap_type_active = True
        # if item.lightmap_analytical_bounce_modifier_override:
        #     mesh_props.lightmap_analytical_bounce_modifier = face_props.lightmap_analytical_bounce_modifier
        #     mesh_props.lightmap_analytical_bounce_modifier_active = True
        # if item.lightmap_general_bounce_modifier_override:
        #     mesh_props.lightmap_general_bounce_modifier = face_props.lightmap_general_bounce_modifier
        #     mesh_props.lightmap_general_bounce_modifier_active = True
        if face_props.lightmap_translucency_tint_color_override:
            mesh_props.lightmap_translucency_tint_color = color_3p_str(
                face_props.lightmap_translucency_tint_color_ui
            )
            mesh_props.lightmap_translucency_tint_color_active = True
        if face_props.lightmap_lighting_from_both_sides_override:
            mesh_props.lightmap_lighting_from_both_sides = bool_str(
                face_props.lightmap_lighting_from_both_sides_ui
            )
            mesh_props.lightmap_lighting_from_both_sides_active = True
        # emissive props
        if face_props.emissive_override:
            mesh_props.material_lighting_attenuation_falloff = jstr(
                face_props.material_lighting_attenuation_falloff_ui
            )
            mesh_props.material_lighting_attenuation_cutoff = jstr(
                face_props.material_lighting_attenuation_cutoff_ui
            )
            mesh_props.material_lighting_emissive_focus = jstr(
                face_props.material_lighting_emissive_focus_ui
            )
            mesh_props.material_lighting_emissive_color = color_4p_str(
                face_props.material_lighting_emissive_color_ui
            )
            mesh_props.material_lighting_emissive_per_unit = bool_str(
                face_props.material_lighting_emissive_per_unit_ui
            )
            mesh_props.material_lighting_emissive_power = jstr(
                face_props.material_lighting_emissive_power_ui
            )
            mesh_props.material_lighting_emissive_quality = jstr(
                face_props.material_lighting_emissive_quality_ui
            )
            mesh_props.material_lighting_use_shader_gel = bool_str(
                face_props.material_lighting_use_shader_gel_ui
            )
            mesh_props.material_lighting_bounce_ratio = jstr(
                face_props.material_lighting_bounce_ratio_ui
            )

        # added two sided property to avoid open edges if collision prop
        if not h4:
            is_poop = (
                mesh_props.mesh_type == "_connected_geometry_mesh_type_poop"
            )
            if is_poop and (mesh_props.ladder or mesh_props.slip_surface):
                mesh_props.face_sides = (
                    "_connected_geometry_face_sides_two_sided"
                )
            # elif is_poop and ob != main_mesh:
            #     mesh_props.poop_render_only = True

    def apply_face_properties(self, context, export_obs, scene_coll, h4):
        valid_mesh_types = (
            "_connected_geometry_mesh_type_collision",
            "_connected_geometry_mesh_type_default",
            "_connected_geometry_mesh_type_poop",
        )
        mesh_obs = [
            ob
            for ob in export_obs
            if ob.nwo.object_type == "_connected_geometry_object_type_mesh"
            and ob.nwo.mesh_type in valid_mesh_types
        ]
        meshes = set([ob.data for ob in mesh_obs])
        me_ob_dict = {
            me: ob for me in meshes for ob in mesh_obs if ob.data == me
        }
        process = "Creating Meshes From Face Properties"
        len_me_ob_dict = len(me_ob_dict)
        any_face_props = False
        for idx, me in enumerate(me_ob_dict.keys()):
            linked_objects = me_ob_dict.get(me)
            # Check to ensure linked objects is not empty
            # (in the case that a mesh exists in the scene without users)
            if not linked_objects:
                continue

            is_linked = type(linked_objects) is list

            if is_linked:
                ob = linked_objects[0]
            else:
                ob = linked_objects

            me_nwo = me.nwo
            ob_nwo = ob.nwo

            face_layers = me_nwo.face_props

            if face_layers:
                update_progress(process, idx / len_me_ob_dict)
                any_face_props = True
                # must force on auto smooth to avoid Normals transfer errors
                me.use_auto_smooth = True

                # get bmesh rep now
                bm = bmesh.new()
                bm.from_mesh(me)

                split_objects = self.split_to_layers(
                    context, ob, ob_nwo, me, face_layers, scene_coll, h4, bm
                )

                # remove the original ob from this list
                split_objects.remove(ob)

                if not split_objects:
                    continue

                # Can skip the below for loop if linked_objects is not a list
                if is_linked:
                    # copy all new face split objects to all linked objects
                    for linked_ob in linked_objects:
                        for split_ob in split_objects:
                            new_ob = split_ob.copy()
                            new_ob.matrix_world = split_ob.matrix_world
                            scene_coll.link(new_ob)

                        if ob.modifiers.get("HaloDataTransfer", 0):
                            mod = linked_ob.modifiers.new(
                                "HaloDataTransfer", "DATA_TRANSFER"
                            )
                            mod.object = ob.modifiers[
                                "HaloDataTransfer"
                            ].object
                            mod.use_object_transform = False
                            mod.use_loop_data = True
                            mod.data_types_loops = {"CUSTOM_NORMAL"}

        if any_face_props:
            update_progress(process, 1)

    def z_rotate_and_apply(self, ob, angle):
        angle = radians(angle)
        axis = (0, 0, 1)
        pivot = ob.location
        M = (
            Matrix.Translation(pivot)
            @ Matrix.Rotation(angle, 4, axis)
            @ Matrix.Translation(-pivot)
        )

        ob.matrix_world = M @ ob.matrix_world
        bpy.ops.object.transform_apply(
            location=False, rotation=True, scale=False
        )

    def bake_animations(
        self,
        armature,
        export_animations,
        current_action,
        timeline_start,
        timeline_end,
        context,
    ):
        print("Baking animations...")
        timeline = context.scene
        for action in bpy.data.actions:
            if export_animations == "ALL" or current_action == action:
                armature.animation_data.action = action

                if action.use_frame_range:
                    frame_start = int(action.frame_start)
                    frame_end = int(action.frame_end)
                else:
                    frame_start = timeline_start
                    frame_end = timeline_end

                timeline.frame_start = timeline_start
                timeline.frame_end = timeline_end

                bpy.ops.object.mode_set(mode="POSE", toggle=False)
                bpy.ops.nla.bake(
                    frame_start=frame_start,
                    frame_end=frame_end,
                    only_selected=False,
                    visual_keying=True,
                    clear_constraints=True,
                    use_current_action=True,
                    clean_curves=True,
                    bake_types={"POSE"},
                )
                bpy.ops.object.mode_set(mode="OBJECT", toggle=False)

    def fix_armature_rotation(
        self,
        armature,
        sidecar_type,
        context,
        export_animations,
        current_action,
        timeline_start,
        timeline_end,
    ):
        forward = context.scene.nwo.forward_direction
        if forward != "x" and sidecar_type in ("MODEL", "FP ANIMATION"):
            armature.select_set(True)
            # bake animation to avoid issues on armature rotation
            if export_animations != "NONE" and 1 <= len(bpy.data.actions):
                self.bake_animations(
                    armature,
                    export_animations,
                    current_action,
                    timeline_start,
                    timeline_end,
                    context,
                )
            # apply rotation based on selected forward direction
            if forward == "y":
                self.z_rotate_and_apply(armature, -90)
            elif forward == "y-":
                self.z_rotate_and_apply(armature, 90)
            elif forward == "x-":
                self.z_rotate_and_apply(armature, 180)

            deselect_all_objects()

    def set_bone_names(self, bones):
        for bone in bones:
            override = bone.nwo.name_override
            if override:
                bone.name = override

    def apply_object_mesh_marker_properties(self, ob, asset_type, reach, nwo):
        # Apply final properties so we can rename objects (and also avoid complex checking in later code)
        # get mesh type
        if nwo.object_type == "_connected_geometry_object_type_mesh":
            if asset_type == "MODEL":
                nwo.region_name = true_region(ob.nwo)
                if (
                    nwo.mesh_type_ui
                    == "_connected_geometry_mesh_type_collision"
                ):
                    nwo.mesh_type = "_connected_geometry_mesh_type_collision"
                elif (
                    nwo.mesh_type_ui == "_connected_geometry_mesh_type_physics"
                ):
                    nwo.mesh_type = "_connected_geometry_mesh_type_physics"
                    nwo.mesh_primitive_type = nwo.mesh_primitive_type_ui
                elif (
                    nwo.mesh_type_ui
                    == "_connected_geometry_mesh_type_object_instance"
                    and not not_bungie_game()
                ):
                    nwo.mesh_type = (
                        "_connected_geometry_mesh_type_object_instance"
                    )
                else:
                    nwo.mesh_type = "_connected_geometry_mesh_type_default"

            if asset_type == "SCENARIO":
                if nwo.mesh_type_ui == "_connected_geometry_mesh_type_poop":
                    nwo.mesh_type = "_connected_geometry_mesh_type_poop"
                    nwo.poop_lighting = nwo.poop_lighting_ui
                    nwo.poop_pathfinding = nwo.poop_pathfinding_ui
                    nwo.poop_imposter_policy = nwo.poop_imposter_policy_ui
                    if (
                        nwo.poop_imposter_policy
                        != "_connected_poop_instance_imposter_policy_never"
                    ):
                        if not nwo.poop_imposter_transition_distance_auto:
                            nwo.poop_imposter_transition_distance = (
                                nwo.poop_imposter_transition_distance_ui
                            )
                            if not reach:
                                nwo.poop_imposter_brightness = (
                                    nwo.poop_imposter_brightness_ui
                                )

                    if nwo.poop_chops_portals_ui:
                        nwo.poop_chops_portals = "1"
                    if nwo.poop_does_not_block_aoe_ui:
                        nwo.poop_does_not_block_aoe = "1"
                    if nwo.poop_excluded_from_lightprobe_ui:
                        nwo.poop_excluded_from_lightprobe = "1"
                    if nwo.poop_decal_spacing_ui:
                        nwo.poop_decal_spacing = "1"

                    if not reach:
                        nwo.poop_streaming_priority = (
                            nwo.poop_streaming_priority_ui
                        )
                        nwo.poop_cinematic_properties = (
                            nwo.poop_cinematic_properties_ui
                        )
                        if nwo.poop_remove_from_shadow_geometry_ui:
                            nwo.poop_remove_from_shadow_geometry = "1"
                        if nwo.poop_disallow_lighting_samples_ui:
                            nwo.poop_disallow_lighting_samples = "1"

                elif (
                    nwo.mesh_type_ui
                    == "_connected_geometry_mesh_type_poop_collision"
                ):
                    nwo.mesh_type = (
                        "_connected_geometry_mesh_type_poop_collision"
                    )
                    nwo.poop_collision_type = nwo.poop_collision_type_ui

                elif nwo.mesh_type_ui == "_connected_geometry_mesh_type_plane":
                    if (
                        nwo.plane_type_ui
                        == "_connected_geometry_plane_type_portal"
                    ):
                        nwo.mesh_type = "_connected_geometry_mesh_type_portal"
                        nwo.portal_type = nwo.portal_type_ui
                        if nwo.portal_ai_deafening_ui:
                            nwo.portal_ai_deafening = "1"
                        if nwo.portal_blocks_sounds_ui:
                            nwo.portal_blocks_sounds = "1"
                        if nwo.portal_is_door_ui:
                            nwo.portal_is_door = "1"

                    elif (
                        nwo.plane_type_ui
                        == "_connected_geometry_plane_type_water_surface"
                    ):
                        nwo.mesh_type = (
                            "_connected_geometry_mesh_type_water_surface"
                        )
                        nwo.mesh_tessellation_density = (
                            nwo.mesh_tessellation_density_ui
                        )

                    elif (
                        nwo.plane_type_ui
                        == "_connected_geometry_plane_type_planar_fog_volume"
                    ):
                        nwo.mesh_type = (
                            "_connected_geometry_mesh_type_planar_fog_volume"
                        )
                        nwo.fog_appearance_tag = nwo.fog_appearance_tag_ui
                        nwo.fog_volume_depth = jstr(nwo.fog_volume_depth_ui)

                elif (
                    nwo.mesh_type_ui == "_connected_geometry_mesh_type_volume"
                ):
                    if (
                        nwo.volume_type_ui
                        == "_connected_geometry_volume_type_soft_ceiling"
                    ):
                        nwo.mesh_type = (
                            "_connected_geometry_mesh_type_boundary_surface"
                        )
                        nwo.boundary_surface_type = "_connected_geometry_boundary_surface_type_soft_ceiling"

                    elif (
                        nwo.volume_type_ui
                        == "_connected_geometry_volume_type_soft_kill"
                    ):
                        nwo.mesh_type = (
                            "_connected_geometry_mesh_type_boundary_surface"
                        )
                        nwo.boundary_surface_type = "_connected_geometry_boundary_surface_type_soft_kill"

                    elif (
                        nwo.volume_type_ui
                        == "_connected_geometry_volume_type_slip_surface"
                    ):
                        nwo.mesh_type = (
                            "_connected_geometry_mesh_type_boundary_surface"
                        )
                        nwo.boundary_surface_type = "_connected_geometry_boundary_surface_type_slip_surface"

                    elif (
                        nwo.volume_type_ui
                        == "_connected_geometry_volume_type_water_physics"
                    ):
                        nwo.mesh_type = "_connected_geometry_mesh_type_water_physics_volume"
                        nwo.water_volume_depth = jstr(
                            nwo.water_volume_depth_ui
                        )
                        nwo.water_volume_flow_direction = jstr(
                            nwo.water_volume_flow_direction_ui
                        )
                        nwo.water_volume_flow_velocity = jstr(
                            nwo.water_volume_flow_velocity_ui
                        )
                        nwo.water_volume_fog_color = color_3p_str(
                            nwo.water_volume_fog_color_ui
                        )
                        nwo.water_volume_fog_murkiness = jstr(
                            nwo.water_volume_fog_murkiness_ui
                        )

                    elif (
                        nwo.volume_type_ui
                        == "_connected_geometry_volume_type_cookie_cutter"
                    ):
                        nwo.mesh_type = (
                            "_connected_geometry_mesh_type_cookie_cutter"
                        )

                    elif (
                        nwo.volume_type_ui
                        == "_connected_geometry_volume_type_lightmap_exclude"
                        and not reach
                    ):
                        nwo.mesh_type = (
                            "_connected_geometry_mesh_type_obb_volume"
                        )
                        nwo.obb_volume_type = "_connected_geometry_mesh_obb_volume_type_lightmapexclusionvolume"

                    elif (
                        nwo.volume_type_ui
                        == "_connected_geometry_volume_type_streaming"
                        and not reach
                    ):
                        nwo.mesh_type = (
                            "_connected_geometry_mesh_type_obb_volume"
                        )
                        nwo.obb_volume_type = "_connected_geometry_mesh_obb_volume_type_streamingvolume"

                    elif (
                        nwo.volume_type_ui
                        == "_connected_geometry_volume_type_lightmap_region"
                        and reach
                    ):
                        nwo.mesh_type = (
                            "_connected_geometry_mesh_type_lightmap_region"
                        )

                    elif (
                        nwo.volume_type_ui
                        == "_connected_geometry_volume_type_poop_rain_blocker"
                    ):
                        nwo.poop_rain_occluder = "1"
                        if reach:
                            nwo.mesh_type = "_connected_geometry_mesh_type_poop_rain_blocker"
                        else:
                            nwo.mesh_type = (
                                "_connected_geometry_mesh_type_poop"
                            )
                    else:
                        nwo.mesh_type = "_connected_geometry_mesh_type_default"
                else:
                    nwo.mesh_type = "_connected_geometry_mesh_type_default"

            if asset_type == "SKY":
                nwo.region_name = true_region(ob.nwo)
                nwo.mesh_type = "_connected_geometry_mesh_type_default"

            if asset_type == "DECORATOR SET":
                nwo.mesh_type = "_connected_geometry_mesh_type_decorator"
                nwo.decorator_lod = str(nwo.decorator_lod_ui)

            if asset_type == "PARTICLE MODEL":
                nwo.mesh_type = "_connected_geometry_mesh_type_default"

            if asset_type == "PREFAB":
                if (
                    nwo.mesh_type_ui
                    == "_connected_geometry_mesh_type_poop_collision"
                ):
                    nwo.mesh_type = (
                        "_connected_geometry_mesh_type_poop_collision"
                    )
                elif (
                    nwo.mesh_type_ui
                    == "_connected_geometry_mesh_type_cookie_cutter"
                ):
                    nwo.mesh_type = (
                        "_connected_geometry_mesh_type_cookie_cutter"
                    )
                else:
                    nwo.mesh_type = "_connected_geometry_mesh_type_poop"

        # get marker type
        elif nwo.object_type == "_connected_geometry_object_type_marker":
            if asset_type == "MODEL":
                nwo.marker_all_regions = bool_str(nwo.marker_all_regions_ui)
                if (
                    nwo.marker_type_ui
                    == "_connected_geometry_marker_type_hint"
                ):
                    nwo.marker_type = "_connected_geometry_marker_type_hint"
                    nwo.marker_hint_length = jstr(nwo.marker_hint_length_ui)
                    ob.name = "hint_"
                    if nwo.marker_hint_type == "bunker":
                        ob.name += "bunker"
                    elif nwo.marker_hint_type == "corner":
                        ob.name += "corner_"
                        if nwo.marker_hint_side == "right":
                            ob.name += "right"
                        else:
                            ob.name += "left"

                    else:
                        if nwo.marker_hint_type == "vault":
                            ob.name += "vault_"
                        elif nwo.marker_hint_type == "mount":
                            ob.name += "mount_"
                        else:
                            ob.name += "hoist_"

                        if nwo.marker_hint_height == "step":
                            ob.name += "step"
                        elif nwo.marker_hint_height == "crouch":
                            ob.name += "crouch"
                        else:
                            ob.name += "stand"

                elif (
                    nwo.marker_type_ui
                    == "_connected_geometry_marker_type_pathfinding_sphere"
                ):
                    nwo.marker_type = (
                        "_connected_geometry_marker_type_pathfinding_sphere"
                    )
                    nwo.marker_sphere_radius = nwo.marker_sphere_radius_ui
                    nwo.marker_pathfinding_sphere_vehicle = bool_str(
                        nwo.marker_pathfinding_sphere_vehicle_ui
                    )
                    nwo.pathfinding_sphere_remains_when_open = bool_str(
                        nwo.pathfinding_sphere_remains_when_open_ui
                    )
                    nwo.pathfinding_sphere_with_sectors = bool_str(
                        nwo.pathfinding_sphere_with_sectors_ui
                    )

                elif (
                    nwo.marker_type_ui
                    == "_connected_geometry_marker_type_physics_constraint"
                ):
                    nwo.marker_type = nwo.physics_constraint_type
                    nwo.physics_constraint_parent = str(
                        nwo.physics_constraint_parent_ui
                    )
                    nwo.physics_constraint_child = str(
                        nwo.physics_constraint_child_ui
                    )
                    nwo.physics_constraint_uses_limits = bool_str(
                        nwo.physics_constraint_uses_limits_ui
                    )
                    nwo.hinge_constraint_minimum = jstr(
                        nwo.hinge_constraint_minimum_ui
                    )
                    nwo.hinge_constraint_maximum = jstr(
                        nwo.hinge_constraint_maximum_ui
                    )
                    nwo.cone_angle = jstr(nwo.cone_angle_ui)
                    nwo.plane_constraint_minimum = jstr(
                        nwo.plane_constraint_minimum_ui
                    )
                    nwo.plane_constraint_maximum = jstr(
                        nwo.plane_constraint_maximum_ui
                    )
                    nwo.twist_constraint_start = jstr(
                        nwo.twist_constraint_start_ui
                    )
                    nwo.twist_constraint_end = jstr(
                        nwo.twist_constraint_end_ui
                    )

                elif (
                    nwo.marker_type_ui
                    == "_connected_geometry_marker_type_target"
                ):
                    nwo.marker_type = "_connected_geometry_marker_type_target"
                elif (
                    nwo.marker_type_ui
                    == "_connected_geometry_marker_type_effects"
                ):
                    if not ob.name.startswith("fx_"):
                        ob.name = "fx_" + ob.name
                        nwo.marker_type = (
                            "_connected_geometry_marker_type_model"
                        )
                else:
                    nwo.marker_type = "_connected_geometry_marker_type_model"
                    if (
                        nwo.marker_type
                        == "_connected_geometry_marker_type_garbage"
                    ):
                        nwo.marker_velocity = vector_str(
                            nwo.marker_velocity_ui
                        )

            elif asset_type in ("SCENARIO", "PREFAB"):
                if (
                    nwo.marker_type_ui
                    == "_connected_geometry_marker_type_game_instance"
                ):
                    nwo.marker_game_instance_tag_name = (
                        nwo.marker_game_instance_tag_name_ui
                    )
                    if (
                        not reach
                        and nwo.marker_game_instance_tag_name.lower().endswith(
                            ".prefab"
                        )
                    ):
                        nwo.marker_type = (
                            "_connected_geometry_marker_type_prefab"
                        )
                    elif (
                        not reach
                        and nwo.marker_game_instance_tag_name.lower().endswith(
                            ".cheap_light"
                        )
                    ):
                        nwo.marker_type = (
                            "_connected_geometry_marker_type_cheap_light"
                        )
                    elif (
                        not reach
                        and nwo.marker_game_instance_tag_name.lower().endswith(
                            ".light"
                        )
                    ):
                        nwo.marker_type = (
                            "_connected_geometry_marker_type_light"
                        )
                    elif (
                        not reach
                        and nwo.marker_game_instance_tag_name.lower().endswith(
                            ".leaf"
                        )
                    ):
                        nwo.marker_type = (
                            "_connected_geometry_marker_type_falling_leaf"
                        )
                    else:
                        nwo.marker_type = (
                            "_connected_geometry_marker_type_game_instance"
                        )
                        nwo.marker_game_instance_tag_variant_name = (
                            nwo.marker_game_instance_tag_variant_name_ui
                        )
                        if not reach:
                            nwo.marker_game_instance_run_scripts = bool_str(
                                nwo.marker_game_instance_run_scripts_ui
                            )
                elif (
                    not reach
                    and nwo.marker_type_ui
                    == "_connected_geometry_marker_type_airprobe"
                ):
                    nwo.marker_type = (
                        "_connected_geometry_marker_type_airprobe"
                    )
                elif (
                    not reach
                    and nwo.marker_type_ui
                    == "_connected_geometry_marker_type_envfx"
                ):
                    nwo.marker_type = "_connected_geometry_marker_type_envfx"
                    nwo.marker_looping_effect = nwo.marker_looping_effect_ui
                elif (
                    not reach
                    and nwo.marker_type_ui
                    == "_connected_geometry_marker_type_lightcone"
                ):
                    nwo.marker_type = (
                        "_connected_geometry_marker_type_lightcone"
                    )
                    nwo.marker_light_cone_tag = nwo.marker_light_cone_tag_ui
                    nwo.marker_light_cone_color = color_3p_str(
                        nwo.marker_light_cone_color_ui
                    )
                    nwo.marker_light_cone_alpha = jstr(
                        nwo.marker_light_cone_alpha_ui
                    )
                    nwo.marker_light_cone_width = jstr(
                        nwo.marker_light_cone_width_ui
                    )
                    nwo.marker_light_cone_length = jstr(
                        nwo.marker_light_cone_length_ui
                    )
                    nwo.marker_light_cone_intensity = jstr(
                        nwo.marker_light_cone_intensity_ui
                    )
                    nwo.marker_light_cone_curve = (
                        nwo.marker_light_cone_curve_ui
                    )
                elif (
                    nwo.marker_type_ui
                    == "_connected_geometry_marker_type_water_volume_flow"
                ):
                    # water volume markers are for the blend scene only
                    self.unlink(ob)
                else:
                    nwo.marker_type = "_connected_geometry_marker_type_model"

            else:
                nwo.marker_type = "_connected_geometry_marker_type_model"

        #  Handling mesh level properties
        # --------------------------------------
        # NOTE not sure if mesh_compression needs to be exposed. Need to test what it does exactly
        # if nwo.mesh_type in ('_connected_geometry_mesh_type_default', '_connected_geometry_mesh_type_poop', '_connected_geometry_mesh_type_decorator', '_connected_geometry_mesh_type_water_surface'):
        #     nwo.mesh_compression = nwo.mesh_compression_ui
        if nwo.mesh_type in (
            "_connected_geometry_mesh_type_collision",
            "_connected_geometry_mesh_type_physics",
            "_connected_geometry_mesh_type_default",
            "_connected_geometry_mesh_type_poop",
        ):
            if asset_type in ("SCENARIO", "PREFAB") or nwo.mesh_type in (
                "_connected_geometry_mesh_type_collision",
                "_connected_geometry_mesh_type_physics",
            ):
                nwo.face_global_material = nwo.face_global_material_ui
            if (
                nwo.mesh_type != "_connected_geometry_mesh_type_physics"
                and nwo.face_two_sided_ui
            ):
                nwo.face_sides = "_connected_geometry_face_sides_two_sided"
            if nwo.mesh_type in (
                "_connected_geometry_mesh_type_default",
                "_connected_geometry_mesh_type_poop",
            ):
                if nwo.precise_position_ui:
                    nwo.precise_position = bool_str(nwo.precise_position_ui)
                if nwo.face_draw_distance_active:
                    nwo.face_draw_distance = nwo.face_draw_distance_ui
                if nwo.texcoord_usage_active:
                    nwo.texcoord_usage = nwo.texcoord_usage_ui
            if asset_type in ("SCENARIO", "PREFAB"):
                h4_structure = (
                    not reach
                    and nwo.mesh_type
                    == "_connected_geometry_mesh_type_default"
                )
                if nwo.face_type_active or h4_structure:
                    if h4_structure:
                        nwo.face_type = "_connected_geometry_face_type_sky"
                    else:
                        nwo.face_type = nwo.face_type_ui
                    if nwo.face_type == "_connected_geometry_face_type_sky":
                        nwo.sky_permutation_index = str(
                            nwo.sky_permutation_index_ui
                        )
                if nwo.face_mode_active:
                    nwo.face_mode = nwo.face_mode_ui
                if nwo.ladder_active:
                    nwo.ladder = bool_str(nwo.ladder_ui)
                if nwo.slip_surface_active:
                    nwo.slip_surface = bool_str(nwo.slip_surface_ui)
                if nwo.decal_offset_active:
                    nwo.decal_offset = bool_str(nwo.decal_offset_ui)
                if nwo.group_transparents_by_plane_active:
                    nwo.group_transparents_by_plane = bool_str(
                        nwo.group_transparents_by_plane_ui
                    )
                if nwo.no_shadow_active:
                    nwo.no_shadow = bool_str(nwo.no_shadow_ui)
                if nwo.no_lightmap_active:
                    nwo.no_lightmap = bool_str(nwo.no_lightmap_ui)
                if nwo.no_pvs_active:
                    nwo.no_pvs = bool_str(nwo.no_pvs_ui)
                if nwo.uvmirror_across_entire_model_active:
                    nwo.uvmirror_across_entire_model = bool_str(
                        nwo.uvmirror_across_entire_model_ui
                    )
                if nwo.lightmap_additive_transparency_active:
                    nwo.lightmap_additive_transparency = (
                        nwo.lightmap_additive_transparency_ui
                    )
                if nwo.lightmap_resolution_scale_active:
                    nwo.lightmap_resolution_scale = jstr(
                        nwo.lightmap_resolution_scale_ui
                    )
                if nwo.lightmap_photon_fidelity_active:
                    nwo.lightmap_photon_fidelity = (
                        nwo.lightmap_photon_fidelity_ui
                    )
                if nwo.lightmap_type_active:
                    nwo.lightmap_type = nwo.lightmap_type_ui
                if nwo.lightmap_analytical_bounce_modifier_active:
                    nwo.lightmap_analytical_bounce_modifier = jstr(
                        nwo.lightmap_analytical_bounce_modifier_ui
                    )
                if nwo.lightmap_general_bounce_modifier_active:
                    nwo.lightmap_general_bounce_modifier = jstr(
                        nwo.lightmap_general_bounce_modifier_ui
                    )
                if nwo.lightmap_translucency_tint_color_active:
                    nwo.lightmap_translucency_tint_color = color_3p_str(
                        nwo.lightmap_translucency_tint_color_ui
                    )
                if nwo.lightmap_lighting_from_both_sides_active:
                    nwo.lightmap_lighting_from_both_sides = bool_str(
                        nwo.lightmap_lighting_from_both_sides_ui
                    )
                if nwo.emissive_active:
                    nwo.material_lighting_attenuation_falloff = jstr(
                        nwo.material_lighting_attenuation_falloff_ui
                    )
                    nwo.material_lighting_attenuation_cutoff = jstr(
                        nwo.material_lighting_attenuation_cutoff_ui
                    )
                    nwo.material_lighting_emissive_focus = jstr(
                        nwo.material_lighting_emissive_focus_ui
                    )
                    nwo.material_lighting_emissive_color = color_3p_str(
                        nwo.material_lighting_emissive_color_ui
                    )
                    nwo.material_lighting_emissive_per_unit = bool_str(
                        nwo.material_lighting_emissive_per_unit_ui
                    )
                    nwo.material_lighting_emissive_power = jstr(
                        nwo.material_lighting_emissive_power_ui
                    )
                    nwo.material_lighting_emissive_quality = jstr(
                        nwo.material_lighting_emissive_quality_ui
                    )
                    nwo.material_lighting_use_shader_gel = bool_str(
                        nwo.material_lighting_use_shader_gel_ui
                    )
                    nwo.material_lighting_bounce_ratio = jstr(
                        nwo.material_lighting_bounce_ratio_ui
                    )

    def strip_prefix(self, ob):
        if ob.name.lower().startswith(("+soft_ceiling", "+slip_surface")):
            ob.name = ob.name[14:]
        if ob.name.lower().startswith(
            ("+cookie", "+portal", "+flair", "+water")
        ):
            ob.name = ob.name[7:]
        if ob.name.lower().startswith(
            ("frame ", "frame_", "+flair", "+water")
        ):
            ob.name = ob.name[6:]
        if ob.name.lower().startswith(("bone ", "bone_", "+seam")):
            ob.name = ob.name[5:]
        if ob.name.lower().startswith(("bip ", "bip_", "+fog")):
            ob.name = ob.name[4:]
        elif ob.name.lower().startswith(("b ", "b_")):
            ob.name = ob.name[2:]
        elif ob.name.lower().startswith(("#", "?", "@", "$", "'")):
            ob.name = ob.name[1:]
        elif ob.name.lower().startswith(("%")):
            ob.name = ob.name[1:]
            if ob.name.lower().startswith(("?", "!", "+", "-", ">", "*")):
                ob.name = ob.name[1:]
                if ob.name.lower().startswith(("?", "!", "+", "-", ">", "*")):
                    ob.name = ob.name[1:]
                    if ob.name.lower().startswith(
                        ("?", "!", "+", "-", ">", "*")
                    ):
                        ob.name = ob.name[1:]

        ob.name = ob.name.strip(" _")

    def set_object_type(self, ob, ob_type, nwo, is_mesh_loose):
        if ob_type == "LIGHT":
            nwo.object_type = "_connected_geometry_object_type_light"
        elif ob_type == "CAMERA":
            # don't export cameras
            self.unlink(ob)
            # ob.nwo.object_type = '_connected_geometry_object_type_animation_camera'
        elif ob_type == "ARMATURE":
            nwo.object_type = "_connected_geometry_object_type_frame"
        elif ob_type == "EMPTY":
            if (
                ob.children
                or nwo.object_type_ui
                != "_connected_geometry_object_type_marker"
            ):
                nwo.object_type = "_connected_geometry_object_type_frame"
            else:
                nwo.object_type = "_connected_geometry_object_type_marker"

        elif is_mesh_loose:
            nwo.object_type = nwo.object_type_ui
        else:
            # Mesh invalid, don't export
            print(f"{ob.name} is invalid. Skipping export")
            self.unlink(ob)

            # strip_prefix(ob)
            # if not_bungie_game():
            #     apply_namespaces(ob, asset)

    def apply_namespaces(self, ob, asset):
        """Reads the objects halo properties and then applies the appropriate maya namespace, or optionally a set namespace if a second arg is passed"""
        nwo = ob.nwo
        namespace = asset
        if nwo.object_type == "_connected_geometry_object_type_frame":
            namespace = "frame"
        elif nwo.object_type == "_connected_geometry_object_type_marker":
            namespace = "marker"
        elif nwo.mesh_type == "_connected_geometry_mesh_type_collision":
            namespace = "collision"
        elif nwo.mesh_type == "_connected_geometry_mesh_type_physics":
            namespace = "physics"
        elif nwo.mesh_type == "_connected_geometry_mesh_type_object_instance":
            namespace = "flair"
        elif nwo.mesh_type == "_connected_geometry_mesh_type_poop":
            namespace = "instance"
        elif nwo.mesh_type == "_connected_geometry_mesh_type_portal":
            namespace = "portal"
        elif nwo.mesh_type == "_connected_geometry_mesh_type_seam":
            namespace = "seam"
        elif nwo.mesh_type == "_connected_geometry_mesh_type_water_surface":
            namespace = "water_surface"
        elif (
            nwo.mesh_type == "_connected_geometry_mesh_type_planar_fog_volume"
        ):
            namespace = "fog"
        elif nwo.mesh_type == "_connected_geometry_mesh_type_boundary_surface":
            namespace = "boundary_surface"
        elif (
            nwo.mesh_type
            == "_connected_geometry_mesh_type_water_physics_volume"
        ):
            namespace = "water_physics"
        elif nwo.mesh_type == "_connected_geometry_mesh_type_poop_collision":
            namespace = "instance_collision"
        elif nwo.mesh_type == "_connected_geometry_mesh_type_poop_physics":
            namespace = "instance_physics"
        elif nwo.mesh_type == "_connected_geometry_mesh_type_cookie_cutter":
            namespace = "cookie_cutter"
        elif nwo.mesh_type == "_connected_geometry_mesh_type_obb_volume":
            namespace = "obb_volume"
        elif nwo.mesh_type == "_connected_geometry_mesh_type_lightmap_region":
            namespace = "lightmap_region"

        ob.name = f"{namespace}:{ob.name}"

    def set_animation_overrides(self, model_armature, current_action):
        if model_armature is not None and len(bpy.data.actions) > 0:
            deselect_all_objects()
            model_armature.select_set(True)
            set_active_object(model_armature)
            for action in bpy.data.actions:
                try:
                    model_armature.animation_data.action = action
                    forced_type = dot_partition(action.name.upper(), True)
                    action.name = dot_partition(action.name)
                    if forced_type in valid_animation_types:
                        action.nwo.animation_type = forced_type
                    if action.nwo.name_override == "":
                        animation = action.name
                        if (
                            animation.rpartition(".")[2]
                            not in valid_animation_types
                        ):
                            animation = (
                                f"{animation}.{action.nwo.animation_type}"
                            )
                        action.nwo.name_override = animation
                except:
                    pass

            if current_action is not None:
                model_armature.animation_data.action = current_action

            deselect_all_objects()

    def set_object_mode(self, context):
        # try: # wrapped this in a try as the user can encounter an assert if no object is selected. No reason for this to crash the export
        if not context.object:
            set_active_object(context.view_layer.objects[0])

        bpy.ops.object.mode_set(mode="OBJECT", toggle=False)

    # except:
    #     print('WARNING: Unable to test mode')

    def get_current_action(self, context, model_armature):
        deselect_all_objects()
        model_armature.select_set(True)
        set_active_object(model_armature)
        current_action = context.active_object.animation_data.action
        deselect_all_objects()
        return current_action

    def exit_local_view(self, context):
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                space = area.spaces[0]
                if space.local_view:
                    for region in area.regions:
                        if region.type == "WINDOW":
                            override = {"area": area, "region": region}
                            bpy.ops.view3d.localview(override)

    def RotateScene(self, scene_obs, model_armature):
        deselect_all_objects()
        angle_z = radians(90)
        axis_z = (0, 0, 1)
        pivot = Vector((0.0, 0.0, 0.0))
        for ob in scene_obs:
            if ob != model_armature:
                M = (
                    Matrix.Translation(pivot)
                    @ Matrix.Rotation(angle_z, 4, axis_z)
                    @ Matrix.Translation(-pivot)
                )
                ob.matrix_world = M @ ob.matrix_world

    def unhide_collections(self, context):
        layer_collection = context.view_layer.layer_collection
        self.recursive_nightmare(layer_collection)

    def recursive_nightmare(self, collections):
        coll_children = collections.children
        for collection in coll_children:
            collection.hide_viewport = False
            if collection.children:
                self.recursive_nightmare(collection)

    def set_timeline_range(self, context):
        scene = context.scene
        timeline_start = scene.frame_start
        timeline_end = scene.frame_end

        scene.frame_start = 0
        scene.frame_end = 0

        return timeline_start, timeline_end

    def FixLightsRotations(self, lights_list):
        deselect_all_objects()
        angle_x = radians(90)
        angle_z = radians(-90)
        axis_x = (1, 0, 0)
        axis_z = (0, 0, 1)
        for ob in lights_list:
            pivot = ob.location
            M = (
                Matrix.Translation(pivot)
                @ Matrix.Rotation(angle_x, 4, axis_x)
                @ Matrix.Rotation(angle_z, 4, axis_z)
                @ Matrix.Translation(-pivot)
            )
            ob.matrix_world = M @ ob.matrix_world

    def get_decorator_lod_count(self, halo_objects, asset_is_decorator):
        lod_count = 0
        if asset_is_decorator:
            for ob in halo_objects.decorators:
                ob_lod = ob.nwo.decorator_lod_ui
                if ob_lod > lod_count:
                    lod_count = ob_lod

        return lod_count

    def disable_excluded_collections(self, context):
        child_coll = context.view_layer.layer_collection.children
        for layer in child_coll:
            self.hide_excluded_recursively(layer)

    def hide_excluded_recursively(self, layer):
        if layer.collection.name.startswith("+exclude") and layer.is_visible:
            layer.exclude = True
        for child_layer in layer.children:
            self.hide_excluded_recursively(child_layer)

    #####################################################################################
    #####################################################################################
    # ARMATURE FUNCTIONS
    def get_scene_armature(self, export_obs, asset, scene_coll):
        for ob in export_obs:
            if ob.type == "ARMATURE":
                return ob, False

        return self.add_temp_armature(export_obs, asset, scene_coll), True

    def add_temp_armature(self, export_obs, asset, scene_coll):
        arm_name = f"{asset}_world"
        arm = bpy.data.armatures.new(arm_name)
        arm_ob = bpy.data.objects.new(arm_name, arm)
        scene_coll.link(arm_ob)
        set_active_object(arm_ob)
        arm_ob.select_set(True)
        bpy.ops.object.mode_set(mode="EDIT", toggle=False)

        bone_name = "implied_root_node"
        bone = arm.edit_bones.new(bone_name)
        bone.tail[1] = 1
        bone.tail[2] = 0

        bpy.ops.object.mode_set(mode="OBJECT", toggle=False)

        arm_ob.select_set(False)

        for ob in export_obs:
            if not ob.parent:
                ob.parent = arm_ob
                ob.parent_bone = bone_name
                ob.parent_type = 'BONE'

        return arm_ob

    def fix_bad_parenting(self, model_armature, export_obs):
        bones = model_armature.data.edit_bones
        mesh_obs = [ob for ob in export_obs if ob.type == "MESH"]
        meshes = set([ob.data for ob in mesh_obs])
        me_ob_dict = {
            me: ob for me in meshes for ob in mesh_obs if ob.data == me
        }
        for item in me_ob_dict.items():
            me = item[0]
            ob = item[1]
            nwo = ob.nwo
            mesh_type = nwo.mesh_type
            marker = (
                nwo.object_type == "_connected_geometry_object_type_marker"
            )
            vertices = me.vertices

            set_active_object(ob)
            ob.select_set(True)

            if ob.vertex_groups:
                bpy.ops.object.vertex_group_lock(action="UNLOCK", mask="ALL")

                # force bone parenting for physics
                parent_type = ob.parent_type
                if (
                    marker
                    or mesh_type == "_connected_geometry_mesh_type_physics"
                ) and parent_type != "BONE":
                    vertex_groups = ob.vertex_groups
                    for vertex_group in vertex_groups:
                        for i, w in self.get_weights(
                            ob, vertex_group, vertices
                        ):
                            if w > 0:
                                bone_name = vertex_group.name
                                for bone in bones:
                                    if bone.name == bone_name:
                                        break
                                else:
                                    bone_name = bones[0].name

                                break

                    parent_type = "BONE"
                    ob.parent_bone = bone_name

                elif mesh_type == "_connected_geometry_mesh_type_collision":
                    bpy.ops.object.vertex_group_clean(
                        limit=0.9999, keep_single=False
                    )

                else:
                    bpy.ops.object.vertex_group_normalize_all()

    def get_weights(self, ob, vertex_group, vertices):
        group_index = vertex_group.index
        for i, v in enumerate(vertices):
            for g in v.groups:
                if g.group == group_index:
                    yield (i, g.weight)
                    break

        # for ob in export_obs:
        #     if (ob.parent == model_armature and ob.parent_type == 'OBJECT') and not any([mod != ' ARMATURE' for mod in ob.modifiers]):
        #         deselect_all_objects()
        #         ob.select_set(True)
        #         set_active_object(model_armature)
        #         if (CheckType.render or CheckType.collision):
        #             bpy.ops.object.parent_set(type='ARMATURE', keep_transform=True)
        #         else:
        #             bpy.ops.object.parent_set(type='BONE', keep_transform=True)

    #####################################################################################
    #####################################################################################
    # BONE FUNCTIONS

    def get_bone_list(self, model_armature, deform_only, h4):
        boneslist = {}
        arm = model_armature.name
        boneslist.update({arm: self.get_armature_props(h4)})
        index = 0
        frameIDs = (
            self.openCSV()
        )  # sample function call to get FrameIDs CSV values as dictionary
        f1 = frameIDs.keys()
        f2 = frameIDs.values()
        bone_list = model_armature.data.bones
        if deform_only:
            bone_list = self.get_deform_bones_only(bone_list)
        for b in bone_list:
            b_nwo = b.nwo
            if b_nwo.frame_id1 == "":
                FrameID1 = list(f1)[index]
            else:
                FrameID1 = b_nwo.frame_id1
            if b_nwo.frame_id2 == "":
                FrameID2 = list(f2)[index]
            else:
                FrameID2 = b_nwo.frame_id2
            index += 1
            boneslist.update(
                {
                    b.name: self.getBoneProperties(
                        FrameID1,
                        FrameID2,
                        b_nwo.object_space_node,
                        b_nwo.replacement_correction_node,
                        b_nwo.fik_anchor_node,
                    )
                }
            )

        return boneslist

    def get_deform_bones_only(self, bone_list):
        return [b for b in bone_list if b.use_deform]

    def get_armature_props(self, h4):
        node_props = {}

        node_props.update(
            {"bungie_object_type": "_connected_geometry_object_type_frame"}
        ),
        node_props.update({"bungie_frame_ID1": "8078"}),
        node_props.update({"bungie_frame_ID2": "378163771"}),
        if h4:
            node_props.update({"bungie_frame_world": "1"}),

        return node_props

    def getBoneProperties(
        self,
        FrameID1,
        FrameID2,
        object_space_node,
        replacement_correction_node,
        fik_anchor_node,
    ):
        node_props = {}

        node_props.update(
            {"bungie_object_type": "_connected_geometry_object_type_frame"}
        ),
        node_props.update({"bungie_frame_ID1": FrameID1}),
        node_props.update({"bungie_frame_ID2": FrameID2}),

        if object_space_node:
            node_props.update({"bungie_is_object_space_offset_node": "1"}),
        if replacement_correction_node:
            node_props.update({"bungie_is_replacement_correction_node": "1"}),
        if fik_anchor_node:
            node_props.update({"bungie_is_fik_anchor_node": "1"}),

        node_props.update({"bungie_object_animates": "1"}),
        node_props.update({"halo_export": "1"}),

        return node_props

    def openCSV(self):
        script_folder_path = path.dirname(path.dirname(__file__))
        filepath = path.join(script_folder_path, "export", "frameidlist.csv")

        frameIDList = {}
        with open(filepath) as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=",")
            for row in csv_reader:
                frameIDList.update({row[0]: row[1]})

        return frameIDList

    def ApplyPredominantShaderNames(self, poops):
        for ob in poops:
            ob.nwo.poop_predominant_shader_name = self.GetProminantShaderName(
                ob
            )

    def GetProminantShaderName(self, ob):
        predominant_shader = ""
        slots = ob.material_slots
        for s in slots:
            material = s.material
            if is_shader(material):
                shader_path = material.nwo.shader_path
                if shader_path.rpartition(".")[0] != "":
                    shader_path = shader_path.rpartition(".")[0]
                shader_path.replace(get_tags_path(), "")
                shader_path.replace(get_tags_path().lower(), "")
                shader_type = material.nwo.Shader_Type
                predominant_shader = f"{shader_path}.{shader_type}"
                break

        return predominant_shader

    def setup_poop_proxies(self, export_obs, h4):
        poops = [
            ob
            for ob in export_obs
            if ob.nwo.mesh_type == "_connected_geometry_mesh_type_poop"
        ]
        if poops:
            any_poop_child = any([ob for ob in poops if ob.children])
        else:
            return None

        if any_poop_child:
            process = "Copying Instanced Geometry Proxy Meshes"
            update_progress(process, 0)
            meshes = set([ob.data for ob in poops])
            me_ob_dict = {
                me: ob for me in meshes for ob in poops if ob.data == me
            }
            len_me_ob_dict = len(me_ob_dict)

            for idx, me in enumerate(me_ob_dict.keys()):
                update_progress(process, idx / len_me_ob_dict)
                linked_poops = me_ob_dict.get(me)

                if type(linked_poops) is not list:
                    continue

                for idx, ob in enumerate(linked_poops):
                    if ob.children:
                        child_ob_set = self.get_poop_children(ob, h4)
                        linked_obs = linked_poops.remove(idx)
                        break
                else:
                    continue

                for ob in linked_obs:
                    for ob in ob.children:
                        self.unlink(ob)

                    # attach child obs to linked obs
                    for child in child_ob_set.keys():
                        local_matrix = child_ob_set.get(child)[1]
                        child_copy = child.copy()
                        child_copy.parent = ob
                        child_copy.matrix_local = local_matrix
                        if h4:
                            world_matrix = Matrix(child_copy.matrix_world)
                            child_copy.parent = None
                            child.matrix_world = world_matrix

            update_progress(process, 1)

    def get_poop_children(self, ob, h4):
        child_ob_set = dict.fromkeys(ob.children)

        child_set = {}  # 'bullet', 'player', 'cookie', 'invis'
        for child in ob.children:
            nwo_mesh_type = child.nwo.mesh_type
            nwo_coll_type = child.nwo.poop_collision_type

            if nwo_mesh_type == "_connected_geometry_mesh_type_cookie_cutter":
                if "cookie" not in child_set:
                    child_ob_set[child] = [
                        "cookie",
                        Matrix(child.matrix_local),
                    ]
                    child_set.add("cookie")

            elif (
                nwo_mesh_type != "_connected_geometry_mesh_type_poop_collision"
            ):
                print(
                    f"Found invalid mesh type parented to instance: Invalid Mesh: {child.name}"
                )
                self.unlink(ob)

            elif (
                nwo_coll_type
                == "_connected_geometry_poop_collision_type_invisible_wall"
                and h4
            ):
                if "invis" not in child_set:
                    child_ob_set[child] = ["invis", Matrix(child.matrix_local)]
                    child_set.add("invis")

            elif (
                nwo_coll_type
                == "_connected_geometry_poop_collision_type_play_collision"
            ):
                if "player" not in child_set:
                    child_ob_set[child] = [
                        "player",
                        Matrix(child.matrix_local),
                    ]
                    child_set.add("player")
                    if not h4:
                        nwo_mesh_type = (
                            "_connected_geometry_mesh_type_poop_physics"
                        )

            elif (
                nwo_coll_type
                == "_connected_geometry_poop_collision_type_bullet_collision"
            ):
                if "bullet" not in child_set:
                    child_ob_set[child] = [
                        "bullet",
                        Matrix(child.matrix_local),
                    ]
                    child_set.add("bullet")
                    if not h4:
                        child.nwo.face_mode = (
                            "_connected_geometry_face_mode_collision_only"
                        )

            elif (
                nwo_coll_type
                == "_connected_geometry_poop_collision_type_default"
                and "player" not in child_set
                and "bullet" not in child_set
            ):
                child_ob_set[child] = ["default", Matrix(child.matrix_local)]
                child_set.add("bullet")
                child_set.add("player")

            elif (
                nwo_coll_type
                == "_connected_geometry_poop_collision_type_default"
                and "player" not in child_set
            ):
                child_ob_set[child] = ["player", Matrix(child.matrix_local)]
                child_set.add("player")
                if not h4:
                    nwo_mesh_type = (
                        "_connected_geometry_mesh_type_poop_physics"
                    )

            elif (
                nwo_coll_type
                == "_connected_geometry_poop_collision_type_default"
                and "bullet" not in child_set
            ):
                child_ob_set[child] = ["bullet", Matrix(child.matrix_local)]
                child_set.add("player")

        return child_ob_set

    def fix_materials(self, ob, me, materials_list, override_mat):
        # fix multi user materials
        slots = ob.material_slots
        mats = dict.fromkeys(slots)
        for idx, slot in enumerate(slots):
            s_name = slot.material.name
            if s_name not in mats.keys():
                mats[s_name] = idx
            else:
                bpy.ops.object.mode_set(mode="EDIT", toggle=False)
                ob.active_material_index = idx
                bpy.ops.object.material_slot_select()
                ob.active_material_index = mats[s_name]
                bpy.ops.object.material_slot_assign()
                bpy.ops.object.mode_set(mode="OBJECT", toggle=False)

        disable_prints()
        bpy.ops.object.material_slot_remove_unused()
        enable_prints()

        if not slots:
            # append the new material to the object
            me.materials.append(override_mat)

    def markerify(self, export_obs, scene_coll, context):
        # get a list of meshes which are nodes
        mesh_markers = [
            ob
            for ob in export_obs
            if ob.nwo.object_type == "_connected_geometry_object_type_marker"
            and ob.type == "MESH"
        ]

        # For each mesh node create an empty with the same Halo props and transforms
        # Mesh objects need their names saved, so we make a dict. Names are stored so that the node can have the exact same name. We add a temp name to each mesh object

        if not mesh_markers:
            return None

        process = "Converting Mesh Markers to Empties"
        update_progress(process, 0)
        len_mesh_markers = len(mesh_markers)

        for idx, ob in enumerate(mesh_markers):
            ob_nwo = ob.nwo
            node = bpy.data.objects.new(ob.name, None)
            scene_coll.link(node)
            if ob.parent is not None:
                node.parent = ob.parent
                node.parent_type = ob.parent_type
                if node.parent_type == "BONE":
                    node.parent_bone = ob.parent_bone

            node.matrix_local = ob.matrix_local
            node.scale = ob.scale
            node_nwo = node.nwo
            if ob_nwo.marker_type in (
                "_connected_geometry_marker_type_pathfinding_sphere",
                "_connected_geometry_marker_type_target",
            ):  # need to handle pathfinding spheres / targets differently. Dimensions aren't retained for empties, so instead we can store the radius in the marker sphere radius
                node_nwo.marker_sphere_radius = max(ob.dimensions) / 2

            # copy the node props from the mesh to the empty
            self.set_node_props(ob_nwo, node_nwo)

            self.unlink(ob)
            update_progress(process, idx / len_mesh_markers)

        update_progress(process, 1)

        # delete_object_list(context, mesh_markers)

    def set_node_props(self, ob_halo, node_halo):
        node_halo.bsp_name = ob_halo.bsp_name

        node_halo.permutation_name = ob_halo.permutation_name

        node_halo.object_type = ob_halo.object_type
        node_halo.marker_type = ob_halo.marker_type

        node_halo.region_name = ob_halo.region_name
        node_halo.marker_all_regions = ob_halo.marker_all_regions
        node_halo.marker_velocity = ob_halo.marker_velocity

        node_halo.marker_game_instance_tag_name = (
            ob_halo.marker_game_instance_tag_name
        )
        node_halo.marker_game_instance_tag_variant_name = (
            ob_halo.marker_game_instance_tag_variant_name
        )
        node_halo.marker_game_instance_run_scripts = (
            ob_halo.marker_game_instance_run_scripts
        )

        node_halo.marker_pathfinding_sphere_vehicle = (
            ob_halo.marker_pathfinding_sphere_vehicle
        )
        node_halo.pathfinding_sphere_remains_when_open = (
            ob_halo.pathfinding_sphere_remains_when_open
        )
        node_halo.pathfinding_sphere_with_sectors = (
            ob_halo.pathfinding_sphere_with_sectors
        )

        node_halo.physics_constraint_parent = ob_halo.physics_constraint_parent
        node_halo.physics_constraint_child = ob_halo.physics_constraint_child
        node_halo.physics_constraint_type = ob_halo.physics_constraint_type
        node_halo.physics_constraint_uses_limits = (
            ob_halo.physics_constraint_uses_limits
        )

        node_halo.marker_hint_length = ob_halo.marker_hint_length

        node_halo.marker_looping_effect = ob_halo.marker_looping_effect

        node_halo.marker_light_cone_tag = ob_halo.marker_light_cone_tag
        node_halo.marker_light_cone_color = ob_halo.marker_light_cone_color
        node_halo.marker_light_cone_alpha = ob_halo.marker_light_cone_alpha
        node_halo.marker_light_cone_intensity = (
            ob_halo.marker_light_cone_intensity
        )
        node_halo.marker_light_cone_width = ob_halo.marker_light_cone_width
        node_halo.marker_light_cone_length = ob_halo.marker_light_cone_length
        node_halo.marker_light_cone_curve = ob_halo.marker_light_cone_curve

    #####################################################################################
    #####################################################################################
    # HALO CLASS

    def halo_objects_init(self):
        self.frames = []
        self.markers = []

        self.render = []
        self.render_perms = set()

        self.collision = []
        self.collision_perms = set()

        self.physics = []
        self.physics_perms = set()

        self.design = []
        self.design_perms = set()
        self.design_bsps = set()

        self.structure = []
        self.structure_perms = set()
        self.structure_bsps = set()

    def halo_objects(self, asset_type, export_obs):
        render_asset = asset_type != "SCENARIO"

        for ob in export_obs:
            nwo = ob.nwo
            object_type = nwo.object_type
            mesh_type = nwo.mesh_type
            permutation = nwo.permutation_name

            if render_asset:
                default = mesh_type in (
                    "_connected_geometry_mesh_type_default",
                    "_connected_geometry_mesh_type_decorator",
                )
            else:
                design = mesh_type in (
                    "_connected_geometry_mesh_type_planar_fog_volume",
                    "_connected_geometry_mesh_type_boundary_surface",
                    "_connected_geometry_mesh_type_water_physics_volume",
                    "_connected_geometry_mesh_type_poop_rain_blocker",
                    "_connected_geometry_mesh_type_poop_vertical_rain_sheet",
                )

            if object_type == "_connected_geometry_object_type_frame":
                self.frames.append(ob)

            elif render_asset:
                if object_type == "_connected_geometry_object_type_marker":
                    self.markers.append(ob)
                elif default:
                    self.render.append(ob)
                    self.render_perms.add(permutation)
                elif mesh_type == "_connected_geometry_mesh_type_collision":
                    self.collision.append(ob)
                    self.collision_perms.add(permutation)
                else:
                    self.physics.append(ob)
                    self.physics_perms.add(permutation)
            else:
                bsp = nwo.bsp_name
                if design:
                    self.design.append(ob)
                    self.design_perms.add(permutation)
                    self.design_bsps.add(bsp)
                else:
                    self.structure.append(ob)
                    self.structure_perms.add(permutation)
                    self.structure_bsps.add(bsp)


#####################################################################################
#####################################################################################
# VARIOUS FUNCTIONS
