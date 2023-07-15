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

import os
import bmesh
import bpy
from os import path
import csv
from math import radians
from mathutils import Matrix, Vector
import xml.etree.ElementTree as ET

from io_scene_foundry.tools.shader_finder import find_shaders
from ..utils.nwo_utils import (
    bool_str,
    closest_bsp_object,
    color_3p_str,
    color_4p_str,
    deselect_all_objects,
    disable_prints,
    dot_partition,
    enable_prints,
    get_prefix,
    jstr,
    layer_face_count,
    layer_faces,
    print_warning,
    run_tool,
    set_active_object,
    is_shader,
    get_tags_path,
    not_bungie_game,
    sort_alphanum,
    true_region,
    true_bsp,
    true_permutation,
    update_job,
    update_progress,
    vector_str,
    frame_prefixes,
)

render_mesh_types_full = [
    "_connected_geometry_mesh_type_default",
    "_connected_geometry_mesh_type_poop",
    "_connected_geometry_mesh_type_water_surface"
]

RENDER_ONLY_FACE_TYPES = (
    "_connected_geometry_face_mode_render_only",
    "_connected_geometry_face_mode_lightmap_only"
    "_connected_geometry_face_mode_shadow_only"
)

# Reach special materials

INVISIBLE_SKY = "InvisibleSky"
SEAM_SEALER = "SeamSealer"
COLLISION_ONLY = "CollisionOnly"
SPHERE_COLLISION_ONLY = "SphereCollisionOnly"
LIGHTMAP_ONLY = "LightmapOnly"
SHADOW_ONLY = "ShadowOnly"


