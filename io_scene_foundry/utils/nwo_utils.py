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
import json
from math import radians
import pathlib
import shutil
import subprocess
import sys
import winreg
import zipfile
import bpy
import platform
from mathutils import Euler, Matrix, Vector, Quaternion
import os
from os.path import exists as file_exists
from subprocess import Popen, check_call
import random
import xml.etree.ElementTree as ET
import numpy as np

from io_scene_foundry.utils import nwo_globals
from io_scene_foundry.utils.nwo_constants import COLLISION_MESH_TYPES, PROTECTED_MATERIALS, VALID_MESHES
from io_scene_foundry.utils.nwo_materials import special_materials, convention_materials
from ..icons import get_icon_id
import requests

from io_scene_foundry.utils.nwo_constants import object_asset_validation, object_game_validation

HALO_SCALE_NODE = ['Scale Multiplier', 'Scale X', 'Scale Y']
MATERIAL_RESOURCES = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'resources', 'materials')

special_material_names = [m.name for m in special_materials]
convention_material_names = [m.name for m in convention_materials]

###########
##GLOBALS##
###########

# Enums #
special_mesh_types = (
    "_connected_geometry_mesh_type_boundary_surface",
    "_connected_geometry_mesh_type_collision",
    "_connected_geometry_mesh_type_decorator",
    "_connected_geometry_mesh_type_default",
    "_connected_geometry_mesh_type_planar_fog_volume",
    "_connected_geometry_mesh_type_portal",
    "_connected_geometry_mesh_type_seam",
    "_connected_geometry_mesh_type_water_physics_volume",
    "_connected_geometry_mesh_type_obb_volume",
)
invalid_mesh_types = (
    "_connected_geometry_mesh_type_boundary_surface",
    "_connected_geometry_mesh_type_cookie_cutter",
    "_connected_geometry_mesh_type_poop_marker",
    "_connected_geometry_mesh_type_poop_rain_blocker",
    "_connected_geometry_mesh_type_poop_vertical_rain_sheet",
    "_connected_geometry_mesh_type_lightmap_region",
    "_connected_geometry_mesh_type_planar_fog_volume",
    "_connected_geometry_mesh_type_portal",
    "_connected_geometry_mesh_type_seam",
    "_connected_geometry_mesh_type_water_physics_volume",
    "_connected_geometry_mesh_type_obb_volume",
)

# animation events #
non_sound_frame_types = [
    "primary keyframe",
    "secondary keyframe",
    "tertiary keyframe",
    "allow interruption",
    "blend range marker",
    "stride expansion",
    "stride contraction",
    "ragdoll keyframe",
    "drop weapon keyframe",
    "match a",
    "match b",
    "match c",
    "match d",
    "right foot lock",
    "right foot unlock",
    "left foot lock",
    "left foot unlock",
]
sound_frame_types = [
    "left foot",
    "right foot",
    "both-feet shuffle",
    "body impact",
]
import_event_types = ["Wrapped Left", "Wrapped Right"]
frame_event_types = {
    "Trigger Events": [
        "primary keyframe",
        "secondary keyframe",
        "tertiary keyframe",
    ],
    "Navigation Events": [
        "match a",
        "match b",
        "match c",
        "match d",
        "stride expansion",
        "stride contraction",
        "right foot lock",
        "right foot unlock",
        "left foot lock",
        "left foot unlock",
    ],
    "Sync Action Events": [
        "ragdoll keyframe",
        "drop weapon keyframe",
        "allow interruption",
        "blend range marker",
    ],
    "Sound Events": [
        "left foot",
        "right foot",
        "body impact",
        "both-feet shuffle",
    ],
    "Import Events": ["Wrapped Left", "Wrapped Right"],
}

# shader exts #
shader_exts = (
    ".shader",
    ".shader_cortana",
    ".shader_custom",
    ".shader_decal",
    ".shader_foliage",
    ".shader_fur",
    ".shader_fur_stencil",
    ".shader_glass",
    ".shader_halogram",
    ".shader_mux",
    ".shader_mux_material",
    ".shader_screen",
    ".shader_skin",
    ".shader_terrain",
    ".shader_water",
    ".material",
)

blender_object_types_mesh = (
    "MESH",
    "CURVE",
    "SURFACE",
    "META",
    "FONT",
    "CURVES",
    "POINTCLOUD",
    "VOLUME",
    "GPENCIL",
)

#############
##FUNCTIONS##
#############


def is_linked(ob):
    return ob.data.users > 1

def get_project_path():
    project = project_from_scene_project(bpy.context.scene.nwo.scene_project)
    if project is None:
        return ""
    return project.project_path.lower()


def get_tool_path():
    toolPath = os.path.join(get_project_path(), get_tool_type())

    return toolPath


def get_tags_path():
    tagsPath = os.path.join(get_project_path(), "tags" + os.sep)

    return tagsPath


def get_data_path():
    dataPath = os.path.join(get_project_path(), "data" + os.sep)

    return dataPath


def get_tool_type():
    return bpy.context.preferences.addons["io_scene_foundry"].preferences.tool_type

def get_perm(
    ob,
):  # get the permutation of an object, return default if the perm is empty
    return true_permutation(ob.nwo)


def is_windows():
    return platform.system() == "Windows"

def is_corinth(context=None):
    if context is None:
        context = bpy.context

    project = project_from_scene_project(context.scene.nwo.scene_project)
    if project is None:
        return False
    return project.project_corinth

def project_from_scene_project(scene_project=None):
    if scene_project is None:
        scene_project = bpy.context.scene.nwo.scene_project
    prefs = get_prefs()
    if not prefs.projects:
        return
    if not scene_project:
        print_warning(f"No Scene project active, returning first project: {prefs.projects[0].name}")
    else:
        for p in prefs.projects:
            if p.name == scene_project:
                return p
        else:
            print_warning(f"Scene project active does not match any user projects. Returning {prefs.projects[0].name}")

    return prefs.projects[0]


def deselect_all_objects():
    bpy.ops.object.select_all(action="DESELECT")


def select_all_objects():
    bpy.ops.object.select_all(action="SELECT")


def set_active_object(ob: bpy.types.Object):
    ob.hide_select = False
    ob.hide_set(False)
    bpy.context.view_layer.objects.active = ob


def get_active_object():
    return bpy.context.view_layer.objects.active


def get_asset_info(filepath):
    asset_path = os.path.dirname(filepath).lower()
    asset = os_sep_partition(asset_path, True)

    return asset_path, asset


def get_asset_path():
    """Returns the path to the asset folder."""
    asset_path = os_sep_partition(relative_path(bpy.context.scene.nwo_halo_launcher.sidecar_path))
    return asset_path

def relative_path(path: str):
    """Gets the tag/data relative path of the given filepath"""
    tags_path = get_tags_path()
    data_path = get_data_path()
    if path.lower().startswith(tags_path):
        return path.lower().rpartition(tags_path)[2]
    elif path.lower().startswith(data_path):
        return path.lower().rpartition(data_path)[2]
    
    return path.lower()


def get_asset_path_full(tags=False):
    """Returns the full system path to the asset folder. For tags, add a True arg to the function call"""
    asset_path = bpy.context.scene.nwo_halo_launcher.sidecar_path.rpartition(os.sep)[0].lower()
    if tags:
        return get_tags_path() + asset_path
    else:
        return get_data_path() + asset_path


# -------------------------------------------------------------------------------------------------------------------


def vector_str(velocity):
    x = velocity.x
    y = velocity.y
    z = velocity.z
    return f"{jstr(x)} {jstr(y)} {jstr(z)}"


def color_3p_str(color):
    red = color.r
    green = color.g
    blue = color.b
    return f"{jstr(red)} {jstr(green)} {jstr(blue)}"


def color_4p_str(color):
    red = color.r * 255
    green = color.g * 255
    blue = color.b * 255
    return f"1 {jstr(red)} {jstr(green)} {jstr(blue)}"

def color_rgba_str(color):
    red = color[0]
    green = color[1]
    blue = color[2]
    alpha = color[3]
    return f"{jstr(red)} {jstr(green)} {jstr(blue)} {jstr(alpha)}"

def color_argb_str(color):
    red = color[0]
    green = color[1]
    blue = color[2]
    alpha = color[3]
    return f"{jstr(alpha)} {jstr(red)} {jstr(green)} {jstr(blue)}"


