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
from uuid import uuid4

from io_scene_foundry.tools.shader_finder import FindShaders
from ..utils.nwo_utils import(
    bool_str,
    color_3p_str,
    color_4p_str,
    deselect_all_objects,
    dot_partition,
    is_linked,
    is_mesh,
    jstr,
    layer_face_count,
    select_all_objects,
    set_active_object,
    CheckType,
    select_halo_objects,
    is_shader,
    get_tags_path,
    not_bungie_game,
    true_region,
    true_bsp,
    true_permutation,
    valid_animation_types,
    vector_str,
)

#####################################################################################
#####################################################################################
# MAIN FUNCTION
def prepare_scene(context, report, asset, sidecar_type, export_hidden, use_armature_deform_only, game_version, meshes_to_empties, export_animations, export_gr2_files, **kwargs):
    # Exit local view. Must do this otherwise fbx export will fail.
    ExitLocalView(context)
    # Get the current set of selected objects. We need this so selected perms/bsps only functionality can be used
    set_object_mode(context)
    # Make all currently unselectable objects selectable again. Exporter needs to loop through and select scene objects so we need this.
    objects_selection = GetCurrentActiveObjectSelection(context)
    # Disable collections with the +exclude prefix. This way they are treated as if they are not part of the asset at all
    HideExcludedCollections(context)
    # Unhide collections. Hidden collections will stop objects in the collection being exported. We only want this functionality if the collection is disabled
    unhide_collections(export_hidden, context)
    # unhide objects if the user has export_hidden ticked
    UnhideObjects(export_hidden, context)
    # set the scene to object mode. Object mode is required for export.
    MakeSelectable(context)
    selected_perms = []
    selected_bsps = []
    if export_gr2_files:
        # get selected perms for use later
        selected_perms = GetSelectedPermutations(objects_selection)
        # get selected bsps for use later
        selected_bsps = GetSelectedBSPs(objects_selection)
    # current_empties = [e.type == 'EMPTY' for e in context.view_layer.objects]
    # convert linked objects to real
    make_instance_collections_real(context)
    # for ob in context.view_layer.objects:
    #     if ob.type == 'EMPTY':
    #         if ob not in current_empties:
    #             unlink(ob)

    # TODO fix missing master instance
    # remove objects with export_this False from view layer
    ignore_non_export_objects(context)
    # update bsp/perm/region names in case any are null.
    fix_blank_group_names(context)
    # make h4 proxy instances from structure
    if sidecar_type == 'SCENARIO' and not_bungie_game():
        structure_to_poops(context)
    # Apply maya namespaces for H4/H2A exports.
    apply_properties(context, sidecar_type, asset)
    if export_gr2_files:
        # ignore water flow markers, we never export these
        hide_water_flow_markers(context)
        # fixup hint marker names
        apply_hint_marker_name(context)
        # Convert mesh markers to empty objects. Especially useful with complex marker shapes, such as prefabs
        MeshesToEmpties(context, meshes_to_empties)
        # add a uv map to meshes without one. This prevents an export assert
        fixup_missing_uvs(context)
        # run find shaders code if any empty paths
        # print("Finding missing shaders...")
        find_shaders_on_export(bpy.data.materials, context, report)
        # build structure seams
        # auto_seam(context)
        # assume_missing_master_instances(context)
        # Set up facemap properties
        # print("Building face properties...")
        apply_face_properties(context)
        # remove meshes with zero faces
        cull_zero_face_meshes(context)
    # Establish a dictionary of scene regions. Used later in export_gr2 and build_sidecar
    regions_dict = get_regions_dict(context.view_layer.objects)
    # Establish a dictionary of scene global materials. Used later in export_gr2 and build_sidecar
    global_materials_dict = get_global_materials_dict(context.view_layer.objects)
    if export_gr2_files:
        # poop proxy madness
        SetPoopProxies(context.view_layer.objects)
    # get all objects that we plan to export later
    halo_objects = HaloObjects(sidecar_type)
    if export_gr2_files:
        # Add materials to all objects without one. No materials = unhappy Tool.exe
        FixMissingMaterials(context, sidecar_type)
        # Get and set the model armature, or create one if none exists.
    model_armature, temp_armature, no_parent_objects = GetSceneArmature(context, sidecar_type, game_version)
    # set bone names equal to their name overrides (if not blank)
    if export_gr2_files:
        if model_armature is not None:
            set_bone_names(model_armature)
    # Handle spooky scary skeleton bones
    skeleton_bones = {}
    current_action = None
    if model_armature is not None:
        ParentToArmature(model_armature, temp_armature, no_parent_objects, context) # ensure all objects are parented to an armature on export. Render and collision mesh is parented with armature deform, the rest uses bone parenting
        skeleton_bones = GetBoneList(model_armature, use_armature_deform_only)      # return a list of bones attached to the model armature, ignoring control / non-deform bones
        if len(bpy.data.actions) > 0:
            try:
                current_action = get_current_action(context, model_armature)
            except:
                pass
    # Set timeline range for use during animation export
    timeline_start, timeline_end = SetTimelineRange(context)
    # rotate the model armature if needed
    if export_gr2_files:
        fix_armature_rotation(model_armature, sidecar_type, context, export_animations, current_action, timeline_start, timeline_end)
        # Set animation name overrides / fix them up for the exporter
    set_animation_overrides(model_armature, current_action)
     # get the max LOD count in the scene if we're exporting a decorator
    lod_count = GetDecoratorLODCount(halo_objects, sidecar_type == 'DECORATOR SET')
    # raise

    return model_armature, skeleton_bones, halo_objects, timeline_start, timeline_end, lod_count, selected_perms, selected_bsps, regions_dict, global_materials_dict, current_action


#####################################################################################
#####################################################################################
# HALO CLASS

class HaloObjects():
    def __init__(self, asset_type):
        self.frame = select_halo_objects('frame', asset_type, ('MODEL', 'SKY', 'DECORATOR SET', 'PARTICLE MODEL', 'SCENARIO', 'PREFAB'))
        self.default = select_halo_objects('render', asset_type, ('MODEL', 'SKY', 'DECORATOR SET', 'PARTICLE MODEL', 'SCENARIO', 'PREFAB'))
        self.collision = select_halo_objects('collision', asset_type, (('MODEL', 'SKY', 'DECORATOR SET', 'PARTICLE MODEL', 'SCENARIO', 'PREFAB')))
        self.physics = select_halo_objects('physics', asset_type, ('MODEL', 'SKY', 'DECORATOR SET', 'PARTICLE MODEL', 'SCENARIO',))
        self.markers = select_halo_objects('marker', asset_type, ('MODEL', 'SKY', 'DECORATOR SET', 'PARTICLE MODEL', 'SCENARIO', 'PREFAB'))
        self.object_instances = select_halo_objects('object_instance', asset_type, ('MODEL'))

        self.decorators = select_halo_objects('decorator', asset_type, ('DECORATOR SET'))
        
        self.cookie_cutters = select_halo_objects('cookie_cutter', asset_type, ('SCENARIO', 'PREFAB'))
        self.poops = select_halo_objects('poop_all', asset_type, ('SCENARIO', 'PREFAB'))
        self.poop_markers = select_halo_objects('poop_marker', asset_type, ('SCENARIO'))
        self.misc = select_halo_objects('misc', asset_type, ('SCENARIO', 'PREFAB'))
        self.seams = select_halo_objects('seam', asset_type, ('SCENARIO'))
        self.portals = select_halo_objects('portal', asset_type, ('SCENARIO'))
        self.water_surfaces = select_halo_objects('water_surface', asset_type, ('SCENARIO', 'PREFAB'))
        self.lights = select_halo_objects('light', asset_type, ('SCENARIO', 'PREFAB', 'SKY', 'MODEL'))
        
        self.boundary_surfaces = select_halo_objects('boundary_surface', asset_type, ('SCENARIO'))
        self.fog = select_halo_objects('fog', asset_type, ('SCENARIO'))
        self.water_physics = select_halo_objects('water_physics', asset_type, ('SCENARIO'))
        self.poop_rain_blockers = select_halo_objects('poop_rain_blocker', asset_type, ('SCENARIO'))

#####################################################################################
#####################################################################################
# VARIOUS FUNCTIONS

def assume_missing_master_instances(context):
    checked_meshes = []
    for ob in context.view_layer.objects:
        for me in bpy.data.meshes:
            if me not in checked_meshes:
                checked_meshes.append(me)
                users = me.users
                if users > 1:
                    master = me.nwo.master_instance
                    if master is not None:
                        continue
                    else:
                        me.nwo.master_instance = ob
                        print(f'MASTER::::::::::::::::{ob.name}')

def make_instance_collections_real(context):
    select_all_objects()
    bpy.ops.object.duplicates_make_real()
    bpy.ops.object.make_local(type='ALL')
    deselect_all_objects()
    bpy.context.view_layer.update()