#####################################################################################
#####################################################################################
# MAIN CLASS
class PrepareScene:
    def __init__(
        self,
        context,
        asset,
        sidecar_type,
        game_version,
        export_animations,
        export_gr2_files,
        export_all_perms,
        export_all_bsps,
    ):
        print("\nPreparing Export Scene")
        print(
            "-----------------------------------------------------------------------\n"
        )
        # time it!
        # NOTE skipping timing as export is really fast now
        # start = time.perf_counter()
        self.warning_hit = False

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

        #rotate -90 if this is a Reach Scenario/Decorator/Particle Model
        if not h4 and sidecar_type in ('SCENARIO', 'DECORATOR SET', 'PARTICLE MODEL'):
            self.rotate_scene(context.view_layer.objects)

        # make objects linked to scene real and local
        # Context override selection does not work here
        disable_prints()

        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.duplicates_make_real()
        bpy.ops.object.make_local(type="ALL")
        bpy.ops.object.select_all(action="DESELECT")

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

        scene_coll = context.scene.collection.objects

        export_obs = context.view_layer.objects[:]

        # build proxy instances from structure
        if h4:
            proxy_owners = [
                ob
                for ob in export_obs
                if ob.nwo.mesh_type_ui == "_connected_geometry_mesh_type_structure"
                and ob.nwo.proxy_instance
            ]
            for ob in proxy_owners:
                proxy_instance = ob.copy()
                proxy_instance.data = ob.data.copy()
                proxy_instance.name = f"{ob.name}(instance)"
                proxy_instance.nwo.mesh_type_ui = "_connected_geometry_mesh_type_poop"
                scene_coll.link(proxy_instance)

            # print("structure_proxy")

        materials = bpy.data.materials

        # create fixup materials
        if "Override" not in materials:
            override_mat = materials.new("Override")
            override_mat.nwo.rendered = False
        else:
            override_mat = materials.get("Override")

        if "invalid" not in materials:
            invalid_mat = materials.new("invalid")
            if h4:
                invalid_mat.nwo.shader_path = r"shaders\invalid.material"
            else:
                invalid_mat.nwo.shader_path = r"shaders\invalid.shader"
        else:
            invalid_mat = materials.get("invalid")

        if "water" not in materials:
            water_surface_mat = materials.new("water")
            if game_version == "h2a":
                water_surface_mat.nwo.shader_path = r"levels\sway\ca_sanctuary\materials\rocks\ca_sanctuary_rockflat_water.material"
            elif h4:
                water_surface_mat.nwo.shader_path = (
                    r"environments\shared\materials\jungle\cave_water.material"
                )
            else:
                water_surface_mat.nwo.shader_path = r"levels\multi\forge_halo\shaders\water\forge_halo_ocean_water.shader_water"
        else:
            water_surface_mat = materials.get("water")

        # add special reach materials
        if not h4:
            if INVISIBLE_SKY not in materials:
                sky_mat = materials.new(INVISIBLE_SKY)
            else:
                sky_mat = materials.get(INVISIBLE_SKY)

            sky_mat.nwo.shader_path = r"bungie_face_type=_connected_geometry_face_type_sky.override"
            sky_mat.nwo.rendered = True # not actually rendered but this lets us use the special shader path input

            if SEAM_SEALER not in materials:
                seam_sealer_mat = materials.new(SEAM_SEALER)
            else:
                seam_sealer_mat = materials.get(SEAM_SEALER)

            seam_sealer_mat.nwo.shader_path = r"bungie_face_type=_connected_geometry_face_type_seam_sealer.override"
            seam_sealer_mat.nwo.rendered = True

            if COLLISION_ONLY not in materials:
                collision_only_mat = materials.new(COLLISION_ONLY)
            else:
                collision_only_mat = materials.get(COLLISION_ONLY)

            collision_only_mat.nwo.shader_path = r"bungie_face_type=_connected_geometry_face_mode_collision_only.override"
            collision_only_mat.nwo.rendered = True

            if SPHERE_COLLISION_ONLY not in materials:
                sphere_collision_only_mat = materials.new(SPHERE_COLLISION_ONLY)
            else:
                sphere_collision_only_mat = materials.get(SPHERE_COLLISION_ONLY)

            sphere_collision_only_mat.nwo.shader_path = r"bungie_face_type=_connected_geometry_face_mode_sphere_collision_only.override"
            sphere_collision_only_mat.nwo.rendered = True

            if LIGHTMAP_ONLY not in materials:
                lightmap_only_mat = materials.new(LIGHTMAP_ONLY)
            else:
                lightmap_only_mat = materials.get(LIGHTMAP_ONLY)

            lightmap_only_mat.nwo.shader_path = r"bungie_face_type=_connected_geometry_face_mode_lightmap_only.override"
            lightmap_only_mat.nwo.rendered = True

            if SHADOW_ONLY not in materials:
                shadow_only_mat = materials.new(SHADOW_ONLY)
            else:
                shadow_only_mat = materials.get(SHADOW_ONLY)

            shadow_only_mat.nwo.shader_path = r"bungie_face_type=_connected_geometry_face_mode_shadow_only.override"
            shadow_only_mat.nwo.rendered = True


        context.view_layer.update()
        export_obs = context.view_layer.objects[:]

        # establish region/global mats sets
        has_regions = sidecar_type in ("MODEL", "SKY")
        has_global_mats = sidecar_type in ("MODEL", "SCENARIO", "PREFAB")

        self.regions = {"default"}
        self.global_materials = {"default"}
        self.bsps = set()
        self.seams = []

        process = "Building Export Objects"
        update_progress(process, 0)
        len_export_obs = len(export_obs)

        self.used_materials = set()
        # start the great loop!
        for idx, ob in enumerate(export_obs):
            set_active_object(ob)
            ob.select_set(True)
            nwo = ob.nwo

            reset_export_props(nwo)
            
            me = ob.data
            ob_type = ob.type
            is_mesh = ob_type == "MESH"
            is_mesh_loose = ob_type in (
                "MESH",
                "CURVE",
                "META",
                "SURFACE",
                "FONT",
            )  
            is_valid_object_type = ob_type in (
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

            self.strip_prefix(ob)
            # if not_bungie_game():
            #     self.apply_namespaces(ob, asset)

            self.set_object_type(ob, ob_type, nwo, is_valid_object_type)

            self.apply_object_mesh_marker_properties(ob, sidecar_type, not h4, nwo)

            is_halo_render = is_mesh_loose and nwo.object_type == '_connected_geometry_object_type_mesh' and self.has_halo_materials(nwo, h4)

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
                self.regions.add(nwo.region_name)

            if uses_global_mat:
                self.global_materials.add(nwo.face_global_material)

            if scenario_asset:
                self.bsps.add(nwo.bsp_name)

            if export_gr2_files:
                # fix meshes with missing UV maps
                if is_mesh:
                    uv_layers = me.uv_layers
                    if not uv_layers:
                        uv_layers.new(name="UVMap_0")

                    # print("uv fix")
                if is_mesh_loose:
                    # Add materials to all objects without one. No materials = unhappy Tool.exe
                    self.fix_materials(
                        ob, me, nwo, override_mat, invalid_mat, water_surface_mat, h4, is_halo_render
                    )
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
        for idx, mat in enumerate(self.used_materials):
            mat_nwo = mat.nwo
            if (
                not mat.is_grease_pencil
                and mat_nwo.rendered
                and not mat_nwo.shader_path
            ):
                self.warning_hit = True
                print("")

                if h4:
                    print_warning("Scene has empty Halo material tag paths")
                    job = "Fixing Empty Material Paths"
                else:
                    print_warning("Scene has empty Halo shader tag paths")
                    job = "Fixing Empty Shader Paths"

                update_job(job, 0)
                no_path_materials = find_shaders(self.used_materials, h4)
                update_job(job, 1)
                if no_path_materials:
                    if h4:
                        print_warning(
                            "Unable to find material tag paths for the following Blender materials:"
                        )
                    else:
                        print_warning(
                            "Unable to find shader tag paths for the following Blender materials:"
                        )
                    for m in no_path_materials:
                        print_warning(m)
                    if h4:
                        print_warning(
                            "\nThese materials should either be given paths to Halo material tags, or specified as a Blender only material (by using the checkbox in Halo Material Paths)\n"
                        )
                    else:
                        print_warning(
                            "\nThese materials should either be given paths to Halo shader tags, or specified as a Blender only material (by using the checkbox in Halo Shader Paths)\n"
                        )
                break

        # print("found_shaders")

        # build seams
        if self.seams:
            if len(self.bsps) < 2:
                self.warning_hit = True
                print_warning(
                    "Only single BSP in scene, seam objects ignored from export"
                )
                for seam in self.seams:
                    # print(seam.name)
                    self.unlink(seam)

            else:
                for seam in self.seams:
                    seam_me = seam.data
                    seam_bm = bmesh.new()
                    seam_bm.from_mesh(seam_me)
                    bmesh.ops.triangulate(seam_bm, faces=seam_bm.faces)
                    seam_bm.to_mesh(seam_me)
                    seam_nwo = seam.nwo

                    back_seam = seam.copy()
                    back_seam.data = seam_me.copy()
                    back_me = back_seam.data

                    back_nwo = back_seam.nwo

                    for f in seam_bm.faces:
                        f.normal_flip()

                    seam_bm.to_mesh(back_me)

                    # apply new bsp association
                    back_ui = seam_nwo.seam_back_ui
                    if (
                        back_ui == ""
                        or back_ui == seam_nwo.bsp_name
                        or back_ui not in self.bsps
                    ):
                        # this attempts to fix a bad back facing bsp ref
                        self.warning_hit = True
                        print_warning(
                            f"{seam.name} has bad back facing bsp reference. Replacing with nearest adjacent bsp"
                        )
                        closest_bsp = closest_bsp_object(seam)
                        if closest_bsp is None:
                            print_warning(
                                f"Failed to automatically set back facing bsp reference for {seam.name}. Removing Seam from export"
                            )
                            self.unlink(seam)
                        else:
                            back_nwo.bsp_name = closest_bsp.nwo.bsp_name
                    else:
                        back_nwo.bsp_name = seam_nwo.seam_back_ui

                    back_seam.name = f"seam({back_nwo.bsp_name}:{seam_nwo.bsp_name})"

                    scene_coll.link(back_seam)

        # get new export_obs
        context.view_layer.update()
        export_obs = context.view_layer.objects[:]

        if export_gr2_files:
            # Convert mesh markers to empty objects
            self.markerify(export_obs, scene_coll)
            # print("markifiy")

            # get new export_obs from deleted markers
            context.view_layer.update()
            export_obs = context.view_layer.objects[:]

        # apply face layer properties
        self.apply_face_properties(
            context, export_obs, scene_coll, h4, sidecar_type == "SCENARIO"
        )
        # print("face_props_applied")

        # get new export_obs from split meshes
        context.view_layer.update()
        export_obs = context.view_layer.objects[:]
        if export_gr2_files:
            # poop proxy madness
            # self.setup_poop_proxies(export_obs, h4)
            # print("poop_proxies") 

            # get new proxy export_obs
            # context.view_layer.update()
            # export_obs = context.view_layer.objects[:]

            #set Reach instanced_collision objects to poops
            if not h4:
                self.fix_reach_poop_collision(export_obs, scene_coll)

            # remove meshes with zero faces
            self.cull_zero_face_meshes(export_obs)

            context.view_layer.update()
            export_obs = context.view_layer.objects[:]

            # print("cull_zero_face")
        # Establish a dictionary of scene regions. Used later in export_gr2 and build_sidecar
        regions = [region for region in self.regions if region]
        self.regions_dict = {region: str(idx) for idx, region in enumerate(regions)}

        # Establish a dictionary of scene global materials. Used later in export_gr2 and build_sidecar
        global_materials = [
            global_material
            for global_material in self.global_materials
            if global_material
        ]
        self.global_materials_dict = {
            global_material: str(idx)
            for idx, global_material in enumerate(global_materials)
            if global_material
        }

        # get all objects that we plan to export later
        self.halo_objects_init()
        self.halo_objects(sidecar_type, export_obs, h4)
        # print("halo_objects")

        context.view_layer.update()
        export_obs = context.view_layer.objects[:]

        # order bsps
        self.structure_bsps = sort_alphanum(self.structure_bsps)
        self.design_bsps = sort_alphanum(self.design_bsps)

        self.model_armature = None
        self.skeleton_bones = {}
        self.current_action = None

        if sidecar_type in ("MODEL", "SKY", "FP ANIMATION"):
            self.model_armature, using_auto_armature = self.get_scene_armature(
                export_obs, asset, scene_coll
            )

            if self.lighting:
                self.create_bsp_box(scene_coll)

            if self.model_armature:
                if not using_auto_armature or sidecar_type != "FP ANIMATION":
                    # unlink any unparented objects from the scene
                    warn = False
                    for ob in export_obs:
                        if ob is not self.model_armature and not ob.parent:
                            if not warn:
                                self.warning_hit = True
                                print("")
                            warn = True
                            print_warning(
                                f"Ignoring {ob.name} because it is not parented to the scene armature"
                            )
                            self.unlink(ob)

                    context.view_layer.update()
                    export_obs = context.view_layer.objects[:]
                    # NOTE skipping vertex group fixes for now until it's more stable
                    self.fix_parenting(self.model_armature, export_obs)

                # set bone names equal to their name overrides (if not blank)
                if export_gr2_files:
                    self.set_bone_names(self.model_armature.data.bones)

                    graph_override = context.scene.nwo.animation_graph_path
                    if graph_override and graph_override.endswith(".model_animation_graph"):
                        full_graph_path = get_tags_path() + graph_override
                        if os.path.exists(full_graph_path):
                            set_frame_ids(context, full_graph_path, self.model_armature)
                        else:
                            print_warning("Model Animation Graph override supplied but tag path does not exist")
                            self.warning_hit = True

                self.skeleton_bones = self.get_bone_list(
                    self.model_armature, h4
                )  # return a list of bones attached to the model armature, ignoring control / non-deform bones
                if bpy.data.actions and self.model_armature.animation_data:
                    self.current_action = self.get_current_action(self.model_armature)

        # print("armature")

        # Set timeline range for use during animation export
        self.timeline_start, self.timeline_end = self.set_timeline_range(context)

        # rotate the model armature if needed
        if export_gr2_files:
            self.fix_armature_rotation(
                self.model_armature,
                sidecar_type,
                context,
                export_animations,
                self.current_action,
                export_obs,
            )

        # Set animation name overrides
        self.set_animation_overrides(self.model_armature)

        # get the max LOD count in the scene if we're exporting a decorator
        self.lods = self.get_decorator_lods(sidecar_type == "DECORATOR SET")

        if self.warning_hit:
            print_warning(
                "\nScene has issues that that have been temporarily resolved for export. These should be fixed for subsequent exports"
            )
            print_warning("Please see above output for details")

        # end = time.perf_counter()
        # print(f"\nScene Prepared in {end - start} seconds")
        # time.sleep(3)
        # raise

    ########################################################################################################################################
    ########################################################################################################################################

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

    def justify_face_split(self, layer_faces_dict, poly_count, h4, ob):
        """Checked whether we actually need to split this mesh up"""
        # check if face layers cover the whole mesh, if they do, we don't need to split the mesh
        for layer, face_seq in layer_faces_dict.items():
            face_count = len(face_seq)
            if poly_count != face_count:
                return False, True # temp
                if h4 or not self.is_material_property(layer, face_seq, ob):
                    return False, True
                else:
                    return False, False

        return False, True

    def apply_reach_material(self, faces, mat_name, mat_slots, me):
        mat_index = -1
        for idx, slot in enumerate(mat_slots):
            if slot.material.name == "mat_name":
                mat_index = idx
                break
        else:
            # Material doesn't exist on mesh, so create it
            me.materials.append(bpy.data.materials[mat_name])

        # Apply material to faces
        for f in faces:
            f.material_index = mat_index

    
    def is_material_property(self, layer, face_seq, ob):
        if self.prop_only("face_type_override", layer):
            if layer.face_type_ui == "_connected_geometry_face_type_seam_sealer":
                self.apply_reach_material(face_seq, SEAM_SEALER, ob.material_slots)
            else:
                self.apply_reach_material(face_seq, INVISIBLE_SKY, ob.material_slots)

            return True
                
        elif self.prop_only("face_mode_override", layer):
            if layer.face_mode_ui == "_connected_geometry_face_mode_collision_only":
                self.apply_reach_material(face_seq, COLLISION_ONLY, ob.material_slots)
            if layer.face_mode_ui == "_connected_geometry_face_mode_sphere_collision_only":
                self.apply_reach_material(face_seq, SPHERE_COLLISION_ONLY, ob.material_slots)
            if layer.face_mode_ui == "_connected_geometry_face_mode_lightmap_only":
                self.apply_reach_material(face_seq, LIGHTMAP_ONLY, ob.material_slots)
            if layer.face_mode_ui == "_connected_geometry_face_mode_shadow_only":
                self.apply_reach_material(face_seq, SHADOW_ONLY, ob.material_slots)
            
            return True

        return False
        

    def prop_only(self, prop, layer):
        if prop != "face_mode_override" and layer.face_mode_override:
            return False
        elif prop != "face_type_override" and layer.face_type_override:
            return False
        elif layer.face_global_material_override:
            return False
        elif layer.region_name_override:
            return False
        elif layer.ladder_override:
            return False
        elif layer.slip_surface_override:
            return False
        elif layer.decal_offset_override:
            return False
        elif layer.group_transparents_by_plane_override:
            return False
        elif layer.no_shadow_override:
            return False
        elif layer.precise_position_override:
            return False
        elif layer.no_lightmap_override:
            return False
        elif layer.no_pvs_override:
            return False
        elif layer.lightmap_additive_transparency_override:
            return False
        elif layer.lightmap_resolution_scale_override:
            return False
        elif layer.lightmap_type_override:
            return False
        elif layer.lightmap_translucency_tint_color_override:
            return False
        elif layer.lightmap_lighting_from_both_sides_override:
            return False
        elif layer.emissive_override:
            return False
        
        return getattr(layer, prop)
        
            
    def strip_nocoll_only_faces(self, layer_faces_dict, bm):
        """Removes faces from a mesh that have the render only property"""
        # loop through each face layer and select non collision faces
        has_sphere_coll = False
        for layer, face_seq in layer_faces_dict.items():
            if (
                layer.face_mode_override
                and layer.face_mode_ui != "_connected_geometry_face_mode_collision_only"
            ):
                if layer.face_mode_ui == "_connected_geometry_face_mode_sphere_collision_only":
                    has_sphere_coll = True
                bmesh.ops.delete(bm, geom=face_seq, context="FACES")

        return len(bm.faces), has_sphere_coll
    
    def strip_nophys_only_faces(self, layer_faces_dict, bm):
        # loop through each face layer and select non phzsics faces
        self.is_sphere_coll = False
        for layer, face_seq in layer_faces_dict.items():
            if (
                layer.face_mode_override
                and layer.face_mode_ui not in ("_connected_geometry_face_mode_sphere_collision_only",)
            ):
                bmesh.ops.delete(bm, geom=face_seq, context="FACES")

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
            if face_seq:
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

                split_ob = ob.copy()

                split_ob.data = me.copy()
                split_me = split_ob.data

                bm.to_mesh(me)

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

                split_objects.append(split_ob)

                if split_me.polygons:
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

    def split_to_layers(self, context, ob, ob_nwo, me, face_layers, scene_coll, h4, bm):
        poly_count = len(bm.faces)
        layer_faces_dict = {
            layer: layer_faces(bm, bm.faces.layers.int.get(layer.layer_name))
            for layer in face_layers
        }

        collision_ob = None
        physics_ob = None
        justified, apply_to_mesh = self.justify_face_split(layer_faces_dict, poly_count, h4, ob)

        if justified:
            # if instance geometry, we need to fix the collision model (provided the user has not already defined one)
            render_mesh = ob.nwo.mesh_type in render_mesh_types_full
            is_poop = ob_nwo.mesh_type == "_connected_geometry_mesh_type_poop"
            if (
                is_poop and not h4
            ):  # don't do this for h4 as collision can be open
                # check for custom collision / physics
                poop_render_only = False
                if ob.nwo.face_mode in RENDER_ONLY_FACE_TYPES:
                    poop_render_only = True
                    ob.nwo.poop_render_only = "1"
                
                # Set this globally for the poop we're about to split
                # We do this because a custom collison mesh is being built
                # and without the render_only property, the mesh will still
                # report open edges in game
                ob.nwo.face_mode = "_connected_geometry_face_mode_render_only"

                has_coll_child = False
                has_phys_child = False

                # Check if the poop already has child collision/physics
                # We can skip building this from face properties if so
                for child in ob.children:
                    if child.nwo.mesh_type == '_connected_geometry_mesh_type_poop_collision':
                        has_coll_child = True
                    elif child.nwo.mesh_type == '_connected_geometry_mesh_type_poop_physics':
                        has_phys_child = True

                if not poop_render_only:
                    if not has_coll_child:
                        collision_ob = ob.copy()
                        collision_ob.nwo.face_mode = ""
                        collision_ob.data = me.copy()
                        scene_coll.link(collision_ob)
                        # Remove render only property faces from coll mesh
                        coll_bm = bmesh.new()
                        coll_bm.from_mesh(collision_ob.data)
                        coll_layer_faces_dict = {
                            layer: layer_faces(
                                coll_bm, coll_bm.faces.layers.int.get(layer.layer_name)
                            )
                            for layer in face_layers
                        }
                        poly_count, has_sphere_coll = self.strip_nocoll_only_faces(coll_layer_faces_dict, coll_bm)

                        coll_bm.to_mesh(collision_ob.data)

                        collision_ob.name = f"{ob.name}(collision)"

                        ori_matrix = ob.matrix_world
                        collision_ob.nwo.mesh_type = (
                            "_connected_geometry_mesh_type_poop_collision"
                        )

                    if has_sphere_coll and not has_phys_child:
                        physics_ob = ob.copy()
                        physics_ob.nwo.face_mode = ""
                        physics_ob.data = me.copy()
                        scene_coll.link(physics_ob)
                        phys_bm = bmesh.new()
                        phys_bm.from_mesh(physics_ob.data)
                        phys_layer_faces_dict = {
                            layer: layer_faces(
                                phys_bm, phys_bm.faces.layers.int.get(layer.layer_name)
                            )
                            for layer in face_layers
                        }

                        self.strip_nophys_only_faces(phys_layer_faces_dict, phys_bm)

                        phys_bm.to_mesh(physics_ob.data)

                        physics_ob.name = f"{ob.name}(physics)"

                        physics_ob.nwo.mesh_type = (
                            "_connected_geometry_mesh_type_poop_physics"
                        )

            normals_ob = ob.copy()
            normals_ob.data = me.copy()

            # Splits the mesh recursively until each new mesh only contains a single face layer
            split_objects_messy = self.recursive_layer_split(
                ob, me, face_layers, layer_faces_dict, h4, scene_coll, [ob], bm
            )

            ori_ob_name = str(ob.name)

            # remove zero poly obs from split_objects_messy
            split_objects = [s_ob for s_ob in split_objects_messy if s_ob.data.polygons]
            
            for split_ob in split_objects:
                more_than_one_prop = False
                obj_bm = bmesh.new()
                obj_bm.from_mesh(split_ob.data)
                obj_name_suffix = ""
                for layer in face_layers:
                    if layer_face_count(
                        obj_bm, obj_bm.faces.layers.int.get(layer.layer_name)
                    ):
                        self.face_prop_to_mesh_prop(split_ob.nwo, layer, h4)
                        if more_than_one_prop:
                            obj_name_suffix += ", "
                        else:
                            more_than_one_prop = True

                        obj_name_suffix += layer.name
                # obj_bm.free()

                if obj_name_suffix:
                    split_ob.name = f"{ori_ob_name}({obj_name_suffix})"
                else:
                    split_ob.name = ori_ob_name

                if render_mesh:
                    # set up data transfer modifier to retain normals
                    mod = split_ob.modifiers.new("HaloDataTransfer", "DATA_TRANSFER")
                    mod.object = normals_ob
                    mod.use_object_transform = False
                    mod.use_loop_data = True
                    mod.data_types_loops = {"CUSTOM_NORMAL"}

            #parent poop coll
            parent_ob = None
            if collision_ob is not None:
                for split_ob in split_objects:
                    if not (split_ob.nwo.face_mode in ("_connected_geometry_face_mode_collision_only", "_connected_geometry_face_mode_sphere_collision_only") or split_ob.nwo.face_type == "_connected_geometry_face_type_seam_sealer"):
                        parent_ob = split_ob
                        break
                else:
                    # only way to make invisible collision...
                    if collision_ob is not None:
                        collision_ob.nwo.mesh_type = "_connected_geometry_mesh_type_poop"
                        collision_ob.nwo.face_mode = "_connected_geometry_face_mode_collision_only"
                    if physics_ob is not None:
                        physics_ob.nwo.mesh_type = "_connected_geometry_mesh_type_poop"
                        physics_ob.nwo.face_mode = "_connected_geometry_face_mode_sphere_collision_only"

                if parent_ob is not None:
                    if collision_ob is not None:
                        collision_ob.parent = parent_ob
                        collision_ob.matrix_world = ori_matrix
                        
                    if physics_ob is not None:
                        physics_ob.parent = parent_ob
                        physics_ob.matrix_world = ori_matrix

                # remove coll only split objects, as this is already covered by the coll mesh
                coll_only_objects = []
                for split_ob in split_objects:
                    if split_ob.nwo.face_mode in ("_connected_geometry_face_mode_collision_only", "_connected_geometry_face_mode_sphere_collision_only") or split_ob.nwo.face_type == "_connected_geometry_face_type_seam_sealer":
                        coll_only_objects.append(split_ob)
                        self.unlink(split_ob)
                        
                # recreate split objects list
                split_objects = [ob for ob in split_objects if ob not in coll_only_objects]

            return split_objects

        elif apply_to_mesh:
            for layer in face_layers:
                self.face_prop_to_mesh_prop(ob.nwo, layer, h4)

            return context.selected_objects

        else:
            bm.to_mesh(me)

            return context.selected_objects
        
    def poop_split_override(self, face_layers):
        for layer in face_layers:
            if layer.face_type_override:
                return False
            if layer.face_mode_override and layer.face_mode_ui != '_connected_geometry_face_mode_render_only':
                return False
            if layer.face_global_material_override:
                return False
            if layer.ladder_override:
                return False
            if layer.slip_surface_override:
                return False
            if layer.decal_offset_override:
                return False
            if layer.group_transparents_by_plane_override:
                return False
            if layer.no_shadow_override:
                return False
            if layer.precise_position_override:
                return False
            if layer.no_lightmap_override:
                return False
            if layer.no_pvs_override:
                return False
            if layer.lightmap_additive_transparency_override:
                return False
            if layer.lightmap_resolution_scale_override:
                return False
            if layer.lightmap_type_override:
                return False
            if layer.lightmap_translucency_tint_color_override:
                return False
            if layer.lightmap_lighting_from_both_sides_override:
                return False
            if layer.emissive_override:
                return False
            
        return True
            

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
            mesh_props.sky_permutation_index = str(face_props.sky_permutation_index_ui)
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
            self.regions.add(mesh_props.region_name)

        if face_props.face_global_material_override:
            mesh_props.face_global_material = face_props.face_global_material_ui
            self.global_materials.add(mesh_props.face_global_material)

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
            mesh_props.precise_position = bool_str(face_props.precise_position_ui)

        if face_props.no_lightmap_override:
            mesh_props.no_lightmap = bool_str(face_props.no_lightmap_ui)

        if face_props.no_pvs_override:
            mesh_props.no_pvs = bool_str(face_props.no_pvs_ui)

        # lightmap props
        if face_props.lightmap_additive_transparency_override:
            if h4:
                mesh_props.lightmap_additive_transparency = color_3p_str(
                    face_props.lightmap_additive_transparency_ui
                )
            else:
                mesh_props.lightmap_additive_transparency = color_4p_str(
                    face_props.lightmap_additive_transparency_ui
                )

            mesh_props.lightmap_additive_transparency_active = True
        if face_props.lightmap_resolution_scale_override:
            mesh_props.lightmap_resolution_scale = str(
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
            is_poop = mesh_props.mesh_type == "_connected_geometry_mesh_type_poop"
            if is_poop and (mesh_props.ladder or mesh_props.slip_surface):
                mesh_props.face_sides = "_connected_geometry_face_sides_two_sided"

    def apply_face_properties(self, context, export_obs, scene_coll, h4, scenario):
        mesh_obs_full = [ob for ob in export_obs if ob.type == "MESH"]
        if not mesh_obs_full:
            return
        
        meshes_full = {ob.data for ob in mesh_obs_full}
        me_ob_dict_full = {}
        for me in meshes_full:
            for ob in mesh_obs_full:
                if ob.data == me:
                    if me not in me_ob_dict_full:
                        me_ob_dict_full[me] = []

                    me_ob_dict_full[me].append(ob)

        valid_mesh_types = (
            "_connected_geometry_mesh_type_collision",
            "_connected_geometry_mesh_type_default",
            "_connected_geometry_mesh_type_poop",
        )

        mesh_obs = [
            ob
            for ob in export_obs
            if ob.nwo.object_type == "_connected_geometry_object_type_mesh"
            and ob.type == "MESH"
            and ob.nwo.mesh_type in valid_mesh_types
            and not (
                ob.nwo.mesh_type == "_connected_geometry_mesh_type_default"
                and h4
                and scenario
            )
        ]
        meshes = {ob.data for ob in mesh_obs}
        if not meshes:
            return
        
        me_ob_dict = {}
        for me in meshes:
            for ob in mesh_obs:
                if ob.data == me:
                    if me not in me_ob_dict:
                        me_ob_dict[me] = []

                    me_ob_dict[me].append(ob)

        process = "Creating Meshes From Face Properties"
        len_me_ob_dict = len(me_ob_dict)
        any_face_props = False

        # make invalid obs seperate mesh data
        if me_ob_dict[me] != me_ob_dict_full[me]:
            new_data = me.copy()
            for ob in me_ob_dict_full[me]:
                if ob not in me_ob_dict[me]:
                    ob.data = new_data

        for idx, me in enumerate(me_ob_dict.keys()):
            linked_objects = me_ob_dict.get(me)
            # Check to ensure linked objects is not empty
            # (in the case that a mesh exists in the scene without users)
            if not linked_objects:
                continue

            is_linked = len(linked_objects) > 1

            ob = linked_objects[0]

            me_nwo = me.nwo
            ob_nwo = ob.nwo

            face_layers = me_nwo.face_props

            if face_layers:
                update_progress(process, idx / len_me_ob_dict)

                any_face_props = True
                # must force on auto smooth to avoid Normals transfer errors
                me.use_auto_smooth = True

                bm = bmesh.new()
                bm.from_mesh(me)

                # must ensure all faces are visible
                for face in bm.faces:
                    face.hide_set(False)

                split_objects = self.split_to_layers(
                    context, ob, ob_nwo, me, face_layers, scene_coll, h4, bm
                )
                # remove the original ob from this list if needed
                # if ob in split_objects:
                #     split_objects.remove(ob)

                # if not split_objects:
                #     continue

                # Can skip the below for loop if linked_objects is not a list
                if is_linked:
                    # copy all new face split objects to all linked objects
                    linked_objects.remove(ob)
                    for linked_ob in linked_objects:
                        for split_ob in split_objects:
                            new_ob = linked_ob
                            if split_ob != ob:
                                new_ob = split_ob.copy()
                                scene_coll.link(new_ob)
                                new_ob.matrix_world = linked_ob.matrix_world

                            if split_ob.children:
                                linked_ob.nwo.face_mode = "_connected_geometry_face_mode_render_only"
                                for child in split_ob.children:
                                    new_child = child.copy()
                                    scene_coll.link(new_child)
                                    if not h4:
                                        new_child.parent = new_ob
                                    
                                    new_child.matrix_world = new_ob.matrix_world

                        if ob.modifiers.get("HaloDataTransfer", 0):
                            mod = linked_ob.modifiers.new(
                                "HaloDataTransfer", "DATA_TRANSFER"
                            )
                            mod.object = ob.modifiers["HaloDataTransfer"].object
                            mod.use_object_transform = False
                            mod.use_loop_data = True
                            mod.data_types_loops = {"CUSTOM_NORMAL"}

        if any_face_props:
            update_progress(process, 1)

    def z_rotate_and_apply(self, model_armature, angle):
        angle = radians(angle)
        axis = (0, 0, 1)
        pivot = model_armature.location
        M = (
            Matrix.Translation(pivot)
            @ Matrix.Rotation(angle, 4, axis)
            @ Matrix.Translation(-pivot)
        )

        model_armature.matrix_world = M @ model_armature.matrix_world

        bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)

    def bake_animations(
        self,
        armature,
        export_animations,
        current_action,
    ):
        job = "Baking Animations"
        update_progress(job, 0)
        export_actions = [a for a in bpy.data.actions if a.use_frame_range]
        for idx, action in enumerate(export_actions):
            if action.use_frame_range and (export_animations == "ALL" or current_action == action):
                armature.animation_data.action = action

                frame_start = int(action.frame_start)
                frame_end = int(action.frame_end)

                # anim_utils.bake_action(armature, action=action, frames=range(frame_start, frame_end), do_pose=True, do_visual_keying=True, do_constraint_clear=True)
                bpy.ops.nla.bake(frame_start=frame_start, frame_end=frame_end, only_selected=False, visual_keying=True, clear_constraints=idx + 1 == len(export_actions), use_current_action=True, bake_types={'POSE'})
                update_progress(job, idx / len(export_actions))

        update_progress(job, 1)

    def fix_armature_rotation(
        self,
        armature,
        sidecar_type,
        context,
        export_animations,
        current_action,
        export_obs,
    ):
        forward = context.scene.nwo.forward_direction
        if forward != "x" and sidecar_type in ("MODEL", "FP ANIMATION"):
            # bake animation to avoid issues on armature rotation
            set_active_object(armature)
            armature.select_set(True)
            if export_animations != "NONE" and bpy.data.actions:
                self.bake_animations(
                    armature,
                    export_animations,
                    current_action,
                )
            # apply rotation based on selected forward direction
            # context.scene.frame_current = 0
            if forward == "y":
                self.z_rotate_and_apply(armature, -90)
            elif forward == "y-":
                self.z_rotate_and_apply(armature, 90)
            elif forward == "x-":
                self.z_rotate_and_apply(armature, 180)

            armature.select_set(False)

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
                nwo.region_name = true_region(nwo)
                if nwo.mesh_type_ui == "_connected_geometry_mesh_type_collision":
                    nwo.mesh_type = "_connected_geometry_mesh_type_collision"
                elif nwo.mesh_type_ui == "_connected_geometry_mesh_type_physics":
                    nwo.mesh_type = "_connected_geometry_mesh_type_physics"
                    nwo.mesh_primitive_type = nwo.mesh_primitive_type_ui
                elif (
                    nwo.mesh_type_ui == "_connected_geometry_mesh_type_object_instance"
                    and not not_bungie_game()
                ):
                    nwo.mesh_type = "_connected_geometry_mesh_type_object_instance"
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
                        nwo.poop_streaming_priority = nwo.poop_streaming_priority_ui
                        nwo.poop_cinematic_properties = nwo.poop_cinematic_properties_ui
                        if nwo.poop_remove_from_shadow_geometry_ui:
                            nwo.poop_remove_from_shadow_geometry = "1"
                        if nwo.poop_disallow_lighting_samples_ui:
                            nwo.poop_disallow_lighting_samples = "1"

                elif nwo.mesh_type_ui == "_connected_geometry_mesh_type_poop_collision":
                    nwo.mesh_type = "_connected_geometry_mesh_type_poop_collision"
                    nwo.poop_collision_type = nwo.poop_collision_type_ui

                elif nwo.mesh_type_ui == "_connected_geometry_mesh_type_seam":
                    nwo.mesh_type = "_connected_geometry_mesh_type_seam"
                    self.seams.append(ob)

                elif nwo.mesh_type_ui == "_connected_geometry_mesh_type_plane":
                    if nwo.plane_type_ui == "_connected_geometry_plane_type_portal":
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
                        nwo.mesh_type = "_connected_geometry_mesh_type_water_surface"
                        nwo.mesh_tessellation_density = nwo.mesh_tessellation_density_ui
                    elif (
                        nwo.plane_type_ui
                        == "_connected_geometry_plane_type_poop_vertical_rain_sheet"
                    ):
                        nwo.mesh_type = (
                            "_connected_geometry_mesh_type_poop_vertical_rain_sheet"
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

                elif nwo.mesh_type_ui == "_connected_geometry_mesh_type_volume":
                    if (
                        nwo.volume_type_ui
                        == "_connected_geometry_volume_type_soft_ceiling"
                    ):
                        nwo.mesh_type = "_connected_geometry_mesh_type_boundary_surface"
                        nwo.boundary_surface_type = (
                            "_connected_geometry_boundary_surface_type_soft_ceiling"
                        )

                    elif (
                        nwo.volume_type_ui
                        == "_connected_geometry_volume_type_soft_kill"
                    ):
                        nwo.mesh_type = "_connected_geometry_mesh_type_boundary_surface"
                        nwo.boundary_surface_type = (
                            "_connected_geometry_boundary_surface_type_soft_kill"
                        )

                    elif (
                        nwo.volume_type_ui
                        == "_connected_geometry_volume_type_slip_surface"
                    ):
                        nwo.mesh_type = "_connected_geometry_mesh_type_boundary_surface"
                        nwo.boundary_surface_type = (
                            "_connected_geometry_boundary_surface_type_slip_surface"
                        )

                    elif (
                        nwo.volume_type_ui
                        == "_connected_geometry_volume_type_water_physics_volume"
                    ):
                        nwo.mesh_type = (
                            "_connected_geometry_mesh_type_water_physics_volume"
                        )
                        nwo.water_volume_depth = jstr(nwo.water_volume_depth_ui)
                        nwo.water_volume_flow_direction = jstr(
                            nwo.water_volume_flow_direction_ui
                        )
                        nwo.water_volume_flow_velocity = jstr(
                            nwo.water_volume_flow_velocity_ui
                        )
                        if reach:
                            nwo.water_volume_fog_color = color_4p_str(
                                nwo.water_volume_fog_color_ui
                            )
                        else:
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
                        nwo.mesh_type = "_connected_geometry_mesh_type_cookie_cutter"

                    elif (
                        nwo.volume_type_ui
                        == "_connected_geometry_volume_type_lightmap_exclude"
                        and not reach
                    ):
                        nwo.mesh_type = "_connected_geometry_mesh_type_obb_volume"
                        nwo.obb_volume_type = "_connected_geometry_mesh_obb_volume_type_lightmapexclusionvolume"

                    elif (
                        nwo.volume_type_ui
                        == "_connected_geometry_volume_type_streaming"
                        and not reach
                    ):
                        nwo.mesh_type = "_connected_geometry_mesh_type_obb_volume"
                        nwo.obb_volume_type = (
                            "_connected_geometry_mesh_obb_volume_type_streamingvolume"
                        )

                    elif (
                        nwo.volume_type_ui
                        == "_connected_geometry_volume_type_lightmap_region"
                        and reach
                    ):
                        nwo.mesh_type = "_connected_geometry_mesh_type_lightmap_region"

                    elif (
                        nwo.volume_type_ui
                        == "_connected_geometry_volume_type_poop_rain_blocker"
                    ):
                        nwo.poop_rain_occluder = "1"
                        if reach:
                            nwo.mesh_type = (
                                "_connected_geometry_mesh_type_poop_rain_blocker"
                            )
                        else:
                            nwo.mesh_type = "_connected_geometry_mesh_type_poop"
                else:
                    nwo.mesh_type = "_connected_geometry_mesh_type_default"

            if asset_type == "SKY":
                nwo.region_name = true_region(nwo)
                nwo.mesh_type = "_connected_geometry_mesh_type_default"

            if asset_type == "DECORATOR SET":
                nwo.mesh_type = "_connected_geometry_mesh_type_decorator"
                nwo.region_name = true_region(nwo)
                nwo.decorator_lod = str(self.decorator_int(ob))

            if asset_type == "PARTICLE MODEL":
                nwo.mesh_type = "_connected_geometry_mesh_type_default"

            if asset_type == "PREFAB":
                if nwo.mesh_type_ui == "_connected_geometry_mesh_type_poop_collision":
                    nwo.mesh_type = "_connected_geometry_mesh_type_poop_collision"
                elif nwo.mesh_type_ui == "_connected_geometry_mesh_type_cookie_cutter":
                    nwo.mesh_type = "_connected_geometry_mesh_type_cookie_cutter"
                else:
                    nwo.mesh_type = "_connected_geometry_mesh_type_poop"

        # get marker type
        elif nwo.object_type == "_connected_geometry_object_type_marker":
            if asset_type == "MODEL":
                nwo.marker_all_regions = bool_str(nwo.marker_all_regions_ui)
                if nwo.marker_all_regions == "0":
                    nwo.region_name = true_region(nwo)
                m_perms = nwo.marker_permutations
                if m_perms:
                    m_perm_set = set()
                    for perm in m_perms:
                        m_perm_set.add(perm.permutation)
                    m_person_json_value = f'''#({', '.join('"' + p + '"' for p in m_perm_set)})'''
                    if nwo.marker_permutation_type == "exclude":
                        nwo.marker_exclude_perms = m_person_json_value
                    else:
                        nwo.marker_include_perms = m_person_json_value


                if nwo.marker_type_ui == "_connected_geometry_marker_type_hint":
                    nwo.marker_type = "_connected_geometry_marker_type_hint"
                    if not reach:
                        max_abs_scale = max(
                            abs(ob.scale.x), abs(ob.scale.y), abs(ob.scale.z)
                        )
                        if ob.type == "EMPTY":
                            nwo.marker_hint_length = jstr(
                                ob.empty_display_size * 2 * max_abs_scale
                            )
                        elif ob.type in ("MESH", "CURVE", "META", "SURFACE", "FONT"):
                            nwo.marker_hint_length = jstr(
                                max(ob.dimensions * max_abs_scale)
                            )

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
                    set_marker_sphere_size(ob, nwo)
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
                    nwo.marker_type = nwo.physics_constraint_type_ui
                    parent = nwo.physics_constraint_parent_ui
                    if (
                        parent is not None
                        and parent.type == "ARMATURE"
                        and nwo.physics_constraint_parent_bone_ui != ""
                    ):
                        nwo.physics_constraint_parent = (
                            nwo.physics_constraint_parent_bone_ui
                        )
                    elif parent is not None:
                        nwo.physics_constraint_parent = str(
                            nwo.physics_constraint_parent_ui.name
                        )
                    child = nwo.physics_constraint_child_ui
                    if (
                        child is not None
                        and child.type == "ARMATURE"
                        and nwo.physics_constraint_child_bone_ui != ""
                    ):
                        nwo.physics_constraint_child = (
                            nwo.physics_constraint_child_bone_ui
                        )
                    elif child is not None:
                        nwo.physics_constraint_child = str(
                            nwo.physics_constraint_child_ui.name
                        )
                    nwo.physics_constraint_uses_limits = bool_str(
                        nwo.physics_constraint_uses_limits_ui
                    )
                    nwo.hinge_constraint_minimum = jstr(nwo.hinge_constraint_minimum_ui)
                    nwo.hinge_constraint_maximum = jstr(nwo.hinge_constraint_maximum_ui)
                    nwo.cone_angle = jstr(nwo.cone_angle_ui)
                    nwo.plane_constraint_minimum = jstr(nwo.plane_constraint_minimum_ui)
                    nwo.plane_constraint_maximum = jstr(nwo.plane_constraint_maximum_ui)
                    nwo.twist_constraint_start = jstr(nwo.twist_constraint_start_ui)
                    nwo.twist_constraint_end = jstr(nwo.twist_constraint_end_ui)

                elif nwo.marker_type_ui == "_connected_geometry_marker_type_target":
                    nwo.marker_type = "_connected_geometry_marker_type_target"
                    set_marker_sphere_size(ob, nwo)
                elif nwo.marker_type_ui == "_connected_geometry_marker_type_effects":
                    if not ob.name.startswith("fx_"):
                        ob.name = "fx_" + ob.name
                        nwo.marker_type = "_connected_geometry_marker_type_model"
                elif (
                    not reach
                    and nwo.marker_type_ui == "_connected_geometry_marker_type_airprobe"
                ):
                    nwo.marker_type = "_connected_geometry_marker_type_airprobe"
                else:
                    nwo.marker_type = "_connected_geometry_marker_type_model"
                    if nwo.marker_type == "_connected_geometry_marker_type_garbage":
                        nwo.marker_velocity = vector_str(nwo.marker_velocity_ui)

            elif asset_type in ("SCENARIO", "PREFAB"):
                if (
                    nwo.marker_type_ui
                    == "_connected_geometry_marker_type_game_instance"
                ):
                    nwo.marker_game_instance_tag_name = (
                        nwo.marker_game_instance_tag_name_ui
                    )
                    if not reach and nwo.marker_game_instance_tag_name.lower().endswith(
                        ".prefab"
                    ):
                        nwo.marker_type = "_connected_geometry_marker_type_prefab"
                    elif (
                        not reach
                        and nwo.marker_game_instance_tag_name.lower().endswith(
                            ".cheap_light"
                        )
                    ):
                        nwo.marker_type = "_connected_geometry_marker_type_cheap_light"
                    elif (
                        not reach
                        and nwo.marker_game_instance_tag_name.lower().endswith(".light")
                    ):
                        nwo.marker_type = "_connected_geometry_marker_type_light"
                    elif (
                        not reach
                        and nwo.marker_game_instance_tag_name.lower().endswith(".leaf")
                    ):
                        nwo.marker_type = "_connected_geometry_marker_type_falling_leaf"
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
                    and nwo.marker_type_ui == "_connected_geometry_marker_type_airprobe"
                ):
                    nwo.marker_type = "_connected_geometry_marker_type_airprobe"
                elif (
                    not reach
                    and nwo.marker_type_ui == "_connected_geometry_marker_type_envfx"
                ):
                    nwo.marker_type = "_connected_geometry_marker_type_envfx"
                    nwo.marker_looping_effect = nwo.marker_looping_effect_ui
                elif (
                    not reach
                    and nwo.marker_type_ui
                    == "_connected_geometry_marker_type_lightcone"
                ):
                    nwo.marker_type = "_connected_geometry_marker_type_lightcone"
                    nwo.marker_light_cone_tag = nwo.marker_light_cone_tag_ui
                    nwo.marker_light_cone_color = color_3p_str(
                        nwo.marker_light_cone_color_ui
                    )
                    nwo.marker_light_cone_alpha = jstr(nwo.marker_light_cone_alpha_ui)
                    nwo.marker_light_cone_width = jstr(nwo.marker_light_cone_width_ui)
                    nwo.marker_light_cone_length = jstr(nwo.marker_light_cone_length_ui)
                    nwo.marker_light_cone_intensity = jstr(
                        nwo.marker_light_cone_intensity_ui
                    )
                    nwo.marker_light_cone_curve = nwo.marker_light_cone_curve_ui
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
                    nwo.precise_position = "1"
                # if nwo.face_draw_distance_active:
                #     nwo.face_draw_distance = nwo.face_draw_distance_ui
                # if nwo.texcoord_usage_active:
                #     nwo.texcoord_usage = nwo.texcoord_usage_ui
                if nwo.decal_offset_ui:
                    nwo.decal_offset = "1"
            if asset_type in ("SCENARIO", "PREFAB"):
                h4_structure = (
                    not reach
                    and nwo.mesh_type == "_connected_geometry_mesh_type_default"
                )
                if nwo.face_type_active or h4_structure:
                    if h4_structure:
                        nwo.face_type = "_connected_geometry_face_type_sky"
                    else:
                        nwo.face_type = nwo.face_type_ui
                    if nwo.face_type == "_connected_geometry_face_type_sky":
                        nwo.sky_permutation_index = str(nwo.sky_permutation_index_ui)
                if nwo.face_mode_active:
                    nwo.face_mode = nwo.face_mode_ui
                if nwo.ladder_active:
                    nwo.ladder = bool_str(nwo.ladder_ui)
                if nwo.slip_surface_active:
                    nwo.slip_surface = bool_str(nwo.slip_surface_ui)
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
                # if nwo.lightmap_photon_fidelity_active: TODO Restore this
                #     nwo.lightmap_photon_fidelity = (
                #         nwo.lightmap_photon_fidelity_ui
                #     )
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
                    if reach:
                        nwo.lightmap_translucency_tint_color = color_4p_str(
                            self.halo.lightmap_translucency_tint_color
                        )
                    else:
                        nwo.lightmap_translucency_tint_color = color_3p_str(
                            self.halo.lightmap_translucency_tint_color
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
                    nwo.material_lighting_emissive_color = color_4p_str(
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
        if ob.name.lower().startswith(("+cookie", "+portal", "+flair", "+water")):
            ob.name = ob.name[7:]
        if ob.name.lower().startswith(("frame ", "frame_", "+flair", "+water")):
            ob.name = ob.name[6:]
        if ob.name.lower().startswith(("bone ", "bone_", "+seam")):
            ob.name = ob.name[5:]
        if ob.name.lower().startswith(("bip ", "bip_", "+fog")):
            ob.name = ob.name[4:]
        if ob.name.lower().startswith(("b ", "b_")):
            ob.name = ob.name[2:]
        if ob.name.lower().startswith(("#", "?", "@", "$", "'")):
            ob.name = ob.name[1:]
        if ob.name.lower().startswith(("%")):
            ob.name = ob.name[1:]
            if ob.name.lower().startswith(("?", "!", "+", "-", ">", "*")):
                ob.name = ob.name[1:]
                if ob.name.lower().startswith(("?", "!", "+", "-", ">", "*")):
                    ob.name = ob.name[1:]
                    if ob.name.lower().startswith(("?", "!", "+", "-", ">", "*")):
                        ob.name = ob.name[1:]

        ob.name = ob.name.strip(" _")

    def set_object_type(self, ob, ob_type, nwo, is_valid_object_type):
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
                or nwo.object_type_ui != "_connected_geometry_object_type_marker"
            ):
                nwo.object_type = "_connected_geometry_object_type_frame"
            else:
                nwo.object_type = "_connected_geometry_object_type_marker"

        elif is_valid_object_type:
            nwo.object_type = nwo.object_type_ui
        else:
            # Mesh invalid, don't export
            print(f"{ob.name} is invalid. Skipping export")
            self.unlink(ob)

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
        elif nwo.mesh_type == "_connected_geometry_mesh_type_planar_fog_volume":
            namespace = "fog"
        elif nwo.mesh_type == "_connected_geometry_mesh_type_boundary_surface":
            namespace = "boundary_surface"
        elif nwo.mesh_type == "_connected_geometry_mesh_type_water_physics_volume":
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

    def set_animation_overrides(self, model_armature):
        if (
            model_armature is not None
            and len(bpy.data.actions) > 0
            and model_armature.animation_data
        ):
            for action in bpy.data.actions:
                action.name = dot_partition(action.name).lower().strip(" :_,-")
                nwo = action.nwo
                if not nwo.name_override:
                    nwo.name_override = action.name

    def set_object_mode(self, context):
        mode = context.mode

        if mode == "OBJECT":
            return

        if mode.startswith("EDIT") and not mode.endswith("GPENCIL"):
            bpy.ops.object.editmode_toggle()
        else:
            match mode:
                case "POSE":
                    bpy.ops.object.posemode_toggle()
                case "SCULPT":
                    bpy.ops.sculpt.sculptmode_toggle()
                case "PAINT_WEIGHT":
                    bpy.ops.paint.weight_paint_toggle()
                case "PAINT_VERTEX":
                    bpy.ops.paint.vertex_paint_toggle()
                case "PAINT_TEXTURE":
                    bpy.ops.paint.texture_paint_toggle()
                case "PARTICLE":
                    bpy.ops.particle.particle_edit_toggle()
                case "PAINT_GPENCIL":
                    bpy.ops.gpencil.paintmode_toggle()
                case "EDIT_GPENCIL":
                    bpy.ops.gpencil.editmode_toggle()
                case "SCULPT_GPENCIL":
                    bpy.ops.gpencil.sculptmode_toggle()
                case "WEIGHT_GPENCIL":
                    bpy.ops.gpencil.weightmode_toggle()
                case "VERTEX_GPENCIL":
                    bpy.ops.gpencil.vertexmode_toggle()
                case "SCULPT_CURVES":
                    bpy.ops.curves.sculptmode_toggle()

    def get_current_action(self, model_armature):
        return model_armature.animation_data.action

    def exit_local_view(self, context):
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                space = area.spaces[0]
                if space.local_view:
                    for region in area.regions:
                        if region.type == "WINDOW":
                            override = {"area": area, "region": region}
                            bpy.ops.view3d.localview(override)

    def rotate_scene(self, objects):
        angle_z = radians(90)
        axis_z = (0, 0, 1)
        pivot = Vector((0.0, 0.0, 0.0))
        for ob in objects:
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
        scene.frame_current = 0

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

    def get_decorator_lods(self, asset_is_decorator):
        lods = set()
        if asset_is_decorator:
            for ob in self.render:
                lods.add(self.decorator_int(ob))

        return lods
    
    def decorator_int(self, ob):
        match ob.nwo.decorator_lod_ui:
            case "high":
                return 1
            case "medium":
                return 2
            case "low":
                return 3
            case _:
                return 4

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
                ob.parent_type = "BONE"

        return arm_ob

    def fix_parenting(self, model_armature, export_obs):
        bones = model_armature.data.bones
        for b in bones:
            if b.use_deform:
                root_bone = b
                root_bone_name = b.name
                break
        else:
            root_bone_name = bones[0].name
            bones[0].use_deform = True
            self.warning_hit = True
            print_warning(
                f"\nNo deform bones in armature, setting {bones[0].name} to deform"
            )

        warn = False
        for ob in export_obs:
            nwo = ob.nwo
            frame = nwo.object_type == "_connected_geometry_object_type_frame"
            marker = nwo.object_type == "_connected_geometry_object_type_marker"
            physics = nwo.mesh_type == "_connected_geometry_mesh_type_physics"
            if ob.parent is None:
                continue
            if ob.parent_type != "BONE":
                if marker or physics:
                    if not warn:
                        self.warning_hit = True
                        print("")
                    warn = True
                    ob.parent_type = "BONE"
                    ob.parent_bone = root_bone_name
                    if not (marker or frame):
                        ob.matrix_parent_inverse = root_bone.matrix_local.inverted()
                    if marker:
                        print_warning(
                            f"{ob.name} is a marker but is not parented to a bone. Binding to bone: {root_bone_name}"
                        )
                    else:
                        print_warning(
                            f"{ob.name} is a physics mesh but is not parented to a bone. Binding to bone: {root_bone_name}"
                        )

                elif ob.type == "MESH":
                    # check if has armature mod
                    modifiers = ob.modifiers
                    for mod in modifiers:
                        if mod.type == "ARMATURE":
                            if mod.object != model_armature:
                                mod.object = model_armature
                            break
                    else:
                        arm_mod = ob.modifiers.new("Armature", "ARMATURE")
                        arm_mod.object = model_armature

            else:
                # Ensure parent inverse matrix set
                # If we don't do this, object can be offset in game
                if not (marker or frame):
                    ob.matrix_parent_inverse = bones[ob.parent_bone].matrix_local.inverted()

        # bones = model_armature.data.edit_bones
        # mesh_obs = [ob for ob in export_obs if ob.type == "MESH"]
        # meshes = set([ob.data for ob in mesh_obs])
        # me_ob_dict = {
        #     me: ob for me in meshes for ob in mesh_obs if ob.data == me
        # }

        # for item in me_ob_dict.items():
        #     me = item[0]
        #     ob = item[1]
        #     nwo = ob.nwo
        #     mesh_type = nwo.mesh_type
        #     marker = (
        #         nwo.object_type == "_connected_geometry_object_type_marker"
        #     )
        #     vertices = me.vertices

        #     set_active_object(ob)
        #     ob.select_set(True)

        #     if ob.vertex_groups:
        #         bpy.ops.object.vertex_group_lock(action="UNLOCK", mask="ALL")

        #         # force bone parenting for physics
        #         parent_type = ob.parent_type
        #         if (
        #             marker
        #             or mesh_type == "_connected_geometry_mesh_type_physics"
        #         ) and parent_type != "BONE":
        #             vertex_groups = ob.vertex_groups
        #             for vertex_group in vertex_groups:
        #                 for i, w in self.get_weights(
        #                     ob, vertex_group, vertices
        #                 ):
        #                     if w > 0:
        #                         bone_name = vertex_group.name
        #                         for bone in bones:
        #                             if bone.name == bone_name:
        #                                 break
        #                         else:
        #                             bone_name = bones[0].name

        #                         break

        #             parent_type = "BONE"
        #             ob.parent_bone = bone_name

        #         elif mesh_type == "_connected_geometry_mesh_type_collision":
        #             bpy.ops.object.vertex_group_clean(
        #                 limit=0.9999, keep_single=False
        #             )

        #         else:
        #             bpy.ops.object.vertex_group_normalize_all()

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

    def get_bone_list(self, model_armature, h4):
        boneslist = {}
        arm = model_armature.name
        boneslist.update({arm: self.get_armature_props(h4)})
        index = 0
        frameIDs = (
            self.openCSV()
        )  # sample function call to get FrameIDs CSV values as dictionary
        f1 = frameIDs.keys()
        f2 = frameIDs.values()
        bone_list = [bone for bone in model_armature.data.bones if bone.use_deform]
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
                    b.name: self.get_bone_properties(
                        FrameID1,
                        FrameID2,
                        b_nwo.object_space_node,
                        b_nwo.replacement_correction_node,
                        b_nwo.fik_anchor_node,
                    )
                }
            )

        return boneslist

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

    def get_bone_properties(
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
            ob.nwo.poop_predominant_shader_name = self.GetProminantShaderName(ob)

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
    
    def fix_reach_poop_collision(self, export_obs, scene_coll):
        for ob in export_obs:
            nwo = ob.nwo
            if nwo.mesh_type == "_connected_geometry_mesh_type_poop_collision" and not poop_parent(ob):
                nwo.mesh_type = "_connected_geometry_mesh_type_poop"
                nwo.poop_lighting = "_connected_geometry_poop_lighting_per_pixel"
                nwo.poop_pathfinding = "_connected_poop_instance_pathfinding_policy_cutout"
                nwo.poop_imposter_policy = "_connected_poop_instance_imposter_policy_never"
                if nwo.poop_collision_type in ("_connected_geometry_poop_collision_type_play_collision", "_connected_geometry_poop_collision_type_invisible_wall"):
                    nwo.face_mode = "_connected_geometry_face_mode_sphere_collision_only"
                else:
                    nwo.face_mode = "_connected_geometry_face_mode_collision_only"

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
            #print(meshes)
            me_ob_dict = {me: ob for me in meshes for ob in poops if ob.data == me}
            print(me_ob_dict)
            print("\n\n\n")
            len_me_ob_dict = len(me_ob_dict)

            for idx, me in enumerate(me_ob_dict.keys()):
                update_progress(process, idx / len_me_ob_dict)
                linked_poops = me_ob_dict.get(me)

                if type(linked_poops) is not list:
                    for ob in linked_poops.children:
                        nwo = ob.nwo
                        if nwo.mesh_type == "_connected_geometry_mesh_type_poop_collision":
                            if nwo.poop_collision_type == "_connected_geometry_poop_collision_type_play_collision":
                                nwo.mesh_type = "_connected_geometry_mesh_type_poop_physics"
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

            elif nwo_mesh_type != "_connected_geometry_mesh_type_poop_collision":
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
                        nwo_mesh_type = "_connected_geometry_mesh_type_poop_physics"

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
                nwo_coll_type == "_connected_geometry_poop_collision_type_default"
                and "player" not in child_set
                and "bullet" not in child_set
            ):
                child_ob_set[child] = ["default", Matrix(child.matrix_local)]
                child_set.add("bullet")
                child_set.add("player")

            elif (
                nwo_coll_type == "_connected_geometry_poop_collision_type_default"
                and "player" not in child_set
            ):
                child_ob_set[child] = ["player", Matrix(child.matrix_local)]
                child_set.add("player")
                if not h4:
                    nwo_mesh_type = "_connected_geometry_mesh_type_poop_physics"

            elif (
                nwo_coll_type == "_connected_geometry_poop_collision_type_default"
                and "bullet" not in child_set
            ):
                child_ob_set[child] = ["bullet", Matrix(child.matrix_local)]
                child_set.add("player")

        return child_ob_set

    def fix_materials(
        self, ob, me, nwo, override_mat, invalid_mat, water_surface_mat, h4, is_halo_render
    ):
        if h4:
            render_mesh_types = (
                "_connected_geometry_mesh_type_poop",
                "_connected_geometry_mesh_type_decorator",
            )
        else:
            render_mesh_types = (
                "_connected_geometry_mesh_type_default",
                "_connected_geometry_mesh_type_poop",
                "_connected_geometry_mesh_type_decorator",
            )
        # fix multi user materials
        slots = ob.material_slots
        materials = me.materials
        mats = dict.fromkeys(slots)
        slots_to_remove = []
        for idx, slot in enumerate(slots):
            slot_mat = slot.material
            if is_halo_render:
                self.used_materials.add(slot_mat)
            if slot_mat:
                s_name = slot_mat.name
                if s_name not in mats.keys():
                    mats[s_name] = idx
                elif ob.type == 'MESH':
                    bpy.ops.object.mode_set(mode="EDIT", toggle=False)
                    ob.active_material_index = idx
                    slots_to_remove.append(idx)
                    bpy.ops.object.material_slot_select()
                    ob.active_material_index = mats[s_name]
                    bpy.ops.object.material_slot_assign()
                    bpy.ops.object.mode_set(mode="OBJECT", toggle=False)
            else:
                if nwo.mesh_type in render_mesh_types:
                    slot.material = invalid_mat
                elif nwo.mesh_type == "_connected_geometry_mesh_type_water_surface":
                    slot.material = water_surface_mat
                else:
                    slot.material = override_mat

        while slots_to_remove:
            materials.pop(index=slots_to_remove[0])
            slots_to_remove.pop(0)
            slots_to_remove = [idx - 1 for idx in slots_to_remove]

        if not slots:
            # append the new material to the object
            if nwo.mesh_type in render_mesh_types:
                me.materials.append(invalid_mat)
            elif nwo.mesh_type == "_connected_geometry_mesh_type_water_surface":
                me.materials.append(water_surface_mat)
            else:
                me.materials.append(override_mat)

    def markerify(self, export_obs, scene_coll):
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
            original_name = str(ob.name)
            ob.name += "_OLD"
            node = bpy.data.objects.new(original_name, None)
            scene_coll.link(node)
            if ob.parent is not None:
                node.parent = ob.parent
                node.parent_type = ob.parent_type
                if node.parent_type == "BONE":
                    node.parent_bone = ob.parent_bone

            node.matrix_local = ob.matrix_local
            node.scale = ob.scale
            node_nwo = node.nwo

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

        node_halo.marker_game_instance_tag_name = ob_halo.marker_game_instance_tag_name
        node_halo.marker_game_instance_tag_variant_name = (
            ob_halo.marker_game_instance_tag_variant_name
        )
        node_halo.marker_game_instance_run_scripts = (
            ob_halo.marker_game_instance_run_scripts
        )
        node_halo.marker_sphere_radius = ob_halo.marker_sphere_radius

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

        node_halo.hinge_constraint_minimum = ob_halo.hinge_constraint_minimum
        node_halo.hinge_constraint_maximum = ob_halo.hinge_constraint_maximum
        node_halo.cone_angle = ob_halo.cone_angle
        node_halo.plane_constraint_minimum = ob_halo.plane_constraint_minimum
        node_halo.plane_constraint_maximum = ob_halo.plane_constraint_maximum
        node_halo.twist_constraint_start = ob_halo.twist_constraint_start
        node_halo.twist_constraint_end = ob_halo.twist_constraint_end

        node_halo.marker_hint_length = ob_halo.marker_hint_length

        node_halo.marker_looping_effect = ob_halo.marker_looping_effect

        node_halo.marker_light_cone_tag = ob_halo.marker_light_cone_tag
        node_halo.marker_light_cone_color = ob_halo.marker_light_cone_color
        node_halo.marker_light_cone_alpha = ob_halo.marker_light_cone_alpha
        node_halo.marker_light_cone_intensity = ob_halo.marker_light_cone_intensity
        node_halo.marker_light_cone_width = ob_halo.marker_light_cone_width
        node_halo.marker_light_cone_length = ob_halo.marker_light_cone_length
        node_halo.marker_light_cone_curve = ob_halo.marker_light_cone_curve

    #####################################################################################
    #####################################################################################
    # HALO CLASS

    def halo_objects_init(self):
        self.frames = []
        self.markers = []
        self.lighting = []

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

    def halo_objects(self, asset_type, export_obs, h4):
        render_asset = asset_type not in ("SCENARIO", "PREFAB")

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

            if (
                object_type == "_connected_geometry_object_type_frame"
                and ob.type != "LIGHT"
            ):
                self.frames.append(ob)

            elif render_asset:
                if default:
                    self.render.append(ob)
                    self.render_perms.add(permutation)
                elif mesh_type == "_connected_geometry_mesh_type_collision":
                    self.collision.append(ob)
                    self.collision_perms.add(permutation)
                elif mesh_type == "_connected_geometry_mesh_type_physics":
                    self.physics.append(ob)
                    self.physics_perms.add(permutation)
                elif (
                    h4
                    and ob.type == "LIGHT"
                    or nwo.marker_type == "_connected_geometry_marker_type_airprobe"
                ):
                    self.lighting.append(ob)
                elif object_type == "_connected_geometry_object_type_marker":
                    self.markers.append(ob)
                else:
                    self.unlink(ob)

            else:
                bsp = nwo.bsp_name
                if design:
                    self.design.append(ob)
                    self.design_perms.add(permutation)
                    if asset_type == 'SCENARIO':
                        self.design_bsps.add(bsp)
                else:
                    self.structure.append(ob)
                    self.structure_perms.add(permutation)
                    if asset_type == 'SCENARIO':
                        self.structure_bsps.add(bsp)

    def create_bsp_box(self, scene_coll):
        me = bpy.data.meshes.new("bsp_box")
        ob = bpy.data.objects.new("bsp_box", me)
        scene_coll.link(ob)

        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=10000)
        for f in bm.faces:
            f.normal_flip()
        bm.to_mesh(me)
        bm.free()

        ob.nwo.object_type = "_connected_geometry_object_type_mesh"
        ob.nwo.mesh_type = "_connected_geometry_mesh_type_default"
        self.lighting.append(ob)
        ob.parent = self.model_armature
        ob.parent_type = "BONE"
        bones = self.model_armature.data.bones
        for b in bones:
            if b.use_deform:
                root_bone_name = b.name
                break
        ob.parent_bone = root_bone_name

        # copy = ob.copy()
        # copy.nwo.mesh_type = '_connected_geometry_mesh_type_lightprobevolume'
        # scene_coll.link(copy)


    def has_halo_materials(self, nwo, h4):
        if h4:
            render_mesh_types = (
                "_connected_geometry_mesh_type_poop",
                "_connected_geometry_mesh_type_decorator",
                "_connected_geometry_mesh_type_water_surface"
            )
        else:
            render_mesh_types = (
                "_connected_geometry_mesh_type_default",
                "_connected_geometry_mesh_type_poop",
                "_connected_geometry_mesh_type_decorator",
                "_connected_geometry_mesh_type_water_surface"
            )
        
        return nwo.mesh_type in render_mesh_types