def bool_str(bool_var):
    """Returns a boolean as a string. 1 if true, 0 if false"""
    if bool_var:
        return "1"
    else:
        return "0"


def radius_str(ob, pill=False):
    """Returns the radius of a sphere (or a pill if second arg is True) as a string"""
    if pill:
        diameter = max(ob.dimensions.x, ob.dimensions.y)
    else:
        diameter = max(ob.dimensions)

    radius = diameter / 2.0

    return jstr(radius)


def jstr(number):
    """Takes a number, rounds it to six decimal places and returns it as a string"""
    
    return format(round(number, 6), 'f')

def true_region(halo):
    if halo.region_name_locked_ui:
        return halo.region_name_locked_ui.lower()
    else:
        return halo.region_name_ui.lower()

def true_permutation(halo):
    if halo.permutation_name_locked_ui:
        return halo.permutation_name_locked_ui.lower()
    else:
        return halo.permutation_name_ui.lower()

def clean_tag_path(path, file_ext=None):
    """Cleans a path and attempts to make it appropriate for reading by Tool. Can accept a file extension (without a period) to force the existing one if it exists to be replaced"""
    if path != "":
        path = path.lower()
        # If a file ext is provided, replace the existing one / add it
        if file_ext is not None:
            path = shortest_string(path, path.rpartition(".")[0])
            path = f"{path}.{file_ext}"
        # remove any quotation characters from path
        path = path.replace("\"'", "")
        # strip bad characters from the start and end of the path
        path = path.strip("\\/.")
        # # remove 'tags' if path starts with this
        # if path.startswith('tags'):
        #     path = path.replace('tags', '')
        #     # strip following backslash
        #     path = path.strip('\\')
        # attempt to make path tag relative
        path = relative_path(path)
        # return the new path in lower case
        return path
    else:
        return ""


def is_shared(ob):
    return true_region(ob.nwo) == "shared"


def shortest_string(*strings):
    """Takes strings and returns the shortest non null string"""
    string_list = [*strings]
    temp_string = ""
    while temp_string == "" and len(string_list) > 0:
        temp_string = min(string_list, key=len)
        string_list.remove(temp_string)

    return temp_string


def print_box(text, line_char="-", char_count=100):
    """Prints the specified text surrounded by lines created with the specified character. Optionally define the number of charactrers to repeat per line"""
    side_char_count = (char_count - len(text) - 2) // 2
    side_char_count = max(side_char_count, 0)
    side_fix = 0
    if side_char_count > 1:
        side_fix = (
            1
            if (char_count - len(text) - 2) // 2 != (char_count - len(text) - 2) / 2
            else 0
        )
    print(line_char * char_count)
    print(
        f"{line_char * side_char_count} {text} {line_char * (side_char_count + side_fix)}"
    )
    print(line_char * char_count)

def run_tool(tool_args: list, in_background=False, null_output=False):
    """Runs Tool using the specified function and arguments. Do not include 'tool' in the args passed"""
    os.chdir(get_project_path())
    command = f"""{get_tool_type()} {' '.join(f'"{arg}"' for arg in tool_args)}"""
    # print(command)
    if in_background:
        if null_output:
            return Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            return Popen(command)  # ,stderr=PIPE)
    else:
        try:
            if null_output:
                return check_call(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                return check_call(command)  # ,stderr=PIPE)

        except Exception as e:
            return e


def run_tool_sidecar(tool_args: list, asset_path):
    """Runs Tool using the specified function and arguments. Do not include 'tool' in the args passed"""
    failed = False
    os.chdir(get_project_path())
    command = f"""{get_tool_type()} {' '.join(f'"{arg}"' for arg in tool_args)}"""
    # print(command)
    error = ""
    p = Popen(command, stderr=subprocess.PIPE)
    error_log = os.path.join(asset_path, "error.log")
    with open(error_log, "w") as f:
        # Read and print stderr contents while writing to the file
        for line in p.stderr:
            line = line.decode().rstrip("\n")
            if failed or is_error_line(line, p):
                print_error(line)
                failed = True
            elif "(skipping tangent-space calculations)" in line or "if it is a decorator" in line:
                # this really shouldn't be a warning, so don't print/write it
                continue
            elif "Uncompressed vertices are not supported for meshes with type" in line:
                # This is just incorrect and outputs when a mesh is a valid type for uncompressed
                # Export logic prevents uncompressed from being applied to invalid types
                continue
            else:
                # need to handle animation stuff. Most animation output is written to stderr...
                if line.startswith("animation:import:"):
                    warning_line = line.rpartition("animation:import: ")[2]
                    if warning_line.startswith("Failed to extract"):
                        print_warning(line)
                    elif warning_line.startswith("Failed"):
                        print_error(line)
                    else:
                        print(line)
                else:
                    print_warning(line)
            f.write(line)

    p.wait()

    if failed:
        # check for known errors, and return an explanation
        error = get_export_error_explanation(error_log)
    else:
        # if there's no fatal error, remove the error log
        os.remove(error_log)

    return failed, error


def get_export_error_explanation(error_log):
    with open(error_log, "r") as f:
        lines = f.readlines()
        for text in lines:
            if "point->node_indices[0]==section->node_index" in text:
                return "A collision mesh had vertex weights that were not equal to 1 or 0. Collision objects must use rigid vertex weighting or be bone parented"
            elif "does not have the required 'BungieExportInfo' model" in text:
                return "Tool built a corrupt GR2 during export. Please try exporting again"
            elif "non-world space mesh has no valid bones" in text:
                ob = text.rpartition("mesh=")[2].strip()
                return f'Object "{ob}" is parented to the armature but has no bone weighting. You should either bone parent this object, or ensure each vertex is correctly weighted to a bone and that an armature modifier is active for "{ob}" and linked to the armature. See object modifiers and vertex groups / weight paint mode to debug'

    return ""


def is_error_line(line, process):
    words = line.split()
    if words:
        # Need to abort import if we got a corrupt granny file
        if line.startswith('importing an invalid granny file,'):
            print_error('Corrupt GR2 File encountered. Please re-run export')
            process.kill()
            raise RuntimeError(line)
        first_word = words[0]
        second_word = ""
        if len(words) > 1:
            second_word = words[1]
        return (
            first_word.isupper()
            or first_word == "content:"
            or first_word == "###"
            or (first_word == "non-world" and second_word == "space")
        )

    return False

def set_project_in_registry():
    """Sets the current project in the users registry"""
    key_path = r"SOFTWARE\Halo\Projects"
    name = bpy.context.scene.nwo.scene_project
    if not name:
        return
    # Get project name
    project = project_from_scene_project(name)
    project_name = project.project_name
    try:
        # Open the registry key
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE) as key:
            winreg.SetValueEx(key, "Current", 0, winreg.REG_SZ, project_name)
    except:
        pass

def run_ek_cmd(args: list, in_background=False):
    """Executes a cmd line argument at the root editing kit directory"""
    # Set the current project in the users registry, this avoids the switch project prompt
    set_project_in_registry()
    os.chdir(get_project_path())
    command = f"""{' '.join(f'"{arg}"' for arg in args)}"""
    # print(command)
    if in_background:
        return Popen(command)
    else:
        try:
            return check_call(command)
        except Exception as e:
            return e

def dot_partition(target_string, get_suffix=False):
    """Returns a string after partitioning it using period. If the returned string will be empty, the function will instead return the argument passed"""
    if get_suffix:
        return shortest_string(target_string.rpartition(".")[2], target_string)
    else:
        return shortest_string(target_string.rpartition(".")[0], target_string)
    
def any_partition(target_string, part, get_suffix=False):
    """Returns a string after partitioning it using the given string. If the returned string will be empty, the function will instead return the argument passed"""
    if get_suffix:
        return shortest_string(target_string.rpartition(part)[2], target_string)
    else:
        return shortest_string(target_string.rpartition(part)[0], target_string)
    
def space_partition(target_string, get_suffix=False):
    """Returns a string after partitioning it using space. If the returned string will be empty, the function will instead return the argument passed"""
    if get_suffix:
        return shortest_string(target_string.rpartition(" ")[2], target_string)
    else:
        return shortest_string(target_string.rpartition(" ")[0], target_string)
    