def auto_seam(context):
    structure_obs = [ob for ob in context.view_layer.objects if ob.type == 'MESH' and ob.nwo.mesh_type == '_connected_geometry_mesh_type_default']
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
            test_ob_mat =  test_ob.matrix_world
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
                bpy.ops.object.mode_set(mode='EDIT', toggle=False)
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.view3d.snap_cursor_to_selected()
                bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
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
                seam = bpy.data.objects.new(f"seam({facing_bsp}:{backfacing_bsp})", seam_data)
                seam_nwo = seam.nwo
                seam_nwo.bsp_name = facing_bsp
                seam_nwo.permutation_name = facing_perm
                seam_nwo.mesh_type = '_connected_geometry_mesh_type_seam'
                context.scene.collection.objects.link(seam)
                set_active_object(seam)
                seam.select_set(True)
                bpy.ops.object.origin_set(type='ORIGIN_CURSOR', center='MEDIAN')
                bpy.ops.object.mode_set(mode='EDIT', toggle=False)
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.mesh.normals_make_consistent(inside=True)
                bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
                seam.select_set(False)
                # now make the new seam to be flipped
                flipped_seam_data = seam_data.copy()
                flipped_seam = seam.copy()
                flipped_seam.data = flipped_seam_data
                flipped_seam.name = f"seam({backfacing_bsp}:{facing_bsp})"
                flipped_seam_nwo = flipped_seam.nwo
                flipped_seam_nwo.bsp_name = backfacing_bsp
                flipped_seam_nwo.permutation_name = backfacing_perm
                flipped_seam_nwo.mesh_type = '_connected_geometry_mesh_type_seam'
                context.scene.collection.objects.link(flipped_seam)
                # use bmesh to flip normals of backfacing seam
                bm = bmesh.new()
                bm.from_mesh(flipped_seam_data)
                bmesh.ops.reverse_faces(bm, faces=bm.faces)
                bm.to_mesh(flipped_seam_data)
                flipped_seam_data.update()
                bm.free()

def unlink(ob):
    for collection in bpy.data.collections:
        if collection in ob.users_collection:
            collection.objects.unlink(ob)
    scene_coll = bpy.context.scene.collection
    if scene_coll in ob.users_collection:
        scene_coll.objects.unlink(ob)

def ignore_non_export_objects(context):
    for ob in context.view_layer.objects:
        ob_nwo = ob.nwo
        if (not ob_nwo.export_this) or ob.type in ('LATTICE', 'LIGHT_PROBE', 'SPEAKER', 'CAMERA') or (ob.type == 'EMPTY' and ob.empty_display_type == 'IMAGE'): # also remove non valid object types - camera, light probes, speaker, lattice, reference image
            unlink(ob)

    context.view_layer.update()

def apply_hint_marker_name(context):
    for ob in context.view_layer.objects:
        if CheckType.get(ob) == '_connected_geometry_object_type_marker' and ob.nwo.marker_type == '_connected_geometry_marker_type_hint':
            ob.name = 'hint_'
            if ob.nwo.marker_hint_type == 'bunker':
                ob.name += 'bunker'
            elif ob.nwo.marker_hint_type == 'corner':
                ob.name += 'corner_'
                if ob.nwo.marker_hint_side == 'right':
                    ob.name += 'right'
                else:
                    ob.name += 'left'

            else:
                if ob.nwo.marker_hint_type == 'vault':
                    ob.name += 'vault_'
                elif ob.nwo.marker_hint_type == 'mount':
                    ob.name += 'mount_'
                else:
                    ob.name += 'hoist_'

                if ob.nwo.marker_hint_height == 'step':
                    ob.name += 'step'
                elif ob.nwo.marker_hint_height == 'crouch':
                    ob.name += 'crouch'
                else:
                    ob.name += 'stand'
                


def hide_water_flow_markers(context):
    for ob in context.view_layer.objects:
        if CheckType.get(ob) == '_connected_geometry_object_type_marker' and ob.nwo.marker_type == '_connected_geometry_marker_type_water_volume_flow':
            unlink(ob)

def cull_zero_face_meshes(context):
    for ob in context.view_layer.objects:
        if ob.type == 'MESH' and len(ob.data.polygons) < 1:
            unlink(ob)

# FACEMAP SPLIT

def any_face_props(ob):
    for item in ob.data.nwo.face_props:
        if (item.region_name_override or item.face_type_override or item.face_mode_override or item.face_sides_override or item.face_draw_distance_override or item.texcoord_usage_override
                         or item.face_global_material_override or item.ladder_override or item.slip_surface_override or item.decal_offset_override or item.group_transparents_by_plane_override
                           or item.no_shadow_override or item.precise_position_override or item.no_lightmap_override or item.no_pvs_override or item.lightmap_additive_transparency_override
                           or item.lightmap_resolution_scale_override or item.lightmap_type_override or item.lightmap_analytical_bounce_modifier_override or item.lightmap_general_bounce_modifier_override
                             or item.lightmap_translucency_tint_color_override or item.lightmap_lighting_from_both_sides_override or item.material_lighting_attenuation_override
                               or item.material_lighting_emissive_focus_override or item.material_lighting_emissive_color_override or item.material_lighting_emissive_per_unit_override
                                 or item.material_lighting_emissive_power_override or item.material_lighting_emissive_quality_override or item.material_lighting_use_shader_gel_override
                                   or item.material_lighting_bounce_ratio_override or item.seam_override
                        ):
            return True
    else:
        return False
    
def justify_face_split(ob):
    """Checked whether we actually need to split this mesh up"""
    face_layers = ob.data.nwo.face_props
    # check that face layers don't cover the full mesh
    me = ob.data
    polygons = len(me.polygons)
    for layer in face_layers:
        bm = bmesh.new()
        bm.from_mesh(me)
        f_layer = bm.faces.layers.int.get(layer.layer_name)
        bm_face_count = layer_face_count(bm, f_layer)
        if polygons != bm_face_count:
            break
    else:
        return False

    return True


def strip_render_only_faces(ob, context):
    """Removes faces from a mesh that have the render only property"""
    # set the context
    current_context = context
    deselect_all_objects()
    ob.select_set(True)
    set_active_object(ob)
    bpy.ops.object.mode_set(mode='EDIT', toggle=False)
    bpy.ops.mesh.select_all(action='DESELECT')
    # loop through each facemap and select non collision faces
    for index, item in enumerate(ob.data.nwo.face_props):
        ob.face_maps.active_index = index
        if item.face_mode_override and item.face_mode == '_connected_geometry_face_mode_render_only':
            bpy.ops.object.face_map_select()

    # delete these faces
    bpy.ops.mesh.delete(type='FACE')
    
    context = current_context

def recursive_layer_split(ob, context, h4, split_objects=[]):
    face_layers = ob.data.nwo.face_props
    me = ob.data
    polygon_count = len(ob.data.polygons)
    layer_remove_list = []
    for layer in face_layers:
        bm = bmesh.new()
        bm.from_mesh(me)
        # remove layers that have no face count
        f_layer = bm.faces.layers.int.get(layer.layer_name)
        bm_face_count = layer_face_count(bm, f_layer)
        if bm_face_count < 1:
            layer_remove_list.append(layer.layer_name)
        else:
            layer.face_count = bm_face_count
        
        bm.free()

    for name in layer_remove_list:
        for index, layer in enumerate(ob.data.nwo.face_props):
            if layer.layer_name == name:
                ob.data.nwo.face_props.remove(index)
                break

    for layer in ob.data.nwo.face_props:
        if polygon_count != layer.face_count:
            bm = bmesh.new()
            bm.from_mesh(me)
            # select the faces associated with this layer and split them off to a new mesh
            f_layer = bm.faces.layers.int.get(layer.layer_name)
            for face in bm.faces:
                face.select = bool(face[f_layer])

            split_bm = bm.copy()
            # delete faces from new mesh
            faces_unselected = [f for f in split_bm.faces if not f.select] 
            bmesh.ops.delete(split_bm, geom=faces_unselected, context='FACES')
            # delete faces from old mesh
            faces_selected = [f for f in bm.faces if f.select]
            bmesh.ops.delete(bm, geom=faces_selected, context='FACES')
            bm.to_mesh(me)
            bm.free()
            split_ob = ob.copy()
            split_ob.name = f"{ob.name}({layer.name})"
            split_ob.data = me.copy()
            split_bm.to_mesh(split_ob.data)
            split_bm.free()
            context.scene.collection.objects.link(split_ob)
            recursive_layer_split(split_ob, context, h4, split_objects)

        else:
            if ob not in split_objects:
                split_objects.append(ob)
            face_prop_to_mesh_prop(ob, h4, layer)

    return split_objects