#####################################################################################
#####################################################################################
# VARIOUS FUNCTIONS


def set_marker_sphere_size(ob, nwo):
    max_abs_scale = max(abs(ob.scale.x), abs(ob.scale.y), abs(ob.scale.z))
    if ob.type == "EMPTY":
        nwo.marker_sphere_radius = jstr(ob.empty_display_size * max_abs_scale)
    else:
        nwo.marker_sphere_radius = jstr(max(ob.dimensions * max_abs_scale / 2))
        
######
# FRAME ID

def set_frame_ids(context, full_graph_path, model_armature):
    frame_count = 0
    if model_armature is not None:
        try:
            framelist = import_tag_xml(context, full_graph_path)
            if framelist is not None:
                tag_bone_names = clean_bone_names(framelist)
                blend_bone_names = clean_bones(model_armature.data.bones)
                blend_bones = model_armature.data.bones

                for blend_bone in blend_bone_names:
                    for tag_bone in tag_bone_names:
                        if blend_bone == tag_bone:
                            apply_frame_ids(blend_bone, blend_bones, framelist)
                            frame_count += 1

        except:
            pass

    return {"FINISHED"}


def apply_frame_ids(bone_name, bone_names_list, framelist):
    for b in bone_names_list:
        if clean_bone(b) == bone_name:
            b.nwo.frame_id1 = get_id(1, bone_name, framelist)
            b.nwo.frame_id2 = get_id(2, bone_name, framelist)