def os_sep_partition(target_string, get_suffix=False):
    """Returns a string after partitioning it using the OS seperator. If the returned string will be empty, the function will instead return the argument passed"""
    if get_suffix:
        return shortest_string(target_string.rpartition(os.sep)[2], target_string)
    else:
        return shortest_string(target_string.rpartition(os.sep)[0], target_string)


def check_path(filePath):
    return filePath.lower().startswith(os.path.join(get_project_path().lower(), "data"))


def valid_nwo_asset(context=None):
    """Returns true if this blender scene is a valid NWO asset i.e. has an existing sidecar file"""
    if not context:
        context = bpy.context
    return context.scene.nwo_halo_launcher.sidecar_path != "" and file_exists(
        os.path.join(get_data_path(), context.scene.nwo_halo_launcher.sidecar_path)
    )


def nwo_asset_type():
    """Returns the NWO asset type"""
    return bpy.context.scene.nwo.asset_type


######################################
# MANAGER STUFF
######################################


def get_collection_parents(current_coll, all_collections):
    coll_list = [current_coll]
    keep_looping = True

    while keep_looping:
        for coll in all_collections:
            keep_looping = True
            if current_coll in tuple(coll.children):
                coll_list.append(coll)
                current_coll = coll
                break
            else:
                keep_looping = False

    return coll_list


def get_coll_prefix(coll, prefixes):
    for prefix in prefixes:
        if coll.startswith(prefix):
            return prefix

    return False


def get_prop_from_collection(ob, valid_type):
    if len(bpy.data.collections) > 0:
        collection = None
        all_collections = bpy.data.collections
        # get direct parent collection
        for c in all_collections:
            if ob in tuple(c.objects):
                collection = c
                break
        # get collection parent tree
        if collection != None:
            collection_list = get_collection_parents(collection, all_collections)

            # test object collection parent tree
            for c in collection_list:
                c_type = c.nwo.type
                if c_type != valid_type: continue
                if c_type == 'region':
                    return c.nwo.region
                elif c_type == 'permutation':
                    return c.nwo.permutation
            
    return ''

def print_warning(string="Warning"):
    print("\033[93m" + string + "\033[0m")


def print_error(string="Error"):
    print("\033[91m" + string + "\033[0m")


def managed_blam_active():
    return nwo_globals.mb_active


def get_valid_shader_name(string):
    shader_name = get_valid_material_name(string)
    return cull_invalid_chars(shader_name)


def get_valid_material_name(material_name):
    """Removes characters from a blender material name that would have been used in legacy material properties"""
    material_parts = material_name.split(" ")
    # clean material name
    if len(material_parts) > 1:
        material_name = material_parts[1]
    else:
        material_name = material_parts[0]
    # ignore if duplicate name
    dot_partition(material_name)
    # ignore material suffixes
    material_name = material_name.rstrip("%#?!@*$^-&=.;)><|~({]}['")
    # dot partition again in case a pesky dot remains
    return dot_partition(material_name).lower()


def cull_invalid_chars(string):
    """Calls invalid characters from a string to make a valid path. Spaces are replaced with underscores"""
    path = string.replace(" ", "_")
    path = path.replace("<", "")
    path = path.replace(">", "")
    path = path.replace(":", "")
    path = path.replace('"', "")
    path = path.replace("/", "")
    path = path.replace("\\", "")
    path = path.replace("|", "")
    path = path.replace("?", "")
    path = path.replace("*", "")

    return path


def protected_material_name(material_name):
    """Returns True if the passed material name is equal to a protected material"""
    return material_name.startswith(PROTECTED_MATERIALS)

############ FOUNDRY UI UTILS
def mesh_object(ob):
    return ob.type in blender_object_types_mesh


def formalise_string(string):
    formal_string = string.replace("_", " ")
    return formal_string.title()


def bpy_enum(name, index):
    return (name, formalise_string(name), "", "", index)


def bpy_enum_list(name, index):
    return (name, name, "", "", index)


def bpy_enum_seam(name, index):
    return (name, name, "", get_icon_id("seam"), index)

def export_objects():
    context = bpy.context
    export_obs = []
    for ob in context.view_layer.objects:
        if ob.nwo.export_this and not any(
            coll.nwo.type == 'exclude' for coll in ob.users_collection
        ):
            export_obs.append(ob)

    return export_obs


def export_objects_no_arm():
    context = bpy.context
    export_obs = []
    for ob in context.view_layer.objects:
        if (
            ob.nwo.export_this
            and ob.type != "ARMATURE"
            and not any(
                coll.nwo.type == 'exclude' for coll in ob.users_collection
            )
        ):
            export_obs.append(ob)

    return export_obs

def export_objects_mesh_only():
    context = bpy.context
    export_obs = []
    for ob in context.view_layer.objects:
        if (
            ob.nwo.export_this
            and is_mesh(ob)
            and not any(
                coll.nwo.type == 'exclude' for coll in ob.users_collection
            )
        ):
            export_obs.append(ob)

    return export_obs


def sort_alphanum(var_list):
    return sorted(
        var_list,
        key=lambda item: (
            int(item.partition(" ")[0]) if item[0].isdigit() else float("inf"),
            item,
        ),
    )


def closest_bsp_object(ob):
    """
    Returns the closest bsp to the specified object
     (that is different from the current objects bsp)
    """
    closest_bsp = None
    distance = -1

    def get_distance(source_object, target_object):
        me = source_object.data
        verts_sel = [v.co for v in me.vertices]
        if verts_sel:
            seam_median = (
                source_object.matrix_world @ sum(verts_sel, Vector()) / len(verts_sel)
            )

            me = target_object.data
            verts = [v.co for v in me.vertices]
            if not verts:
                return

            target_median = (
                target_object.matrix_world @ sum(verts, Vector()) / len(verts)
            )

            [x1, y1, z1] = seam_median
            [x2, y2, z2] = target_median

            return (((x2 - x1) ** 2) + ((y2 - y1) ** 2) + ((z2 - z1) ** 2)) ** (1 / 2)

        return

    valid_targets = [ob for ob in export_objects() if ob.type in VALID_MESHES]

    for target_ob in valid_targets:
        if (
            ob != target_ob
            and target_ob.nwo.mesh_type_ui == "_connected_geometry_mesh_type_structure"
            and true_region(target_ob.nwo) != true_region(ob.nwo)
        ):
            d = get_distance(ob, target_ob)
            if d is not None:
                if distance < 0 or d < distance:
                    distance = d
                    closest_bsp = target_ob

    return closest_bsp


def object_median_point(ob):
    """Returns the median point of a blender object"""
    me = ob.data
    verts = [v.co for v in me.vertices]
    return ob.matrix_world @ sum(verts, Vector()) / len(verts)


def layer_face_count(bm, face_layer) -> int:
    """Returns the number of faces in a bmesh that have an face int custom_layer with a value greater than 0"""
    if face_layer:
        return len([face for face in bm.faces if face[face_layer]])


def layer_faces(bm, face_layer):
    """Returns the faces in a bmesh that have an face int custom_layer with a value greater than 0"""
    if face_layer:
        return [face for face in bm.faces if face[face_layer]]


def random_color(max_hue=True) -> list:
    """Returns a random color. Selects one of R,G,B and sets maximum hue"""
    rgb = [random.random() for i in range(3)]
    if max_hue:
        rand_idx = random.randint(0, 2)
        rgb[rand_idx] = 1
    return rgb


def nwo_enum(enum_name, display_name, description, icon="", index=-1, custom_icon=True) -> tuple:
    """Returns a single enum entry for use with bpy EnumPropertys"""
    full_enum = icon != "" or index != -1
    if full_enum:
        if custom_icon:
            return (
                enum_name,
                display_name,
                description,
                get_icon_id(icon),
                index,
            )

        return (enum_name, display_name, description, icon, index)

    return (enum_name, display_name, description)


def area_redraw(context):
    windows = context.window_manager.windows
    for window in windows:
        areas = window.screen.areas
        for area in areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


def delete_object_list(context, object_list):
    """Deletes the given object list from the blend scene"""
    override = context.copy()
    override["selected_objects"] = object_list
    with context.temp_override(**override):
        bpy.ops.object.delete()


def disable_prints():
    """Disables console prints"""
    sys.stdout = open(os.devnull, "w")


def enable_prints():
    """Enables console prints"""
    sys.stdout = sys.__stdout__
    
class MutePrints():
    def __enter__(self):
        disable_prints()
        return self
        
    def __exit__(self, exc_type, exc_value, traceback):
        enable_prints()
        