def split_to_layers(ob, context, h4):
    if justify_face_split(ob):
        # if instance geometry, we need to fix the collision model (provided the user has not already defined one)
        if CheckType.poop(ob) and not ob.nwo.poop_render_only and not h4: # don't do this for h4 as collision can be open
            # check for custom collision / physics
            if len(ob.children) < 1:
                collision_mesh = ob.copy()
                collision_mesh.data = ob.data.copy()
                context.scene.collection.objects.link(collision_mesh)
                # Remove render only property faces from coll mesh
                strip_render_only_faces(collision_mesh, context)
                collision_mesh.name = ob.name + "(collision)"
                # Need to handle collision assingment differently between reach and h4
                collision_mesh.parent = ob
    
                collision_mesh.matrix_world = ob.matrix_world
                collision_mesh.nwo.mesh_type = '_connected_geometry_mesh_type_poop_collision'
        
        normals_mesh = ob.copy()
        normals_mesh.data = ob.data.copy()
        # context.scene.collection.objects.link(normals_mesh)
        # normals_mesh.hide_set(True)

        selection = recursive_layer_split(ob, context, h4, [ob])

        for obj in selection:
            if len(obj.data.polygons) > 0:
                # TODO only do data transfer for rendered geo
                # set up data transfer modifier to retain normals
                mod = obj.modifiers.new("HaloDataTransfer", "DATA_TRANSFER")
                mod.object = normals_mesh
                mod.use_object_transform = False
                mod.use_loop_data = True
                mod.data_types_loops = {'CUSTOM_NORMAL'}
                # if obj.data.face_props:
                #     obj.name = f'{dot_partition(obj.name)}({obj.face_maps[0].name})'
            # make sure we're not parenting the collision to a zero face mesh
            elif collision_mesh is not None and collision_mesh.parent == ob:
                collision_mesh.parent = None
                # can't have a free floating coll mesh in Reach, so we make it a poop and make it invisible
                collision_mesh.nwo.mesh_type = '_connected_geometry_mesh_type_poop'
                collision_mesh.nwo.face_mode = '_connected_geometry_face_mode_collision_only'
                # collision_mesh.nwo.face_type = '_connected_geometry_face_type_seam_sealer'
                collision_mesh.matrix_world = ob.matrix_world
                
        return selection
    
    else:
        return context.selected_objects
    
def structure_to_poops(context):
    """Duplicates structure geo and set it to poops for H4"""
    for ob in context.view_layer.objects:
        if  ob.nwo.mesh_type_ui == '_connected_geometry_mesh_type_structure' and ob.nwo.proxy_instance:
            poop_ob = ob.copy()
            poop_ob.name = f'{ob.name}(instance)'
            poop_ob.nwo.mesh_type_ui = "_connected_geometry_mesh_type_poop"
            context.scene.collection.objects.link(poop_ob)
    
def create_adjacent_seam(ob, adjacent_bsp):
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
    flipped_seam_name = ob.name.rpartition('(')[0]
    flipped_seam.name = flipped_seam_name + f"({adjacent_bsp}:{facing_bsp})"
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

def face_prop_to_mesh_prop(ob, h4, layer):
    # ignore unused face_prop items
    mesh_props = ob.nwo
    face_props = layer
    # run through each face prop and apply it to the mesh if override set
    # if face_props.seam_override and ob.nwo.mesh_type == '_connected_geometry_mesh_type_default':
    #     mesh_props.mesh_type = '_connected_geometry_mesh_type_seam'
    #     create_adjacent_seam(ob, face_props.seam_adjacent_bsp)
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
    if face_props.face_global_material_override:
        mesh_props.face_global_material = face_props.face_global_material_ui
    if face_props.ladder_override:
        mesh_props.ladder = bool_str(face_props.ladder_ui)
    if face_props.slip_surface_override:
        mesh_props.slip_surface = bool_str(face_props.slip_surface_ui)
    if face_props.decal_offset_override:
        mesh_props.decal_offset = bool_str(face_props.decal_offset_ui)
    if face_props.group_transparents_by_plane_override:
        mesh_props.group_transparents_by_plane = bool_str(face_props.group_transparents_by_plane_ui)
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
        mesh_props.lightmap_additive_transparency = jstr(face_props.lightmap_additive_transparency_ui)
        mesh_props.lightmap_additive_transparency_active = True
    if face_props.lightmap_resolution_scale_override:
        mesh_props.lightmap_resolution_scale = int(face_props.lightmap_resolution_scale_ui)
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
        mesh_props.lightmap_translucency_tint_color = color_3p_str(face_props.lightmap_translucency_tint_color_ui)
        mesh_props.lightmap_translucency_tint_color_active = True
    if face_props.lightmap_lighting_from_both_sides_override:
        mesh_props.lightmap_lighting_from_both_sides = bool_str(face_props.lightmap_lighting_from_both_sides_ui)
        mesh_props.lightmap_lighting_from_both_sides_active = True
    # emissive props
    if face_props.emissive_override:
        mesh_props.material_lighting_attenuation_falloff = jstr(face_props.material_lighting_attenuation_falloff_ui)
        mesh_props.material_lighting_attenuation_cutoff = jstr(face_props.material_lighting_attenuation_cutoff_ui)
        mesh_props.material_lighting_emissive_focus = jstr(face_props.material_lighting_emissive_focus_ui)
        mesh_props.material_lighting_emissive_color = color_4p_str(face_props.material_lighting_emissive_color_ui)
        mesh_props.material_lighting_emissive_per_unit = bool_str(face_props.material_lighting_emissive_per_unit_ui)
        mesh_props.material_lighting_emissive_power = jstr(face_props.material_lighting_emissive_power_ui)
        mesh_props.material_lighting_emissive_quality = jstr(face_props.material_lighting_emissive_quality_ui)
        mesh_props.material_lighting_use_shader_gel = bool_str(face_props.material_lighting_use_shader_gel_ui)
        mesh_props.material_lighting_bounce_ratio = jstr(face_props.material_lighting_bounce_ratio_ui)

    # added two sided property to avoid open edges if collision prop
    if not h4:
        is_poop = CheckType.poop(ob)
        if is_poop and (mesh_props.ladder or mesh_props.slip_surface):
            mesh_props.face_sides = '_connected_geometry_face_sides_two_sided'
        # elif is_poop and ob != main_mesh:
        #     mesh_props.poop_render_only = True

def apply_face_properties(context):
    objects = []
    h4 = not_bungie_game()
    valid_mesh_types = ('_connected_geometry_mesh_type_collision', '_connected_geometry_mesh_type_default', '_connected_geometry_mesh_type_poop')

    for ob in context.view_layer.objects:
        if CheckType.mesh(ob) and ob.nwo.mesh_type in valid_mesh_types:
            objects.append(ob)

    meshes = []
    for ob in objects:
        if ob.data in meshes:
            continue

        meshes.append(ob.data)

        face_layers = ob.data.nwo.face_props
        if len(face_layers):
            # split for all linked objects
            me = ob.data
            # must force on auto smooth to avoid Normals transfer errors
            me.use_auto_smooth = True
            linked_objects = []

            for obj in context.view_layer.objects:
                if obj.data == me and obj != ob:
                    linked_objects.append(obj)

            split_objects = split_to_layers(ob, context, h4)
            
            del split_objects[0]

            if not split_objects:
                continue
            
            # copy all new face split objects to all linked objects
            for obj in linked_objects:
                for s_ob in split_objects:
                    new_ob = s_ob.copy()
                    new_ob.matrix_world = obj.matrix_world
                    context.scene.collection.objects.link(new_ob)

                if ob.modifiers.get("HaloDataTransfer", 0):
                    # otherwise do!
                    mod = obj.modifiers.new("HaloDataTransfer", "DATA_TRANSFER")
                    mod.object = ob.modifiers["HaloDataTransfer"].object
                    mod.use_object_transform = False
                    mod.use_loop_data = True
                    mod.data_types_loops = {'CUSTOM_NORMAL'}

    
                
def z_rotate_and_apply(ob, angle):
    angle = radians(angle)
    axis = (0, 0, 1)
    pivot = ob.location
    M = (
        Matrix.Translation(pivot) @
        Matrix.Rotation(angle, 4, axis) @   
        Matrix.Translation(-pivot)
        )
    
    ob.matrix_world = M @ ob.matrix_world
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)

def bake_animations(armature, export_animations, current_action, timeline_start, timeline_end, context):
    print('Baking animations...')
    timeline = context.scene
    for action in bpy.data.actions:
        if export_animations == 'ALL' or current_action == action:
            armature.animation_data.action = action

            if action.use_frame_range:
                frame_start = int(action.frame_start)
                frame_end = int(action.frame_end)
            else:
                frame_start = timeline_start
                frame_end = timeline_end

            timeline.frame_start = timeline_start
            timeline.frame_end = timeline_end

            bpy.ops.object.mode_set(mode='POSE', toggle=False)
            bpy.ops.nla.bake(frame_start=frame_start, frame_end=frame_end, only_selected=False, visual_keying=True, clear_constraints=True, use_current_action=True, clean_curves=True, bake_types={'POSE'})
            bpy.ops.object.mode_set(mode='OBJECT', toggle=False)

def fix_armature_rotation(armature, sidecar_type, context, export_animations, current_action, timeline_start, timeline_end):
    forward = context.scene.nwo.forward_direction
    if forward != 'x' and sidecar_type in ('MODEL', 'FP ANIMATION'):
        armature.select_set(True)
        # bake animation to avoid issues on armature rotation
        if export_animations != 'NONE' and 1<=len(bpy.data.actions):
            bake_animations(armature, export_animations, current_action, timeline_start, timeline_end, context)
        # apply rotation based on selected forward direction
        if forward == 'y':
            z_rotate_and_apply(armature, -90)
        elif forward == 'y-':
            z_rotate_and_apply(armature, 90)
        elif forward == 'x-':
            z_rotate_and_apply(armature, 180)

        deselect_all_objects()