def get_id(ID, name, framelist):
    frame = ""
    for x in framelist:
        b_name = clean_bone_name(x[0])
        if b_name == name:
            frame = x[ID]
    return frame


def clean_bone_names(bones):
    cleanlist = []
    for b in bones:
        prefix = get_prefix(b[0], frame_prefixes)
        cleaned_bone = b[0].removeprefix(prefix)
        cleanlist.append(cleaned_bone)

    return cleanlist


def clean_bones(bones):
    cleanlist = []
    for b in bones:
        prefix = get_prefix(b.name, frame_prefixes)
        cleaned_bone = b.name.removeprefix(prefix)
        cleanlist.append(cleaned_bone)

    return cleanlist


def clean_bone(bone):
    prefix = get_prefix(bone.name, frame_prefixes)
    cleaned_bone = bone.name.removeprefix(prefix)

    return cleaned_bone


def clean_bone_name(bone):
    prefix = get_prefix(bone, frame_prefixes)
    cleaned_bone = bone.removeprefix(prefix)

    return cleaned_bone


def import_tag_xml(context, full_graph_path):
    xml_path = get_tags_path() + "temp.xml"
    run_tool(["export-tag-to-xml", full_graph_path, xml_path])
    if not os.path.exists(xml_path):
        return
    
    bonelist = parse_xml(xml_path, context)
    os.remove(xml_path)
    return bonelist