class ExportManager():
    def __enter__(self):
        bpy.context.scene.nwo.export_in_progress = True
        return self
        
    def __exit__(self, exc_type, exc_value, traceback):
        bpy.context.scene.nwo.export_in_progress = False

def data_relative(path: str) -> str:
    """
    Takes a full system path to a location within
    the data folder and returns the data relative path
    """
    return path.replace(get_data_path(), "")

def tag_relative(path: str) -> str:
    """
    Takes a full system path to a location within
    the tags folder and returns the tags relative path
    """
    return path.replace(get_tags_path(), "")


def update_progress(job_title, progress):
    if progress <= 1:
        length = 20  # modify this to change the length
        block = int(round(length * progress))
        msg = "\r{0}: {1} {2}%".format(
            job_title,
            "■" * block + "□" * (length - block),
            round(progress * 100, 2),
        )
        if progress >= 1:
            msg += "     \r\n"
        sys.stdout.write(msg)
        sys.stdout.flush()


def update_job(job_title, progress):
    msg = "\r{0}".format(job_title)
    if progress < 1:
        msg += "..."
    else:
        msg += "     \r\n"

    sys.stdout.write(msg)
    sys.stdout.flush()


def update_job_count(message, spinner, completed, total):
    msg = "\r{0}".format(message)
    msg += f" ({completed} / {total}) "
    if completed < total:
        msg += f"{spinner}"
    else:
        msg += "     \r\n"

    sys.stdout.write(msg)
    sys.stdout.flush()


def poll_ui(selected_types) -> bool:
    scene_nwo = bpy.context.scene.nwo
    asset_type = scene_nwo.asset_type

    return asset_type in selected_types


def is_halo_object(ob) -> bool:
    return (
        ob
        and ob.type not in ("LATTICE", "LIGHT_PROBE", "SPEAKER", "CAMERA")
        and not (ob.type == "EMPTY" and ob.empty_display_type == "IMAGE")
        and poll_ui(
            (
                "MODEL",
                "SCENARIO",
                "SKY",
                "DECORATOR SET",
                "PARTICLE MODEL",
                "PREFAB",
            )
        )
    )


def has_mesh_props(ob) -> bool:
    valid_mesh_types = (
        "_connected_geometry_mesh_type_collision",
        "_connected_geometry_mesh_type_physics",
        "_connected_geometry_mesh_type_default",
        "_connected_geometry_mesh_type_structure",
        "_connected_geometry_mesh_type_lightmap_only",
    )
    nwo = ob.nwo
    return (
        ob
        and nwo.export_this
        and is_mesh(ob)
        and nwo.mesh_type_ui in valid_mesh_types
    )


def has_face_props(ob) -> bool:
    valid_mesh_types = [
        "_connected_geometry_mesh_type_default",
        "_connected_geometry_mesh_type_structure",
    ]
    if poll_ui('MODEL'):
        valid_mesh_types.append('_connected_geometry_mesh_type_collision')
    if is_corinth() and ob.nwo.mesh_type_ui == '_connected_geometry_mesh_type_structure' and poll_ui('SCENARIO') and not ob.nwo.proxy_instance:
        return False
    return (
        ob
        and ob.nwo.export_this
        and ob.type == 'MESH'
        and ob.nwo.mesh_type_ui in valid_mesh_types
    )

def has_shader_path(mat):
    """Returns whether the given material supports shader paths"""
    name = mat.name
    return not (mat.grease_pencil or name.startswith('+sky') or name in special_material_names or name in convention_material_names)

def get_halo_material_count() -> tuple:
    count = 0
    total = 0
    for mat in bpy.data.materials:
        nwo = mat.nwo
        if not has_shader_path(mat): continue
        nwo = mat.nwo
        if nwo.shader_path:
            count += 1

        total += 1

    return count, total

def validate_ek() -> str | None:
    """Returns an relevant error message if the current game does not reference a valid editing kit. Else returns None"""
    ek = get_project_path()
    scene_project = bpy.context.scene.nwo.scene_project
    if not os.path.exists(ek):
        return f"{scene_project} Editing Kit path invalid"
    elif not os.path.exists(os.path.join(ek, get_tool_type() + ".exe")):
        return f"Tool not found, please check that you have tool.exe within your {scene_project} directory"
    elif not os.path.exists(os.path.join(ek, "data")):
        return f"Editing Kit data folder not found. Please ensure your {scene_project} directory has a 'data' folder"
    elif not os.path.exists(os.path.join(ek, "bin", "ManagedBlam.dll")):
        return f"ManagedBlam not found in your {scene_project} bin folder, please ensure this exists"
    elif not nwo_globals.clr_installed:
        return 'ManagedBlam dependancy not installed. Please install this from Foundry preferences or use "Initialize ManagedBlam" in the Foundry Panel'
    else:
        prefs = get_prefs()
        projects = prefs.projects
        for p in projects:
            if p.name == scene_project:
                if os.path.exists(p.project_path):
                    return
                return f'{p.name} project path does not exist'
        return 'Please select a project in Foundry Scene Properties'
    
def foundry_update_check(current_version):
    update_url = 'https://api.github.com/repos/iloveagoodcrisp/foundry-halo-blender-creation-kit/releases'
    if not bpy.app.background:
        try:
            response = requests.get(update_url, timeout=1)
            releases = response.json()
            latest_release = releases[0]
            latest_version = latest_release['tag_name']
            if current_version < latest_version:
                return f"New Foundry version available: {latest_version}", True
        except:
            pass

    return "Foundry is up to date", False

def unlink(ob):
    data_coll = bpy.data.collections
    for collection in data_coll:
        if collection in ob.users_collection:
            collection.objects.unlink(ob)

    scene_coll = bpy.context.scene.collection
    if scene_coll in ob.users_collection:
        scene_coll.objects.unlink(ob)

def set_object_mode(context):
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

def get_prefs():
    return bpy.context.preferences.addons["io_scene_foundry"].preferences

def is_halo_mapping_node(node: bpy.types.Node) -> bool:
    """Given a Node and a list of valid inputs (each a string), checks if the given Node has exactly the inputs supplied"""
    inputs = node.inputs
    if len(inputs) != len(HALO_SCALE_NODE):
        return False
    for i in node.inputs:
        if i.name in HALO_SCALE_NODE: continue
        return False
    return True

def recursive_image_search(tree_owner):
    nodes = tree_owner.node_tree.nodes
    for n in nodes:
        if getattr(n, "image", 0):
            return True
        elif n.type == 'GROUP':
            image_found = recursive_image_search(n)
            if image_found:
                return True
            

def remove_chars(string, chars):
    for c in chars:
        string = string.replace(c, "")

    return string

def write_projects_list(project_list):
    appdata = os.getenv('APPDATA')
    foundry_folder = os.path.join(appdata, "FoundryHBCK")

    if not os.path.exists(foundry_folder):
        os.makedirs(foundry_folder)

    projects = os.path.join(foundry_folder, "projects.json")
    with open(projects, 'w') as file:
        json.dump(project_list, file, indent=4)

def read_projects_list() -> list:
    projects_list = []
    appdata = os.getenv('APPDATA')
    foundry_folder = os.path.join(appdata, "FoundryHBCK")

    if not os.path.exists(foundry_folder):
        return print("No Foundry Folder")

    projects = os.path.join(foundry_folder, "projects.json")
    if not os.path.exists(projects):
        return print("No Foundry json")
    
    with open(projects, 'r') as file:
        projects_list = json.load(file)

    return projects_list

class ProjectXML():
    def __init__(self, project_root):
        self.name = ""
        self.display_name = ""
        self.remote_database_name = ""
        self.project_xml = ""
        self.read_xml(project_root)

    def read_xml(self, project_root):
        self.project_xml = os.path.join(project_root, "project.xml")
        if not os.path.exists(self.project_xml):
            return print(f"{project_root} is not a path to a valid Halo project. Expected project root directory to contain project.xml")
        with open(self.project_xml, 'r') as file:
            xml = file.read()
            root = ET.fromstring(xml)
            self.name = root.get('name', 0)
            if not self.name:
                return print(f"Failed to parse XML: {self.project_xml}. Could not return Name")
            self.display_name = root.get('displayName', 0)
            if not self.display_name:
                return print(f"Failed to parse XML: {self.project_xml}. Could not return displayName")
            self.remote_database_name = root.find('./tagDatastore').get('remoteDatabaseName', 0)
            if not self.remote_database_name:
                return print(f"Failed to parse XML: {self.project_xml}. Could not return remoteDatabaseName")
            # It's fine if these fail, they are only used to render icons
            self.remote_server_name = root.find('./tagDatastore').get('remoteServerName', 0)
            image = root.find('./imagePath')
            if image is not None:
             self.image_path = image.text

