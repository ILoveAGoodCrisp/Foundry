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
from math import degrees, radians
from mathutils import Matrix, Vector
from io_scene_foundry.managed_blam.render_model import RenderModelTag
from io_scene_foundry.managed_blam.animation import AnimationTag
from io_scene_foundry.utils.nwo_materials import special_materials
from io_scene_foundry.utils.nwo_constants import VALID_MESHES
from ..utils.nwo_utils import (
    blender_halo_rotation_diff,
    bool_str,
    closest_bsp_object,
    color_3p_str,
    color_4p_str,
    color_argb_str,
    color_rgba_str,
    deselect_all_objects,
    disable_prints,
    dot_partition,
    enable_prints,
    exit_local_view,
    get_area_info,
    get_camera_track_camera,
    get_object_type,
    get_rig,
    get_sky_perm,
    has_shader_path,
    is_marker,
    is_mesh,
    jstr,
    layer_face_count,
    layer_faces,
    library_instanced_collection,
    print_warning,
    relative_path,
    rig_root_deform_bone,
    transform_scene,
    get_tags_path,
    is_corinth,
    set_object_mode,
    set_origin_to_centre,
    set_origin_to_floor,
    stomp_scale_multi_user,
    true_region,
    true_permutation,
    type_valid,
    update_progress,
    vector_str,
    special_material_names,
    convention_material_names,
)

render_mesh_types = [
    "_connected_geometry_mesh_type_poop",
    "_connected_geometry_mesh_type_water_surface",
    "_connected_geometry_mesh_type_decorator",
    "_connected_geometry_mesh_type_object_instance",
]

# Reach special materials

INVISIBLE_SKY = "InvisibleSky"
SEAM_SEALER = "SeamSealer"
COLLISION_ONLY = "CollisionOnly"
SPHERE_COLLISION_ONLY = "SphereCollisionOnly"
LIGHTMAP_ONLY = "LightmapOnly"

# Bone matrix constants

PEDESTAL_MATRIX_X_POSITIVE = Matrix(((1.0, 0.0, 0.0, 0.0),
                                (0.0, 1.0, 0.0, 0.0),
                                (0.0, 0.0, 1.0, 0.0),
                                (0.0, 0.0, 0.0, 1.0)))

PEDESTAL_MATRIX_Y_NEGATIVE = Matrix(((0.0, 1.0, 0.0, 0.0),
                                    (-1.0, 0.0, 0.0, 0.0),
                                    (0.0, 0.0, 1.0, 0.0),
                                    (0.0, 0.0, 0.0, 1.0)))

PEDESTAL_MATRIX_Y_POSITIVE = Matrix(((0.0, -1.0, 0.0, 0.0),
                                    (1.0, 0.0, 0.0, 0.0),
                                    (0.0, 0.0, 1.0, 0.0),
                                    (0.0, 0.0, 0.0, 1.0)))

PEDESTAL_MATRIX_X_NEGATIVE = Matrix(((-1.0, 0.0, 0.0, 0.0),
                                    (0.0, -1.0, 0.0, 0.0),
                                    (0.0, 0.0, 1.0, 0.0),
                                    (0.0, 0.0, 0.0, 1.0)))


TARGET_SCALE = Vector.Fill(3, 1)

halo_x_rot = Matrix.Rotation(radians(90), 4, 'X')
halo_z_rot = Matrix.Rotation(radians(180), 4, 'Z')