def parse_xml(xmlPath, context):
    parent = []
    scene = context.scene
    scene_nwo = scene.nwo

    if scene_nwo.game_version in ("h4", "h2a"):
        tree = ET.parse(xmlPath, parser=ET.XMLParser(encoding="iso-8859-5"))
        root = tree.getroot()
        for b in root.findall("block"):
            for e in b.findall("element"):
                name = ""
                frameID1 = ""
                frameID2 = ""
                for f in e.findall("field"):
                    attributes = f.attrib
                    if attributes.get("name") == "frame_ID1":
                        name = e.get("name")
                        frameID1 = attributes.get("value")
                    elif attributes.get("name") == "frame_ID2":
                        frameID2 = attributes.get("value")
                if not name == "":
                    temp = [name, frameID1, frameID2]
                    parent.append(temp)
    else:
        tree = ET.parse(xmlPath)
        root = tree.getroot()
        for e in root.findall("element"):
            name = ""
            frameID1 = ""
            frameID2 = ""
            for f in e.findall("field"):
                attributes = f.attrib
                if attributes.get("name") == "frame_ID1":
                    name = e.get("name")
                    frameID1 = attributes.get("value")
                elif attributes.get("name") == "frame_ID2":
                    frameID2 = attributes.get("value")
            if not name == "":
                temp = [name, frameID1, frameID2]
                parent.append(temp)

    return parent