def setup_projects_list(skip_registry_check=False, report=None):
    projects_list = read_projects_list()
    new_projects_list = []
    prefs = get_prefs()
    prefs.projects.clear()
    display_names = []
    if projects_list is not None:
        for i in projects_list:
            xml = ProjectXML(i)
            if xml.name and xml.display_name and xml.remote_database_name and xml.project_xml:
                if xml.display_name in display_names:
                    warning = f"{xml.display_name} already exists. Ensure new project has a unique project display name. This can be changed by editing the displayName field in {os.path.join(i, 'project.xml')}"
                    print_warning(warning)
                    if report is not None:
                        report({'WARNING'}, warning)
                    continue

                display_names.append(xml.display_name)
                new_projects_list.append(i)
                p = prefs.projects.add()
                p.project_path = i
                p.project_xml = xml.project_xml
                p.project_name = xml.name
                p.name = xml.display_name
                p.project_remote_server_name = xml.remote_server_name
                p.project_image_path = xml.image_path
                p.project_corinth = xml.remote_database_name == "tags"
    
    if new_projects_list:
        # Write new file to ensure sync
        write_projects_list(new_projects_list)
        return prefs.projects
    elif not skip_registry_check:
        # Attempt to get the current project if no projects found
        key_path = r"bonobo\shell\open\command"
        try:
            # Open the registry key
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, key_path) as key:
                # Read the default value (an empty string) of the key
                value, _ = winreg.QueryValueEx(key, None)
                
            bonobo_path = value.rpartition('.exe"')[0].strip('"\' ')
            project_root = os.path.dirname(bonobo_path)
            if os.path.exists(os.path.join(project_root, "project.xml")):
                write_projects_list([project_root])
                setup_projects_list(True, report)
                    
        except:
            pass

def update_tables_from_objects(context):
    regions_table = context.scene.nwo.regions_table
    region_names = [e.name for e in regions_table]
    permutations_table = context.scene.nwo.permutations_table
    permutation_names = [e.name for e in permutations_table]
    scene_obs = context.scene.objects
    for ob in scene_obs:
        ob_region = true_region(ob.nwo)
        if not ob_region:
            ob.nwo.region_name_ui = region_names[0]
        elif ob_region not in region_names:
            new_region = regions_table.add()
            new_region.name = ob_region
            region_names.add(ob_region)
            ob.nwo.region_name_ui = ob_region

        ob_permutation = true_permutation(ob.nwo)
        if not ob_permutation:
            ob.nwo.permutation_name_ui = permutation_names[0]
        elif ob_permutation not in permutation_names:
            new_permutation = permutations_table.add()
            new_permutation.name = ob_permutation
            permutation_names.add(ob_permutation)
            ob.nwo.permutation_name_ui = ob_permutation

# def update_objects_from_tables(context, table_str, ob_prop_str):
#     entry_names = [e.name for e in getattr(context.scene.nwo, table_str)]
#     default_entry = entry_names[0]
#     scene_obs = context.scene.objects
#     for ob in scene_obs:
#         if getattr(ob.nwo, ob_prop_str) not in entry_names:
#             setattr(ob.nwo, ob_prop_str, default_entry)

def addon_root():
    return os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

def extract_from_resources(relative_file_path):
    p = pathlib.PureWindowsPath(relative_file_path)
    resources_zip = os.path.join(addon_root(), 'resources.zip')
    os.chdir(addon_root())
    with zipfile.ZipFile(resources_zip, "r") as zip:
        file = zip.extract(p.as_posix())
    return file

def import_gltf(path):
    unit_settings = bpy.context.scene.unit_settings
    old_unit_scale = unit_settings.scale_length
    unit_settings.scale_length = 1
    print(path)
    bpy.ops.import_scene.gltf(filepath=path, import_shading='FLAT')
    unit_settings.scale_length = old_unit_scale

def get_mesh_display(mesh_type):
    match mesh_type:
        case '_connected_geometry_mesh_type_structure':
            return 'Structure', get_icon_id('structure')
        case '_connected_geometry_mesh_type_collision':
            return 'Collision', get_icon_id('collider')
        case '_connected_geometry_mesh_type_physics':
            return 'Physics', get_icon_id('physics')
        case '_connected_geometry_mesh_type_seam':
            return 'Seam', get_icon_id('seam')
        case '_connected_geometry_mesh_type_portal':
            return 'Portal', get_icon_id('portal')
        case '_connected_geometry_mesh_type_water_surface':
            return 'Water Surface', get_icon_id('water')
        case '_connected_geometry_mesh_type_water_physics_volume':
            return 'Water Physics Volume', get_icon_id('water_physics')
        case '_connected_geometry_mesh_type_soft_ceiling':
            return 'Soft Ceiling Volume', get_icon_id('soft_ceiling')
        case '_connected_geometry_mesh_type_soft_kill':
            return 'Soft Kill Volume', get_icon_id('soft_ceiling')
        case '_connected_geometry_mesh_type_slip_surface':
            return 'Slip Surface Volume', get_icon_id('slip_surface')
        case '_connected_geometry_mesh_type_poop_rain_blocker':
            return 'Rain Blocker Volume', get_icon_id('rain_blocker')
        case '_connected_geometry_mesh_type_lightmap_exclude':
            return 'Lightmap Exclusion Volume', get_icon_id('lightmap_exclude')
        case '_connected_geometry_mesh_type_streaming':
            return 'Texture Streaming Volume', get_icon_id('streaming')
        case '_connected_geometry_mesh_type_poop_vertical_rain_sheet':
            return 'Rain Sheet', get_icon_id('rain_sheet')
        case '_connected_geometry_mesh_type_cookie_cutter':
            return 'Pathfinding Cutout Volume', get_icon_id('cookie_cutter')
        case '_connected_geometry_mesh_type_planar_fog_volume':
            return 'Fog Sheet', get_icon_id('fog')
        case '_connected_geometry_mesh_type_lightmap_only':
            return 'Lightmap Only', get_icon_id('lightmap')
        case _:
            if poll_ui(('SCENARIO', 'PREFAB')):
                return 'Instanced Geometry', get_icon_id('instance')
            elif poll_ui(('DECORATOR')):
                return 'Decorator', get_icon_id('decorator')
            else:
                return 'Render', get_icon_id('render_geometry')

def library_instanced_collection(ob):
    return ob.instance_type == 'COLLECTION' and ob.instance_collection and ob.instance_collection.library

def get_marker_display(mesh_type):
    match mesh_type:
        case '_connected_geometry_marker_type_effects':
            return 'Effects', get_icon_id('effects')
        case '_connected_geometry_marker_type_garbage':
            return 'Garbage', get_icon_id('garbage')
        case '_connected_geometry_marker_type_hint':
            return 'Hint', get_icon_id('hint')
        case '_connected_geometry_marker_type_pathfinding_sphere':
            return 'Pathfinding Sphere', get_icon_id('pathfinding_sphere')
        case '_connected_geometry_marker_type_physics_constraint':
            return 'Physics Constraint', get_icon_id('physics_constraint')
        case '_connected_geometry_mesh_type_water_surface':
            return 'Water Surface', get_icon_id('water')
        case '_connected_geometry_marker_type_target':
            return 'Target', get_icon_id('target')
        case '_connected_geometry_marker_type_game_instance':
            return 'Game Object', get_icon_id('game_object')
        case '_connected_geometry_marker_type_airprobe':
            return 'Airprobe', get_icon_id('airprobe')
        case '_connected_geometry_marker_type_envfx':
            return 'Environment Effect', get_icon_id('environment_effect')
        case '_connected_geometry_marker_type_lightCone':
            return 'Light Cone', get_icon_id('light_cone')
        case _:
            if poll_ui(('SCENARIO', 'PREFAB')):
                return 'Structure Marker', get_icon_id('marker')
            else:
                return 'Model Marker', get_icon_id('marker')
            