def set_bone_names(armature):
    for bone in armature.data.bones:
        override = bone.nwo.name_override
        if override != '':
            bone.name = override

def apply_object_mesh_marker_properties(ob, asset_type):
    # Apply final properties so we can rename objects (and also avoid complex checking in later code)
    reach = not not_bungie_game()
    nwo = ob.nwo
    # get mesh type
    if CheckType.get(ob) == '_connected_geometry_object_type_mesh':
        if asset_type == 'MODEL':
            nwo.region_name = true_region(ob.nwo)
            if nwo.mesh_type_ui == '_connected_geometry_mesh_type_collision':
                nwo.mesh_type = '_connected_geometry_mesh_type_collision'
            elif nwo.mesh_type_ui == '_connected_geometry_mesh_type_physics':
                nwo.mesh_type = '_connected_geometry_mesh_type_physics'
                nwo.mesh_primitive_type = nwo.mesh_primitive_type_ui
            elif nwo.mesh_type_ui == '_connected_geometry_mesh_type_object_instance' and not not_bungie_game():
                nwo.mesh_type = '_connected_geometry_mesh_type_object_instance'
            else:
                nwo.mesh_type = '_connected_geometry_mesh_type_default'

        if asset_type == 'SCENARIO':
            if nwo.mesh_type_ui == '_connected_geometry_mesh_type_poop':
                nwo.mesh_type = '_connected_geometry_mesh_type_poop'
                nwo.poop_lighting = nwo.poop_lighting_ui
                nwo.poop_pathfinding = nwo.poop_pathfinding_ui
                nwo.poop_imposter_policy = nwo.poop_imposter_policy_ui
                if nwo.poop_imposter_policy != '_connected_poop_instance_imposter_policy_never':
                    if not nwo.poop_imposter_transition_distance_auto:
                        nwo.poop_imposter_transition_distance = nwo.poop_imposter_transition_distance_ui
                        if not reach:
                            nwo.poop_imposter_brightness = nwo.poop_imposter_brightness_ui

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

            elif nwo.mesh_type_ui == '_connected_geometry_mesh_type_poop_collision':
                nwo.mesh_type = '_connected_geometry_mesh_type_poop_collision'
                nwo.poop_collision_type = nwo.poop_collision_type_ui

            elif nwo.mesh_type_ui == '_connected_geometry_mesh_type_plane':
                if nwo.plane_type_ui == '_connected_geometry_plane_type_portal':
                    nwo.mesh_type = '_connected_geometry_mesh_type_portal'
                    nwo.portal_type = nwo.portal_type_ui
                    if nwo.portal_ai_deafening_ui:
                        nwo.portal_ai_deafening = "1"
                    if nwo.portal_blocks_sounds_ui:
                        nwo.portal_blocks_sounds = "1"
                    if nwo.portal_is_door_ui:
                        nwo.portal_is_door = "1"

                elif nwo.plane_type_ui == '_connected_geometry_plane_type_water_surface':
                    nwo.mesh_type = '_connected_geometry_mesh_type_water_surface'
                    nwo.mesh_tessellation_density = nwo.mesh_tessellation_density_ui

                elif nwo.plane_type_ui == '_connected_geometry_plane_type_planar_fog_volume':
                    nwo.mesh_type = '_connected_geometry_mesh_type_planar_fog_volume'
                    nwo.fog_appearance_tag = nwo.fog_appearance_tag_ui
                    nwo.fog_volume_depth = jstr(nwo.fog_volume_depth_ui)

            elif nwo.mesh_type_ui == '_connected_geometry_mesh_type_volume':
                if nwo.volume_type_ui == '_connected_geometry_volume_type_soft_ceiling':
                    nwo.mesh_type = '_connected_geometry_mesh_type_boundary_surface'
                    nwo.boundary_surface_type = '_connected_geometry_boundary_surface_type_soft_ceiling'
                    
                elif nwo.volume_type_ui == '_connected_geometry_volume_type_soft_kill':
                    nwo.mesh_type = '_connected_geometry_mesh_type_boundary_surface'
                    nwo.boundary_surface_type = '_connected_geometry_boundary_surface_type_soft_kill'

                elif nwo.volume_type_ui == '_connected_geometry_volume_type_slip_surface':
                    nwo.mesh_type = '_connected_geometry_mesh_type_boundary_surface'
                    nwo.boundary_surface_type = '_connected_geometry_boundary_surface_type_slip_surface'

                elif nwo.volume_type_ui == '_connected_geometry_volume_type_water_physics':
                    nwo.mesh_type = '_connected_geometry_mesh_type_water_physics_volume'
                    nwo.water_volume_depth = jstr(nwo.water_volume_depth_ui)
                    nwo.water_volume_flow_direction = jstr(nwo.water_volume_flow_direction_ui)
                    nwo.water_volume_flow_velocity = jstr(nwo.water_volume_flow_velocity_ui)
                    nwo.water_volume_fog_color = color_3p_str(nwo.water_volume_fog_color_ui)
                    nwo.water_volume_fog_murkiness = jstr(nwo.water_volume_fog_murkiness_ui)

                elif nwo.volume_type_ui == '_connected_geometry_volume_type_cookie_cutter':
                    nwo.mesh_type = '_connected_geometry_mesh_type_cookie_cutter'
                    
                elif nwo.volume_type_ui == '_connected_geometry_volume_type_lightmap_exclude' and not reach:
                    nwo.mesh_type = '_connected_geometry_mesh_type_obb_volume'
                    nwo.obb_volume_type = '_connected_geometry_mesh_obb_volume_type_lightmapexclusionvolume'

                elif nwo.volume_type_ui == '_connected_geometry_volume_type_streaming' and not reach:
                    nwo.mesh_type = '_connected_geometry_mesh_type_obb_volume'
                    nwo.obb_volume_type = '_connected_geometry_mesh_obb_volume_type_streamingvolume'

                elif nwo.volume_type_ui == '_connected_geometry_volume_type_lightmap_region' and reach:
                    nwo.mesh_type = '_connected_geometry_mesh_type_lightmap_region'

                elif nwo.volume_type_ui == '_connected_geometry_volume_type_poop_rain_blocker':
                    if reach:
                        nwo.mesh_type = '_connected_geometry_mesh_type_poop_rain_blocker'
                    else:
                        nwo.mesh_type = '_connected_geometry_mesh_type_poop'
                        nwo.poop_rain_occluder = "1"
                else:
                    nwo.mesh_type = '_connected_geometry_mesh_type_default'
            else:
                nwo.mesh_type = '_connected_geometry_mesh_type_default'

        if asset_type == 'SKY':
            nwo.region_name = true_region(ob.nwo)
            nwo.mesh_type = '_connected_geometry_mesh_type_default'

        if asset_type == 'DECORATOR SET':
            nwo.mesh_type = '_connected_geometry_mesh_type_decorator'
            nwo.decorator_lod = str(nwo.decorator_lod_ui)

        if asset_type == 'PARTICLE MODEL':
            nwo.mesh_type = '_connected_geometry_mesh_type_default'

        if asset_type == 'PREFAB':
            if nwo.mesh_type_ui == '_connected_geometry_mesh_type_poop_collision':
                nwo.mesh_type = '_connected_geometry_mesh_type_poop_collision'
            elif nwo.mesh_type_ui == '_connected_geometry_mesh_type_cookie_cutter':
                nwo.mesh_type = '_connected_geometry_mesh_type_cookie_cutter'
            else:
                nwo.mesh_type = '_connected_geometry_mesh_type_poop'

    # get marker type
    elif CheckType.get(ob) == '_connected_geometry_object_type_marker':
        if asset_type == 'MODEL':
            nwo.marker_all_regions = bool_str(nwo.marker_all_regions_ui)
            if nwo.marker_type_ui == '_connected_geometry_marker_type_hint':
                nwo.marker_type = '_connected_geometry_marker_type_hint'
                nwo.marker_hint_length = jstr(nwo.marker_hint_length_ui)
            elif nwo.marker_type_ui == '_connected_geometry_marker_type_pathfinding_sphere':
                nwo.marker_type = '_connected_geometry_marker_type_pathfinding_sphere'
                nwo.marker_sphere_radius = nwo.marker_sphere_radius_ui
                nwo.marker_pathfinding_sphere_vehicle = bool_str(nwo.marker_pathfinding_sphere_vehicle_ui)
                nwo.pathfinding_sphere_remains_when_open = bool_str(nwo.pathfinding_sphere_remains_when_open_ui)
                nwo.pathfinding_sphere_with_sectors = bool_str(nwo.pathfinding_sphere_with_sectors_ui)

            elif nwo.marker_type_ui == '_connected_geometry_marker_type_physics_constraint':
                nwo.marker_type = nwo.physics_constraint_type
                nwo.physics_constraint_parent = str(nwo.physics_constraint_parent_ui)
                nwo.physics_constraint_child = str(nwo.physics_constraint_child_ui)
                nwo.physics_constraint_uses_limits = bool_str(nwo.physics_constraint_uses_limits_ui)
                nwo.hinge_constraint_minimum = jstr(nwo.hinge_constraint_minimum_ui)
                nwo.hinge_constraint_maximum = jstr(nwo.hinge_constraint_maximum_ui)
                nwo.cone_angle = jstr(nwo.cone_angle_ui)
                nwo.plane_constraint_minimum = jstr(nwo.plane_constraint_minimum_ui)
                nwo.plane_constraint_maximum = jstr(nwo.plane_constraint_maximum_ui)
                nwo.twist_constraint_start = jstr(nwo.twist_constraint_start_ui)
                nwo.twist_constraint_end = jstr(nwo.twist_constraint_end_ui)

            elif nwo.marker_type_ui == '_connected_geometry_marker_type_target':
                nwo.marker_type = '_connected_geometry_marker_type_target'
            elif nwo.marker_type_ui == '_connected_geometry_marker_type_effects':
                if not ob.name.startswith('fx_'):
                    ob.name = 'fx_' + ob.name
                    nwo.marker_type = '_connected_geometry_marker_type_model'
            else:
                nwo.marker_type = '_connected_geometry_marker_type_model'
                if nwo.marker_type == '_connected_geometry_marker_type_garbage':
                    nwo.marker_velocity = vector_str(nwo.marker_velocity_ui)


        elif asset_type in ('SCENARIO', 'PREFAB'):
            if nwo.marker_type_ui == '_connected_geometry_marker_type_game_instance':
                nwo.marker_game_instance_tag_name = nwo.marker_game_instance_tag_name_ui
                if not reach and nwo.marker_game_instance_tag_name.lower().endswith('.prefab'):
                    nwo.marker_type = '_connected_geometry_marker_type_prefab'
                elif not reach and nwo.marker_game_instance_tag_name.lower().endswith('.cheap_light'):
                    nwo.marker_type = '_connected_geometry_marker_type_cheap_light'
                elif not reach and nwo.marker_game_instance_tag_name.lower().endswith('.light'):
                    nwo.marker_type = '_connected_geometry_marker_type_light'
                elif not reach and nwo.marker_game_instance_tag_name.lower().endswith('.leaf'):
                    nwo.marker_type = '_connected_geometry_marker_type_falling_leaf'
                else:
                    nwo.marker_type = '_connected_geometry_marker_type_game_instance'
                    nwo.marker_game_instance_tag_variant_name = nwo.marker_game_instance_tag_variant_name_ui
                    if not reach:
                        nwo.marker_game_instance_run_scripts = bool_str(nwo.marker_game_instance_run_scripts_ui)
            elif not reach and nwo.marker_type_ui == '_connected_geometry_marker_type_airprobe':
                nwo.marker_type = '_connected_geometry_marker_type_airprobe'
            elif not reach and nwo.marker_type_ui == '_connected_geometry_marker_type_envfx':
                nwo.marker_type = '_connected_geometry_marker_type_envfx'
                nwo.marker_looping_effect = nwo.marker_looping_effect_ui
            elif not reach and nwo.marker_type_ui == '_connected_geometry_marker_type_lightcone':
                nwo.marker_type = '_connected_geometry_marker_type_lightcone'
                nwo.marker_light_cone_tag = nwo.marker_light_cone_tag_ui
                nwo.marker_light_cone_color = color_3p_str(nwo.marker_light_cone_color_ui)
                nwo.marker_light_cone_alpha = jstr(nwo.marker_light_cone_alpha_ui)
                nwo.marker_light_cone_width = jstr(nwo.marker_light_cone_width_ui)
                nwo.marker_light_cone_length = jstr(nwo.marker_light_cone_length_ui)
                nwo.marker_light_cone_intensity = jstr(nwo.marker_light_cone_intensity_ui)
                nwo.marker_light_cone_curve = nwo.marker_light_cone_curve_ui
            else:
                nwo.marker_type = '_connected_geometry_marker_type_model'

        else:
            nwo.marker_type = '_connected_geometry_marker_type_model'

    #  Handling mesh level properties
    # --------------------------------------
    # NOTE not sure if mesh_compression needs to be exposed. Need to test what it does exactly
    # if nwo.mesh_type in ('_connected_geometry_mesh_type_default', '_connected_geometry_mesh_type_poop', '_connected_geometry_mesh_type_decorator', '_connected_geometry_mesh_type_water_surface'):
    #     nwo.mesh_compression = nwo.mesh_compression_ui
    if nwo.mesh_type in ('_connected_geometry_mesh_type_collision', '_connected_geometry_mesh_type_physics', '_connected_geometry_mesh_type_default', '_connected_geometry_mesh_type_poop'):
        if asset_type in ('SCENARIO', 'PREFAB') or nwo.mesh_type in ('_connected_geometry_mesh_type_collision', '_connected_geometry_mesh_type_physics'):
            nwo.face_global_material = nwo.face_global_material_ui
        if nwo.mesh_type != '_connected_geometry_mesh_type_physics' and nwo.face_two_sided_ui:
            nwo.face_sides = "_connected_geometry_face_sides_two_sided"
        if nwo.mesh_type in ('_connected_geometry_mesh_type_default', '_connected_geometry_mesh_type_poop'):
            if nwo.precise_position_ui:
                nwo.precise_position = bool_str(nwo.precise_position_ui)
            if nwo.face_draw_distance_active:
                nwo.face_draw_distance = nwo.face_draw_distance_ui
            if nwo.texcoord_usage_active:
                nwo.texcoord_usage = nwo.texcoord_usage_ui
        if asset_type in ('SCENARIO', 'PREFAB'):
            h4_structure = (not reach and nwo.mesh_type == '_connected_geometry_mesh_type_default')
            if nwo.face_type_active or h4_structure:
                if h4_structure:
                    nwo.face_type = '_connected_geometry_face_type_sky'
                else:
                    nwo.face_type = nwo.face_type_ui
                if nwo.face_type == '_connected_geometry_face_type_sky':
                    nwo.sky_permutation_index = str(nwo.sky_permutation_index_ui)
            if nwo.face_mode_active:
                nwo.face_mode = nwo.face_mode_ui
            if nwo.ladder_active:
                nwo.ladder = bool_str(nwo.ladder_ui)
            if nwo.slip_surface_active:
                nwo.slip_surface = bool_str(nwo.slip_surface_ui)
            if nwo.decal_offset_active:
                nwo.decal_offset = bool_str(nwo.decal_offset_ui)
            if nwo.group_transparents_by_plane_active:
                nwo.group_transparents_by_plane = bool_str(nwo.group_transparents_by_plane_ui)
            if nwo.no_shadow_active:
                nwo.no_shadow = bool_str(nwo.no_shadow_ui)
            if nwo.no_lightmap_active:
                nwo.no_lightmap = bool_str(nwo.no_lightmap_ui)
            if nwo.no_pvs_active:
                nwo.no_pvs = bool_str(nwo.no_pvs_ui)
            if nwo.uvmirror_across_entire_model_active:
                nwo.uvmirror_across_entire_model = bool_str(nwo.uvmirror_across_entire_model_ui)
            if nwo.lightmap_additive_transparency_active:
                nwo.lightmap_additive_transparency = nwo.lightmap_additive_transparency_ui
            if nwo.lightmap_resolution_scale_active:
                nwo.lightmap_resolution_scale = jstr(nwo.lightmap_resolution_scale_ui)
            if nwo.lightmap_photon_fidelity_active:
                nwo.lightmap_photon_fidelity = nwo.lightmap_photon_fidelity_ui
            if nwo.lightmap_type_active:
                nwo.lightmap_type = nwo.lightmap_type_ui
            if nwo.lightmap_analytical_bounce_modifier_active:
                nwo.lightmap_analytical_bounce_modifier = jstr(nwo.lightmap_analytical_bounce_modifier_ui)
            if nwo.lightmap_general_bounce_modifier_active:
                nwo.lightmap_general_bounce_modifier = jstr(nwo.lightmap_general_bounce_modifier_ui)
            if nwo.lightmap_translucency_tint_color_active:
                nwo.lightmap_translucency_tint_color = color_3p_str(nwo.lightmap_translucency_tint_color_ui)
            if nwo.lightmap_lighting_from_both_sides_active:
                nwo.lightmap_lighting_from_both_sides = bool_str(nwo.lightmap_lighting_from_both_sides_ui)
            if nwo.emissive_active:
                nwo.material_lighting_attenuation_falloff = jstr(nwo.material_lighting_attenuation_falloff_ui)
                nwo.material_lighting_attenuation_cutoff = jstr(nwo.material_lighting_attenuation_cutoff_ui)
                nwo.material_lighting_emissive_focus = jstr(nwo.material_lighting_emissive_focus_ui)
                nwo.material_lighting_emissive_color = color_3p_str(nwo.material_lighting_emissive_color_ui)
                nwo.material_lighting_emissive_per_unit = bool_str(nwo.material_lighting_emissive_per_unit_ui)
                nwo.material_lighting_emissive_power = jstr(nwo.material_lighting_emissive_power_ui)
                nwo.material_lighting_emissive_quality = jstr(nwo.material_lighting_emissive_quality_ui)
                nwo.material_lighting_use_shader_gel = bool_str(nwo.material_lighting_use_shader_gel_ui)
                nwo.material_lighting_bounce_ratio = jstr(nwo.material_lighting_bounce_ratio_ui)
            
