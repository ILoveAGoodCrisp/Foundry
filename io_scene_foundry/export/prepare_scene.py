# ##### BEGIN MIT LICENSE BLOCK #####
#
# MIT License
#
# Copyright (c) 2022 Generalkidd & Crisp
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
from os import path
import csv
from math import radians
from mathutils import Matrix, Vector
from uuid import uuid4

from io_scene_foundry.tools.shader_finder import FindShaders
from ..utils.nwo_utils import(
    deselect_all_objects,
    dot_partition,
    is_mesh,
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
)

#####################################################################################
#####################################################################################
# MAIN FUNCTION
def prepare_scene(context, report, sidecar_type, export_hidden, use_armature_deform_only, game_version, meshes_to_empties, export_animations, **kwargs):
    # Exit local view. Must do this otherwise fbx export will fail.
    ExitLocalView(context)
    # Disable collections with the +exclude prefix. This way they are treated as if they are not part of the asset at all
    HideExcludedCollections(context)
    # Unhide collections. Hidden collections will stop objects in the collection being exported. We only want this functionality if the collection is disabled
    unhide_collections(export_hidden, context)
    # Get the current set of selected objects. We need this so selected perms/bsps only functionality can be used
    objects_selection = GetCurrentActiveObjectSelection(context)
    # unhide objects if the user has export_hidden ticked
    UnhideObjects(export_hidden, context)
    # set the scene to object mode. Object mode is required for export.
    set_object_mode(context)
    # Make all currently unselectable objects selectable again. Exporter needs to loop through and select scene objects so we need this.
    MakeSelectable(context)
    # Apply maya namespaces for H4/H2A exports.
    # apply_maya_namespaces(context)
    # update bsp/perm/region names in case any are null.
    fix_blank_group_names(context)
    # add a uv map to meshes without one. This prevents an export assert
    fixup_missing_uvs(context)
    # run find shaders code if any empty paths
    find_shaders_on_export(bpy.data.materials, context, report)
    # Set up facemap properties
    apply_face_properties(context)
    # Establish a dictionary of scene regions. Used later in export_gr2 and build_sidecar
    regions_dict = get_regions_dict(context.view_layer.objects)
    # Establish a dictionary of scene global materials. Used later in export_gr2 and build_sidecar
    global_materials_dict = get_global_materials_dict(context.view_layer.objects)
    # Convert mesh markers to empty objects. Especially useful with complex marker shapes, such as prefabs
    MeshesToEmpties(context, meshes_to_empties)
    # poop proxy madness
    SetPoopProxies(context.view_layer.objects)
    # get all objects that we plan to export later
    halo_objects = HaloObjects(sidecar_type)
    # Add materials to all objects without one. No materials = unhappy Tool.exe
    FixMissingMaterials(context, sidecar_type)
    # Get and set the model armature, or create one if none exists.
    model_armature, temp_armature, no_parent_objects = GetSceneArmature(context, sidecar_type, game_version)
    # set bone names equal to their name overrides (if not blank)
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
    fix_armature_rotation(model_armature, sidecar_type, context, export_animations, current_action, timeline_start, timeline_end)
    # Set animation name overrides / fix them up for the exporter
    set_animation_overrides(model_armature, current_action)
     # get the max LOD count in the scene if we're exporting a decorator
    lod_count = GetDecoratorLODCount(halo_objects, sidecar_type == 'DECORATOR SET')
    # get selected perms for use later
    selected_perms = GetSelectedPermutations(objects_selection)
    # get selected bsps for use later
    selected_bsps = GetSelectedBSPs(objects_selection)

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
        self.poops = select_halo_objects('poop', asset_type, ('SCENARIO', 'PREFAB'))
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

# FACEMAP SPLIT