def is_mesh(ob):
    return ob.type in VALID_MESHES

def is_marker(ob):
    return ob.type == 'EMPTY' and not ob.children and not library_instanced_collection(ob) and ob.empty_display_type != "IMAGE"

def is_frame(ob):
    return (ob.type == 'EMPTY' and ob.children) or ob.type == 'ARMATURE'

def is_light(ob):
    return ob.type == 'LIGHT'

def is_camera(ob):
    return ob.type == 'CAMERA'

def get_object_type(ob, get_ui_name=False):
    if is_mesh(ob):
        return 'Mesh' if get_ui_name else '_connected_geometry_object_type_mesh'
    elif is_marker(ob):
        return 'Marker' if get_ui_name else '_connected_geometry_object_type_marker'
    elif is_frame(ob):
        return 'Frame' if get_ui_name else '_connected_geometry_object_type_frame'
    elif is_light(ob):
        return 'Light' if get_ui_name else '_connected_geometry_object_type_light'
    elif is_camera(ob):
        return 'Camera' if get_ui_name else '_connected_geometry_object_type_animation_camera'
    else:
        return 'None' if get_ui_name else '_connected_geometry_object_type_none'
    
def type_valid(m_type, asset_type=None, game_version=None):
    if asset_type is None:
        asset_type = bpy.context.scene.nwo.asset_type
    if game_version is None:
        game_version = 'corinth' if is_corinth() else 'reach'
    return asset_type in object_asset_validation[m_type] and game_version in object_game_validation[m_type]

def get_shader_name(mat):
    if not protected_material_name(mat.name):
        shader_name = get_valid_shader_name(mat.name)
        if shader_name != "":
            return shader_name

    return None

def get_arm_count(context: bpy.types.Context):
    arms = [ob for ob in context.view_layer.objects if ob.type == 'ARMATURE']
    return len(arms)

def blender_toolset_installed():
    script_dirs = bpy.utils.script_paths()
    for dir in script_dirs:
        if os.path.exists(os.path.join(dir, 'addons', 'io_scene_halo')):
            return True
    return False
    
def amf_addon_installed():
    script_dirs = bpy.utils.script_paths()
    for dir in script_dirs:
        if os.path.exists(os.path.join(dir, 'addons', 'Blender AMF2.py')):
            return 'Blender AMF2'
        elif os.path.exists(os.path.join(dir, 'addons', 'Blender_AMF2.py')):
            return 'Blender_AMF2'
        
    return False
    
def has_collision_type(ob: bpy.types.Object) -> bool:
    nwo = ob.nwo
    mesh_type = nwo.mesh_type_ui
    if not poll_ui(('SCENARIO', 'PREFAB')) and mesh_type != '_connected_geometry_mesh_type_collision':
        return False
    if mesh_type in COLLISION_MESH_TYPES:
        return True
    if is_instance_or_structure_proxy(ob):
        return True
    return False

def get_sky_perm(mat: bpy.types.Material) -> int:
    name = mat.name
    index_part = name.rpartition('+sky')[2]
    if not index_part:
        return -1
    index_ignore_period = dot_partition(index_part)
    index = ''.join(c for c in index_ignore_period if c.isdigit())
    if not index:
        return -1
    return int(index)
        
def is_instance_or_structure_proxy(ob) -> bool:
    mesh_type = ob.nwo.mesh_type_ui
    if not poll_ui(('SCENARIO', 'PREFAB')):
        return False
    if mesh_type == '_connected_geometry_mesh_type_default':
        return True
    if is_corinth() and mesh_type == '_connected_geometry_mesh_type_structure' and ob.nwo.proxy_instance:
        return True
    return False

def set_origin_to_floor(ob):
    bbox = ob.bound_box
    world_coords = []
    min_z = None
    for co in bbox:
        world_co = ob.matrix_world @ Vector((co[0], co[1], co[2]))
        if min_z is None:
            min_z = world_co.z
        else:
            min_z = min(min_z, world_co.z)
        world_coords.append(world_co)
    
    floor_corners = []
    for vec in world_coords:
        if vec.z == min_z:
            floor_corners.append(vec)
    assert(len(floor_corners) == 4)
    # Calc center point
    avg_x = sum(v.x for v in floor_corners) / 4.0
    avg_y = sum(v.y for v in floor_corners) / 4.0
    center_point = Vector((avg_x, avg_y, min_z))
    bpy.context.scene.cursor.location = center_point
    set_active_object(ob)
    ob.select_set(True)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR', center='MEDIAN')
    ob.select_set(False)
    
def set_origin_to_centre(ob):
    set_active_object(ob)
    ob.select_set(True)
    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='MEDIAN')
    ob.select_set(False)
    
def path_as_tag_path_no_ext(path):
    return dot_partition(path.replace(get_tags_path(), ''))

def get_project_from_scene(scene):
    scene_project = scene.nwo.scene_project
    projects = get_prefs().projects
    for p in projects:
        if p.name == scene_project:
            return p
        
    print("Failed to get project")
    
def material_read_only(path):
    """Returns true if a material is read only aka in the project's protected list"""
    # Return false immediately if user has disabled material protection
    if not get_prefs().protect_materials: return False
    # Ensure path is correctly sliced
    path = path_as_tag_path_no_ext(path)
    project = get_project_from_scene(bpy.context.scene)
    protected_list = os.path.join(addon_root(), 'protected_tags', project.project_name, 'materials.txt')
    if not os.path.exists(protected_list): return False
    protected_materials = None
    with open(protected_list, 'r') as f:
        protected_materials = [line.rstrip('\n') for line in f]
    if protected_materials is None: return False
    for tag in protected_materials:
        if path == tag:
            return True
    return False

def stomp_scale_multi_user(objects):
    """Checks that at least one user of a mesh has a uniform scale of 1,1,1. If not, applies scale to all linked objects, using the object with the smallest scale as a basis"""
    good_scale = Vector.Fill(3, 1)
    meshes = {ob.data for ob in objects}
    mesh_ob_dict = {mesh: [ob for ob in objects if ob.data == mesh] for mesh in meshes}
    deselect_all_objects()
    for me in mesh_ob_dict.keys():
        scales = []
        for ob in mesh_ob_dict[me]:
            abs_scale = Vector((abs(ob.scale.x), abs(ob.scale.y), abs(ob.scale.z)))
            if abs_scale == good_scale:
                # print(f"{me.name} has at least one object with good scale [{ob.name}]")
                scales.clear()
                break
            scales.append(abs(ob.scale.x))
        if not scales: continue
        basis_scale = np.median(scales)
        obs_matching_basis = [ob for ob in mesh_ob_dict[me] if abs(ob.scale.x) == basis_scale]
        if obs_matching_basis:
            basis_ob = obs_matching_basis[0]
        else:
            basis_ob = mesh_ob_dict[me][0]
        set_active_object(basis_ob)
        [ob.select_set(True) for ob in mesh_ob_dict[me]]
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        deselect_all_objects()
        
def get_scale_ratio(scale):
    return round(scale.x / scale.y, 6), round(scale.y / scale.z, 6), round(scale.z / scale.x, 6)

def enforce_uniformity(objects):
    """Check for non-uniform scale objects and split them into new meshes if needed with applied scale"""
    meshes = {ob.data for ob in objects}
    mesh_ob_dict = {mesh: [ob for ob in objects if ob.data == mesh] for mesh in meshes}
    deselect_all_objects()
    for me in mesh_ob_dict.keys():
        scale_ob_dict = {}
        for ob in mesh_ob_dict[me]:
            scale = ob.scale
            if scale.x == scale.y and scale.x == scale.z:
                continue
            scale_ratio = get_scale_ratio(scale)
            if scale_ob_dict.get(scale_ratio, 0):
                scale_ob_dict[scale_ratio].append(ob)
            else:
                scale_ob_dict[scale_ratio] = [ob]
    
    for k in scale_ob_dict:
        [ob.select_set(True) for ob in scale_ob_dict[k]]
        set_active_object(scale_ob_dict[k][0])
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True, isolate_users=True)
        deselect_all_objects()
        
        
def calc_light_intensity(light_data):
    if light_data.type == "SUN":
        return light_data.energy
    
    intensity = (light_data.energy / 0.03048**-2) / (10 if is_corinth() else 300)
    
    return intensity