def strip_prefix(ob):
    if ob.name.lower().startswith(('+soft_ceiling','+slip_surface')):
        ob.name = ob.name[14:]
    if ob.name.lower().startswith(('+cookie','+portal','+flair','+water')):
        ob.name = ob.name[7:]
    if ob.name.lower().startswith(('frame ','frame_','+flair','+water')):
        ob.name = ob.name[6:]
    if ob.name.lower().startswith(('bone ','bone_','+seam')):
        ob.name = ob.name[5:]
    if ob.name.lower().startswith(('bip ','bip_','+fog')):
        ob.name = ob.name[4:]
    elif ob.name.lower().startswith(('b ','b_')):
        ob.name = ob.name[2:]
    elif ob.name.lower().startswith(('#','?','@','$',"'")):
        ob.name = ob.name[1:]
    elif ob.name.lower().startswith(('%')):
        ob.name = ob.name[1:]
        if ob.name.lower().startswith(('?','!','+','-','>','*')):
            ob.name = ob.name[1:]
            if ob.name.lower().startswith(('?','!','+','-','>','*')):
                ob.name = ob.name[1:]
                if ob.name.lower().startswith(('?','!','+','-','>','*')):
                    ob.name = ob.name[1:]

    ob.name = ob.name.strip(' _')