def poop_parent(ob):
    parent = ob.parent
    if parent is None:
        return False
    return parent.nwo.mesh_type == '_connected_geometry_mesh_type_poop'

# RESET PROPS

def reset_export_props(nwo):
    """Sets export props to empty strings in case they have leftover data"""
    nwo.object_type = ""
    nwo.mesh_type = ""
    nwo.marker_type = ""
    nwo.permutation_name = ""
    nwo.bsp_name = ""
    nwo.is_pca = ""
    nwo.boundary_surface_type = ""
    nwo.poop_lighting = ""
    nwo.poop_lightmap_resolution_scale = ""
    nwo.poop_pathfinding = ""
    nwo.poop_imposter_policy = ""
    nwo.poop_imposter_brightness = ""
    nwo.poop_imposter_transition_distance = ""
    nwo.poop_streaming_priority = ""
    nwo.poop_render_only = ""
    nwo.poop_chops_portals = ""
    nwo.poop_does_not_block_aoe = ""
    nwo.poop_excluded_from_lightprobe = ""
    nwo.poop_decal_spacing = ""
    nwo.poop_remove_from_shadow_geometry = ""
    nwo.poop_disallow_lighting_samples = ""
    nwo.poop_rain_occluder = ""
    nwo.poop_cinematic_properties = ""
    nwo.poop_collision_type = ""
    nwo.portal_type = ""
    nwo.portal_ai_deafening = ""
    nwo.portal_blocks_sounds = ""
    nwo.portal_is_door = ""
    nwo.mesh_tessellation_density = ""
    nwo.mesh_primitive_type = ""
    nwo.decorator_lod = ""
    nwo.seam_associated_bsp = ""
    nwo.water_volume_depth = ""
    nwo.water_volume_flow_direction = ""
    nwo.water_volume_flow_velocity = ""
    nwo.water_volume_fog_color = ""
    nwo.water_volume_fog_murkiness = ""
    nwo.fog_appearance_tag = ""
    nwo.fog_volume_depth = ""
    nwo.obb_volume_type = ""
    nwo.face_type = ""
    nwo.face_mode = ""
    nwo.face_sides = ""
    nwo.face_draw_distance = ""
    nwo.texcoord_usage = ""
    nwo.region_name = ""
    nwo.uvmirror_across_entire_model = ""
    nwo.face_global_material = ""
    nwo.sky_permutation_index = ""
    nwo.ladder = ""
    nwo.slip_surface = ""
    nwo.decal_offset = ""
    nwo.group_transparents_by_plane = ""
    nwo.no_shadow = ""
    nwo.precise_position = ""
    nwo.no_lightmap = ""
    nwo.no_pvs = ""
    nwo.mesh_compression = ""
    nwo.lightmap_additive_transparency = ""
    nwo.lightmap_resolution_scale = ""
    nwo.lightmap_photon_fidelity = ""
    nwo.lightmap_type = ""
    nwo.lightmap_analytical_bounce_modifier = ""
    nwo.lightmap_general_bounce_modifier = ""
    nwo.lightmap_translucency_tint_color = ""
    nwo.lightmap_lighting_from_both_sides = ""
    nwo.material_lighting_attenuation_cutoff = ""
    nwo.material_lighting_attenuation_falloff = ""
    nwo.material_lighting_emissive_focus = ""
    nwo.material_lighting_emissive_color = ""
    nwo.material_lighting_emissive_per_unit = ""
    nwo.material_lighting_emissive_power = ""
    nwo.material_lighting_emissive_quality = ""
    nwo.material_lighting_use_shader_gel = ""
    nwo.material_lighting_bounce_ratio = ""
    nwo.marker_all_regions = ""
    nwo.marker_game_instance_tag_name = ""
    nwo.marker_game_instance_tag_variant_name = ""
    nwo.marker_game_instance_run_scripts = ""
    nwo.marker_hint_length = ""
    nwo.marker_sphere_radius = ""
    nwo.marker_velocity = ""
    nwo.marker_pathfinding_sphere_vehicle = ""
    nwo.pathfinding_sphere_remains_when_open = ""
    nwo.pathfinding_sphere_with_sectors = ""
    nwo.physics_constraint_parent = ""
    nwo.physics_constraint_child = ""
    nwo.physics_constraint_type = ""
    nwo.physics_constraint_uses_limits = ""
    nwo.hinge_constraint_minimum = ""
    nwo.hinge_constraint_maximum = ""
    nwo.cone_angle = ""
    nwo.plane_constraint_minimum = ""
    nwo.plane_constraint_maximum = ""
    nwo.twist_constraint_start = ""
    nwo.twist_constraint_end = ""
    nwo.marker_looping_effect = ""
    nwo.marker_light_cone_tag = ""
    nwo.marker_light_cone_color = ""
    nwo.marker_light_cone_alpha = ""
    nwo.marker_light_cone_width = ""
    nwo.marker_light_cone_length = ""
    nwo.marker_light_cone_intensity = ""
    nwo.marker_light_cone_curve = ""