def calc_light_energy(light_data, intensity):
    if light_data.type == "SUN":
        return intensity
    
    energy = intensity * (0.03048 ** -2) * (10 if is_corinth() else 300)
    
    return energy

def get_blender_shader(node_tree: bpy.types.NodeTree) -> bpy.types.Node | None:
    """Gets the BSDF shader node from a node tree"""
    output = None
    shaders = []
    for node in node_tree.nodes:
        if node.type == "OUTPUT_MATERIAL":
            output = node
        elif node.type.startswith("BSDF"):
            shaders.append(node)
    # Get the shader plugged into the output
    if output is None:
        return
    for s in shaders:
        outputs = s.outputs
        if not outputs:
            return
        links = outputs[0].links
        if not links:
            return
        if links[0].to_node == output:
            return s

    return

def find_mapping_node(node: bpy.types.Node) -> bpy.types.Node | None:
    links = node.inputs['Vector'].links
    if not links: return
    scale_node = links[0].from_node
    if scale_node.type == 'MAPPING' or is_halo_mapping_node(scale_node):
        return scale_node

def find_linked_node(start_node: bpy.types.Node, input_name: str, node_type: str) -> bpy.types.Node:
    """Using the given node as a base, finds the first node from the given input that matches the given node type"""
    for i in start_node.inputs:
        if input_name in i.name.lower():
            if i.links:
                input = i
                break
            else:
                return
    else:
        return
    
    node, _ = find_node_in_chain(node_type, input.links[0].from_node)
    if node:
        return node
    
def find_node_in_chain(node_type: str, node: bpy.types.Node, group_output_input=None, group_node=None) -> tuple[bpy.types.Node, bpy.types.Node]:
    if node.type == node_type:
        return node, group_node
    
    elif node.type == 'GROUP':
        group_nodes = node.node_tree.nodes
        for n in group_nodes:
            if n.type == 'GROUP_OUTPUT':
                for i in n.inputs:
                    if i.name == group_output_input:
                        links = i.links
                        if links:
                            for l in links:
                                new_node = l.from_node
                                valid_node, group_node = find_node_in_chain(node_type, new_node, group_output_input, node)
                                if valid_node:
                                    return valid_node, group_node
                                break
                break
            
    for input in node.inputs:
        for link in input.links:
            next_node = link.from_node
            if next_node.type == 'GROUP':
                valid_node, group_node = find_node_in_chain(node_type, next_node, link.from_socket.name, node)
            else:
                valid_node, group_node = find_node_in_chain(node_type, next_node, group_output_input)
            if valid_node:
                return valid_node, group_node
    
    return None, None
            
def get_material_albedo(source: bpy.types.Material | bpy.types.Node, input=None) -> tuple[float, float, float, float]:
    """Returns the albedo tint of a material as a tuple in the form RGBA directly from the material or from the given node"""
    col = [1, 1, 1]
    if type(source) == bpy.types.Material:
        col = source.diffuse_color
    else:
        if input:
            color_node = find_linked_node(source, input.name.lower(), 'RGB')
        else:
            color_node = find_linked_node(source, 'color', 'RGB')
        if color_node:
            col = color_node.color
        if input:
            col = input.default_value
        else:
            for i in source.inputs:
                if 'color' in i.name.lower():
                    col = i.default_value
                    break
                
    return col[:3] # Only 3 since we don't care about the alpha
            
def get_rig(context, return_mutliple=False) -> bpy.types.Object | None | list[bpy.types.Object]:
    """Gets the main armature from the scene (or tries to)"""
    scene_nwo = context.scene.nwo
    ob = context.object
    if scene_nwo.main_armature:
        return scene_nwo.main_armature
    obs = export_objects()
    rigs = [ob for ob in obs if ob.type == 'ARMATURE']
    if not rigs:
        return
    elif len(rigs) > 1 and return_mutliple:
        return rigs
    if ob in rigs:
        scene_nwo.main_armature = ob
        return ob
    else:
        scene_nwo.main_armature = rigs[0]
        return rigs[0]
    
def find_file_in_directory(root_dir, filename) -> str:
    """Finds the first file in the current and sub-directories matching the given filename. If none found, returns an empty string"""
    for root, _, files in os.walk(root_dir):
        for file in files:
            if file == filename:
                return os.path.join(root, file)
            
    return ''

def add_node_from_resources(name):
    if not bpy.data.node_groups.get(name, 0):
        lib_blend = os.path.join(MATERIAL_RESOURCES, 'shared_nodes.blend')
        with bpy.data.libraries.load(lib_blend, link=True) as (_, data_to):
            if not bpy.data.node_groups.get(name, 0):
                data_to.node_groups = [name]
            
    return bpy.data.node_groups.get(name)

def rgb_to_float_list(red, green, blue):
    return [red / 255, green / 255, blue / 255]

def copy_file(from_path, to_path):
    shutil.copyfile(from_path, to_path)
    
def get_foundry_storage_scene() -> bpy.types.Scene:
    """Returns the Foundry storage scene, creating it if it does not exist"""
    storage_scene = bpy.data.scenes.get('foundry_object_storage')
    if storage_scene is None:
        storage_scene =  bpy.data.scenes.new('foundry_object_storage')
        storage_scene.nwo.storage_only = True
        
    return storage_scene

def base_material_name(name: str, strip_legacy_halo_names=False) -> str:
    """Returns a material name with legacy halo naming conventions stripped and ignoring .00X blender duplicate names"""
    """Tries to find a shader match. Includes logic for filtering out legacy material name prefixes/suffixes"""
    partitioned = dot_partition(name)
    if not strip_legacy_halo_names:
        return partitioned
    parts = partitioned.split(" ")
    if len(parts) > 1:
        material_name = parts[1]
    else:
        material_name = parts[0]
    # ignore material suffixes
    return material_name.rstrip("%#?!@*$^-&=.;)><|~({]}['") # excluding 0 here as it can interfere with normal naming convention

def reset_to_basis(keep_animation=False):
    animated_objects = [ob for ob in bpy.data.objects if ob.animation_data]
    for ob in animated_objects:
        if not keep_animation:
            ob.animation_data.action = None
        ob.matrix_basis = Matrix()
        if ob.type == 'ARMATURE':
            for bone in ob.pose.bones:
                bone.matrix_basis = Matrix()
                
def asset_path_from_blend_location() -> str | None:
    blend_path = bpy.data.filepath.lower()
    data_path = get_data_path()
    if blend_path.startswith(data_path):
        return os.path.dirname(blend_path).replace(data_path, '')
    return None

def get_export_scale(context) -> int:
    export_scale = 1
    scene_nwo = context.scene.nwo
    if scene_nwo.scale == 'blender':
        export_scale = (1 / 0.03048)
        
    return export_scale

def wu(meters) -> int:
    '''Converts a meter to a world unit'''
    return meters * 3.048

def exit_local_view(context):
    for area in context.screen.areas:
        if area.type == "VIEW_3D":
            space = area.spaces[0]
            if space.local_view:
                for region in area.regions:
                    if region.type == "WINDOW":
                        override = context.copy()
                        override["area"] = area
                        override["region"] = region
                        with context.temp_override(**override):
                            bpy.ops.view3d.localview()
                            
class NodeChild():
    def __init__(self, ob):
        self.ob: bpy.types.Object = ob
        self.parent: bpy.types.Object = None
        self.parent_bone: str = None
        self.matrix: Matrix = None
        # self.group: str = None