def set_object_type(ob):
    if ob.type == 'LIGHT':
        ob.nwo.object_type = '_connected_geometry_object_type_light'
    elif ob.type == 'CAMERA':
        # don't export cameras
        unlink(ob)
        # ob.nwo.object_type = '_connected_geometry_object_type_animation_camera'
    elif ob.type == 'ARMATURE':
        ob.nwo.object_type = '_connected_geometry_object_type_frame'
    elif ob.type == 'EMPTY':
        if len(ob.children) > 0 or ob.nwo.object_type_ui != '_connected_geometry_object_type_marker':
            ob.nwo.object_type = '_connected_geometry_object_type_frame'
        else:
            ob.nwo.object_type = '_connected_geometry_object_type_marker'

    elif ob.type in ('MESH', 'EMPTY', 'CURVE', 'META', 'SURFACE', 'FONT'):
        ob.nwo.object_type = ob.nwo.object_type_ui
    else:
        # Mesh invalid, don't export
        print(f'{ob.name} is invalid. Skipping export')
        unlink(ob)



def apply_properties(context, asset_type, asset):
    """Applies properties"""
    for ob in context.view_layer.objects:
        # set active to update properties
        set_active_object(ob)
        set_object_type(ob)
        nwo = ob.nwo
        nwo.permutation_name = true_permutation(ob.nwo)
        if asset_type == 'SCENARIO':
            nwo.bsp_name = true_bsp(ob.nwo)
        if ob.type in ('MESH', 'EMPTY', 'CURVE', 'META', 'SURFACE', 'FONT'):
            apply_object_mesh_marker_properties(ob, asset_type)
            
        # strip_prefix(ob)
        # if not_bungie_game():
        #     apply_namespaces(ob, asset)


def apply_namespaces(ob, asset):
    """Reads the objects halo properties and then applies the appropriate maya namespace, or optionally a set namespace if a second arg is passed"""
    nwo = ob.nwo
    namespace = asset
    if nwo.object_type == '_connected_geometry_object_type_frame':
        namespace = 'frame'
    elif nwo.object_type == '_connected_geometry_object_type_marker':
        namespace = 'marker'
    elif nwo.mesh_type == '_connected_geometry_mesh_type_collision':
        namespace = 'collision'
    elif nwo.mesh_type == '_connected_geometry_mesh_type_physics':
        namespace = 'physics'
    elif nwo.mesh_type == '_connected_geometry_mesh_type_object_instance':
        namespace = 'flair'
    elif nwo.mesh_type == '_connected_geometry_mesh_type_poop':
        namespace = 'instance'
    elif nwo.mesh_type == '_connected_geometry_mesh_type_portal':
        namespace = 'portal'
    elif nwo.mesh_type == '_connected_geometry_mesh_type_seam':
        namespace = 'seam'
    elif nwo.mesh_type == '_connected_geometry_mesh_type_water_surface':
        namespace = 'water_surface'
    elif nwo.mesh_type == '_connected_geometry_mesh_type_planar_fog_volume':
        namespace = 'fog'
    elif nwo.mesh_type == '_connected_geometry_mesh_type_boundary_surface':
        namespace = 'boundary_surface'
    elif nwo.mesh_type == '_connected_geometry_mesh_type_water_physics_volume':
        namespace = 'water_physics'
    elif nwo.mesh_type == '_connected_geometry_mesh_type_poop_collision':
        namespace = 'instance_collision'
    elif nwo.mesh_type == '_connected_geometry_mesh_type_poop_physics':
        namespace = 'instance_physics'
    elif nwo.mesh_type == '_connected_geometry_mesh_type_cookie_cutter':
        namespace = 'cookie_cutter'
    elif nwo.mesh_type == '_connected_geometry_mesh_type_obb_volume':
        namespace = 'obb_volume'
    elif nwo.mesh_type == '_connected_geometry_mesh_type_lightmap_region':
        namespace = 'lightmap_region'

    ob.name = f'{namespace}:{ob.name}'


def set_animation_overrides(model_armature, current_action):
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
                if action.nwo.name_override == '':
                    animation =  action.name
                    if animation.rpartition('.')[2] not in valid_animation_types:
                        animation = f'{animation}.{action.nwo.animation_type}'
                    action.nwo.name_override = animation
            except:
                pass
        
        if current_action is not None:
            model_armature.animation_data.action = current_action
        
        deselect_all_objects()


def find_shaders_on_export(materials, context, report):
    for material in materials:
        if material.nwo.shader_path == '':
            FindShaders(context, '', report, False)
            break

def fix_blank_group_names(context):
    for ob in context.view_layer.objects:
        if ob.nwo.bsp_name_ui == '':
            ob.nwo.bsp_name_ui = 'default'
        if ob.nwo.permutation_name_ui == '':
            ob.nwo.permutation_name_ui = 'default'
        if ob.nwo.region_name_ui == '':
            ob.nwo.region_name_ui = 'default'

def fixup_missing_uvs(context):
    for ob in context.view_layer.objects:
        if ob.type == 'MESH':
            mesh = ob.data
            if mesh.uv_layers.active is None:
                mesh.uv_layers.new(name="UVMap_0")

def set_object_mode(context):
    try: # wrapped this in a try as the user can encounter an assert if no object is selected. No reason for this to crash the export
        if context.view_layer.objects.active == None: 
            context.view_layer.objects.active = context.view_layer.objects[0]

        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
    except:
        print('WARNING: Unable to test mode')


def get_current_action(context, model_armature):
    deselect_all_objects()
    model_armature.select_set(True)
    set_active_object(model_armature)
    current_action = context.active_object.animation_data.action
    deselect_all_objects()
    return current_action


def get_regions_dict(objects):
    regions = {'default': '0'}
    index = 0
    for ob in objects:
        name = true_region(ob.nwo)
        if name not in regions.keys():
            index +=1
            regions.update({name: str(index)})

    return regions

def get_global_materials_dict(objects):
    global_materials = {'default': '0'}
    index = 0
    for ob in objects:
        name = ob.nwo.face_global_material
        if name not in global_materials.keys() and name != '':
            index +=1
            global_materials.update({name: str(index)})

    return global_materials

def GetSelectedPermutations(selection):
    selected_perms = []
    # cycle through selected objects and get their permutation
    for ob in selection:
        perm = ''
        if ob.nwo.permutation_name_locked_ui != '':
            perm = ob.nwo.permutation_name_locked_ui
        else:
            perm = ob.nwo.permutation_name_ui
        if perm not in selected_perms:
            selected_perms.append(perm)
    
    return selected_perms

def GetSelectedBSPs(selection):
    selected_bsps = []
    # cycle through selected objects and get their permutation
    for ob in selection:
        bsp = ''
        if ob.nwo.bsp_name_locked_ui != '':
            bsp = ob.nwo.bsp_name_locked_ui
        else:
            bsp = ob.nwo.bsp_name_ui
        if bsp not in selected_bsps:
            selected_bsps.append(bsp)
    
    return selected_bsps

def ExitLocalView(context):
    for area in context.screen.areas:
        if area.type == 'VIEW_3D':
            space = area.spaces[0]
            if space.local_view:
                for region in area.regions:
                    if region.type == 'WINDOW':
                        override = {'area': area, 'region': region}
                        bpy.ops.view3d.localview(override)