def remove_unused_facemaps(ob, context):
    if ob.type == 'MESH':
        ob.select_set(True)
        context.view_layer.objects.active = ob
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        if len(ob.face_maps) > 0:
            faces = ob.data.polygons
            for f in faces:                   
                f.select = False
            index = 0 
            for _ in range(len(ob.face_maps)):
                ob.face_maps.active_index = index
                bpy.ops.object.face_map_select()
                if ob.data.count_selected_items()[2] > 0:
                    bpy.ops.object.face_map_deselect()
                    index +=1
                else:
                    bpy.ops.object.face_map_remove()
                
            bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
            ob.select_set(False)

def split_by_face_map(ob, context):
    # remove unused face maps
    ob.select_set(True)
    set_active_object(ob)
    if ob.type == 'MESH' and len(ob.face_maps) > 0:
        remove_unused_facemaps(ob, context)
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        while len(ob.face_maps) > 0:
            # Deselect all faces except those in the current face map
            bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.object.face_map_select()
                    
            # Split the mesh by the selected faces
            bpy.ops.mesh.separate(type='SELECTED')

            bpy.ops.object.face_map_remove()
            
            # Rename the newly created object to match the face map name
            # new_ob = bpy.context.active_object
            # new_ob.name = 'TEST'
            # new_ob.data.name = 'test'

        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)

        # Remove unused face maps for objects
        new_selection = context.selected_objects
        for ob in new_selection:
            remove_unused_facemaps(ob, context)
            ob.name = f'{dot_partition(ob.name)}({ob.face_maps[0].name})'

        return new_selection

def face_prop_to_mesh_prop(ob):
    # ignore unused face_prop items
    if ob.face_maps:
        for item in ob.nwo_face.face_props:
            if item.name == ob.face_maps[0].name:
                face_props = item
                mesh_props = ob.nwo
                # run through each face prop and apply it to the mesh if override set
                if face_props.face_type_override:
                    mesh_props.Face_Type = face_props.face_type
                    mesh_props.Sky_Permutation_Index = face_props.sky_permutation_index
                if face_props.face_mode_override:
                    mesh_props.Face_Mode = face_props.face_mode
                if face_props.face_sides_override:
                    mesh_props.Face_Sides = face_props.face_sides
                if face_props.face_draw_distance_override:
                    mesh_props.Face_Draw_Distance = face_props.face_draw_distance
                if face_props.texcoord_usage_override:
                    mesh_props.texcoord_usage = face_props.texcoord_usage
                if face_props.region_name_override:
                    mesh_props.Region_Name = face_props.region_name
                if face_props.face_global_material_override:
                    mesh_props.Face_Global_Material = face_props.face_global_material
                if face_props.ladder_override:
                    mesh_props.Ladder = face_props.ladder
                if face_props.slip_surface_override:
                    mesh_props.Slip_Surface = face_props.slip_surface
                if face_props.decal_offset_override:
                    mesh_props.Decal_Offset = face_props.decal_offset
                if face_props.group_transparents_by_plane_override:
                    mesh_props.Group_Transparents_By_Plane = face_props.group_transparents_by_plane
                if face_props.no_shadow_override:
                    mesh_props.No_Shadow = face_props.no_shadow
                if face_props.precise_position_override:
                    mesh_props.Precise_Position = face_props.precise_position
                if face_props.no_lightmap_override:
                    mesh_props.no_lightmap = face_props.no_lightmap
                if face_props.no_pvs_override:
                    mesh_props.no_pvs = face_props.no_pvs

                break


def apply_face_properties(context):
    objects = []
    for ob in context.view_layer.objects:
        objects.append(ob)
    for ob in objects:
        deselect_all_objects()
        ob.select_set(True)
        set_active_object(ob)
        # must make single user for this process
        bpy.ops.object.make_single_user(object=True, obdata=True)
        if ob.face_maps:
            split_objects = split_by_face_map(ob, context)
            for ob in split_objects:
                face_prop_to_mesh_prop(ob)
            # set mode again
            set_object_mode(context)

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

def apply_maya_namespaces(context):
    for ob in context.view_layer.objects:
        apply_prefix_properties(ob)
        apply_namespaces(ob)