#####################################################################################
#####################################################################################
# MAIN CLASS
class PrepareScene:
    def __init__(self):  
        self.warning_hit = False
        self.bsps_with_structure = set()
        self.pedestal = None
        self.aim_pitch = None
        self.aim_yaw = None
        self.gun = None
        self.arm_name = ""
        self.verbose_warnings = False # For outputting info about things we otherwise silently fix
        self.no_export_objects = False
        self.too_many_root_bones = False
        
    def prepare_scene(self, context, asset, asset_type, scene_nwo_export):
        print("\nPreparing Export Scene")
        print(
            "-----------------------------------------------------------------------\n"
        )
        # time it!
        # NOTE skipping timing as export is really fast now
        # start = time.perf_counter()
        
        # Get 3D Viewport area/region/space
        self.area, self.area_region, self.area_space = get_area_info(context)
        
        self.supports_regions_and_perms = asset_type in ('MODEL', 'SKY', 'SCENARIO', 'PREFAB')
        
        self.validated_regions = set()
        self.validated_permutations = set()
        
        if self.supports_regions_and_perms:
            self.regions = [entry.name for entry in context.scene.nwo.regions_table]
            self.permutations = [entry.name for entry in context.scene.nwo.permutations_table]
        else:
            self.regions = ['default']
            self.permutations = ['default']
            self.validated_regions.add('default')
            self.validated_permutations.add('default')
            
        self.default_region = self.regions[0]
        self.default_permutation = self.permutations[0]
        
        self.reg_name = 'BSP' if asset_type in ('SCENARIO', 'PREFAB') else 'region'
        self.perm_name = 'layer' if asset_type in ('SCENARIO', 'PREFAB') else 'permutation'

        h4 = is_corinth(context)
        game_version = 'corinth' if h4 else 'reach'
        
        scene_nwo = context.scene.nwo
        
        global render_mesh_types
        if not h4 or asset_type in ('MODEL', 'SKY'):
            render_mesh_types.append('_connected_geometry_mesh_type_default')

        # Exit local view. Must do this otherwise fbx export will fail.
        exit_local_view(context)
        # print("exit_local_view")

        # Force set object mode
        context.view_layer.update()
        set_object_mode(context)
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
        disable_prints()
        all_obs_start = context.view_layer.objects
        # Remove all marker instancing
        markers = [ob for ob in all_obs_start if is_marker(ob)]
        for ob in markers:
            ob.instance_type = 'NONE'
            
        existing_curves = [ob for ob in bpy.data.objects if ob.type in ('FONT', 'CURVE')]
        
        with context.temp_override(selected_editable_objects=bpy.data.objects):
            bpy.ops.object.duplicates_make_real()
            
        context.view_layer.update()
        # Need to do this due to blender bug which duplicates curves
        new_curves = [ob for ob in bpy.data.objects if ob.type in ('FONT', 'CURVE')]
        
        for ob in new_curves:
            if ob not in existing_curves:
                bpy.data.objects.remove(ob)
            
        context.view_layer.update()
        
        with context.temp_override(selected_editable_objects=bpy.data.objects):
            bpy.ops.object.make_local(type="ALL")
                
        bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)

        enable_prints()

        context.view_layer.update()
        # print("make_local")
        scene_coll = context.scene.collection.objects
        
        # apply geometry nodes
        for ob in bpy.data.objects:
            for mod in ob.modifiers:
                if mod.type == 'NODES' and mod.node_group:
                    with context.temp_override(object=ob):
                        bpy.ops.object.modifier_apply(modifier=mod.name, single_user=True)
        
        # Scale objects
        scale_factor = (1 / 0.03048) if scene_nwo.scale == 'blender' else 1
        rotation = blender_halo_rotation_diff(scene_nwo.forward_direction)
        if scale_factor != 1 or rotation:
            print("--- Transforming Scene")
            transform_scene(context, scale_factor, rotation, scene_nwo.forward_direction, 'x')
            
        # cast view_layer objects to variable
        all_obs = context.view_layer.objects
        
        if asset_type == 'camera_track_set':
            self.camera = get_camera_track_camera(context)
            if not self.camera:
                print_warning('No Camera in scene, cannot export camera track')
                raise RuntimeError
            return
        
        # Combine Armatures is possible
        
        self.model_armature = None
        if asset_type in ("MODEL", "SKY", "FP ANIMATION"):
            self.model_armature = get_rig(context)
            if self.model_armature and not self.model_armature.nwo.exportable:
                print_warning(f'Scene Armature [{self.model_armature.name}] is set to not export. Export cancelled')
                raise RuntimeError
        
            if asset_type in ('MODEL', 'FP ANIMATION') and scene_nwo.main_armature and any((scene_nwo.support_armature_a, scene_nwo.support_armature_b, scene_nwo.support_armature_c)):
                self.consolidate_rig(context, scene_nwo)

        # unlink non export objects
        if asset_type == "FP ANIMATION":
            non_export_obs = [ob for ob in all_obs if ob.type != "ARMATURE"]
        else:
            non_export_obs = [
                ob
                for ob in all_obs
                if not ob.nwo.export_this
                or ob.type in ("LATTICE", "LIGHT_PROBE", "SPEAKER", "CAMERA")
                or (ob.type == "EMPTY" and ob.empty_display_type == "IMAGE")
            ]
        for ob in non_export_obs:
            self.unlink(ob)

        context.view_layer.update()
        export_obs = context.view_layer.objects[:]
        
        scenario_asset = asset_type == "SCENARIO"

        protected_names = self.get_bone_names(export_obs, context.scene.nwo)
        # build proxy instances from structure
        if h4:
            proxy_owners = []
            for ob in export_obs:
                if is_mesh(ob) and ob.nwo.mesh_type_ui == '_connected_geometry_mesh_type_structure' and ob.nwo.proxy_instance:
                    proxy_owners.append(ob)
            if proxy_owners:
                len_proxy_owners = len(proxy_owners)
                process = "--- Creating Proxy Instances from Structure"
                update_progress(process, 0)
                for idx, ob in enumerate(proxy_owners):
                    struc_nwo = ob.nwo
                    struc_nwo.region_name_ui = true_region(struc_nwo)
                    struc_nwo.permutation_name_ui = true_permutation(struc_nwo)
                    proxy_instance = ob.copy()
                    proxy_instance.data = ob.data.copy()
                    proxy_instance.name = f"{ob.name}(instance)"
                    proxy_instance.data.nwo.mesh_type_ui = '_connected_geometry_mesh_type_default'
                    scene_coll.link(proxy_instance)
                    update_progress(process, idx / len_proxy_owners)
                    
                update_progress(process, 1)

        materials = bpy.data.materials

        # create fixup materials
        for sm in special_materials:
            m = materials.get(sm.name)
            if not m:
                m = materials.new(sm.name)
            if h4:
                m.nwo.shader_path = sm.shader_path + '.material' # No support for material face props in H4, so always a material
            else:
                m.nwo.shader_path = sm.shader_path + '.override' if sm.is_face_property else sm.shader_path + '.shader' 
            match sm.name:
                case '+invisible':
                    self.invisible_mat = m
                case '+invalid':
                    self.invalid_mat = m
                case '+seamsealer':
                    self.seamsealer_mat = m
                case '+sky':
                    self.sky_mat = m
                case '+collision':
                    self.collision_mat = m
                case '+sphere_collision':
                    self.sphere_collision_mat = m
                    
        # Not avalialbe to user, but creating this to ensure water renders
        self.water_surface_mat = materials.get("+water")
        if self.water_surface_mat is None:
            self.water_surface_mat = materials.new("+water")
        if h4:
            h2a_water = r"levels\sway\ca_sanctuary\materials\rocks\ca_sanctuary_rockflat_water.material"
            if os.path.exists(get_tags_path() + h2a_water):
                self.water_surface_mat.nwo.shader_path = h2a_water
            else:
                self.water_surface_mat.nwo.shader_path = r"environments\shared\materials\jungle\cave_water.material"
        else:
            self.water_surface_mat.nwo.shader_path = r"levels\multi\forge_halo\shaders\water\forge_halo_ocean_water.shader_water"

        context.view_layer.update()
        export_obs = context.view_layer.objects[:]

        # establish region/global mats sets
        has_global_mats = asset_type in ("MODEL", "SCENARIO", "PREFAB")

        self.global_materials = {"default"}
        self.seams = []
        process = "--- Setting Up Export Scene"
        update_progress(process, 0)
        len_export_obs = len(export_obs)
        self.used_materials = set()
        reach_sky_lights = []
        is_sky = asset_type == 'SKY'
        is_scenario = asset_type == 'SCENARIO'
        # start the great loop!
        for idx, ob in enumerate(export_obs):
            nwo = ob.nwo

            reset_export_props(nwo)
            
            me = ob.data
            ob_type = ob.type
            is_mesh_loose = ob_type in VALID_MESHES

            # export objects must be visible and selectable
            ob.hide_set(False)
            ob.hide_select = False

            # If this is a Reach light, fix it's rotation
            # Blender lights emit in -z, while Halo emits light from +y
            if not h4 and ob_type == "LIGHT":
                if is_sky:
                    reach_sky_lights.append(ob)
                    self.unlink(ob)
                    continue
                elif not is_scenario:
                    self.unlink(ob)
                    continue
                
                ob.matrix_world = ob.matrix_world @ halo_x_rot @ halo_z_rot

            self.strip_prefix(ob, protected_names)
            # if not_bungie_game():
            #     self.apply_namespaces(ob, asset)

            nwo.object_type = get_object_type(ob)

            if asset_type in ('MODEL', 'SKY', 'SCENARIO', 'PREFAB'):
                nwo.permutation_name_ui = self.default_region if not nwo.permutation_name_ui else nwo.permutation_name_ui
                nwo.region_name_ui = self.default_permutation if not nwo.region_name_ui else nwo.region_name_ui

                # cast ui props to export props
                if self.supports_regions_and_perms and nwo.object_type == '_connected_geometry_object_type_mesh' and nwo.mesh_type_ui != '_connected_geometry_mesh_type_object_instance':
                    reg = true_region(nwo)
                    if reg in self.regions:
                        self.validated_regions.add(reg)
                        nwo.region_name = true_region(nwo)
                    else:
                        self.warning_hit = True
                        print_warning(f"Object [{ob.name}] has {self.reg_name} [{reg}] which is not presented in the {self.reg_name}s table. Setting {self.reg_name} to: {self.default_region}")
                        nwo.permutation_name = self.default_permutation
                        
                    perm = true_permutation(nwo)
                    if perm in self.permutations:
                        self.validated_permutations.add(perm)
                        nwo.permutation_name = true_permutation(nwo)
                    else:
                        self.warning_hit = True
                        print_warning(f"Object [{ob.name}] has {self.perm_name} [{perm}] which is not presented in the {self.perm_name}s table. Setting {self.perm_name} to: {self.default_permutation}")
                        nwo.permutation_name = self.default_permutation
                else:
                    nwo.region_name = 'default'
                    nwo.permutation_name = 'default'
            
            if nwo.object_type == '_connected_geometry_object_type_none':
                self.unlink(ob)
                continue
            
            elif nwo.object_type == '_connected_geometry_object_type_mesh':
                if nwo.mesh_type_ui == '':
                    nwo.mesh_type_ui = '_connected_geometry_mesh_type_default'
                if type_valid(nwo.mesh_type_ui, asset_type, game_version):
                    if self.setup_mesh_properties(ob, nwo.mesh_type_ui, asset_type, h4, nwo):
                        if scene_nwo_export.triangulate:
                            add_triangle_mod(ob)
                    else:
                        self.unlink(ob)
                        continue
                    
                else:
                    self.warning_hit = True
                    print_warning(f"{ob.name} has illegal mesh type: [{nwo.mesh_type_ui}]. Skipped")
                    self.unlink(ob)
                    continue
                
            elif nwo.object_type == '_connected_geometry_object_type_marker':
                if nwo.marker_type_ui == '':
                    nwo.marker_type_ui = '_connected_geometry_marker_type_model'
                if type_valid(nwo.marker_type_ui, asset_type, game_version):
                    self.setup_marker_properties(ob, nwo.marker_type_ui, asset_type, h4, nwo)
                else:
                    self.warning_hit = True
                    print_warning(f"{ob.name} has illegal marker type: [{nwo.marker_type_ui}]. Skipped")
                    self.unlink(ob)
                    continue

            is_halo_render = is_mesh_loose and nwo.object_type == '_connected_geometry_object_type_mesh' and nwo.mesh_type in render_mesh_types

            # add region/global_mat to sets
            uses_global_mat = has_global_mats and (nwo.mesh_type in ("_connected_geometry_mesh_type_collision", "_connected_geometry_mesh_type_physics", "_connected_geometry_mesh_type_poop", "_connected_geometry_mesh_type_poop_collision") or scenario_asset and not h4 and nwo.mesh_type == "_connected_geometry_mesh_type_default")

            if uses_global_mat:
                self.global_materials.add(nwo.face_global_material)

            if scene_nwo_export.export_gr2_files:
                if is_mesh_loose:
                    # Add materials to all objects without one. No materials = unhappy Tool.exe
                    does_not_support_sky = nwo.mesh_type != '_connected_geometry_mesh_type_default' or asset_type != 'SCENARIO'
                    self.fix_materials(
                        context, ob, me, nwo, h4, is_halo_render, does_not_support_sky, scene_coll
                    )
                
            update_progress(process, idx / len_export_obs)

        update_progress(process, 1)

        # OB LOOP COMPLETE----------------------------------------------------------------------------------------------
        # --------------------------------------------------------------------------------------------------------------
        # print("ob_loop")

        # get selected perms and bsps for use later
        self.selected_perms = set()
        self.selected_bsps = set()

        sel_perms = scene_nwo_export.export_all_perms == "selected"
        sel_bsps = scene_nwo_export.export_all_bsps == "selected"

        if sel_perms or sel_bsps:
            for ob in objects_selection:
                nwo = ob.nwo

                if sel_perms:
                    self.selected_perms.add(nwo.permutation_name)

                if sel_bsps:
                    self.selected_bsps.add(nwo.region_name)
                    
        self.null_path_materials = []
        self.invalid_path_materials = []
        for idx, mat in enumerate(self.used_materials):
            mat_nwo = mat.nwo
            if has_shader_path(mat):
                # Enforce relativity
                mat_nwo.shader_path = relative_path(mat_nwo.shader_path)
                if not mat_nwo.shader_path:
                    self.null_path_materials.append(mat)
                    self.warning_hit = True
                    mat.nwo.shader_path = self.invalid_mat.nwo.shader_path
                        
                elif not os.path.exists(get_tags_path() + mat_nwo.shader_path):
                    self.invalid_path_materials.append(mat)
                    self.warning_hit = True
                    mat.nwo.shader_path = self.invalid_mat.nwo.shader_path
                
        if self.null_path_materials:
            if h4:
                print_warning("\nFound blender materials with empty material tag paths:")
            else:
                print_warning("\nFound blender materials with empty shader tag paths:")
                
            for m in self.null_path_materials:
                print_warning(f'  {m.name}')
                
        if self.invalid_path_materials:
            if h4:
                print_warning("\nFound blender materials with invalid material tag paths:")
            else:
                print_warning("\nFound blender materials with invalid shader tag paths:")
                
            for m in self.invalid_path_materials:
                print_warning(f'  {m.name}')

        # build seams
        if self.seams:
            if len(self.regions) < 2:
                self.warning_hit = True
                print_warning(
                    "Only single BSP in scene, seam objects ignored from export"
                )
                for seam in self.seams:
                    # print(seam.name)
                    self.unlink(seam)

            else:
                len_seams = len(self.seams)
                skip_seams = []
                for idx, seam in enumerate(self.seams):
                    if seam in skip_seams:
                        continue
                    seam_me = seam.data
                    seam_bm = bmesh.new()
                    seam_bm.from_mesh(seam_me)
                    bmesh.ops.triangulate(seam_bm, faces=seam_bm.faces)
                    seam_bm.to_mesh(seam_me)
                    seam_nwo = seam.nwo
                    # existing_back_seam = self.check_existing_back_seam(seam)
                    # if existing_back_seam:
                    #     skip_seams.append(existing_back_seam)
                    #     self.unlink(existing_back_seam)
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
                        or back_ui == seam_nwo.region_name
                        or back_ui not in self.regions
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
                            back_nwo.region_name = closest_bsp.nwo.region_name
                    else:
                        back_nwo.region_name = seam_nwo.seam_back_ui

                    back_seam.name = f"seam({back_nwo.region_name}:{seam_nwo.region_name})"

                    scene_coll.link(back_seam)

        # get new export_obs
        context.view_layer.update()
        export_obs = context.view_layer.objects[:]
        
        if not export_obs:
            # If there are no objects in the scene, abort the export
            self.no_export_objects = True
            return

        # apply face layer properties
        self.apply_face_properties(
            context, export_obs, scene_coll, h4, asset_type == "SCENARIO",  asset_type == "PREFAB"
        )
        # print("face_props_applied")

        # get new export_obs from split meshes
        context.view_layer.update()
        export_obs = context.view_layer.objects[:]
        if scene_nwo_export.export_gr2_files:
            # poop proxy madness
            # self.setup_poop_proxies(export_obs, h4)
            # print("poop_proxies") 

            # get new proxy export_obs
            # context.view_layer.update()
            # export_obs = context.view_layer.objects[:]

            # remove meshes with zero faces
            self.cull_zero_face_meshes(export_obs, context)

            context.view_layer.update()
            export_obs = context.view_layer.objects[:]
            
            # Fix objects with bad scale values
            poops, nonstandard_scale = self.fix_scale(context, export_obs)
            if poops and nonstandard_scale:
                stomp_scale_multi_user(poops)
                
        # Update tables from any new set entries created during export
        # update_tables_from_objects(context)
        # Establish a dictionary of scene regions. Used later in export_gr2 and build_sidecar
        # regions = [region for region in self.regions if region]
        # self.regions_dict = {region: str(idx) for idx, region in enumerate(regions)}
        # Now just using the scene regions table

        # Establish a dictionary of scene global materials. Used later in export_gr2 and build_sidecar
        global_materials = ["default"]
        for glob_mat in self.global_materials:
            if glob_mat != "default" and glob_mat:
                global_materials.append(glob_mat)

        self.global_materials_dict = {
            global_material: str(idx)
            for idx, global_material in enumerate(global_materials)
            if global_material
        }

        # get all objects that we plan to export later
        self.halo_objects_init()
        self.halo_objects(asset_type, export_obs, h4)
        # print("halo_objects")

        context.view_layer.update()
        export_obs = context.view_layer.objects[:]

        self.skeleton_bones = {}
        self.current_action = None

        if asset_type in ("MODEL", "SKY", "FP ANIMATION"):
            forward = context.scene.nwo.forward_direction
            if self.lighting:
                self.create_bsp_box(scene_coll)

            if self.model_armature:
                if bpy.data.actions:
                    self.current_action = bpy.data.actions[scene_nwo.active_action_index]
                    context.scene.tool_settings.use_keyframe_insert_auto = False

                self.remove_relative_parenting(context, export_obs)

                if self.model_armature and asset_type != "FP ANIMATION":
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
                if scene_nwo_export.export_gr2_files and self.model_armature:
                    # self.set_bone_names(self.model_armature.data.bones) NOTE no longer renaming bones
                    root_bones = [b for b in self.model_armature.data.bones if b.use_deform and not b.parent]
                    if len(root_bones) > 1:
                        self.too_many_root_bones = True
                        return
                    self.skeleton_bones = self.get_bone_list(
                        self.model_armature, h4, context, asset_type
                    )
                
                if self.model_armature:
                    if forward == "x":
                        self.pedestal_matrix = PEDESTAL_MATRIX_X_POSITIVE
                    elif forward == "x-":
                        self.pedestal_matrix = PEDESTAL_MATRIX_X_NEGATIVE
                    elif forward == "y":
                        self.pedestal_matrix = PEDESTAL_MATRIX_Y_POSITIVE
                    else:
                        self.pedestal_matrix = PEDESTAL_MATRIX_Y_NEGATIVE

        # print("armature")

        # Set timeline range for use during animation export
        self.timeline_start, self.timeline_end = self.set_timeline_range(context)
        
        if not self.render and asset_type in ("MODEL", "SKY", "DECORATOR SET", "PARTICLE MODEL", "FP ANIMATION"):
            self.render = [self.add_null_render(scene_coll)]
            context.view_layer.update()
            export_obs = context.view_layer.objects[:]

        # rotate the model armature if needed
        if scene_nwo_export.export_gr2_files:
            if self.model_armature:
                self.force_fcurves_to_start_at_zero(
                    asset_type,
                    scene_nwo_export.export_animations,
                )

        # Set animation name overrides
        if self.model_armature:
            self.set_animation_overrides(self.model_armature)

        # get the max LOD count in the scene if we're exporting a decorator
        self.lods = self.get_decorator_lods(asset_type == "DECORATOR SET")
        
        # Validate regions and perms
        null_regions = [r for r in self.regions if r not in self.validated_regions]
        if null_regions:
            self.warning_hit = True
            print('')
            for r in null_regions:
                print_warning(f'No export object has {self.reg_name}: {r}')
                
            self.regions = [r for r in self.regions if r not in null_regions]
            
        null_permutations = [p for p in self.permutations if p not in self.validated_permutations]
        if null_permutations:
            self.warning_hit = True
            print('')
            for p in null_permutations:
                print_warning(f'No export object has {self.perm_name}: {p}')
                
            self.permutations = [p for p in self.permutations if p not in null_permutations]
            
        # Order these to match regions/perms table
        if len(self.structure_bsps) > 1:
            self.structure_bsps = [b for b in self.regions if b in self.structure_bsps]
        if len(self.structure_perms) > 1:
            self.structure_perms = [l for l in self.permutations if l in self.structure_perms]
        if len(self.design_bsps) > 1:
            self.design_bsps = [b for b in self.regions if b in self.design_bsps]
        if len(self.design_perms) > 1:
            self.design_perms = [l for l in self.permutations if l in self.design_perms]
        
        if asset_type == 'SCENARIO':
            if self.generate_structure(export_obs, scene_coll, h4):
                context.view_layer.update()
        
        # Build skylight dict
        self.skylights = {}
        if reach_sky_lights:
            # undo scale change
            if scale_factor != 1:
                light_scale = 0.03048 ** 2
                sun_scale = 0.03048
            else:
                light_scale = 1
                sun_scale = 1
            sun = None
            lightGen_colors = []
            lightGen_directions = []
            lightGen_solid_angles = []
            for ob in reach_sky_lights:
                if (ob.data.energy * light_scale) < 0.01:
                    sun = ob
                down = Vector((0, 0, -1))
                down.rotate(ob.rotation_euler)
                lightGen_colors.append(color_3p_str(ob.data.color))
                lightGen_directions.append(f'{jstr(down[0])} {jstr(down[1])} {jstr(down[2])}')
                lightGen_solid_angles.append(jstr(ob.data.energy * light_scale))
                
            self.skylights['lightGen_colors'] = ' '.join(lightGen_colors)
            self.skylights['lightGen_directions'] = ' '.join(lightGen_directions)
            self.skylights['lightGen_solid_angles'] = ' '.join(lightGen_solid_angles)
            self.skylights['lightGen_samples'] = str(len(reach_sky_lights) - 1)
            
            if sun is not None:
                if sun.data.color.v > 1:
                    sun.data.color.v = 1
                self.skylights['sun_size'] = jstr((max(sun.scale.x, sun.scale.y, sun.scale.z) * sun_scale))
                self.skylights['sun_intensity'] = jstr(sun.data.energy * 10000 * light_scale)
                self.skylights['sun_color'] = color_3p_str(sun.data.color)

        if self.warning_hit:
            print_warning(
                "\nScene has issues that should be resolved for subsequent exports"
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

    def cull_zero_face_meshes(self, export_obs, context):
        # disable_prints()
        # convert mesh-like objects to real meshes to properly assess them
        mesh_like_objects = [ob for ob in export_obs if ob.type in ("CURVE", "SURFACE", "META", "FONT")]
        if mesh_like_objects:
            [ob.select_set(True) for ob in mesh_like_objects]
            context.view_layer.objects.active = mesh_like_objects[0]
            bpy.ops.object.convert(target='MESH')
            [ob.select_set(False) for ob in mesh_like_objects]
            
        for ob in export_obs:
            # apply all modifiers if mesh has no polys
            if ob.type == "MESH" and not ob.data.polygons and ob.modifiers:
                with context.temp_override(active_object=ob):
                    modifiers = ob.modifiers
                    for mod in modifiers:
                        try:
                            mod.show_render = True
                            mod.show_viewport = True
                            bpy.ops.object.modifier_apply(modifier=mod.name, single_user=True)
                        except:
                            print(f'Failed to apply {mod.name} modifier to {ob.name}')
                

            if ob.type == "MESH" and not ob.data.polygons:
                # print_warning(f"Removed object: [{ob.name}] from export because it has no polygons")
                # self.warning_hit = True
                self.unlink(ob)

        # enable_prints()

    # FACEMAP SPLIT

    def justify_face_split(self, layer_faces_dict, poly_count):
        """Checked whether we actually need to split this mesh up"""
        # check if face layers cover the whole mesh, if they do, we don't need to split the mesh
        for layer, face_seq in layer_faces_dict.items():
            if not face_seq:
                continue
            face_count = len(face_seq)
            if not face_count:
                continue

            if poly_count != face_count:
                return True

        return False
            
    def strip_nocoll_only_faces(self, layer_faces_dict, bm):
        """Removes faces from a mesh that shouldn't be used to build proxy collision"""
        for layer, face_seq in layer_faces_dict.items():
            if layer.render_only_override or layer.sphere_collision_only_override or layer.breakable_override:
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
        is_proxy,
        is_recursion=False
    ):
        # faces_layer_dict = {faces: layer for layer, faces in layer_faces_dict.keys()}
        faces_layer_dict = {}
        for layer, face_seq in layer_faces_dict.items():
            fs = tuple(face_seq)
            if fs in faces_layer_dict.keys() and face_seq:
                faces_layer_dict[fs].append(layer)
            elif face_seq:
                faces_layer_dict[fs] = [layer]

        length_layer_dict = len(faces_layer_dict.keys())
        for idx, face_seq in enumerate(faces_layer_dict.keys()):
            if face_seq:
                if not is_recursion and idx == length_layer_dict - 1:
                    split_objects.append(ob)
                else:
                    # delete faces from new mesh
                    to_delete_indexes = [f.index for f in bm.faces if f in face_seq]
                    split_bm = bm.copy()
                    # new_face_seq = [face for face in split_bm.faces if face not in face_seq]
                    bmesh.ops.delete(
                        bm,
                        geom=[f for f in bm.faces if not f.index in to_delete_indexes],
                        context="FACES",
                    )
                    split_ob = ob.copy()

                    split_ob.data = me.copy()
                    split_me = split_ob.data

                    bm.to_mesh(me)
                    bmesh.ops.delete(
                        split_bm,
                        geom=[f for f in split_bm.faces if f.index in to_delete_indexes],
                        context="FACES",
                    )
                    split_bm.to_mesh(split_me)

                    if not is_proxy:
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
                            is_proxy,
                            True,
                        )

        return split_objects
    
    # def needs_collision_proxy(self, ob):
    #     for props in ob.data.nwo.face_props:
    #         if props.face_global_material_override:
    #             return True
    #         if props.ladder_override:
    #             return True
    #         if props.slip_surface_override:
    #             return True
    #         if props.decal_offset_override:
    #             return True
    #         if props.no_shadow_override:
    #             return True
    #         if props.precise_position_override:
    #             return True
    #         if props.no_lightmap_override:
    #             return True
    #         if props.no_pvs_override:
    #             return True
    #         if props.lightmap_additive_transparency_override:
    #             return True
    #         if props.lightmap_resolution_scale_override:
    #             return True
    #         if props.lightmap_type_override:
    #             return True
    #         if props.lightmap_translucency_tint_color_override:
    #             return True
    #         if props.lightmap_lighting_from_both_sides_override:
    #             return True
    #         if props.emissive_override:
    #             return True
            
    #     return False
    
    def coll_proxy_two_sided(self, ob, bm: bmesh.types.BMesh):
        for props in ob.data.nwo.face_props:
            if props.face_two_sided_override:
                if layer_face_count(bm, bm.faces.layers.int.get(props.layer_name)):
                    return True
            
        return False
        

    def split_to_layers(self, ob, ob_nwo, me, face_layers, scene_coll, h4, bm, is_proxy):
        poly_count = len(bm.faces)
        layer_faces_dict = {
            layer: layer_faces(bm, bm.faces.layers.int.get(layer.layer_name))
            for layer in face_layers
        }

        collision_ob = None
        justified = self.justify_face_split(layer_faces_dict, poly_count)
        bm.to_mesh(me)
        if justified:
            # if instance geometry, we need to fix the collision model (provided the user has not already defined one)
            render_mesh = ob.nwo.mesh_type in render_mesh_types
            is_poop = ob_nwo.mesh_type == "_connected_geometry_mesh_type_poop"
            
            if (
                is_poop and not h4
            ):  # don't do this for h4 as collision can be open
                # check for custom collision / physics
                
                # Set this globally for the poop we're about to split
                # We do this because a custom collison mesh is being built
                # and without the render_only property, the mesh will still
                # report open edges in game
                ob.nwo.face_mode = "_connected_geometry_face_mode_render_only"

                has_coll_child = False

                # Check if the poop already has child collision/physics
                # We can skip building this from face properties if so
                for child in ob.children:
                    if child.nwo.mesh_type == '_connected_geometry_mesh_type_poop_collision':
                        has_coll_child = True

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
                    poly_count = self.strip_nocoll_only_faces(coll_layer_faces_dict, coll_bm)

                    coll_bm.to_mesh(collision_ob.data)

                    collision_ob.name = f"{ob.name}(collision)"
                    if self.coll_proxy_two_sided(ob, coll_bm):
                        collision_ob.nwo.face_sides = '_connected_geometry_face_sides_two_sided'

                    ori_matrix = ob.matrix_world
                    collision_ob.nwo.mesh_type = "_connected_geometry_mesh_type_poop_collision"

            normals_ob = ob.copy()
            normals_ob.data = me.copy()

            # create new face layer for remaining faces
            remaining_faces = []
            for f in bm.faces:
                for fseq in layer_faces_dict.values():
                    if f in fseq:
                        break
                else:
                    remaining_faces.append(f)

            layer_faces_dict["|~~no_face_props~~|"] = remaining_faces
            # Splits the mesh recursively until each new mesh only contains a single face layer
            split_objects_messy = self.recursive_layer_split(
                ob, me, face_layers, layer_faces_dict, h4, scene_coll, [ob], bm, is_proxy
            )
            ori_ob_name = str(ob.name)
                
            # remove zero poly obs from split_objects_messy
            split_objects = [s_ob for s_ob in split_objects_messy if s_ob.data.polygons]
            no_polys = [s_ob for s_ob in split_objects_messy if s_ob not in split_objects]

            # Ensure existing proxies aren't parented to zero face mesh
            for s_ob in no_polys:
                if s_ob.children:
                    for child in s_ob.children:
                        child.parent = split_objects[0]
            
            for split_ob in split_objects:
                more_than_one_prop = False
                obj_bm = bmesh.new()
                obj_bm.from_mesh(split_ob.data)
                obj_name_suffix = ""
                for layer in split_ob.data.nwo.face_props:
                    if layer_face_count(
                        obj_bm, obj_bm.faces.layers.int.get(layer.layer_name)
                    ):
                        self.face_prop_to_mesh_prop(split_ob.nwo, layer, h4, split_ob, scene_coll)
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
                for split_ob in reversed(split_objects):
                    if not split_ob.nwo.face_mode in ("_connected_geometry_face_mode_collision_only", "_connected_geometry_face_mode_sphere_collision_only", "_connected_geometry_face_mode_breakable"):
                        parent_ob = split_ob
                        break
                else:
                    # only way to make invisible collision...
                    if collision_ob is not None:
                        collision_ob.nwo.mesh_type = "_connected_geometry_mesh_type_poop"
                        collision_ob.nwo.face_mode = "_connected_geometry_face_mode_collision_only"

                if parent_ob is not None:
                    if collision_ob is not None:
                        collision_ob.parent = parent_ob
                        collision_ob.matrix_world = ori_matrix
                        
                # remove coll only split objects, as this is already covered by the coll mesh
                coll_only_objects = []
                for split_ob in split_objects:
                    if split_ob.nwo.face_mode == "_connected_geometry_face_mode_collision_only":
                        coll_only_objects.append(split_ob)
                        self.unlink(split_ob)
                        
                # recreate split objects list
                split_objects = [ob for ob in split_objects if ob not in coll_only_objects]

            return split_objects

        else:
            for layer in face_layers:
                self.face_prop_to_mesh_prop(ob.nwo, layer, h4, ob, scene_coll)

            return [ob]
    
            
    def face_prop_to_mesh_prop(self, mesh_props, face_props, h4, ob, scene_coll):
        # ignore unused face_prop items
        # run through each face prop and apply it to the mesh if override set
        # if face_props.seam_override and ob.nwo.mesh_type == '_connected_geometry_mesh_type_default':
        #     mesh_props.mesh_type = '_connected_geometry_mesh_type_seam'
        #     create_adjacent_seam(ob, face_props.seam_adjacent_bsp)

        # reset mesh props
        # first set the persistent mesh props, followed by the optional


        if face_props.render_only_override:
            if h4:
                mesh_props.poop_collision_type = "_connected_geometry_poop_collision_type_none"
            else:
                mesh_props.face_mode = "_connected_geometry_face_mode_render_only"
        elif face_props.collision_only_override:
            if h4:
                mesh_props.mesh_type = '_connected_geometry_mesh_type_poop_collision'
                mesh_props.poop_collision_type = "_connected_geometry_poop_collision_type_default"
            else:
                mesh_props.face_mode = "_connected_geometry_face_mode_collision_only"
        elif face_props.sphere_collision_only_override:
            if h4:
                mesh_props.mesh_type = '_connected_geometry_mesh_type_poop_collision'
                mesh_props.poop_collision_type = "_connected_geometry_poop_collision_type_invisible_wall"
            else:
                mesh_props.face_mode = "_connected_geometry_face_mode_sphere_collision_only"
        elif h4 and face_props.player_collision_only_override:
            mesh_props.mesh_type = '_connected_geometry_mesh_type_poop_collision'
            mesh_props.poop_collision_type = "_connected_geometry_poop_collision_type_play_collision"
        elif h4 and face_props.bullet_collision_only_override:
            mesh_props.mesh_type = '_connected_geometry_mesh_type_poop_collision'
            mesh_props.poop_collision_type = "_connected_geometry_poop_collision_type_bullet_collision"
            
        if not h4 and face_props.breakable_override:
            mesh_props.face_mode = '_connected_geometry_face_mode_breakable'

        # Handle face sides, game wants an enum but Foundry uses flags
        face_sides_value = "_connected_geometry_face_sides_"
        has_transparency = face_props.face_transparent_override and mesh_props.mesh_type in render_mesh_types
        if face_props.face_two_sided_override:
            # Only h4+ support properties for the backside face
            if h4 and mesh_props.mesh_type in render_mesh_types:
                face_sides_value += face_props.face_two_sided_type_ui
            else:
                face_sides_value += "two_sided"
            # Add transparency if set
            if has_transparency:
                face_sides_value += "_transparent"
            mesh_props.face_sides = face_sides_value
            
        elif has_transparency:
            face_sides_value += "one_sided_transparent"
            mesh_props.face_sides = face_sides_value
        

        if face_props.region_name_override:
            reg = face_props.region_name_ui
            
            if reg in self.regions:
                self.validated_regions.add(reg)
                mesh_props.region_name = reg
            else:
                self.warning_hit = True
                print_warning(f"Object [{ob.name}] has {self.reg_name} face property [{reg}] which is not presented in the {self.reg_name}s table. Setting {self.reg_name} to: {self.default_region}")
                mesh_props.region_name = self.default_region

        if face_props.face_global_material_override:
            mesh_props.face_global_material = face_props.face_global_material_ui
            self.global_materials.add(mesh_props.face_global_material)

        if face_props.ladder_override:
            mesh_props.ladder = "1"

        if face_props.slip_surface_override:
            mesh_props.slip_surface = "1"

        if face_props.decal_offset_override:
            mesh_props.decal_offset = "1"

        if face_props.no_shadow_override:
            mesh_props.no_shadow = "1"

        if face_props.precise_position_override:
            mesh_props.precise_position = "1"

        if face_props.no_lightmap_override:
            mesh_props.no_lightmap = "1"

        if face_props.no_pvs_override:
            mesh_props.no_pvs = "1"

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
            mesh_props.lightmap_resolution_scale = jstr(
                face_props.lightmap_resolution_scale_ui
            )

            mesh_props.lightmap_resolution_scale_active = True
        if face_props.lightmap_type_override:
            mesh_props.lightmap_type = face_props.lightmap_type_ui
            
        if face_props.lightmap_translucency_tint_color_override:
            mesh_props.lightmap_translucency_tint_color = color_4p_str(
                face_props.lightmap_translucency_tint_color_ui
            )
            mesh_props.lightmap_translucency_tint_color_active = True
        if face_props.lightmap_lighting_from_both_sides_override:
            mesh_props.lightmap_lighting_from_both_sides = "1"
            
        # emissive props
        if face_props.emissive_override:
            mesh_props.material_lighting_attenuation_falloff = jstr(
                face_props.material_lighting_attenuation_falloff_ui * 100 * 0.03048 * 0.328084
            )
            mesh_props.material_lighting_attenuation_cutoff = jstr(
                face_props.material_lighting_attenuation_cutoff_ui * 100 * 0.03048 * 0.328084
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
            if h4:
                mesh_props.material_lighting_emissive_power = jstr(
                    face_props.material_lighting_emissive_power_ui * 0.03048 * 0.328084 / 20
                )
            else:
                mesh_props.material_lighting_emissive_power = jstr(
                    face_props.material_lighting_emissive_power_ui * 0.03048 * 0.328084
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
                special_ob = ob.copy()
                scene_coll.link(special_ob)
                mesh_props.ladder = ""
                mesh_props.slip_surface = ""
                special_ob.nwo.face_sides = "_connected_geometry_face_sides_two_sided"
                special_ob.nwo.face_mode = "_connected_geometry_face_mode_sphere_collision_only"


    def proxy_face_split(self, ob, context, scene_coll, h4):
        me = ob.data
        me_nwo = me.nwo
        ob_nwo = ob.nwo

        face_layers = me_nwo.face_props

        if face_layers:
            bm = bmesh.new()
            bm.from_mesh(me)

            # must ensure all faces are visible
            for face in bm.faces:
                face.hide_set(False)

            return self.split_to_layers(
                ob, ob_nwo, me, face_layers, scene_coll, h4, bm, True
            )

        return [ob]

    def setup_instance_proxies(self, scenario, prefab, me, h4, linked_objects, scene_coll, context):
        if scenario or prefab:
            proxy_physics = me.nwo.proxy_physics
            proxy_collision = me.nwo.proxy_collision
            proxy_cookie_cutter = me.nwo.proxy_cookie_cutter
            
            coll = proxy_collision is not None
            phys = proxy_physics is not None
            cookie = proxy_cookie_cutter is not None and not h4
            
            if phys:
                proxy_physics.nwo.object_type = "_connected_geometry_object_type_mesh"
                glob_mat_phys = proxy_physics.data.nwo.face_global_material_ui
                if glob_mat_phys:
                    proxy_physics.nwo.face_global_material = glob_mat_phys
                    self.global_materials.add(glob_mat_phys)

                if h4:
                    proxy_physics.nwo.mesh_type = "_connected_geometry_mesh_type_poop_collision"
                    proxy_physics.nwo.poop_collision_type = "_connected_geometry_poop_collision_type_play_collision"
                    split_physics = self.proxy_face_split(proxy_physics, context, scene_coll, h4)
                else:
                    proxy_physics.nwo.mesh_type = "_connected_geometry_mesh_type_poop_physics"
                    if proxy_physics.data.nwo.face_global_material_ui or proxy_physics.data.nwo.face_props:
                        self.set_reach_coll_materials(proxy_physics.data, bpy.data.materials)


            
            if coll:
                proxy_collision.nwo.object_type = "_connected_geometry_object_type_mesh"
                proxy_collision.nwo.mesh_type = "_connected_geometry_mesh_type_poop_collision"
                glob_mat_coll = proxy_collision.data.nwo.face_global_material_ui
                if glob_mat_coll:
                    proxy_collision.nwo.face_global_material = glob_mat_coll
                    self.global_materials.add(glob_mat_coll)
                if h4:
                    if phys:
                        proxy_collision.nwo.poop_collision_type = "_connected_geometry_poop_collision_type_bullet_collision"
                    else:
                        proxy_collision.nwo.poop_collision_type = "_connected_geometry_poop_collision_type_default"

                    split_collision = self.proxy_face_split(proxy_collision, context, scene_coll, h4)
                elif proxy_collision.data.nwo.face_global_material_ui or proxy_collision.data.nwo.face_props:
                    self.set_reach_coll_materials(proxy_collision.data, bpy.data.materials)

            
            if cookie:
                proxy_cookie_cutter.nwo.object_type = "_connected_geometry_object_type_mesh"
                proxy_cookie_cutter.nwo.mesh_type = "_connected_geometry_mesh_type_cookie_cutter"

            if phys or coll or cookie:
                poops = [o for o in linked_objects if o.nwo.mesh_type == "_connected_geometry_mesh_type_poop"]
                for o in poops:
                    if coll:
                        if h4:
                            for s_ob in split_collision:
                                o_collision = s_ob.copy()
                                scene_coll.link(o_collision)
                                o_collision.nwo.permutation_name = o.nwo.permutation_name
                                o_collision.nwo.region_name = o.nwo.region_name
                                o_collision.parent = o
                                o_collision.matrix_world = o.matrix_world
                        else:
                            o.nwo.face_mode = "_connected_geometry_face_mode_render_only"
                            o_collision = proxy_collision.copy()
                            scene_coll.link(o_collision)
                            o_collision.nwo.permutation_name = o.nwo.permutation_name
                            o_collision.nwo.region_name = o.nwo.region_name
                            o_collision.parent = o
                            o_collision.matrix_world = o.matrix_world

                    if phys:
                        if h4:
                            for s_ob in split_physics:
                                o_physics = s_ob.copy()
                                scene_coll.link(o_physics)
                                o_physics.nwo.permutation_name = o.nwo.permutation_name
                                o_physics.nwo.region_name = o.nwo.region_name
                                o_physics.parent = o
                                o_physics.matrix_world = o.matrix_world

                        else:
                            o_physics = proxy_physics.copy()
                            scene_coll.link(o_physics)
                            o_physics.nwo.permutation_name = o.nwo.permutation_name
                            o_physics.nwo.region_name = o.nwo.region_name
                            o_physics.parent = o
                            o_physics.matrix_world = o.matrix_world

                    if cookie:
                        o_cookie_cutter = proxy_cookie_cutter.copy()
                        scene_coll.link(o_cookie_cutter)
                        o_cookie_cutter.nwo.permutation_name = o.nwo.permutation_name
                        o_cookie_cutter.nwo.region_name = o.nwo.region_name
                        o_cookie_cutter.parent = o
                        o_cookie_cutter.matrix_world = o.matrix_world
                        
                        
                    # Correctly setup original coll type for poop if h4
                    if h4:
                        if coll:
                            o.nwo.poop_collision_type = '_connected_geometry_poop_collision_type_none'
                        elif phys:
                            o.nwo.poop_collision_type = '_connected_geometry_poop_collision_type_bullet_collision'

    def apply_face_properties(self, context, export_obs, scene_coll, h4, scenario, prefab):
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

        # Fix meshes with missing UV maps and align UV map names
        for dat in me_ob_dict_full.keys():
            uv_layers = dat.uv_layers
            if uv_layers:
                for idx, uv_map in enumerate(uv_layers):
                    if uv_map.name != 'lighting' and uv_map.name != 'vertex_id':
                        uv_map.name = f"UVMap{idx}"
            else:
                uv_layers.new(name="UVMap0")

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

        process = "--- Creating Meshes From Face Properties"
        len_me_ob_dict = len(me_ob_dict)
        self.any_face_props = False

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

            # Running instance proxy stuff here because it makes the most sense
            me_nwo = me.nwo
            ob_nwo = ob.nwo
            
            if ob_nwo.mesh_type == '_connected_geometry_mesh_type_poop' and not ob_nwo.reach_poop_collision and not me_nwo.render_only_ui:
                self.setup_instance_proxies(scenario, prefab, me, h4, linked_objects, scene_coll, context)

            face_layers = me_nwo.face_props

            if face_layers:
                update_progress(process, idx / len_me_ob_dict)

                self.any_face_props = True
                # must force on auto smooth to avoid Normals transfer errors
                me.use_auto_smooth = True

                bm = bmesh.new()
                bm.from_mesh(me)

                # must ensure all faces are visible
                for face in bm.faces:
                    face.hide_set(False)

                split_objects = self.split_to_layers(
                    ob, ob_nwo, me, face_layers, scene_coll, h4, bm, False
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
                            if linked_ob.data == split_ob.data:
                                new_ob.name = split_ob.name
                                for layer in new_ob.data.nwo.face_props:
                                    self.face_prop_to_mesh_prop(new_ob.nwo, layer, h4, new_ob, scene_coll)
                            else:
                                new_ob = split_ob.copy()
                                scene_coll.link(new_ob)
                                new_ob.matrix_world = linked_ob.matrix_world
                                # linked objects might have different group assignments, ensure their split objects match this
                                new_ob.nwo.region_name = linked_ob.nwo.region_name
                                new_ob.nwo.permutation_name = linked_ob.nwo.permutation_name
                                new_ob.nwo.region_name = linked_ob.nwo.region_name

                            if split_ob.children and not new_ob.children:
                                new_ob.nwo.face_mode = "_connected_geometry_face_mode_render_only"
                                for child in split_ob.children:
                                    if not child.nwo.proxy_parent:
                                        new_child = child.copy()
                                        scene_coll.link(new_child)
                                        new_child.parent = new_ob
                                        new_child.matrix_world = new_ob.matrix_world
                                        new_child.nwo.region_name = new_ob.nwo.region_name
                                        new_child.nwo.permutation_name = new_ob.nwo.permutation_name
                                        new_child.nwo.region_name = new_ob.nwo.region_name

                        if ob.modifiers.get("HaloDataTransfer", 0):
                            mod = linked_ob.modifiers.new(
                                "HaloDataTransfer", "DATA_TRANSFER"
                            )
                            mod.object = ob.modifiers["HaloDataTransfer"].object
                            mod.use_object_transform = False
                            mod.use_loop_data = True
                            mod.data_types_loops = {"CUSTOM_NORMAL"}

        if self.any_face_props:
            update_progress(process, 1)

    def force_fcurves_to_start_at_zero(self, asset_type, export_animations):
        if asset_type in ("MODEL", "FP ANIMATION"):
            if export_animations != "NONE" and bpy.data.actions:
                # Force the keyframes to start at frame 0
                for animation in bpy.data.actions:
                    frames_from_zero = int(animation.frame_start)
                    if frames_from_zero == 0: continue
                    for fcurve in animation.fcurves:
                        for kfp in fcurve.keyframe_points:
                            kfp.co[0] -= frames_from_zero
                            
                    animation.frame_start = 0
                    animation.frame_end -= frames_from_zero

    def set_bone_names(self, bones):
        for b in bones:
            set_bone_prefix(b)
            
    def setup_poop_props(self, nwo, h4, nwo_data):
        nwo.poop_lighting = nwo.poop_lighting_ui
        nwo.poop_pathfinding = nwo.poop_pathfinding_ui
        nwo.poop_imposter_policy = nwo.poop_imposter_policy_ui
        if (
            nwo.poop_imposter_policy
            != "_connected_poop_instance_imposter_policy_never"
        ):
            if not nwo.poop_imposter_transition_distance_auto:
                nwo.poop_imposter_transition_distance = jstr(nwo.poop_imposter_transition_distance_ui)
            if h4:
                nwo.poop_imposter_brightness = jstr(nwo.poop_imposter_brightness_ui)
        if nwo_data.render_only_ui:
            nwo.poop_render_only = "1"
            if h4:
                nwo.poop_collision_type = '_connected_geometry_poop_collision_type_none'
            else:
                nwo.face_mode = '_connected_geometry_face_mode_render_only'
        elif not h4 and nwo_data.sphere_collision_only_ui:
            nwo.face_mode = '_connected_geometry_face_mode_sphere_collision_only'
        elif h4:
            nwo.poop_collision_type = nwo_data.poop_collision_type_ui
        if nwo.poop_chops_portals_ui:
            nwo.poop_chops_portals = "1"
        if nwo.poop_does_not_block_aoe_ui:
            nwo.poop_does_not_block_aoe = "1"
        if nwo.poop_excluded_from_lightprobe_ui:
            nwo.poop_excluded_from_lightprobe = "1"
        if nwo.poop_decal_spacing_ui:
            nwo.poop_decal_spacing = "1"

        if h4:
            nwo.poop_streaming_priority = nwo.poop_streaming_priority_ui
            nwo.poop_cinematic_properties = nwo.poop_cinematic_properties_ui
            if nwo.poop_remove_from_shadow_geometry_ui:
                nwo.poop_remove_from_shadow_geometry = "1"
            if nwo.poop_disallow_lighting_samples_ui:
                nwo.poop_disallow_lighting_samples = "1"
            
    def setup_mesh_properties(self, ob: bpy.types.Object, mesh_type, asset_type, h4, nwo):
        is_map = asset_type in ('SCENARIO', 'PREFAB')
        if is_map:
            # The ol switcheroo
            if mesh_type == '_connected_geometry_mesh_type_default':
                mesh_type = '_connected_geometry_mesh_type_poop'
            elif mesh_type == '_connected_geometry_mesh_type_structure':
                self.bsps_with_structure.add(nwo.region_name)
                mesh_type = '_connected_geometry_mesh_type_default'
                if ob.data.nwo.render_only_ui:
                    nwo.face_mode = '_connected_geometry_face_mode_render_only'
            
        nwo.mesh_type = mesh_type
        nwo_data = ob.data.nwo
        if mesh_type == "_connected_geometry_mesh_type_physics":
            nwo.mesh_primitive_type = nwo.mesh_primitive_type_ui
            if nwo.mesh_primitive_type in ('_connected_geometry_primitive_type_box', '_connected_geometry_primitive_type_pill'):
                set_origin_to_floor(ob)
            elif nwo.mesh_primitive_type == '_connected_geometry_primitive_type_sphere':
                set_origin_to_centre(ob)
                
        elif mesh_type == '_connected_geometry_mesh_type_object_instance':
            nwo.marker_all_regions = bool_str(not nwo.marker_uses_regions)
            if nwo.marker_uses_regions:
                nwo.region_name = true_region(nwo)
                self.validated_regions.add(nwo.region_name)
                for perm in nwo.marker_permutations:
                    self.validated_permutations.add(perm.name)
                
        elif mesh_type == '_connected_geometry_mesh_type_poop':
            self.setup_poop_props(nwo, h4, nwo_data)
                    
        elif mesh_type == "_connected_geometry_mesh_type_seam":
            self.seams.append(ob)
            
        elif mesh_type == "_connected_geometry_mesh_type_portal":
            nwo.portal_type = nwo.portal_type_ui
            if nwo.portal_ai_deafening_ui:
                nwo.portal_ai_deafening = "1"
            if nwo.portal_blocks_sounds_ui:
                nwo.portal_blocks_sounds = "1"
            if nwo.portal_is_door_ui:
                nwo.portal_is_door = "1"
                
        elif mesh_type == "_connected_geometry_mesh_type_water_surface":
            nwo.mesh_tessellation_density = nwo.mesh_tessellation_density_ui
            
        elif mesh_type == "_connected_geometry_mesh_type_planar_fog_volume":
            nwo.fog_appearance_tag = nwo.fog_appearance_tag_ui
            nwo.fog_volume_depth = jstr(nwo.fog_volume_depth_ui)
            
        elif mesh_type == "_connected_geometry_mesh_type_soft_ceiling":
            nwo.mesh_type = "_connected_geometry_mesh_type_boundary_surface"
            nwo.boundary_surface_type = '_connected_geometry_boundary_surface_type_soft_ceiling'
            
        elif mesh_type == "_connected_geometry_mesh_type_soft_kill":
            nwo.mesh_type = "_connected_geometry_mesh_type_boundary_surface"
            nwo.boundary_surface_type = '_connected_geometry_boundary_surface_type_soft_kill'
            
        elif mesh_type == "_connected_geometry_mesh_type_slip_surface":
            nwo.mesh_type = "_connected_geometry_mesh_type_boundary_surface"
            nwo.boundary_surface_type = '_connected_geometry_boundary_surface_type_slip_surface'
            
        elif mesh_type == "_connected_geometry_mesh_type_lightmap_only":
            nwo.mesh_type = "_connected_geometry_mesh_type_poop"
            nwo.face_mode = '_connected_geometry_face_mode_lightmap_only'
            if ob.data.materials != [self.invisible_mat]:
                ob.data.materials.clear()
                ob.data.materials.append(self.invisible_mat)
            
        elif mesh_type == "_connected_geometry_mesh_type_water_physics_volume":
            nwo.water_volume_depth = jstr(nwo.water_volume_depth_ui)
            nwo.water_volume_flow_direction = jstr(degrees(nwo.water_volume_flow_direction_ui))
            nwo.water_volume_flow_velocity = jstr(nwo.water_volume_flow_velocity_ui)
            nwo.water_volume_fog_murkiness = jstr(nwo.water_volume_fog_murkiness_ui)
            if h4:
                nwo.water_volume_fog_color = color_rgba_str(nwo.water_volume_fog_color_ui)
            else:
                nwo.water_volume_fog_color = color_argb_str(nwo.water_volume_fog_color_ui)
                
        elif mesh_type == "_connected_geometry_mesh_type_lightmap_exclude":
            nwo.mesh_type = "_connected_geometry_mesh_type_obb_volume"
            nwo.obb_volume_type = "_connected_geometry_mesh_obb_volume_type_lightmapexclusionvolume"
            
        elif mesh_type == "_connected_geometry_mesh_type_streaming":
            nwo.mesh_type = "_connected_geometry_mesh_type_obb_volume"
            nwo.obb_volume_type = "_connected_geometry_mesh_obb_volume_type_streamingvolume"
            
        elif mesh_type == '_connected_geometry_mesh_type_collision' and asset_type in ('SCENARIO', 'PREFAB'):
            if h4:
                nwo.mesh_type = '_connected_geometry_mesh_type_poop_collision'
                nwo.poop_collision_type = nwo_data.poop_collision_type_ui
            else:
                nwo.mesh_type = '_connected_geometry_mesh_type_poop'
                nwo.poop_lighting = "_connected_geometry_poop_lighting_single_probe"
                nwo.poop_pathfinding = "_connected_poop_instance_pathfinding_policy_cutout"
                nwo.poop_imposter_policy = "_connected_poop_instance_imposter_policy_never"
                nwo.reach_poop_collision = True
                if nwo_data.sphere_collision_only_ui:
                    nwo.face_mode = '_connected_geometry_face_mode_sphere_collision_only'
                else:
                    nwo.face_mode = '_connected_geometry_face_mode_collision_only'
        
        elif asset_type == 'PREFAB':
            nwo.mesh_type = '_connected_geometry_mesh_type_poop'
            self.setup_poop_props(nwo, h4, nwo_data)
            
        elif asset_type == 'DECORATOR SET':
            nwo.mesh_type = '_connected_geometry_mesh_type_decorator'
            nwo.decorator_lod = str(self.decorator_int(ob))
        
        
        # MESH LEVEL PROPERTIES
        if nwo.mesh_type in (
            "_connected_geometry_mesh_type_collision",
            "_connected_geometry_mesh_type_physics",
            "_connected_geometry_mesh_type_default",
            "_connected_geometry_mesh_type_object_instance",
            "_connected_geometry_mesh_type_poop",
            "_connected_geometry_mesh_type_poop_collision",
        ):
            if asset_type in ("SCENARIO", "PREFAB") or nwo.mesh_type in (
                "_connected_geometry_mesh_type_collision",
                "_connected_geometry_mesh_type_physics",
            ) and not (not h4 and nwo.mesh_type in "_connected_geometry_mesh_type_poop"):
                
                nwo.face_global_material = nwo_data.face_global_material_ui
                if nwo.mesh_type != "_connected_geometry_mesh_type_physics" and not h4:
                    if nwo_data.ladder_ui:
                        nwo.ladder = "1"
                    if nwo_data.slip_surface_ui:
                        nwo.slip_surface = "1"
            if nwo.mesh_type != "_connected_geometry_mesh_type_physics":
                # Handle face sides, game wants an enum but Foundry uses flags
                face_sides_value = "_connected_geometry_face_sides_"
                has_transparency = nwo_data.face_transparent_ui and nwo.mesh_type in render_mesh_types
                if nwo_data.face_two_sided_ui:
                    # Only h4+ support properties for the backside face
                    if not h4 or nwo.mesh_type not in render_mesh_types:
                        face_sides_value += "two_sided"
                    else:
                        face_sides_value += nwo_data.face_two_sided_type_ui
                    # Add transparency if set
                    if has_transparency:
                        face_sides_value += "_transparent"
                    nwo.face_sides = face_sides_value
                    
                elif has_transparency:
                    face_sides_value += "one_sided_transparent"
                    nwo.face_sides = face_sides_value

            if nwo.mesh_type in ('_connected_geometry_mesh_type_default', '_connected_geometry_mesh_type_poop'):
                if nwo_data.precise_position_ui and not (asset_type == 'SCENARIO' and nwo.mesh_type == '_connected_geometry_mesh_type_default'):
                    nwo.precise_position = "1"
                # if nwo.face_draw_distance_active:
                #     nwo.face_draw_distance = nwo.face_draw_distance_ui
                # if nwo.texcoord_usage_active:
                #     nwo.texcoord_usage = nwo.texcoord_usage_ui
                if nwo_data.decal_offset_ui:
                    nwo.decal_offset = "1"
                # if asset_type in ('MODEL', 'SKY') and h4 and nwo_data.uvmirror_across_entire_model_ui:
                #     nwo.uvmirror_across_entire_model = "1"
            if asset_type in ("SCENARIO", "PREFAB"):   
                if nwo_data.no_shadow_ui:
                    nwo.no_shadow = "1"
                if h4:
                    if nwo_data.no_lightmap_ui:
                        nwo.no_lightmap = "1"
                    if nwo_data.no_pvs_ui:
                        nwo.no_pvs = "1"
                if nwo_data.lightmap_additive_transparency_active:
                    nwo.lightmap_additive_transparency =  color_4p_str(nwo_data.lightmap_additive_transparency_ui)
                if nwo_data.lightmap_resolution_scale_active:
                    nwo.lightmap_resolution_scale = jstr(
                        nwo_data.lightmap_resolution_scale_ui
                    )
                if nwo_data.lightmap_type_active:
                    nwo.lightmap_type = nwo_data.lightmap_type_ui
                if nwo_data.lightmap_analytical_bounce_modifier_active:
                    nwo.lightmap_analytical_bounce_modifier = jstr(
                        nwo_data.lightmap_analytical_bounce_modifier_ui
                    )
                if nwo_data.lightmap_general_bounce_modifier_active:
                    nwo.lightmap_general_bounce_modifier = jstr(
                        nwo_data.lightmap_general_bounce_modifier_ui
                    )
                if nwo_data.lightmap_translucency_tint_color_active:
                    nwo.lightmap_translucency_tint_color = color_4p_str(
                        nwo_data.lightmap_translucency_tint_color_ui
                    )

                if nwo_data.lightmap_lighting_from_both_sides_active:
                    nwo.lightmap_lighting_from_both_sides = bool_str(
                        nwo_data.lightmap_lighting_from_both_sides_ui
                    )
                if nwo_data.emissive_active:
                    nwo.material_lighting_attenuation_falloff = jstr(
                        nwo_data.material_lighting_attenuation_falloff_ui * 100 * 0.03048 * 0.328084
                    )
                    nwo.material_lighting_attenuation_cutoff = jstr(
                        nwo_data.material_lighting_attenuation_cutoff_ui * 100 * 0.03048 * 0.328084
                    )
                    nwo.material_lighting_emissive_focus = jstr(
                        nwo_data.material_lighting_emissive_focus_ui
                    )
                    nwo.material_lighting_emissive_color = color_4p_str(
                        nwo_data.material_lighting_emissive_color_ui
                    )
                    nwo.material_lighting_emissive_per_unit = bool_str(
                        nwo_data.material_lighting_emissive_per_unit_ui
                    )
                    if h4:
                        nwo.material_lighting_emissive_power = jstr(
                            nwo_data.material_lighting_emissive_power_ui * 0.03048 * 0.328084 / 20
                        )
                    else:
                        nwo.material_lighting_emissive_power = jstr(
                            nwo_data.material_lighting_emissive_power_ui * 0.03048 * 0.328084
                        )
                    nwo.material_lighting_emissive_quality = jstr(
                        nwo_data.material_lighting_emissive_quality_ui
                    )
                    nwo.material_lighting_use_shader_gel = bool_str(
                        nwo_data.material_lighting_use_shader_gel_ui
                    )
                    nwo.material_lighting_bounce_ratio = jstr(
                        nwo_data.material_lighting_bounce_ratio_ui
                    )
                    
        return True

    
    def setup_marker_properties(self, ob, marker_type, asset_type, h4, nwo):
        nwo.marker_type = marker_type
        if asset_type in ('MODEL', 'SKY'):
            nwo.marker_all_regions = bool_str(not nwo.marker_uses_regions)
            if marker_type == "_connected_geometry_marker_type_hint":
                if h4:
                    max_abs_scale = max(abs(ob.scale.x), abs(ob.scale.y), abs(ob.scale.z))
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
                        
            elif marker_type == "_connected_geometry_marker_type_pathfinding_sphere":
                set_marker_sphere_size(ob, nwo)
                nwo.marker_pathfinding_sphere_vehicle = bool_str(nwo.marker_pathfinding_sphere_vehicle_ui)
                nwo.pathfinding_sphere_remains_when_open = bool_str(nwo.pathfinding_sphere_remains_when_open_ui)
                nwo.pathfinding_sphere_with_sectors = bool_str(nwo.pathfinding_sphere_with_sectors_ui)
                
            elif marker_type == "_connected_geometry_marker_type_physics_constraint":
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
                
            elif marker_type == "_connected_geometry_marker_type_target":
                set_marker_sphere_size(ob, nwo)
                
            elif marker_type == "_connected_geometry_marker_type_effects":
                nwo.marker_type = "_connected_geometry_marker_type_model"
                if not ob.name.startswith("fx_"):
                    ob.name = "fx_" + ob.name
                    
            elif marker_type == "_connected_geometry_marker_type_garbage":
                nwo.marker_type = "_connected_geometry_marker_type_model"
                nwo.marker_velocity = vector_str(nwo.marker_velocity_ui)
        
        elif asset_type in ("SCENARIO", "PREFAB"):
            if marker_type == "_connected_geometry_marker_type_game_instance":
                nwo.marker_game_instance_tag_name = (
                    nwo.marker_game_instance_tag_name_ui
                )
                if h4 and nwo.marker_game_instance_tag_name.lower().endswith(
                    ".prefab"
                ):
                    nwo.marker_type = "_connected_geometry_marker_type_prefab"
                elif (
                    h4
                    and nwo.marker_game_instance_tag_name.lower().endswith(
                        ".cheap_light"
                    )
                ):
                    nwo.marker_type = "_connected_geometry_marker_type_cheap_light"
                elif (
                    h4
                    and nwo.marker_game_instance_tag_name.lower().endswith(".light")
                ):
                    nwo.marker_type = "_connected_geometry_marker_type_light"
                elif (
                    h4
                    and nwo.marker_game_instance_tag_name.lower().endswith(".leaf")
                ):
                    nwo.marker_type = "_connected_geometry_marker_type_falling_leaf"
                else:
                    nwo.marker_game_instance_tag_variant_name = (nwo.marker_game_instance_tag_variant_name_ui)
                    if h4:
                        nwo.marker_game_instance_run_scripts = bool_str(nwo.marker_game_instance_run_scripts_ui)
            
            elif marker_type == "_connected_geometry_marker_type_envfx":
                nwo.marker_looping_effect = nwo.marker_looping_effect_ui
                
            elif marker_type == "_connected_geometry_marker_type_lightCone":
                nwo.marker_light_cone_tag = nwo.marker_light_cone_tag_ui
                nwo.marker_light_cone_color = color_3p_str(nwo.marker_light_cone_color_ui)
                nwo.marker_light_cone_alpha = jstr(nwo.marker_light_cone_alpha_ui)
                nwo.marker_light_cone_width = jstr(nwo.marker_light_cone_width_ui)
                nwo.marker_light_cone_length = jstr(nwo.marker_light_cone_length_ui)
                nwo.marker_light_cone_intensity = jstr(nwo.marker_light_cone_intensity_ui )
                nwo.marker_light_cone_curve = nwo.marker_light_cone_curve_ui

    def strip_prefix(self, ob, protected_names):
        name = ob.name.lower()
        keep_stripping = True
        while keep_stripping:
            if name.startswith(("frame ", "frame_")):
                name = name[6:]
            elif name.startswith(("bone ", "bone_")):
                name = name[5:]
            elif name.startswith(("bip ", "bip_")):
                name = name[4:]
            elif name.startswith(("b ", "b_")):
                name = name[2:]
            elif name.startswith(("#", "?", "@", "$", "'")):
                name = name[1:]
            elif name.startswith(("%")):
                name = name[1:]
                if name.startswith(("?", "!", "+", "-", ">", "*")):
                    name = name[1:]
                    if name.startswith(("?", "!", "+", "-", ">", "*")):
                        name = name[1:]
                        if name.startswith(("?", "!", "+", "-", ">", "*")):
                            name = name[1:]

            else:
                keep_stripping = False

        ob.name = name.strip(" _")
        while ob.name in protected_names:
            if not ob.name.rpartition(".")[0]:
                ob.name += "."
            ob.name += "padding"

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
        ):
            for action in bpy.data.actions:
                action.name = dot_partition(action.name).lower().strip(" :_,-")
                nwo = action.nwo
                if not nwo.name_override:
                    nwo.name_override = action.name

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

        scene.frame_current = 0
        scene.frame_start = 0
        scene.frame_end = 0

        return timeline_start, timeline_end

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
        if layer.collection.nwo.type == 'exclude' and layer.is_visible:
            layer.exclude = True
        for child_layer in layer.children:
            self.hide_excluded_recursively(child_layer)

    #####################################################################################
    #####################################################################################
    # ARMATURE FUNCTIONS
    def get_scene_armature(self, export_obs, asset, scene_nwo):
        # arm_name = f"{asset}_world"
        # old_ob = bpy.data.objects.get(arm_name)
        # if old_ob:
        #     old_ob.name += "__OLD__"
        # self.arm_name = arm_name
        # arm = None
        if scene_nwo.main_armature:
            arm = scene_nwo.main_armature
        else:
            for ob in export_obs:
                if ob.type == "ARMATURE":
                    arm = ob
        
        if arm is not None:
            # arm.name = arm_name
            scene_nwo.main_armature = arm
            return arm
    
    def get_bone_names(self, export_obs, scene_nwo):
        for ob in export_obs:
            if ob.type == "ARMATURE":
                for b in ob.data.bones:
                    if not self.aim_pitch and (scene_nwo.node_usage_pose_blend_pitch == b.name or b.name.endswith("aim_pitch")):
                        self.aim_pitch = b.name
                    elif not self.aim_yaw and (scene_nwo.node_usage_pose_blend_yaw == b.name or b.name.endswith("aim_yaw")):
                        self.aim_yaw = b.name
                    elif not self.gun and b.name == ("b_gun"):
                        self.gun = b.name
                    elif not self.pedestal and b.use_deform:
                        self.pedestal = b.name
                return ob.data.bones
            
        return []

    def fix_parenting(self, model_armature, export_obs):
        bones = model_armature.data.bones
        valid_bone_names = [b.name for b in bones if b.use_deform]
        if valid_bone_names:
            root_bone_name = valid_bone_names[0]
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
            marker = nwo.object_type == "_connected_geometry_object_type_marker"
            physics = nwo.mesh_type == "_connected_geometry_mesh_type_physics"
            if ob.parent is None:
                continue
            if ob.parent_type != "BONE":
                if marker or physics:
                    # if not warn:
                    #     self.warning_hit = True
                    #     print("")
                    warn = True
                    ob.parent_type = "BONE"
                    ob.parent_bone = root_bone_name
                    world = ob.matrix_world.copy()
                    if ob.parent_bone in valid_bone_names:
                        ob.matrix_parent_inverse = bones[ob.parent_bone].matrix_local.inverted()
                    else:
                        self.warning_hit = True
                        print_warning(f'{ob.name} is parented to bone {ob.parent_bone} but this bone is either non-deform or does not exist. Parenting object to {root_bone_name}')
                        ob.parent_bone = root_bone_name
                        ob.matrix_parent_inverse = bones[root_bone_name].matrix_local.inverted()
                    ob.matrix_world = world
                    # if marker:
                    #     print_warning(
                    #         f"{ob.name} is a marker but is not parented to a bone. Binding to bone: {root_bone_name}"
                    #     )
                    # else:
                    #     print_warning(
                    #         f"{ob.name} is a physics mesh but is not parented to a bone. Binding to bone: {root_bone_name}"
                    #     )

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
                world = ob.matrix_world.copy()
                if ob.parent_bone in valid_bone_names:
                    ob.matrix_parent_inverse = bones[ob.parent_bone].matrix_local.inverted()
                else:
                    self.warning_hit = True
                    print_warning(f'{ob.name} is parented to bone {ob.parent_bone} but this bone is either non-deform or does not exist. Parenting object to {root_bone_name}')
                    ob.parent_bone = root_bone_name
                    ob.matrix_parent_inverse = bones[root_bone_name].matrix_local.inverted()

                ob.matrix_world = world

            if ob.parent_type == "BONE":
                if ob.modifiers:
                    for mod in ob.modifiers:
                        if mod.type == "ARMATURE":
                            ob.modifiers.remove(mod)

    def get_weights(self, ob, vertex_group, vertices):
        group_index = vertex_group.index
        for i, v in enumerate(vertices):
            for g in v.groups:
                if g.group == group_index:
                    yield (i, g.weight)
                    break

    #####################################################################################
    #####################################################################################
    # BONE FUNCTIONS

    def get_bone_list(self, model_armature, h4, context, asset_type):
        boneslist = {}
        nodes_order = {}
        nodes_order_gun = {}
        nodes_order_fp = {}
        arm = model_armature.name
        boneslist.update({arm: self.get_armature_props(h4)})
        frameIDs = (
            self.openCSV()
        )  # sample function call to get FrameIDs CSV values as dictionary
        f1 = frameIDs.keys()
        f2 = frameIDs.values()
        bone_list = [bone for bone in model_armature.data.bones if bone.use_deform]
        root_bone = rig_root_deform_bone(model_armature)
        if not root_bone:
            raise RuntimeError(f"Armature [{model_armature.name}] does not have a root deform bone. Export will fail")
        elif type(root_bone) == list:
            raise RuntimeError(f"Armature [{model_armature.name}] has multiple root deform bones. Export will fail")
        # sort list
        def sorting_key(value):
            return nodes_order.get(value.name, len(nodes))
        
        scene_nwo = context.scene.nwo
        if scene_nwo.render_model_path:
            node_order_source = scene_nwo.render_model_path
            node_order_source_is_model = True
        else:
            node_order_source = scene_nwo.animation_graph_path
            node_order_source_is_model = False
            
        fp_model = context.scene.nwo.fp_model_path
        gun_model = context.scene.nwo.gun_model_path
        if asset_type == 'MODEL' and node_order_source:
            if os.path.exists(get_tags_path() + node_order_source):
                if node_order_source_is_model:
                    with RenderModelTag(path=node_order_source, hide_prints=True) as render_model:
                        nodes = render_model.get_nodes()
                else:
                    with AnimationTag(path=node_order_source, hide_prints=True) as animation:
                        nodes = animation.get_nodes()
                        
                nodes_order = {v: i for i, v in enumerate(nodes)}
                bone_list = sorted(bone_list, key=sorting_key)
            else:
                if node_order_source_is_model:
                    print_warning("Render Model path supplied but file does not exist")
                else:
                    print_warning("Model Animation Graph path supplied but file does not exist")  
                self.warning_hit = True
        
        elif asset_type == 'FP ANIMATION' and (fp_model or gun_model):
            if gun_model:
                full_gun_model_path = get_tags_path() + gun_model
                if os.path.exists(full_gun_model_path):
                    with RenderModelTag(path=gun_model, hide_prints=True) as render_model:
                        nodes = render_model.get_nodes()
                    # add a 1000 to each index to ensure gun bones sorted last
                    nodes_order_gun = {v: i + 1000 for i, v in enumerate(nodes)}
                else:
                    print_warning("Gun Render Model supplied but tag path does not exist")
                    self.warning_hit = True
            if fp_model:
                full_fp_model_path = get_tags_path() + fp_model
                if os.path.exists(full_fp_model_path):
                    with RenderModelTag(path=fp_model, hide_prints=True) as render_model:
                        nodes = render_model.get_nodes()
                    nodes_order_fp = {v: i for i, v in enumerate(nodes)}
                else:
                    print_warning("FP Render Model supplied but tag path does not exist")
                    self.warning_hit = True
            
            nodes_order.update(nodes_order_fp)
            nodes_order.update(nodes_order_gun)
            bone_list = sorted(bone_list, key=sorting_key)
            
        else:
            # Fine, I'll order it myself
            bones_ordered = []
            bones_ordered.append(root_bone)
            idx = 0
            while idx < len(bone_list):
                for b in bone_list:
                    if idx < len(bones_ordered) and b.parent and b.parent == bones_ordered[idx]:
                        bones_ordered.append(b)
                idx += 1
                
            bone_list = bones_ordered
            
        for idx, b in enumerate(bone_list):
            b_nwo = b.nwo
            FrameID1 = list(f1)[idx]
            FrameID2 = list(f2)[idx]
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

        node_props["bungie_object_type"] = '_connected_geometry_object_type_frame'
        node_props["bungie_frame_ID1"] = FrameID1
        node_props["bungie_frame_ID2"] = FrameID2

        if object_space_node:
            node_props["bungie_is_object_space_offset_node"] = "1"
        if replacement_correction_node:
            node_props["bungie_is_replacement_correction_node"] = "1"
        if fik_anchor_node:
            node_props["bungie_is_fik_anchor_node"] = "1"

        node_props["bungie_object_animates"] = '1'

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
            process = "--- Copying Instanced Geometry Proxy Meshes"
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
        self, context, ob, me, nwo, h4, is_halo_render, does_not_support_sky, scene_coll
    ):
        # fix multi user materials
        slots = ob.material_slots
        materials = me.materials
        scene_mats = bpy.data.materials
        mats = dict.fromkeys(slots)
        if me.nwo.face_global_material_ui and nwo.reach_poop_collision:
            self.set_reach_coll_materials(me, scene_mats, True)
        else:
            self.loop_and_fix_slots(context, slots, is_halo_render, mats, ob, nwo, materials, me, does_not_support_sky, scene_coll, h4)

    def set_reach_coll_materials(self, me, scene_mats, mesh_level=False):
        # handle reach poop collision material assignment
        mesh_global_mat = me.nwo.face_global_material_ui
        if mesh_global_mat:
            me.materials.clear()
            new_mat_name = f"global_material_{mesh_global_mat}"
            if new_mat_name not in scene_mats:
                coll_mat = scene_mats.new(new_mat_name)
            else:
                coll_mat = scene_mats.get(new_mat_name)

            
            tag_path = f"levels\\reference\\sound\\shaders\\bsp_{mesh_global_mat}.shader"
            full_tag_path = get_tags_path() + tag_path
            if os.path.exists(full_tag_path):
                coll_mat.nwo.shader_path = tag_path
            else:
                self.warning_hit = True
                print_warning(f"Couldn't find collision material shader in 'tags\\levels\\reference\\sound\\shaders'. Please ensure a shader tag exists for {mesh_global_mat} prefixed with 'bsp_'")

            me.materials.append(coll_mat)
        if mesh_level or not me.nwo.face_props: return
        # set up the materials by face props
        bm = bmesh.new()
        bm.from_mesh(me)
        layers = me.nwo.face_props
        for l in layers:
            if not l.face_global_material_ui or l.face_global_material_ui == me.nwo.face_global_material_ui:
                continue
            faces = layer_faces(bm, bm.faces.layers.int.get(l.layer_name))
            if not faces:
                continue
            new_mat_face_name = f"global_material_{l.face_global_material_ui}"
            if new_mat_face_name not in scene_mats:
                coll_face_mat = scene_mats.new(new_mat_face_name)
            else:
                coll_face_mat = scene_mats.get(new_mat_face_name)

            tag_path = f"levels\\reference\\sound\\shaders\\bsp_{l.face_global_material_ui}.shader"
            full_tag_path = get_tags_path() + tag_path
            if os.path.exists(full_tag_path):
                coll_face_mat.nwo.shader_path = tag_path
                me.materials.append(coll_face_mat)
                mat_dict = {mat: i for i, mat in enumerate(me.materials)}
                for f in faces:
                    f.material_index = mat_dict[coll_face_mat]

            else:
                self.warning_hit = True
                print_warning(f"Couldn't find collision material shader in 'tags\\levels\\reference\\sound\\shaders'. Please ensure a shader tag exists for {l.face_global_material_ui} prefixed with 'bsp_'")

        bm.to_mesh(me)
        bm.free()

    def loop_and_fix_slots(self, context, slots, is_halo_render, mats, ob, nwo, materials, me, does_not_support_sky, scene_coll, h4):
        slots_to_remove = []
        dupe_slots_dict = {}
        is_true_mesh = ob.type == 'MESH'
        for idx, slot in enumerate(slots):
            if slot.material:
                if slot.material.name in special_material_names:
                    if h4 and slot.material.name not in ('+invisible', '+invalid'):
                        slot.material = self.invisible_mat
                    elif not h4 and slot.material.name.startswith('+sky') and does_not_support_sky:
                        slot.material = self.seamsealer_mat
                elif slot.material.name in convention_material_names:
                    slot.material = self.invisible_mat
                elif is_halo_render:
                    self.used_materials.add(slot.material)
                s_name = slot.material.name
                if s_name not in mats.keys():
                    mats[s_name] = idx
                elif is_true_mesh:
                    slots_to_remove.append(idx)
                    dupe_slots_dict[idx] = mats[s_name]
                    
            else:
                if nwo.mesh_type in render_mesh_types:
                    slot.material = self.invalid_mat
                elif nwo.mesh_type == "_connected_geometry_mesh_type_water_surface":
                    slot.material = self.water_surface_mat
                else:
                    slot.material = self.invisible_mat
                    
        if dupe_slots_dict:
            bm = bmesh.new()
            bm.from_mesh(me)
            bm.faces.ensure_lookup_table()
            for face in bm.faces:
                # face: bmesh.types.BMFace
                if face.material_index in dupe_slots_dict.keys():
                    face.material_index = dupe_slots_dict[face.material_index]
                    
            bm.to_mesh(me)

        while slots_to_remove:
            materials.pop(index=slots_to_remove[0])
            slots_to_remove.pop(0)
            slots_to_remove = [idx - 1 for idx in slots_to_remove]

        if not slots:
            # append the new material to the object
            if nwo.mesh_type in render_mesh_types:
                me.materials.append(self.invalid_mat)
            elif nwo.mesh_type == "_connected_geometry_mesh_type_water_surface":
                me.materials.append(self.water_surface_mat)
            else:
                me.materials.append(self.invisible_mat)
        elif not h4:
            sky_slots = [s for s in ob.material_slots if s.material.name.startswith('+sky')]
            # Loop through slots with sky material, if a permutation is given we need to make a new mesh
            if not sky_slots: return
            # If there's only one sky material can skip face split code below
            if len(sky_slots) == 1 or not is_true_mesh:
                sky_index = get_sky_perm(sky_slots[0].material)
                if sky_index > -1 and sky_index < 32:
                    nwo.sky_permutation_index = str(sky_index)
                sky_slots[0].material = self.sky_mat
                return
                    
            original_bm = bmesh.new()
            original_bm.from_mesh(me)
            for s in sky_slots:
                sky_index = get_sky_perm(s.material)
                if sky_index > -1 and sky_index < 32:
                    original_bm.faces.ensure_lookup_table()
                    mat_faces = [f for f in original_bm.faces if f.material_index == s.slot_index]
                    # Exit early here if all faces are assigned to one sky perm
                    if len(mat_faces) == len(original_bm.faces):
                        nwo.sky_permutation_index = str(sky_index)
                        break
                    
                    face_indexes = [f.index for f in original_bm.faces if f in mat_faces]
                    new_bm = original_bm.copy()
                    bmesh.ops.delete(original_bm, geom=[f for f in original_bm.faces if f.index in face_indexes], context="FACES")
                    bmesh.ops.delete(new_bm, geom=[f for f in new_bm.faces if not f.index in face_indexes], context="FACES")
                    new_sky_me = me.copy()
                    new_bm.to_mesh(new_sky_me)
                    original_bm.to_mesh(me)
                    new_sky_ob = ob.copy()
                    new_sky_ob.name = ob.name + f'(sky_perm_{str(sky_index)})'
                    new_sky_ob.data = new_sky_me
                    scene_coll.link(new_sky_ob)
                    new_sky_ob.nwo.sky_permutation_index = str(sky_index)
                
                s.material = self.sky_mat

                    
    def generate_structure(self, export_obs, scene_coll, h4):
        bsps_in_need = [bsp for bsp in self.structure_bsps if bsp not in self.bsps_with_structure]
        if not bsps_in_need:
            return False
        default_bsp_part = self.default_permutation
        for bsp in bsps_in_need:
            bsp_obs = [ob for ob in export_obs if ob.nwo.region_name == bsp]
            min_x, min_y, min_z, max_x, max_y, max_z = 0, 0, 0, 0, 0, 400
            padding = 0 if h4 else 0.01 # Reach needs a little padding so poop geo isn't overidden by sky
            for ob in bsp_obs:
                if ob.type == 'MESH':
                    bbox = ob.bound_box
                    for co in bbox:
                        bounds = ob.matrix_world @ Vector((co[0], co[1], co[2]))
                        min_x = min(min_x, bounds.x - padding)
                        min_y = min(min_y, bounds.y - padding)
                        min_z = min(min_z, bounds.z - padding)
                        max_x = max(max_x, bounds.x + padding)
                        max_y = max(max_y, bounds.y + padding)
                        max_z = max(max_z, bounds.z + padding)
                else:
                    bounds = ob.location
                    min_x = min(min_x, bounds.x - padding)
                    min_y = min(min_y, bounds.y - padding)
                    min_z = min(min_z, bounds.z - padding)
                    max_x = max(max_x, bounds.x + padding)
                    max_y = max(max_y, bounds.y + padding)
                    max_z = max(max_z, bounds.z + padding)
        
            # Create the box with bmesh
            bm = bmesh.new()
            xyz = bm.verts.new(Vector((min_x, min_y, min_z)))
            xyz = bm.verts.new(Vector((min_x, min_y, min_z)))
            xYz = bm.verts.new(Vector((min_x, max_y, min_z)))
            xYZ = bm.verts.new(Vector((min_x, max_y, max_z)))
            xyZ = bm.verts.new(Vector((min_x, min_y, max_z)))
            
            Xyz = bm.verts.new(Vector((max_x, min_y, min_z)))
            XYz = bm.verts.new(Vector((max_x, max_y, min_z)))
            XYZ = bm.verts.new(Vector((max_x, max_y, max_z)))
            XyZ = bm.verts.new(Vector((max_x, min_y, max_z)))
            
            bm.faces.new([xyz, xYz, xYZ, xyZ]) # Create the minimum x face
            bm.faces.new([Xyz, XYz, XYZ, XyZ]) # Create the maximum x face
            
            bm.faces.new([xyz, Xyz, XyZ, xyZ]) # Create the minimum y face
            bm.faces.new([xYz, xYZ, XYZ, XYz]) # Create the maximum y face
            
            bm.faces.new([xyz, xYz, XYz, Xyz]) # Create the minimum z face
            bm.faces.new([xyZ, xYZ, XYZ, XyZ]) # Create the maximum z face
            
            # Calculate consistent faces
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            # Flip em since bmesh by default calculates outside normals
            bmesh.ops.reverse_faces(bm, faces=bm.faces)
            
            # Create the mesh and object
            structure_mesh = bpy.data.meshes.new('autogenerated_structure')
            bm.to_mesh(structure_mesh)
            structure = bpy.data.objects.new('autogenerated_structure', structure_mesh)
            scene_coll.link(structure)
            nwo = structure.nwo
            nwo.object_type = '_connected_geometry_object_type_mesh'
            nwo.mesh_type = '_connected_geometry_mesh_type_default'
            if h4:
                structure_mesh.materials.append(self.invisible_mat)
            else:
                structure_mesh.materials.append(self.sky_mat)
            nwo.region_name = bsp
            nwo.permutation_name = default_bsp_part
            self.structure.append(structure)

        return True

    def markerify(self, export_obs, scene_coll):
        # get a list of meshes which are nodes
        mesh_markers = [
            ob
            for ob in export_obs
            if ob.nwo.object_type == "_connected_geometry_object_type_marker"
            and ob.type in VALID_MESHES
        ]

        # For each mesh node create an empty with the same Halo props and transforms
        # Mesh objects need their names saved, so we make a dict. Names are stored so that the node can have the exact same name. We add a temp name to each mesh object

        if not mesh_markers:
            return None

        process = "--- Converting Mesh Markers to Empties"
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

            node.matrix_world = ob.matrix_world
            # node.matrix_local = ob.matrix_local
            # node.matrix_parent_inverse = ob.matrix_parent_inverse
            node.scale = ob.scale
            node_nwo = node.nwo

            # copy the node props from the mesh to the empty
            self.set_node_props(ob_nwo, node_nwo)

            self.unlink(ob)
            update_progress(process, idx / len_mesh_markers)

        update_progress(process, 1)

        # delete_object_list(context, mesh_markers)

    def set_node_props(self, ob_halo, node_halo):
        node_halo.region_name = ob_halo.region_name

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
        self.design_bsps = set()
        self.design_perms = set()

        self.structure = []
        self.structure_bsps = set()
        self.structure_perms = set()

    def halo_objects(self, asset_type, export_obs, h4):
        render_asset = asset_type in ("MODEL", "SKY", "DECORATOR SET", "PARTICLE MODEL")

        for ob in export_obs:
            nwo = ob.nwo
            object_type = nwo.object_type
            mesh_type = nwo.mesh_type
            permutation = nwo.permutation_name
            region = nwo.region_name

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
                elif object_type == "_connected_geometry_object_type_marker" or (object_type == '_connected_geometry_object_type_mesh' and mesh_type == "_connected_geometry_mesh_type_object_instance"):
                    self.markers.append(ob)
                else:
                    self.unlink(ob)

            else:
                if design:
                    self.design.append(ob)
                    self.design_bsps.add(region)
                    self.design_perms.add(permutation)
                else:
                    self.structure.append(ob)
                    self.structure_bsps.add(region)
                    self.structure_perms.add(permutation)

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
        if self.model_armature:
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
    
    def counter_matrix(self, mat_old, mat_new, bone, objects):
        old_rot = mat_old.to_quaternion()
        new_rot = mat_new.to_quaternion()
        diff_rot = new_rot.rotation_difference(old_rot)
        diff_rot_mat = diff_rot.to_matrix().to_4x4()
        for ob in objects:
            if ob.parent == self.model_armature and ob.parent_bone == bone:
                ob.matrix_world = diff_rot_mat @ ob.matrix_world

    def remove_relative_parenting(self, context: bpy.types.Context, export_obs):
        context.view_layer.objects.active = self.model_armature
        relative_bones = set()
        for b in self.model_armature.data.bones:
            if b.use_relative_parent:
                relative_bones.add(b.name)

        bpy.ops.object.mode_set(mode="EDIT", toggle=False)
        for ob in export_obs:
            if ob.parent == self.model_armature and ob.parent_bone in relative_bones:
                bone = self.model_armature.data.edit_bones[ob.parent_bone]
                ob.matrix_parent_inverse = (self.model_armature.matrix_world @ Matrix.Translation(bone.tail - bone.head) @ bone.matrix).inverted()

        bpy.ops.object.mode_set(mode="OBJECT", toggle=False)
        for b in self.model_armature.data.bones:
            if b.use_relative_parent:
                b.use_relative_parent = False
        
        context.view_layer.objects.active = None
        
    
    def consolidate_rig(self, context, scene_nwo):
        if scene_nwo.support_armature_a:
            child_bone = rig_root_deform_bone(scene_nwo.support_armature_a, True)
            if child_bone and scene_nwo.support_armature_a_parent_bone:
                self.join_armatures(context, scene_nwo.main_armature, scene_nwo.support_armature_a, scene_nwo.support_armature_a_parent_bone, child_bone)
            else:
                self.unlink(scene_nwo.support_armature_a)
                if not scene_nwo.support_armature_a_parent_bone:
                    self.warning_hit = True
                    print_warning(f"No parent bone specified in Asset Editor panel for {scene_nwo.support_armature_a_parent_bone}. Ignoring support armature")
                    
                if not child_bone:
                    self.warning_hit = True
                    print_warning(f"{scene_nwo.support_armature_a.name} has multiple root bones, could not join to {scene_nwo.main_armature.name}. Ignoring support armature")
                    
        if scene_nwo.support_armature_b:
            child_bone = rig_root_deform_bone(scene_nwo.support_armature_b, True)
            if child_bone and scene_nwo.support_armature_b_parent_bone:
                self.join_armatures(context, scene_nwo.main_armature, scene_nwo.support_armature_b, scene_nwo.support_armature_b_parent_bone, child_bone)
            else:
                self.unlink(scene_nwo.support_armature_b)
                if not scene_nwo.support_armature_b_parent_bone:
                    self.warning_hit = True
                    print_warning(f"No parent bone specified in Asset Editor panel for {scene_nwo.support_armature_b_parent_bone}. Ignoring support armature")
                    
                if not child_bone:
                    self.warning_hit = True
                    print_warning(f"{scene_nwo.support_armature_b.name} has multiple root bones, could not join to {scene_nwo.main_armature.name}. Ignoring support armature")
                    
        if scene_nwo.support_armature_c:
            child_bone = rig_root_deform_bone(scene_nwo.support_armature_c, True)
            if child_bone and scene_nwo.support_armature_c_parent_bone:
                self.join_armatures(context, scene_nwo.main_armature, scene_nwo.support_armature_c, scene_nwo.support_armature_c_parent_bone, child_bone)
            else:
                self.unlink(scene_nwo.support_armature_c)
                if not scene_nwo.support_armature_c_parent_bone:
                    self.warning_hit = True
                    print_warning(f"No parent bone specified in Asset Editor panel for {scene_nwo.support_armature_c_parent_bone}. Ignoring support armature")
                    
                if not child_bone:
                    self.warning_hit = True
                    print_warning(f"{scene_nwo.support_armature_c.name} has multiple root bones, could not join to {scene_nwo.main_armature.name}. Ignoring support armature")
                    
    def join_armatures(self, context: bpy.types.Context, parent, child, parent_bone, child_bone):
        with context.temp_override(selected_editable_objects=[parent, child], active_object=parent):
            bpy.ops.object.join()
        # Couldn't get context override working for accessing edit_bones
        context.view_layer.objects.active = parent
        bpy.ops.object.mode_set(mode="EDIT", toggle=False)
        edit_child = parent.data.edit_bones.get(child_bone, 0)
        edit_parent = parent.data.edit_bones.get(parent_bone, 0)
        if edit_child and edit_parent:
            edit_child.parent = edit_parent
        else:
            self.warning_hit = True
            print_warning(f"Failed to join bones {parent_bone} and {child_bone} for {parent.name}")
            
        bpy.ops.object.mode_set(mode="OBJECT", toggle=False)
        
        context.view_layer.objects.active = None

    def remove_constraints(self, context, arm):
        with context.temp_override(active_object=arm, selected_editable_objects=[arm]):
            # arm_constraints = arm.constraints
            # for c in arm_constraints:
            #     arm_constraints.remove(c)
            bpy.ops.object.posemode_toggle()
            bones = arm.pose.bones
            for b in bones:
                bone_constraints = b.constraints
                for c in bone_constraints:
                    bone_constraints.remove(c)
            bpy.ops.object.posemode_toggle()
        
    def fix_scale(self, context, objects):
        apply_targets = []
        poops = []
        linked_poops_with_nonstandard_scale = False
        for ob in objects:
            abs_scale = Vector((abs(ob.scale.x), abs(ob.scale.y), abs(ob.scale.z)))
            is_poop = ob.nwo.mesh_type == '_connected_geometry_mesh_type_poop'
            is_poop_with_outlandish_scale = is_poop and ((abs_scale > TARGET_SCALE * 10) or (abs_scale < TARGET_SCALE / 10))
            if is_poop:
                if not is_poop_with_outlandish_scale:
                    continue
                poops.append(ob)
            if abs_scale != TARGET_SCALE:
                if ob.type == 'ARMATURE':
                    self.warning_hit = True
                    print_warning(f'Armature [{ob.name}] has bad scale. Animations will not work as expected in game')
                
                elif ob.data and ob.data.users:
                    if ob.data.users > 1 and is_poop:
                        linked_poops_with_nonstandard_scale = True
                        continue
                    elif ob.data.users > 1:
                        # Create new mesh data and apply scale
                        if self.verbose_warnings:
                            print_warning(f'{ob.name} has scale values of: {ob.scale}. New mesh data created')
                        ob.data = ob.data.copy()
                apply_targets.append(ob)
                if self.verbose_warnings:
                    print_warning(f'Applying scale to {ob.name}')
                    
        if apply_targets:
            with context.temp_override(selected_editable_objects=apply_targets, active_object=apply_targets[0]):
                bpy.ops.object.transform_apply(location=False, rotation=False, scale=True, isolate_users=True)
            
        return poops, linked_poops_with_nonstandard_scale
    
    def add_null_render(self, scene_coll):
        verts = [Vector((-32, -32, 0.0)), Vector((32, -32, 0.0)), Vector((-32, 32, 0.0))]
        faces = [[0, 1, 2]]
        me = bpy.data.meshes.new('null')
        me.from_pydata(verts, [], faces)
        me.materials.append(self.invisible_mat)
        ob = bpy.data.objects.new('null', me)
        scene_coll.link(ob)
        if self.model_armature:
            ob.parent = self.model_armature
            ob.parent_type = 'BONE'
            ob.parent_bone = [b.name for b in self.model_armature.data.bones if b.use_deform][0]
        ob.nwo.object_type = '_connected_geometry_object_type_mesh'
        ob.nwo.mesh_type = '_connected_geometry_mesh_type_default'
        ob.nwo.region_name  = self.default_region
        ob.nwo.permutation_name  = self.default_permutation
        return ob

#####################################################################################
#####################################################################################
# VARIOUS FUNCTIONS

def set_marker_sphere_size(ob, nwo):
    max_abs_scale = max(abs(ob.scale.x), abs(ob.scale.y), abs(ob.scale.z))
    if ob.type == "EMPTY":
        nwo.marker_sphere_radius = jstr(ob.empty_display_size * max_abs_scale)
    else:
        nwo.marker_sphere_radius = jstr(max(ob.dimensions * max_abs_scale / 2))

def poop_parent(ob):
    parent = ob.parent
    if parent is None:
        return False
    return parent.nwo.mesh_type == '_connected_geometry_mesh_type_poop'

def set_bone_prefix(bone):
    name = bone.name.lower()
    keep_stripping = True
    while keep_stripping:
        if name.startswith(("frame ", "frame_")):
            name = name[6:]
        elif name.startswith(("bone ", "bone_")):
            name = name[5:]
        elif name.startswith(("bip ", "bip_")):
            name = name[4:]
        elif name.startswith(("b ", "b_")):
            name = name[2:]
        else:
            keep_stripping = False

    bone.name = f"b_{name.strip(' _')}"

def set_bone_prefix_str(string):
    name = string.lower()
    keep_stripping = True
    while keep_stripping:
        if name.startswith(("frame ", "frame_")):
            name = name[6:]
        elif name.startswith(("bone ", "bone_")):
            name = name[5:]
        elif name.startswith(("bip ", "bip_")):
            name = name[4:]
        elif name.startswith(("b ", "b_")):
            name = name[2:]
        else:
            keep_stripping = False

    return f"b_{name.strip(' _')}"

# RESET PROPS

def reset_export_props(nwo):
    """Sets export props to empty strings in case they have leftover data"""
    nwo.object_type = ""
    nwo.mesh_type = ""
    nwo.marker_type = ""
    nwo.permutation_name = ""
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
    nwo.marker_exclude_perms = ""
    nwo.marker_include_perms = ""
    nwo.reach_poop_collision = False


def matrices_equal(mat_1, mat_2):
    for i in range(4):
        for j in range(4):
            if abs(mat_1[i][j] - mat_2[i][j]) > 1e-6:
                return False
    return True

def add_triangle_mod(ob: bpy.types.Object):
    mods = ob.modifiers
    for m in mods:
        if m.type == 'TRIANGULATE': return
        
    tri_mod = mods.new('Triangulate', 'TRIANGULATE')
    tri_mod.quad_method = 'FIXED'
    tri_mod.keep_custom_normals = True