# def ApplyObjectIDs(scene_obs):
#     for ob in scene_obs:
#         ob.nwo.object_id
#         if ob.nwo.object_id == '':
#             ob.nwo.object_id = str(uuid4())

def RotateScene(scene_obs, model_armature):
    deselect_all_objects()
    angle_z = radians(90)
    axis_z = (0, 0, 1)
    pivot = Vector((0.0, 0.0, 0.0))
    for ob in scene_obs:
        if ob != model_armature:
            M = (
                Matrix.Translation(pivot) @
                Matrix.Rotation(angle_z, 4, axis_z) @       
                Matrix.Translation(-pivot)
                )
            ob.matrix_world = M @ ob.matrix_world

def UnhideObjects(export_hidden, context):
    if export_hidden:
        for ob in context.view_layer.objects:
            ob.hide_set(False)

def unhide_collections(export_hidden, context):
    layer_collection = context.view_layer.layer_collection
    recursive_nightmare(layer_collection)

def recursive_nightmare(collections):
    for collection in collections.children:
        if collection.hide_viewport or len(collection.children) > 0:
            if collection.hide_viewport:
                collection.hide_viewport = False
            if len(collection.children) > 0:
                recursive_nightmare(collection)

def SetTimelineRange(context):
    scene = context.scene
    timeline_start = scene.frame_start
    timeline_end = scene.frame_end

    scene.frame_start = 0
    scene.frame_end = 0

    return timeline_start, timeline_end

def GetCurrentActiveObjectSelection(context):
    objects_selection = None
    try:
        objects_selection = context.selected_objects
    except:
        print('ASSERT: Unable to attain selection')

    return objects_selection

def FixLightsRotations(lights_list):
    deselect_all_objects()
    angle_x = radians(90)
    angle_z = radians(-90)
    axis_x = (1, 0, 0)
    axis_z = (0, 0, 1)
    for ob in lights_list:
        pivot = ob.location
        M = (
            Matrix.Translation(pivot) @
            Matrix.Rotation(angle_x, 4, axis_x) @
            Matrix.Rotation(angle_z, 4, axis_z) @       
            Matrix.Translation(-pivot)
            )
        ob.matrix_world = M @ ob.matrix_world


def GetDecoratorLODCount(halo_objects, asset_is_decorator):
    lod_count = 0
    if asset_is_decorator:
        for ob in halo_objects.decorators:
            ob_lod = ob.nwo.decorator_lod_ui
            if ob_lod > lod_count:
                lod_count =  ob_lod
    
    return lod_count

def HideExcludedCollections(context):
    for layer in context.view_layer.layer_collection.children:
        hide_excluded_recursively(layer)

def hide_excluded_recursively(layer):
    if layer.collection.name.startswith('+exclude') and layer.is_visible:
            layer.exclude = True
    for child_layer in layer.children:
        hide_excluded_recursively(child_layer)


#####################################################################################
#####################################################################################
# ARMATURE FUNCTIONS
def GetSceneArmature(context, sidecar_type, game_version):
    model_armature = None
    temp_armature = False
    no_parent_objects = []
    for ob in context.view_layer.objects:
        if ob.type == 'ARMATURE' and not ob.name.startswith('+'): # added a check for a '+' prefix in armature name, to support special animation control armatures in the future
            model_armature = ob
            break
    if model_armature is None and (sidecar_type not in ('SCENARIO', 'PREFAB', 'PARTICLE MODEL', 'DECORATOR SET')):
        model_armature, no_parent_objects = AddTempArmature(context)
        temp_armature = True

    return model_armature, temp_armature, no_parent_objects

def AddTempArmature(context):
    ops = bpy.ops
    ops.object.armature_add(enter_editmode=True, align='WORLD', location=(0, 0, 0), scale=(1, 1, 1))
    model_armature = context.view_layer.objects.active
    model_armature.data.edit_bones[0].name = 'implied_root_node'
    model_armature.data.edit_bones[0].tail[1] = 1
    model_armature.data.edit_bones[0].tail[2] = 0
    bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
    no_parent_objects = []
    for ob in context.view_layer.objects:
        if ob.parent == None:
            ob.select_set(True)
            no_parent_objects.append(ob)

    set_active_object(model_armature)
    ops.object.parent_set(type='OBJECT')

    return model_armature, no_parent_objects

def ParentToArmature(model_armature, temp_armature, no_parent_objects, context):
    if temp_armature:
        for ob in no_parent_objects:
            ob.select_set(True)
        set_active_object(model_armature)
        bpy.ops.object.parent_set(type='BONE', keep_transform=True)
    else:
        for ob in context.view_layer.objects:
            if (ob.parent == model_armature and ob.parent_type == 'OBJECT') and not any(m != ' ARMATURE' for m in ob.modifiers):
                deselect_all_objects()
                ob.select_set(True)
                set_active_object(model_armature)
                if (CheckType.render or CheckType.collision):
                    bpy.ops.object.parent_set(type='ARMATURE', keep_transform=True)
                else:
                    bpy.ops.object.parent_set(type='BONE', keep_transform=True)
                    
#####################################################################################
#####################################################################################
# BONE FUNCTIONS

def GetBoneList(model_armature, deform_only):
    boneslist = {}
    arm = model_armature.name
    boneslist.update({arm: getArmatureProperties()})
    index = 0
    frameIDs = openCSV() #sample function call to get FrameIDs CSV values as dictionary
    f1 = frameIDs.keys()
    f2 = frameIDs.values()
    bone_list = model_armature.data.bones
    #bone_list = 
    #bone_list = SortList(model_armature)
    if deform_only:
        bone_list = GetDeformBonesOnly(bone_list)
    for b in bone_list:
        if b.nwo.frame_id1 == '':
            FrameID1 = list(f1)[index]
        else:
            FrameID1 = b.nwo.frame_id1
        if b.nwo.frame_id2 == '':
            FrameID2 = list(f2)[index]
        else:
            FrameID2 = b.nwo.frame_id2
        index +=1
        boneslist.update({b.name: getBoneProperties(FrameID1, FrameID2, b.nwo.object_space_node, b.nwo.replacement_correction_node, b.nwo.fik_anchor_node)})

    return boneslist

def GetDeformBonesOnly(bone_list):
    deform_list = []
    for b in bone_list:
        if b.use_deform:
            deform_list.append(b)
    
    return deform_list
        

def getArmatureProperties():
    node_props = {}

    node_props.update({"bungie_object_type": "_connected_geometry_object_type_frame"}),
    node_props.update({"bungie_frame_ID1": "8078"}),
    node_props.update({"bungie_frame_ID2": "378163771"}),
    if not_bungie_game():
        node_props.update({"bungie_frame_world": "1"}),

    return node_props

def getBoneProperties(FrameID1, FrameID2, object_space_node, replacement_correction_node, fik_anchor_node):
    node_props = {}

    node_props.update({"bungie_object_type": "_connected_geometry_object_type_frame"}),
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

def openCSV():
    script_folder_path = path.dirname(path.dirname(__file__))
    filepath = path.join(script_folder_path, "export", "frameidlist.csv")

    frameIDList = {}
    with open(filepath) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        for row in csv_reader:
            frameIDList.update({row[0]: row[1]})

    return frameIDList

def ApplyPredominantShaderNames(poops):
    for ob in poops:
        ob.nwo.poop_predominant_shader_name = GetProminantShaderName(ob)

def GetProminantShaderName(ob):
    predominant_shader = ''
    slots = ob.material_slots
    for s in slots:
        material = s.material
        if is_shader(material):
            shader_path = material.nwo.shader_path
            if shader_path.rpartition('.')[0] != '':
                shader_path = shader_path.rpartition('.')[0]
            shader_path.replace(get_tags_path(), '')
            shader_path.replace(get_tags_path().lower(), '')
            shader_type = material.nwo.Shader_Type
            predominant_shader = f'{shader_path}.{shader_type}'
            break

    return predominant_shader

def SetPoopProxies(scene_objects):
    proxies = []
    if not not_bungie_game():
        poops = [ob for ob in scene_objects if CheckType.poop(ob)]
        if len(poops) > 1:
            print('Building instanced geometry proxy meshes')
            mesh_data = []
            proxy_collision = None
            proxy_physics = None
            proxy_cookie_cutter = None
            collision_offset = 0
            physics_offset = 0
            cookie_cutter_offset = 0
            poop_offset = 0
            deselect_all_objects()
            for ob in poops:
                if is_linked(ob) and ob.data.nwo.master_instance != ob:
                    continue
                mesh_data.append(ob.data.name)
                for obj in poops:
                    if obj.data.name == ob.data.name and len(obj.children) > 0 and CheckType.poop(obj):
                        proxy_collision, collision_offset = GetPoopProxyCollision(obj)
                        proxy_physics, physics_offset = GetPoopProxyPhysics(obj)
                        proxy_cookie_cutter, cookie_cutter_offset = GetPoopProxyCookie(obj)
                        obj.select_set(True)
                        break
                else:
                    continue

                for obj in poops:
                    if CheckType.poop(obj) and obj.data.name == ob.data.name and len(obj.children) == 0:
                        deselect_all_objects()
                        obj.select_set(True)
                        poop_offset = obj.matrix_world
                        poop_proxies = AttachPoopProxies(obj, proxy_collision, proxy_physics, proxy_cookie_cutter, collision_offset, physics_offset, cookie_cutter_offset, poop_offset)
                        for p in poop_proxies:
                                proxies.append(p)

    proxies = []