def apply_prefix_properties(ob):
    """Applies the properties set by an objects Halo prefix and then removes the prefix"""
    pass

def apply_namespaces(ob, namespace=''):
    """Reads the objects halo properties and then applies the appropriate maya namespace, or optionally a set namespace if a second arg is passed"""
    if namespace != '':
        ob.name = f'{namespace}:{ob.name}'
    else:
        pass

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
        if ob.nwo.bsp_name == '':
            ob.nwo.bsp_name = '000'
        if ob.nwo.Permutation_Name == '':
            ob.nwo.Permutation_Name = 'default'
        if ob.nwo.Region_Name == '':
            ob.nwo.Region_Name = 'default'

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
        name = ob.nwo.Face_Global_Material
        if name not in global_materials.keys() and name != '':
            index +=1
            global_materials.update({name: str(index)})

    return global_materials

def GetSelectedPermutations(selection):
    selected_perms = []
    # cycle through selected objects and get their permutation
    for ob in selection:
        perm = ''
        if ob.nwo.Permutation_Name_Locked != '':
            perm = ob.nwo.Permutation_Name_Locked
        else:
            perm = ob.nwo.Permutation_Name
        if perm not in selected_perms:
            selected_perms.append(perm)
    
    return selected_perms

def GetSelectedBSPs(selection):
    selected_bsps = []
    # cycle through selected objects and get their permutation
    for ob in selection:
        bsp = ''
        if ob.nwo.bsp_name_locked != '':
            bsp = ob.nwo.bsp_name_locked
        else:
            bsp = ob.nwo.bsp_name
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
            ob_lod = ob.nwo.Decorator_LOD
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
        ob.nwo.Poop_Predominant_Shader_Name = GetProminantShaderName(ob)

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
                if ob.data.name not in mesh_data:
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
                        if ob.nwo.Poop_Collision_Type == '_connected_geometry_poop_collision_type_play_collision':
                            mat = 'playCollision'
                        elif ob.nwo.Poop_Collision_Type == '_connected_geometry_poop_collision_type_bullet_collision':
                            mat = 'bulletCollision'
                        elif ob.nwo.Poop_Collision_Type == '_connected_geometry_poop_collision_type_invisible_wall':
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
                elif CheckType.default(ob) and ob.nwo.Face_Type == '_connected_geometry_face_type_sky':
                    mat = 'Sky'
                elif (CheckType.default(ob) or CheckType.poop(ob)) and ob.nwo.Face_Type == '_connected_geometry_face_type_seam_sealer':
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
            node = context.object
            node_name = TempName(ob.name)
            ob.name = str(uuid4())
            node.name = node_name
            if ob.parent is not None:
                node.parent = ob.parent
                # Added 08-12-2022 to fix empty nodes not being bone parented
                node.parent_type = ob.parent_type
                if node.parent_type == 'BONE':
                    node.parent_bone = ob.parent_bone

            node.matrix_local = ob.matrix_local
            if CheckType.pathfinding_sphere(ob): # need to handle path finding spheres differently. Dimensions aren't retained for empties, so instead we can store the radius in the marker sphere radius
                node.nwo.marker_sphere_radius = max(ob.dimensions) / 2
            node.scale = ob.scale
            # copy the node props from the mesh to the empty
            SetNodeProps(node, ob)
            # hide the mesh so it doesn't get included in the export
            ob.hide_set(True)

    # mesh to empties with deletion
    # if meshes_to_empties:
    #     # get a list of meshes which are nodes
    #     mesh_nodes = []
    #     for ob in context.view_layer.objects:
    #         if CheckType.marker(ob) and ob.type == 'MESH':
    #             mesh_nodes.append(ob)

    #     # For each mesh node create an empty with the same Halo props and transforms
    #     # Mesh objects need their names saved, so we make a dict. Names are stored so that the node can have the exact same name. We add a temp name to each mesh object
    #     for ob in mesh_nodes:
    #         deselect_all_objects()
    #         bpy.ops.object.empty_add(type='ARROWS')
    #         node = context.object
    #         if ob.parent is not None:
    #             node.parent = ob.parent
    #             # Added 08-12-2022 to fix empty nodes not being bone parented
    #             node.parent_type = ob.parent_type
    #             if node.parent_type == 'BONE':
    #                 node.parent_bone = ob.parent_bone

    #         node.matrix_local = ob.matrix_local
    #         if CheckType.pathfinding_sphere(ob): # need to handle path finding spheres differently. Dimensions aren't retained for empties, so instead we can store the radius in the marker sphere radius
    #             node.nwo.marker_sphere_radius = max(ob.dimensions) / 2
    #         node.scale = ob.scale
    #         # copy the node props from the mesh to the empty
    #         SetNodeProps(node, ob)
    #         # get the meshes name
    #         mesh_name = str(ob.name)
    #         # cast the mesh into the abyss
    #         deselect_all_objects()
    #         ob.select_set(True)
    #         bpy.ops.object.delete() 
    #         # Apply the saved mesh name to the new node
    #         node.name = mesh_name