def scale_scene(context: bpy.types.Context, scale_factor, rotation):
    # armatures = [ob for ob in bpy.data.objects if ob.type == 'ARMATURE']
    armatures = []
    scene_coll = context.scene.collection.objects
    axis_z = Vector((0, 0, 1))
    pivot = Vector((0.0, 0.0, 0.0))
    rotation_matrix = Matrix.Rotation(rotation, 4, axis_z)
    pivot_matrix = (Matrix.Translation(pivot) @ rotation_matrix @ Matrix.Translation(-pivot))
    scale_matrix = Matrix.Scale(scale_factor, 4)
    transform_matrix = rotation_matrix @ scale_matrix
    parented_objects = {}
    for ob in bpy.data.objects:
        if ob.parent and ((ob.parent.type == 'ARMATURE' and ob.parent_type == 'BONE') or (ob.parent_type == 'OBJECT' and ob.parent.type != 'ARMATURE')):
            child_ob = NodeChild(ob)
            child_ob.parent = ob.parent
            # child_ob.group = ob.parent.name
            if ob.parent_type == 'BONE' and ob.parent_bone:
                child_ob.parent_bone = ob.parent_bone
                # child_ob.group += f'-:--:-{ob.parent_bone}'
                
            parented_objects[ob] = child_ob
    
    if parented_objects:
        override = context.copy()
        override['selected_objects'] = list(parented_objects.keys())
        override['selected_editable_objects'] = list(parented_objects.keys())
        override['active_object'] = list(parented_objects.keys())[0]
        area, area_region, area_space = get_area_info(context)
        override["area"] = area
        override["region"] = area_region
        override["space_data"] = area_space
        with context.temp_override(**override):
            bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
    
    for ob in bpy.data.objects:
        no_data_transform = ob.type in ('EMPTY', 'CAMERA', 'LIGHT', 'LIGHT_PROBE', 'SPEAKER')
        loc, rot, sca = ob.matrix_world.decompose()
        if ob.rotation_mode == 'QUATERNION':
            rot = ob.rotation_quaternion
        else:
            rot = ob.rotation_euler
            
        loc *= scale_factor
        if rotation:
            loc = pivot_matrix @ loc
            
        if ob.type != 'ARMATURE':
            rot.rotate(rotation_matrix)
        
        # Lights need scaling to have correct display 
        if ob.type == 'LIGHT':
            sca *= scale_factor
            
        if ob.type == 'EMPTY':
            ob.empty_display_size *= scale_factor
            
        elif ob.type == 'ARMATURE':
            armatures.append(ob)
        
        ob.matrix_world = Matrix.LocRotScale(loc, rot, sca)

        if parented_objects.get(ob, 0):
            parented_objects[ob].matrix = ob.matrix_world
        
        for mod in ob.modifiers:
            match mod.type:
                case 'BEVEL':
                    mod.width *= scale_factor
                case 'DISPLACE':
                    mod.strength *= scale_factor
                case 'CAST':
                    mod.radius *= scale_factor
                case 'SHRINKWRAP':
                    mod.offset *= scale_factor
                case 'WAVE':
                    mod.offset *= scale_factor
                    mod.height *= scale_factor
                    mod.width *= scale_factor
                    
        for con in ob.constraints:
            match con.type:
                case 'LIMIT_DISTANCE':
                    con.distance *= scale_factor
                case 'LIMIT_LOCATION':
                    con.min_x *= scale_factor
                    con.min_y *= scale_factor
                    con.min_z *= scale_factor
                    con.max_x *= scale_factor
                    con.max_y *= scale_factor
                    con.max_z *= scale_factor
                case 'STRETCH_TO':
                    con.rest_length *= scale_factor
                case 'SHRINKWRAP':
                    con.distance *= scale_factor
            
    for curve in bpy.data.curves:
        if hasattr(curve, 'size'):
            curve.size *= scale_factor
            
        curve.transform(scale_matrix)
        curve.nwo.material_lighting_attenuation_falloff_ui *= scale_factor
        curve.nwo.material_lighting_attenuation_cutoff_ui *= scale_factor
        curve.nwo.material_lighting_emissive_power_ui *= scale_factor
        
    for metaball in bpy.data.metaballs:
        metaball.transform(scale_matrix)
        metaball.nwo.material_lighting_attenuation_falloff_ui *= scale_factor
        metaball.nwo.material_lighting_attenuation_cutoff_ui *= scale_factor
        metaball.nwo.material_lighting_emissive_power_ui *= scale_factor
        
    for lattice in bpy.data.lattices:
        lattice.transform(scale_matrix)
    
    for mesh in bpy.data.meshes:
        mesh.transform(scale_matrix)
        mesh.nwo.material_lighting_attenuation_falloff_ui *= scale_factor
        mesh.nwo.material_lighting_attenuation_cutoff_ui *= scale_factor
        mesh.nwo.material_lighting_emissive_power_ui *= scale_factor
        
    for camera in bpy.data.cameras:
        camera.display_size *= scale_factor
        
    for light in bpy.data.lights:
        light.energy *= scale_factor ** 2
        light.nwo.light_far_attenuation_start *= scale_factor
        light.nwo.light_far_attenuation_end *= scale_factor
        light.nwo.light_near_attenuation_start *= scale_factor
        light.nwo.light_near_attenuation_end *= scale_factor
        light.nwo.light_fade_start_distance *= scale_factor
        light.nwo.light_fade_end_distance *= scale_factor
            
    for arm in armatures:
        if arm.library or arm.data.library:
            print_warning(f'Cannot scale {arm.name}')
            continue
        
        should_be_hidden = False
        should_be_unlinked = False
        data: bpy.types.Armature = arm.data
        if arm.hide_get():
            arm.hide_set(False)
            should_be_hidden = True
            
        if not arm.visible_get():
            unlink(arm)
            scene_coll.link(arm)
            should_be_unlinked = True
            
        set_active_object(arm)
        
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        
        uses_edit_mirror = bool(arm.data.use_mirror_x)
        if uses_edit_mirror:
            arm.data.use_mirror_x = False
        
        edit_bones = data.edit_bones
        connected_bones = [b for b in edit_bones if b.use_connect] 
        for edit_bone in connected_bones:
            edit_bone.use_connect = False
            
        for edit_bone in edit_bones:
            edit_bone.transform(transform_matrix)
            
        for edit_bone in connected_bones:
            edit_bone.use_connect = True
    
        if uses_edit_mirror:
            arm.data.use_mirror_x = True
        
        bpy.ops.object.mode_set(mode='POSE', toggle=False)
        
        uses_pose_mirror = bool(arm.pose.use_mirror_x)
        if uses_pose_mirror:
            arm.pose.use_mirror_x = False
        
        for pose_bone in arm.pose.bones:
            # pose_bone: bpy.types.PoseBone
            pose_bone.matrix_basis = Matrix()
            pose_bone.custom_shape_translation *= scale_factor
            if pose_bone.use_custom_shape_bone_size:
                pose_bone.custom_shape_scale_xyz *= (1 / scale_factor)
            
            for con in pose_bone.constraints:
                match con.type:
                    case 'LIMIT_DISTANCE':
                        con.distance *= scale_factor
                    case 'LIMIT_LOCATION':
                        con.min_x *= scale_factor
                        con.min_y *= scale_factor
                        con.min_z *= scale_factor
                        con.max_x *= scale_factor
                        con.max_y *= scale_factor
                        con.max_z *= scale_factor
                    case 'STRETCH_TO':
                        con.rest_length *= scale_factor
                    case 'SHRINKWRAP':
                        con.distance *= scale_factor

        if uses_pose_mirror:
            arm.pose.use_mirror_x = True
            
        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
        
        for bone in data.bones:
            bone.bbone_x *= scale_factor
            bone.bbone_z *= scale_factor
        
        if should_be_hidden:
            arm.hide_set(True)
            
        if should_be_unlinked:
            unlink(arm)
    
    for child in parented_objects.values():
        child.ob.parent = child.parent
        if child.parent_bone:
            child.ob.parent_bone = child.parent_bone
        child.ob.matrix_world = child.matrix

    for action in bpy.data.actions:
        for fcurve in action.fcurves:
            if fcurve.data_path.endswith('location'):
                for mod in fcurve.modifiers:
                    if mod.type == 'NOISE':
                        mod.strength *= scale_factor
                for keyframe_point in fcurve.keyframe_points:
                    keyframe_point.co[1] *= scale_factor
                    
                fcurve.keyframe_points.handles_recalc()
                
def get_area_info(context):
    area = [
        area
        for area in context.screen.areas
        if area.type == "VIEW_3D"
    ][0]
    return area, area.regions[-1], area.spaces.active

def blender_halo_rotation_diff(direction):
    """Returns the rotation (radians) needed to go from the current blender forward to Halo X forward"""
    match direction:
        case "y":
            return radians(-90)
        case "y-":
            return radians(90)
        case "x-":
            return radians(180)
            
    return 0

def blender_rotation_diff(direction, scene_direction):
    """Returns the rotation (radians) needed to go from the current blender forward to the selected forward"""
    rot = blender_halo_rotation_diff(scene_direction)
    match direction:
        case "y":
            return rot - radians(-90)
        case "y-":
            return rot - radians(90)
        case "x-":
            return rot - radians(180)
        case "x":
            return rot - 0
            
    return 0
    