def AttachPoopProxies(obj, proxy_collision, proxy_physics, proxy_cookie_cutter, collision_offset, physics_offset, cookie_cutter_offset, poop_offset):
    ops = bpy.ops
    context = bpy.context
    proxy = []
    deselect_all_objects()
    if proxy_collision is not None:
        proxy_collision.select_set(True)
    if proxy_physics is not None:
        proxy_physics.select_set(True)
    if proxy_cookie_cutter is not None:
        proxy_cookie_cutter.select_set(True)

    ops.object.duplicate(linked=True, mode='TRANSLATION')

    if proxy_collision is not None:
        proxy_collision.select_set(False)
    if proxy_physics is not None:
        proxy_physics.select_set(False)
    if proxy_cookie_cutter is not None:
        proxy_cookie_cutter.select_set(False)

    proxy = [p for p in context.selected_objects]

    context.view_layer.objects.active = obj

    ops.object.parent_set(type='OBJECT', keep_transform=False)

    for ob in proxy:
        if CheckType.poop_collision(ob):
            ob.matrix_local = collision_offset
        elif CheckType.poop_physics(ob):
            ob.matrix_local = physics_offset
        else:
            ob.matrix_local = cookie_cutter_offset
    
    return proxy


def GetPoopProxyCollision(obj):
    collision = None
    collision_offset = 0
    for child in obj.children:
        if CheckType.poop_collision(child):
            collision = child
            collision_offset = collision.matrix_local
            break
    

    return collision, collision_offset

def GetPoopProxyPhysics(obj):
    physics = None
    physics_offset = 0
    for child in obj.children:
        if CheckType.poop_physics(child):
            physics = child
            physics_offset = physics.matrix_local
            break

    return physics, physics_offset

def GetPoopProxyCookie(obj):
    cookie = None
    cookie_offset = 0
    for child in obj.children:
        if CheckType.cookie_cutter(child):
            cookie = child
            cookie_offset = cookie.matrix_local
            break

    return cookie, cookie_offset

def MakeSelectable(context):
    unselectable_objects = []
    for ob in context.view_layer.objects:
        if ob.hide_select:
            unselectable_objects.append(ob)
    
    for ob in unselectable_objects:
        ob.hide_select = False

    return unselectable_objects


def FixMissingMaterials(context, sidecar_type):
    # set some locals
    ops = bpy.ops
    materials_list = bpy.data.materials
    mat = ''
    # loop through each object in the scene
    for ob in context.scene.objects:
        if is_mesh(ob): # check if we're processing a mesh
            # remove empty material slots
            for index, slot in enumerate(ob.material_slots.items()):
                if slot == '':
                    override = context.copy()
                    override["object.active_material_index"] = index
                    with context.temp_override(override):
                        ops.object.material_slot_remove()
                    
            if len(ob.material_slots) <= 0: # if no material slots...
                # determine what kind of mesh this is
                if CheckType.collision(ob):
                    if not_bungie_game():
                        if ob.nwo.poop_collision_type == '_connected_geometry_poop_collision_type_play_collision':
                            mat = 'playCollision'
                        elif ob.nwo.poop_collision_type == '_connected_geometry_poop_collision_type_bullet_collision':
                            mat = 'bulletCollision'
                        elif ob.nwo.poop_collision_type == '_connected_geometry_poop_collision_type_invisible_wall':
                            mat = 'wallCollision'
                        else:
                            mat = 'collisionVolume'
                    
                    else:
                        mat = 'collisionVolume'

                elif CheckType.physics(ob):
                    mat = 'physicsVolume'
                elif CheckType.portal(ob):
                    mat = 'Portal'
                elif CheckType.seam(ob):
                    mat = 'Seam'
                elif CheckType.cookie_cutter(ob):
                    mat = 'cookieCutter'
                elif CheckType.water_physics(ob):
                    mat = 'waterVolume'
                elif CheckType.poop(ob) and ob.nwo.poop_rain_occluder:
                    mat = 'rainBlocker'
                elif CheckType.default(ob) and ob.nwo.face_type == '_connected_geometry_face_type_sky':
                    mat = 'Sky'
                elif (CheckType.default(ob) or CheckType.poop(ob)) and ob.nwo.face_type == '_connected_geometry_face_type_seam_sealer':
                    mat = 'seamSealer'
                elif CheckType.default(ob) and not_bungie_game() and sidecar_type == 'SCENARIO':
                    mat = 'Structure'
                elif CheckType.default(ob) or CheckType.poop(ob) or CheckType.decorator(ob):
                    mat = 'invalid'
                else:
                    mat = 'Override'
                
                # if this special material isn't already in the users scene, add it
                if mat not in materials_list:
                    materials_list.new(mat)

                # convert mat to a material object
                mat = materials_list.get(mat)
                # finally, append the new material to the object
                ob.data.materials.append(mat)

def MeshesToEmpties(context, meshes_to_empties):
    if meshes_to_empties:
        # get a list of meshes which are nodes
        mesh_nodes = []
        for ob in context.view_layer.objects:
            if CheckType.marker(ob) and ob.type == 'MESH':
                mesh_nodes.append(ob)

        # For each mesh node create an empty with the same Halo props and transforms
        # Mesh objects need their names saved, so we make a dict. Names are stored so that the node can have the exact same name. We add a temp name to each mesh object
        for ob in mesh_nodes:
            deselect_all_objects()
            bpy.ops.object.empty_add(type='ARROWS')
            node_name = temp_name(ob.name)
            ob.name = str(uuid4())
            node = bpy.data.objects.new(node_name, None)
            if ob.parent is not None:
                node.parent = ob.parent
                # Added 08-12-2022 to fix empty nodes not being bone parented
                node.parent_type = ob.parent_type
                if node.parent_type == 'BONE':
                    node.parent_bone = ob.parent_bone

            node.matrix_local = ob.matrix_local
            if ob.nwo.marker_type in ('_connected_geometry_marker_type_pathfinding_sphere', '_connected_geometry_marker_type_target'): # need to handle pathfinding spheres / targets differently. Dimensions aren't retained for empties, so instead we can store the radius in the marker sphere radius
                node.nwo.marker_sphere_radius = max(ob.dimensions) / 2
            node.scale = ob.scale
            # copy the node props from the mesh to the empty
            set_node_props(node, ob)
            # hide the mesh so it doesn't get included in the export
            unlink(ob)

def temp_name(name):
    return name + ''

def set_node_props(node, ob):
    node_halo = node.nwo
    ob_halo = ob.nwo

    node_halo.bsp_name = ob_halo.bsp_name

    node_halo.permutation_name = ob_halo.permutation_name

    node_halo.object_type = ob_halo.object_type
    node_halo.marker_type = ob_halo.marker_type

    node_halo.region_name = ob_halo.region_name
    node_halo.marker_all_regions = ob_halo.marker_all_regions
    node_halo.marker_velocity = ob_halo.marker_velocity

    node_halo.marker_game_instance_tag_name = ob_halo.marker_game_instance_tag_name
    node_halo.marker_game_instance_tag_variant_name = ob_halo.marker_game_instance_tag_variant_name
    node_halo.marker_game_instance_run_scripts = ob_halo.marker_game_instance_run_scripts

    node_halo.marker_pathfinding_sphere_vehicle = ob_halo.marker_pathfinding_sphere_vehicle
    node_halo.pathfinding_sphere_remains_when_open = ob_halo.pathfinding_sphere_remains_when_open
    node_halo.pathfinding_sphere_with_sectors = ob_halo.pathfinding_sphere_with_sectors

    node_halo.physics_constraint_parent = ob_halo.physics_constraint_parent
    node_halo.physics_constraint_child = ob_halo.physics_constraint_child
    node_halo.physics_constraint_type = ob_halo.physics_constraint_type
    node_halo.physics_constraint_uses_limits = ob_halo.physics_constraint_uses_limits

    node_halo.marker_hint_length = ob_halo.marker_hint_length

    node_halo.marker_looping_effect = ob_halo.marker_looping_effect

    node_halo.marker_light_cone_tag = ob_halo.marker_light_cone_tag
    node_halo.marker_light_cone_color = ob_halo.marker_light_cone_color
    node_halo.marker_light_cone_alpha = ob_halo.marker_light_cone_alpha
    node_halo.marker_light_cone_intensity = ob_halo.marker_light_cone_intensity
    node_halo.marker_light_cone_width = ob_halo.marker_light_cone_width
    node_halo.marker_light_cone_length = ob_halo.marker_light_cone_length
    node_halo.marker_light_cone_curve = ob_halo.marker_light_cone_curve