def TempName(name):
    return name + ''

def SetNodeProps(node, ob):
    node_halo = node.nwo
    ob_halo = ob.nwo

    if ob.users_collection[0].name != 'Scene Collection':
        try:
            bpy.data.collections[ob.users_collection[0].name].objects.link(node)
        except:
            pass # lazy try except as this can cause an assert.
    
    node_halo.bsp_name = true_bsp(ob_halo)

    node_halo.Permutation_Name = true_permutation(ob_halo)

    node_halo.ObjectMarker_Type_H4 = ob_halo.ObjectMarker_Type_H4
    node_halo.ObjectMarker_Type = ob_halo.ObjectMarker_Type

    node_halo.Marker_Region = ob_halo.Marker_Region
    node_halo.Region_Name = true_region(ob_halo)
    node_halo.Marker_All_Regions = ob_halo.Marker_All_Regions
    node_halo.Marker_Velocity = ob_halo.Marker_Velocity

    node_halo.Marker_Game_Instance_Tag_Name = ob_halo.Marker_Game_Instance_Tag_Name
    node_halo.Marker_Game_Instance_Tag_Variant_Name = ob_halo.Marker_Game_Instance_Tag_Variant_Name
    node_halo.marker_game_instance_run_scripts = ob_halo.marker_game_instance_run_scripts

    node_halo.Marker_Pathfinding_Sphere_Vehicle = ob_halo.Marker_Pathfinding_Sphere_Vehicle
    node_halo.Pathfinding_Sphere_Remains_When_Open = ob_halo.Pathfinding_Sphere_Remains_When_Open
    node_halo.Pathfinding_Sphere_With_Sectors = ob_halo.Pathfinding_Sphere_With_Sectors

    node_halo.Physics_Constraint_Parent = ob_halo.Physics_Constraint_Parent
    node_halo.Physics_Constraint_Child = ob_halo.Physics_Constraint_Child
    node_halo.Physics_Constraint_Type = ob_halo.Physics_Constraint_Type
    node_halo.Physics_Constraint_Uses_Limits = ob_halo.Physics_Constraint_Uses_Limits

    node_halo.marker_hint_length = ob_halo.marker_hint_length

    node_halo.marker_looping_effect = ob_halo.marker_looping_effect

    node_halo.marker_light_cone_tag = ob_halo.marker_light_cone_tag
    node_halo.marker_light_cone_color = ob_halo.marker_light_cone_color
    node_halo.marker_light_cone_alpha = ob_halo.marker_light_cone_alpha
    node_halo.marker_light_cone_intensity = ob_halo.marker_light_cone_intensity
    node_halo.marker_light_cone_width = ob_halo.marker_light_cone_width
    node_halo.marker_light_cone_length = ob_halo.marker_light_cone_length
    node_halo.marker_light_cone_curve = ob_halo.marker_light_cone_curve

    # node_halo.object_id = ob_halo.object_id





