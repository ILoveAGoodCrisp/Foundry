from collections import Counter
import ctypes
from enum import Enum, auto
import itertools
import json
from math import radians
from pathlib import Path, PureWindowsPath
import shutil
import subprocess
import sys
import threading
import time
from uuid import uuid4
import winreg
import zipfile
import bmesh
import bpy
import platform
from mathutils import Euler, Matrix, Vector, Quaternion
import os
from subprocess import Popen, check_call
import random
import xml.etree.ElementTree as ET
import numpy as np

from .constants import COLLISION_MESH_TYPES, PROTECTED_MATERIALS, VALID_MESHES
from .tools.materials import special_materials, convention_materials
from .icons import get_icon_id, get_icon_id_in_directory
import requests

from .constants import object_asset_validation, object_game_validation

spinny = itertools.cycle(["|", "/", "—", "\\"])

HALO_SCALE_NODE = ['Scale Multiplier', 'Scale X', 'Scale Y']
MATERIAL_RESOURCES = os.path.join(os.path.dirname((os.path.realpath(__file__))), 'blends', 'materials')

special_material_names = [m.name for m in special_materials]
convention_material_names = [m.name for m in convention_materials]

object_exts = '.crate', '.scenery', '.effect_scenery', '.device_control', '.device_machine', '.device_terminal', '.device_dispenser', '.biped', '.creature', '.giant', '.vehicle', '.weapon', '.equipment'

legacy_lightmap_prefixes = 'lm:', 'lp:', 'hl:', 'ds:', 'ds:', 'pf:', 'lt:', 'to:', 'at:', 'ro:'

###########
##GLOBALS##
###########

foundry_output_state = True

hit_target = False

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

BLENDER_IMAGE_FORMATS = (".bmp", ".sgi", ".rgb", ".bw", ".png", ".jpg", ".jpeg", ".jp2", ".j2c", ".tga", ".cin", ".dpx", ".exr", ".hdr", ".tiff", ".tif", ".webp")

#############
##FUNCTIONS##
#############


def is_linked(ob):
    return ob.data.users > 1

def get_project_path(project_name=None):
    if project_name is None:
        project = get_project(bpy.context.scene.nwo.scene_project)
    else:
        project = get_project(project_name)
    if not project:
        return ""
    return project.project_path


def get_tool_path():
    project = get_project(bpy.context.scene.nwo.scene_project)
    if not project:
        return ""
    return str(Path(project.project_path, get_tool_type()))

def get_tags_path():
    project = get_project(bpy.context.scene.nwo.scene_project)
    if not project:
        return ""
    return project.tags_directory

def get_data_path():
    project = get_project(bpy.context.scene.nwo.scene_project)
    if not project:
        return ""
    return project.data_directory


def get_tool_type():
    return bpy.context.preferences.addons[__package__].preferences.tool_type

def get_perm(
    ob,
):  # get the permutation of an object, return default if the perm is empty
    return true_permutation(ob.nwo)


def is_windows():
    return platform.system() == "Windows"

def is_corinth(context=None):
    if context is None:
        context = bpy.context
    project = get_project(context.scene.nwo.scene_project)
    return project and project.corinth

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


def get_asset_info(filepath=""):
    if not filepath:
        filepath = bpy.context.scene.nwo.sidecar_path
    asset_path = os.path.dirname(filepath).lower()
    asset = os_sep_partition(asset_path, True)

    return asset_path, asset

def get_asset_path():
    """Returns the path to the asset folder."""
    return str(Path(relative_path(bpy.context.scene.nwo.sidecar_path)).parent)

def relative_path(path: str | Path):
    """Gets the tag/data relative path of the given filepath"""
    path = Path(path)
    tags_path = Path(get_tags_path())
    data_path = Path(get_data_path())
    if path.is_relative_to(tags_path):
        return str(path.relative_to(tags_path))
    elif path.is_relative_to(data_path):
        return str(path.relative_to(data_path))
    
    return str(path)


def get_asset_path_full(tags=False):
    """Returns the full system path to the asset folder. For tags, add a True arg to the function call"""
    asset_path = bpy.context.scene.nwo.sidecar_path.rpartition(os.sep)[0].lower()
    if tags:
        return str(Path(get_tags_path(), asset_path))
    else:
        return str(Path(get_data_path(), asset_path))


# -------------------------------------------------------------------------------------------------------------------


def vector_str(velocity):
    x = velocity.x
    y = velocity.y
    z = velocity.z
    return f"1 {jstr(x)} {jstr(y)} {jstr(z)}"

def color_3p_str(color):
    red = linear_to_srgb(color.r)
    green = linear_to_srgb(color.g)
    blue = linear_to_srgb(color.b)
    return f"{jstr(red)} {jstr(green)} {jstr(blue)}"


def color_4p_str(color):
    red = color.r * 255
    green = color.g * 255
    blue = color.b * 255
    return f"1 {jstr(red)} {jstr(green)} {jstr(blue)}"

def color_rgba_str(color):
    red = linear_to_srgb(color[0])
    green = linear_to_srgb(color[1])
    blue = linear_to_srgb(color[2])
    alpha = linear_to_srgb(color[3])
    return f"{jstr(red)} {jstr(green)} {jstr(blue)} {jstr(alpha)}"

def color_argb_str(color):
    red = linear_to_srgb(color[0])
    green = linear_to_srgb(color[1])
    blue = linear_to_srgb(color[2])
    alpha = linear_to_srgb(color[3])
    return f"{jstr(alpha)} {jstr(red)} {jstr(green)} {jstr(blue)}"

def linear_to_srgb(linear):
    if linear <= 0.0031308:
        return 12.92 * linear
    else:
        return 1.055 * (linear ** (1/2.4)) - 0.055

def bool_str(bool_var):
    """Returns a boolean as a string. 1 if true, 0 if false"""
    if bool_var:
        return "1"
    else:
        return "0"


def radius_str(ob, pill=False, scale=1):
    """Returns the radius of a sphere (or a pill if second arg is True) as a string"""
    if pill:
        diameter = max(ob.dimensions.x, ob.dimensions.y)
    else:
        diameter = max(ob.dimensions)

    radius = diameter / 2.0

    return jstr(radius * scale)


def jstr(number):
    """Takes a number, rounds it to six decimal places and returns it as a string"""
    
    return format(round(number, 6), 'f')

def true_region(halo):
    if halo.region_name_locked:
        return halo.region_name_locked.lower()
    else:
        return halo.region_name.lower()

def true_permutation(halo):
    if halo.permutation_name_locked:
        return halo.permutation_name_locked.lower()
    else:
        return halo.permutation_name.lower()

def clean_tag_path(path, file_ext=None):
    """Cleans a path and attempts to make it appropriate for reading by Tool. Can accept a file extension (without a period) to force the existing one if it exists to be replaced"""
    path = path.strip('. "\'')
    if not path:
        return ""
    path = Path(path)
    if file_ext and not file_ext.startswith('.'):
        file_ext = '.' + file_ext
    # If a file ext is provided, replace the existing one / add it
    if file_ext is not None:
        path = path.with_suffix(file_ext)
    # attempt to make path tag relative
    path = relative_path(path)
    return path

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
            elif "Failed to find any animated nodes" and "idle" in line:
                # Skip because we often want the idle to not have animation e.g. for vehicles
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
        return 'ASSERTION FAILED' in line

    return False

def set_project_in_registry():
    """Sets the current project in the users registry"""
    key_path = r"SOFTWARE\Halo\Projects"
    name = bpy.context.scene.nwo.scene_project
    if not name:
        return
    # Get project name
    project = get_project(name)
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
    return context.scene.nwo.sidecar_path != "" and Path(get_data_path(), context.scene.nwo.sidecar_path).exists()


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

def export_objects(context):
    return {ob for ob in context.view_layer.objects if ob.nwo.exportable}

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


def closest_bsp_object(context, ob, valid_targets=[]):
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

    if not valid_targets:
        valid_targets = {ob for ob in export_objects(context) if ob.type in VALID_MESHES}

    for target_ob in valid_targets:
        if (
            ob != target_ob
            and target_ob.data.nwo.mesh_type == "_connected_geometry_mesh_type_structure"
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
    
    return 0

def layer_faces(bm, face_layer):
    """Returns the faces in a bmesh that have an face int custom_layer with a value greater than 0"""
    if face_layer:
        return [face for face in bm.faces if face[face_layer]]
    
def layer_face_indexes(bm, face_layer):
    """Returns the face indexes in a bmesh that have an face int custom_layer with a value greater than 0"""
    if face_layer:
        return {face.index for face in bm.faces if face[face_layer]}


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

def update_progress(job_title, progress):
    if progress <= 1:
        length = 20
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
    
def job_for_spinner(message):
    message += "     \r\n"
    sys.stdout.write(message)
    sys.stdout.flush()

def poll_ui(selected_types) -> bool:
    scene_nwo = bpy.context.scene.nwo
    asset_type = scene_nwo.asset_type

    return asset_type == 'resource' or asset_type in selected_types


def is_halo_object(ob) -> bool:
    return (
        ob
        and ob.type not in ("LATTICE", "LIGHT_PROBE", "SPEAKER", "CAMERA")
        and not (ob.type == "EMPTY" and ob.empty_display_type == "IMAGE")
        and poll_ui(
            (
                "model",
                "scenario",
                "sky",
                "decorator_set",
                "particle_model",
                "prefab",
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
        "_connected_geometry_mesh_type_object_instance",
        "_connected_geometry_mesh_type_water_surface",
    )
    nwo = ob.nwo
    return (
        ob
        and nwo.export_this
        and is_mesh(ob)
        and nwo.mesh_type in valid_mesh_types
    )


def has_face_props(ob) -> bool:
    valid_mesh_types = [
        "_connected_geometry_mesh_type_default",
        "_connected_geometry_mesh_type_structure",
    ]
    if poll_ui('model'):
        valid_mesh_types.append('_connected_geometry_mesh_type_collision')
    if is_corinth() and ob.nwo.mesh_type == '_connected_geometry_mesh_type_structure' and poll_ui('scenario') and not ob.nwo.proxy_instance:
        return False
    return (
        ob
        and ob.nwo.export_this
        and ob.type == 'MESH'
        and ob.nwo.mesh_type in valid_mesh_types
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
    ek = Path(get_project_path())
    scene_project = bpy.context.scene.nwo.scene_project
    if not ek.exists():
        return f"{scene_project} Editing Kit path invalid"
    elif not Path(ek, get_tool_type()).with_suffix('.exe').exists():
        return f"Tool not found, please check that you have tool.exe within your {scene_project} directory"
    elif not Path(ek, "data").exists():
        return f"Editing Kit data folder not found. Please ensure your {scene_project} directory has a 'data' folder"
    elif not Path(ek, "bin", "ManagedBlam.dll").exists():
        return f"ManagedBlam not found in your {scene_project} bin folder, please ensure this exists"
    # elif not managed_blam.mb_operational:
    #     return 'Failed to load Managedblam.dll. Please check that your Halo Editing Kit is installed correctly'
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
    for collection in ob.users_collection: collection.objects.unlink(ob)

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
    return bpy.context.preferences.addons[__package__].preferences

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
    while any(c in string for c in chars):
        for c in chars:
            string = string.replace(c, "")

    return string

def write_projects_list(project_list):
    appdata = os.getenv('APPDATA')
    foundry_folder = Path(appdata, "Foundry")

    if not foundry_folder.exists():
        foundry_folder.mkdir(exist_ok=True)
    
    if not foundry_folder.exists():
        return print('Failed to write projects list. Foundry will not work correctly')

    projects = Path(foundry_folder, "projects.json")
    with open(projects, 'w') as file:
        json.dump(project_list, file, indent=4)

def read_projects_list() -> list:
    projects_list = []
    appdata = os.getenv('APPDATA')
    foundry_folder = os.path.join(appdata, "Foundry")

    if not os.path.exists(foundry_folder):
        return print("No Foundry Folder")

    projects = os.path.join(foundry_folder, "projects.json")
    if not os.path.exists(projects):
        return print("No Foundry json")
    
    with open(projects, 'r') as file:
        projects_list = json.load(file)

    return projects_list

class ProjectXML():
    def __init__(self):
        self.name = ""
        self.display_name = ""
        self.remote_database_name = ""
        self.project_xml = ""
        self.image_path = ""
        self.default_material = ""
        self.default_water = ""

    def parse(self, project_root):
        has_changes = False
        self.project_xml = Path(project_root, "project.xml")
        if not self.project_xml.exists():
            return print(f"{project_root} is not a path to a valid Halo project. Expected project root directory to contain project.xml")
        tree = ET.parse(self.project_xml)
        root = tree.getroot()
        if self.name and self.name != root.get('name', 0):
            root.set("name", self.name)
            has_changes = True
        else:
            self.name = root.get('name', 0)
            if not self.name:
                return print(f"Failed to parse XML: {self.project_xml}. Could not return Name")
        if self.display_name and self.display_name != root.get('displayName', 0):
            root.set("displayName", self.display_name)
            has_changes = True
        else:
            self.display_name = root.get('displayName', 0)
            if not self.display_name:
                return print(f"Failed to parse XML: {self.project_xml}. Could not return displayName")
        self.remote_database_name = root.find('./tagDatastore').get('remoteDatabaseName', 0)
        if not self.remote_database_name:
            return print(f"Failed to parse XML: {self.project_xml}. Could not return remoteDatabaseName")
        # It's fine if these fail, they are only used to render icons
        self.remote_server_name = root.find('./tagDatastore').get('remoteServerName', 0)
        image = root.find('./imagePath', 0)
        if image is not None:
            self.image_path = image.text
            
        material = root.find('./defaultMaterial', 0)
        if material is not None:
            if self.default_material and self.default_material != material.text:
                material.text = self.default_material
            else:
                self.default_material = material.text
        else:
            material = ET.SubElement(root, 'defaultMaterial')
            match self.remote_server_name:
                case 'bngtoolsql':
                    material.text = r"shaders\invalid.shader"
                case 'metawins':
                    material.text = r"shaders\invalid.material"
                case 'episql.343i.selfhost.corp.microsoft.com':
                    material.text = r"shaders\invalid.material"
            self.default_material = material.text
            has_changes = True
        
        water = root.find('./defaultWater', 0)
        if water is not None:
            if self.default_water and self.default_water != water.text:
                water.text = self.default_water
            else:
                self.default_water = water.text
        else:
            water = ET.SubElement(root, 'defaultWater')
            match self.remote_server_name:
                case 'bngtoolsql':
                    water.text = r"levels\solo\m50\shaders\water\m50_atrium_fountain_water.shader_water"
                case 'metawins':
                    water.text = r"levels\multi\z11_valhalla\materials\valhalla_water_river.material"
                case 'episql.343i.selfhost.corp.microsoft.com':
                    water.text = r"levels\sway\ca_sanctuary\materials\rocks\ca_sanctuary_rockflat_water.material"
            self.default_water = water.text
            has_changes = True
        
        if has_changes:
            tree.write(self.project_xml, encoding='utf-8', xml_declaration=True)

def setup_projects_list(skip_registry_check=False, report=None):
    projects_list = read_projects_list()
    new_projects_list = []
    prefs = get_prefs()
    prefs.projects.clear()
    display_names = []
    if projects_list is not None:
        for i in projects_list:
            xml = ProjectXML()
            xml.parse(i)
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
                p.tags_directory = str(Path(i, "tags"))
                p.data_directory = str(Path(i, "data"))
                p.project_xml = str(xml.project_xml)
                p.project_name = xml.name
                p.name = xml.display_name
                p.remote_server_name = xml.remote_server_name
                p.image_path = xml.image_path
                p.corinth = xml.remote_database_name == "tags"
                p.default_material = xml.default_material
                p.default_water = xml.default_water
    
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
            ob.nwo.region_name = region_names[0]
        elif ob_region not in region_names:
            new_region = regions_table.add()
            new_region.name = ob_region
            region_names.add(ob_region)
            ob.nwo.region_name = ob_region

        ob_permutation = true_permutation(ob.nwo)
        if not ob_permutation:
            ob.nwo.permutation_name = permutation_names[0]
        elif ob_permutation not in permutation_names:
            new_permutation = permutations_table.add()
            new_permutation.name = ob_permutation
            permutation_names.add(ob_permutation)
            ob.nwo.permutation_name = ob_permutation

# def update_objects_from_tables(context, table_str, ob_prop_str):
#     entry_names = [e.name for e in getattr(context.scene.nwo, table_str)]
#     default_entry = entry_names[0]
#     scene_obs = context.scene.objects
#     for ob in scene_obs:
#         if getattr(ob.nwo, ob_prop_str) not in entry_names:
#             setattr(ob.nwo, ob_prop_str, default_entry)

def addon_root():
    return os.path.dirname(os.path.realpath(__file__))

def extract_from_resources(relative_file_path):
    p = PureWindowsPath(relative_file_path)
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
        case '_connected_geometry_mesh_type_object_instance':
            return 'Instanced Object', get_icon_id('instance')
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
            if poll_ui(('scenario', 'prefab')):
                return 'Instanced Geometry', get_icon_id('instance')
            elif poll_ui(('DECORATOR')):
                return 'Decorator', get_icon_id('decorator')
            else:
                return 'Render', get_icon_id('model')

def library_instanced_collection(ob):
    return ob.instance_type == 'COLLECTION' and ob.instance_collection and ob.instance_collection.library

def get_marker_display(mesh_type, ob):
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
        case '_connected_geometry_marker_type_target':
            return 'Target', get_icon_id('target')
        case '_connected_geometry_marker_type_game_instance':
            match dot_partition(ob.nwo.marker_game_instance_tag_name).lower():
                case "crate":
                    name = "Crate Tag"
                    icon = "crate"
                case "scenery":
                    name = "Scenery Tag"
                    icon = "scenery"
                case "effect_scenery":
                    name = "Effect Scenery Tag"
                    icon = "effect_scenery"
                case "device_control":
                    name = "Device Control Tag"
                    icon = "device_control"
                case "device_machine":
                    name = "Device Machine Tag"
                    icon = "device_machine"
                case "device_terminal":
                    name = "Device Terminal Tag"
                    icon = "device_terminal"
                case "device_dispenser":
                    name = "Device Dispenser Tag"
                    icon = "device_dispenser"
                case "biped":
                    name = "Biped Tag"
                    icon = "biped"
                case "creature":
                    name = "Creature Tag"
                    icon = "creature"
                case "giant":
                    name = "Giant Tag"
                    icon = "giant"
                case "vehicle":
                    name = "Vehicle Tag"
                    icon = "vehicle"
                case "weapon":
                    name = "Weapon Tag"
                    icon = "weapon"
                case "equipment":
                    name = "Equipment Tag"
                    icon = "equipment"
                case "prefab":
                    name = "Prefab Tag"
                    icon = "prefab"
                case "light":
                    name = "Light Tag"
                    icon = "light_cone"
                case "cheap_light":
                    name = "Cheap Light Tag"
                    icon = "light_cone"
                case "leaf":
                    name = "Leaf Tag"
                    icon = "decorator"
                case "decorator_set":
                    name = "Decorator Set Tag"
                    icon = "decorator"
                case _:
                    name = "Game Object"
                    icon = "game_object"
            return name, get_icon_id(icon)
        case '_connected_geometry_marker_type_airprobe':
            return 'Airprobe', get_icon_id('airprobe')
        case '_connected_geometry_marker_type_envfx':
            return 'Environment Effect', get_icon_id('environment_effect')
        case '_connected_geometry_marker_type_lightCone':
            return 'Light Cone', get_icon_id('light_cone')
        case _:
            if poll_ui(('scenario', 'prefab')):
                return 'Structure Marker', get_icon_id('marker')
            else:
                return 'Model Marker', get_icon_id('marker')
            
def is_mesh(ob):
    return ob.type in VALID_MESHES

def is_marker(ob):
    return ob.type == 'EMPTY'  and not ob.children and not library_instanced_collection(ob) and ob.empty_display_type != "IMAGE"

def is_marker_quick(ob):
    return ob.type == 'EMPTY'  and not library_instanced_collection(ob) and ob.empty_display_type != "IMAGE"

def is_frame(ob):
    return (ob.type == 'EMPTY' and ob.children) or ob.type == 'ARMATURE'

def is_light(ob):
    return ob.type == 'LIGHT'

def is_camera(ob):
    return ob.type == 'CAMERA'

def get_object_type(ob, get_ui_name=False):
    if is_mesh(ob):
        return 'Mesh' if get_ui_name else '_connected_geometry_object_type_mesh'
    elif is_light(ob):
        return 'Light' if get_ui_name else '_connected_geometry_object_type_light'
    elif is_camera(ob):
        return 'Camera' if get_ui_name else '_connected_geometry_object_type_animation_camera'
    elif is_frame(ob):
        return 'Frame' if get_ui_name else '_connected_geometry_object_type_frame'
    elif is_marker_quick(ob):
        return 'Marker' if get_ui_name else '_connected_geometry_object_type_marker'
    else:
        return 'None' if get_ui_name else '_connected_geometry_object_type_none'
    
def type_valid(m_type, asset_type=None, game_version=None):
    if asset_type is None:
        asset_type = bpy.context.scene.nwo.asset_type
    if game_version is None:
        game_version = 'corinth' if is_corinth() else 'reach'
    return asset_type in object_asset_validation.get(m_type, []) and game_version in object_game_validation.get(m_type, [])

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

def fbx_addon_installed():
    script_dirs = bpy.utils.script_paths()
    for dir in script_dirs:
        if Path(dir, 'addons', 'io_scene_fbx').exists() or Path(dir, 'addons_core', 'io_scene_fbx').exists():
            return True
        
    return False
    
def has_collision_type(ob: bpy.types.Object) -> bool:
    nwo = ob.nwo
    mesh_type = nwo.mesh_type
    if not poll_ui(('scenario', 'prefab')) and mesh_type != '_connected_geometry_mesh_type_collision':
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
    mesh_type = ob.nwo.mesh_type
    if not poll_ui(('scenario', 'prefab')):
        return False
    if mesh_type == '_connected_geometry_mesh_type_default':
        return True
    if is_corinth() and mesh_type == '_connected_geometry_mesh_type_structure' and ob.nwo.proxy_instance:
        return True
    return False
    
def set_origin_to_floor(ob):
    bounding_box_corners = [Vector(corner) for corner in ob.bound_box]
    min_z = min([corner.z for corner in bounding_box_corners])
    translation = Vector((0, 0, -min_z))
    for vert in ob.data.vertices:
        vert.co += translation
        
    ob.matrix_world = ob.matrix_world @ Matrix.Translation(-translation)
    
def set_origin_to_centre(ob):
    with bpy.context.temp_override(object=ob, selected_editable_objects=[ob]):
        bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='MEDIAN')
        
    centroid = Vector((0, 0, 0))
    for vert in ob.data.vertices:
        centroid += vert.co
    centroid /= len(ob.data.vertices)
    
    translation = -centroid
    
    for vert in ob.data.vertices:
        vert.co += translation
        
    ob.matrix_world = ob.matrix_world @ Matrix.Translation(-translation)

def get_project(project_name):
    projects = get_prefs().projects
    if projects:
        for p in projects:
            if p.name == project_name:
                return p
        
        return projects[0]
    
def material_read_only(path):
    """Returns true if a material is read only aka in the project's protected list"""
    # Return false immediately if user has disabled material protection
    if not get_prefs().protect_materials: return False
    # Ensure path is correctly sliced
    path = path.strip(" .\"'")
    if not path: return False
    path = str(Path(relative_path(path)).with_suffix(""))
    project = get_project(bpy.context.scene.nwo.scene_project)
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
    mesh_ob_dict = {mesh: [ob for ob in bpy.data.objects if ob.data == mesh] for mesh in meshes}
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
        with bpy.context.temp_override(active_object=basis_ob, selected_editable_objects=[ob for ob in mesh_ob_dict[me]]):
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True, isolate_users=True)
        
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
        
        
def calc_light_intensity(light_data, factor=1):
    if light_data.type == "SUN":
        return light_data.energy
    
    intensity = factor * ((light_data.energy / 0.03048**-2) / (100 if is_corinth() else 300))
    
    return intensity

def calc_emissive_intensity(emissive_power, scale_factor=1):
    intensity = (emissive_power / 0.03048**-2) / (300 if is_corinth() else 3)
    return intensity * (scale_factor ** 2)

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

def find_mapping_node(node: bpy.types.Node, start_node: bpy.types.Node) -> bpy.types.Node | None:
    links = node.inputs['Vector'].links
    if not links:
        return None, None
    next_node = links[0].from_node
    if next_node.type == 'MAPPING':
        return next_node, False
    elif is_halo_mapping_node(next_node):
        return next_node, True
    else:
        global hit_target
        tile_node, _ = find_node_in_chain('GROUP', start_node, first_target=node.name, group_is_tiling_node=True)
        hit_target = False
        if tile_node:
            return tile_node, True
        else:
            tile_node, _ = find_node_in_chain('MAPPING', start_node, first_target=node.name)
            hit_target = False
            if tile_node:
                return tile_node, False
    
    return None, None

def find_linked_node(start_node: bpy.types.Node, input_name: str, node_type: str) -> bpy.types.Node:
    """Using the given node as a base, finds the first node from the given input that matches the given node type"""
    for i in start_node.inputs:
        if input_name == i.name.lower():
            if i.links:
                input = i
                break
            else:
                return
    else:
        return
    
    link = input.links[0]
    node, _ = find_node_in_chain(node_type, link.from_node, link.from_socket.name.lower())
    if node:
        return node
    
def find_node_in_chain(node_type: str, node: bpy.types.Node, group_output_input='', group_node=None, last_input_name='', first_target=None, group_is_tiling_node=False) -> tuple[bpy.types.Node, bpy.types.Node]:
    global hit_target
    if node.type == node_type and (not group_is_tiling_node or is_halo_mapping_node(node)) and (first_target is None or hit_target):
        return node, group_node
    
    if node.name == first_target:
        hit_target = True
    
    if node.type == 'GROUP':
        group_node = node
        group_nodes = node.node_tree.nodes
        for n in group_nodes:
            if n.type == 'GROUP_OUTPUT':
                for input in n.inputs:
                    if input.name.lower() == group_output_input:
                        links = input.links
                        for l in links:
                            new_node = l.from_node
                            valid_node, group_node = find_node_in_chain(node_type, new_node, group_output_input, group_node, input.name, first_target, group_is_tiling_node)
                            if valid_node:
                                return valid_node, group_node

                break
            
    elif node.type == 'GROUP_INPUT':
        for input in node.inputs:
            if input.name.lower() == last_input_name:
                group_test_input = input
                for link in group_test_input.links:
                    next_node = link.from_node
                    valid_node, group_node = find_node_in_chain(node_type, next_node, link.from_socket.name, None, group_test_input.name, first_target, group_is_tiling_node)
                    if valid_node:
                        return valid_node, group_node
            
    for input in node.inputs:
        for link in input.links:
            next_node = link.from_node
            if next_node.type == 'GROUP':
                valid_node, group_node = find_node_in_chain(node_type, next_node, link.from_socket.name, node, input.name, first_target, group_is_tiling_node)
            else:
                valid_node, group_node = find_node_in_chain(node_type, next_node, group_output_input, group_node, input.name, first_target, group_is_tiling_node)
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
            
def get_rig(context=None, return_mutliple=False) -> bpy.types.Object | None | list[bpy.types.Object]:
    """Gets the main armature from the scene (or tries to)"""
    if context is None:
        context = bpy.context
    scene_nwo = context.scene.nwo
    ob = context.object
    if scene_nwo.main_armature and context.scene.objects.get(scene_nwo.main_armature.name):
        return scene_nwo.main_armature
    obs = export_objects(context)
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
    material_name = dot_partition(name)
    if not strip_legacy_halo_names:
        return material_name
    # match lightmap prefixe/suffixes
    parts = material_name.split()
    if len(parts) > 1:
        if parts[0].startswith(legacy_lightmap_prefixes):
            material_name = ' '.join(parts[1:])
        elif parts[-1].startswith(legacy_lightmap_prefixes):
            material_name = ' '.join(parts[:-1])
            
    # ignore material suffixes
    return material_name.rstrip("%#?!@*$^-&=.;)><|~({]}[' ") # excluding 0 here as it can interfere with normal naming convention


def get_animated_objects(context) -> list[bpy.types.Object]:
    scene_nwo = context.scene.nwo
    animated_objects = []
    if context.object and context.object.animation_data:
        animated_objects.append(context.object)
    if scene_nwo.main_armature and scene_nwo.main_armature.animation_data:
        animated_objects.append(scene_nwo.main_armature)
    if scene_nwo.support_armature_a and scene_nwo.support_armature_a.animation_data:
        animated_objects.append(scene_nwo.support_armature_a)
    if scene_nwo.support_armature_b and scene_nwo.support_armature_b.animation_data:
        animated_objects.append(scene_nwo.support_armature_b)
    if scene_nwo.support_armature_c and scene_nwo.support_armature_c.animation_data:
        animated_objects.append(scene_nwo.support_armature_c)
        
    control_objects = get_object_controls(context)
    if control_objects:
        animated_objects.extend(control_objects)
        
    return animated_objects

def reset_to_basis(context, keep_animation=False) -> list[bpy.types.Object]:
    animated_objects = get_animated_objects(context)
    for ob in animated_objects:
        if not keep_animation:
            ob.animation_data.action = None
        # ob.matrix_basis = Matrix()
        if ob.type == 'ARMATURE':
            for bone in ob.pose.bones:
                bone.matrix_basis = Matrix()
                      
    return animated_objects

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
                            
def rotate_follow_path_axis(con_axis: str, old_forward: str, new_forward: str):
    if old_forward == new_forward:
        return
    axis = con_axis[-1]
    if axis == 'Z':
        return con_axis
    
    forward_back = con_axis[:-1]
    
    if forward_back == 'FORWARD_':
        forward_back_inverse = 'TRACK_NEGATIVE_'
    else:
        forward_back_inverse = 'FORWARD_'
        
    if axis in old_forward.upper() and axis in new_forward.upper():
        if con_axis.startswith('TRACK_NEGATIVE'):
            return con_axis.replace('TRACK_NEGATIVE', 'FORWARD')
        else:
            return con_axis.replace('FORWARD', 'TRACK_NEGATIVE')
    else:
        if '-' in old_forward and '-' in new_forward:
            if axis == 'X':
                return forward_back + 'Y'
            else:
                return forward_back + 'X'
        else:
            if axis == 'X':
                return forward_back_inverse + 'Y'
            else:
                return forward_back_inverse + 'X'
            
def fix_mirror_angles(mod, old_forward, new_forward):
    if old_forward == new_forward:
        return
    old_axis = old_forward[0]
    new_axis = new_forward[0]
    old_axis_negative = len(old_forward) > 1
    new_axis_negative = len(new_forward) > 1
    
    axis_x, axis_y, _ = mod.use_axis
    bisect_x, bisect_y, _ = mod.use_bisect_axis
    flip_x, flip_y, _ = mod.use_bisect_flip_axis
    
    if old_axis != new_axis:
        if bisect_y and flip_x:
            mod.use_bisect_axis[1] = False
            mod.use_bisect_flip_axis[0] = False
        else:
            if axis_x != axis_y:
                mod.use_axis[0] = (not axis_x)
                mod.use_axis[1] = (not axis_y)
            if bisect_x != bisect_y:
                mod.use_bisect_axis[0] = (not bisect_x)
                mod.use_bisect_axis[1] = (not bisect_y)
            mod.use_bisect_flip_axis[0] = (not flip_x)
            mod.use_bisect_flip_axis[1] = (not flip_y)
                    
    if old_axis_negative != new_axis_negative:
        mod.use_bisect_flip_axis[0] = (not mod.use_bisect_flip_axis[0])
        mod.use_bisect_flip_axis[1] = (not mod.use_bisect_flip_axis[1])
        
                            
class BoneChild():
    def __init__(self, ob: bpy.types.Object, parent: bpy.types.Object, parent_bone: str):
        self.ob = ob
        self.parent = parent
        self.parent_bone = parent_bone
        
class ArmatureWithParent():
    def __init__(self, ob: bpy.types.Object, parent: bpy.types.Object, parent_type: str, parent_bone: str):
        self.ob = ob
        self.parent = parent
        self.parent_type = parent_type
        self.parent_bone = parent_bone
        
class TransformManager():
    def __enter__(self):
        bpy.context.scene.nwo.transforming = True
        return self
        
    def __exit__(self, exc_type, exc_value, traceback):
        bpy.context.scene.nwo.transforming = False
        
def rotation_and_pivot(rotation):
    axis_z = Vector((0, 0, 1))
    pivot = Vector((0.0, 0.0, 0.0))
    rotation_matrix = Matrix.Rotation(rotation, 4, axis_z)
    pivot_matrix = (Matrix.Translation(pivot) @ rotation_matrix @ Matrix.Translation(-pivot))
    
    return rotation_matrix, pivot_matrix

def halo_transforms(ob, scale=None, rotation=None, marker=False):
    '''
    Returns an object's matrix_world transformed for Halo. Used when writing object transforms directly to tags
    '''
    if scale is None:
        if bpy.context.scene.nwo.scale == 'max':
            scale = 0.03048
        else:
            scale = 1
            
    scale *= 0.328084
    
    if rotation is None:
        rotation = blender_halo_rotation_diff(bpy.context.scene.nwo.forward_direction)
        
    rotation_matrix, pivot_matrix = rotation_and_pivot(rotation)
    
    loc, rot, sca = ob.matrix_world.decompose()
    
    loc *= scale
    loc = pivot_matrix @ loc
    
    if ob.rotation_mode == 'QUATERNION':
        rot = ob.rotation_quaternion.copy()
    else:
        rot = ob.rotation_euler.copy()
        
    rot.rotate(rotation_matrix)
    
    if marker and not bpy.context.scene.nwo.maintain_marker_axis:
        if isinstance(rot, Quaternion):
            rot = rot.to_euler()
        
        rot: Euler
        rot.rotate_axis('Z', rotation)
    
    new_matrix = Matrix.LocRotScale(loc, rot, sca)
    
    return new_matrix

def halo_transform_matrix(matrix: Matrix):
    scale = 1
    if bpy.context.scene.nwo.scale == 'max':
        scale = 0.03048
            
    scale *= 0.328084
    
    rotation = blender_halo_rotation_diff(bpy.context.scene.nwo.forward_direction)
    
    rotation_matrix, pivot_matrix = rotation_and_pivot(rotation)
    
    loc, rot, sca = matrix.decompose()
    
    loc *= scale
    loc = pivot_matrix @ loc
    
    rot.rotate(rotation_matrix)
    
    return Matrix.LocRotScale(loc, rot, sca)

def transform_scene(context: bpy.types.Context, scale_factor, rotation, old_forward, new_forward, keep_marker_axis=None, objects=None, actions=None, apply_rotation=False, exclude_scale_models=False):
    """Transform blender objects by the given scale factor and rotation. Optionally this can be scoped to a set of objects and animations rather than all"""
    with TransformManager():
        # armatures = [ob for ob in bpy.data.objects if ob.type == 'ARMATURE']
        if objects is None:
            objects = bpy.data.objects
            
        if exclude_scale_models:
            objects = [ob for ob in objects if not ob.nwo.scale_model]
            
        curves = {ob.data for ob in objects if ob.type =='CURVE'}
        metaballs = {ob.data for ob in objects if ob.type =='METABALL'}
        meshes = {ob.data for ob in objects if ob.type =='MESH'}
        cameras = {ob.data for ob in objects if ob.type =='CAMERA'}
        lights = {ob.data for ob in objects if ob.type =='LIGHT'}
            
        if actions is None:
            actions = bpy.data.actions
            
        if keep_marker_axis is None:
            keep_marker_axis = context.scene.nwo.maintain_marker_axis

        armatures = [ob for ob in objects if ob.type == 'ARMATURE']
        parented_armatures = [ob for ob in armatures if ob.parent]
        armature_parents = [ArmatureWithParent(ob, ob.parent, ob.parent_type, ob.parent_bone) for ob in parented_armatures]
        scene_coll = context.scene.collection.objects
        axis_z = Vector((0, 0, 1))
        pivot = Vector((0.0, 0.0, 0.0))
        rotation_matrix = Matrix.Rotation(rotation, 4, axis_z)
        pivot_matrix = (Matrix.Translation(pivot) @ rotation_matrix @ Matrix.Translation(-pivot))
        scale_matrix = Matrix.Scale(scale_factor, 4)
        transform_matrix = rotation_matrix @ scale_matrix
        frames = [ob for ob in bpy.data.objects if is_frame(ob)]
        bone_children = []
                
        if parented_armatures:
            with context.temp_override(object=parented_armatures[0], selected_editable_objects=parented_armatures):
                bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
                
        for ob in objects:
            old_scale = ob.scale.copy()
            # no_data_transform = ob.type in ('EMPTY', 'CAMERA', 'LIGHT', 'LIGHT_PROBE', 'SPEAKER')
            bone_parented = False
            if ob.parent and ob.parent.type == 'ARMATURE' and ob.parent_type == 'BONE' and ob.parent_bone:
                par_bone = ob.parent.data.bones.get(ob.parent_bone)
                if par_bone and not par_bone.use_relative_parent:
                    bone_parented = True
                
            object_parented = (ob.parent and ob.parent.type != 'ARMATURE' and ob.parent_type == 'OBJECT')
            loc, rot, sca = ob.matrix_basis.decompose()
            if ob.rotation_mode == 'QUATERNION':
                rot = ob.rotation_quaternion
            else:
                rot = ob.rotation_euler
                
            loc *= scale_factor
                
            if rotation and not bone_parented:
                loc = pivot_matrix @ loc
            
            is_a_frame = ob in frames
            
            if not (ob.type == 'ARMATURE' or bone_parented):
                rot.rotate(rotation_matrix)
            elif bone_parented and ob.matrix_parent_inverse != Matrix.Identity(4):
                bone_children.append(BoneChild(ob, ob.parent, ob.parent_bone))
                
            if ob.type == 'EMPTY':
                ob.empty_display_size *= scale_factor
                
            ob.matrix_basis = Matrix.LocRotScale(loc, rot, sca)
            if object_parented:
                local_loc, local_rot, local_sca = ob.matrix_local.decompose()
                local_loc *= scale_factor
                ob.matrix_local = Matrix.LocRotScale(local_loc, local_rot, local_sca)
            
            if keep_marker_axis and not is_a_frame and is_marker(ob) and nwo_asset_type() in ('model', 'sky', 'scenario', 'prefab'):
                ob.rotation_euler.rotate_axis('Z', -rotation)
            
            if ob.type == 'LATTICE' or ob.type == 'LIGHT':
                ob.scale *= scale_factor
            else:
                ob.scale = old_scale
                

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
                        mod.project_limit *= scale_factor
                    case 'WAVE':
                        mod.offset *= scale_factor
                        mod.height *= scale_factor
                        mod.width *= scale_factor
                        mod.falloff_radius *= scale_factor
                        mod.narrowness *= scale_factor
                        mod.start_position_x *= scale_factor
                        mod.start_position_y *= scale_factor
                    case 'OCEAN':
                        mod.depth *= scale_factor
                        mod.wave_scale_min *= scale_factor
                        mod.wind_velocity *= scale_factor
                    case 'ARRAY':
                        mod.constant_offset_displace *= scale_factor
                        mod.merge_threshold *= scale_factor
                    case 'MIRROR':
                        mod.merge_threshold *= scale_factor
                        mod.bisect_threshold *= scale_factor
                        if not keep_marker_axis and mod.mirror_object and is_marker(mod.mirror_object):
                            fix_mirror_angles(mod, old_forward, new_forward)
                    case 'REMESH':
                        mod.voxel_size *= scale_factor
                        mod.adaptivity *= scale_factor
                    case 'SCREW':
                        mod.screw_offset *= scale_factor
                    case 'SOLIDIFY':
                        mod.thickness *= scale_factor
                    case 'WELD':
                        mod.merge_threshold *= scale_factor
                    case 'WIREFRAME':
                        mod.thickness *= scale_factor
                    case 'CAST':
                        mod.radius *= scale_factor
                    case 'HOOK':
                        mod.falloff_radius *= scale_factor
                    case 'WARP':
                        mod.falloff_radius *= scale_factor
                    case 'DATA_TRANSFER':
                        mod.islands_precision *= scale_factor
                        mod.max_distance *= scale_factor
                        mod.ray_radius *= scale_factor
                        
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
                    case 'FOLLOW_PATH':
                        if rotation:
                            con.forward_axis = rotate_follow_path_axis(con.forward_axis, old_forward, new_forward)
                    case 'CHILD_OF':
                        con.inverse_matrix = con.inverse_matrix @ rotation_matrix.inverted()
                        if scale_factor != 1:
                            con_loc, con_rot, con_sca = con.inverse_matrix.decompose()
                            con_loc *= scale_factor
                            con.inverse_matrix = Matrix.LocRotScale(con_loc, con_rot, con_sca)
                
        for curve in curves:
            if hasattr(curve, 'size'):
                curve.size *= scale_factor
            if hasattr(curve, 'use_radius'):
                curve.use_radius = False
                
            curve.transform(scale_matrix)
            curve.nwo.material_lighting_attenuation_falloff *= scale_factor
            curve.nwo.material_lighting_attenuation_cutoff *= scale_factor
            
        for metaball in metaballs:
            metaball.transform(scale_matrix)
            metaball.nwo.material_lighting_attenuation_falloff *= scale_factor
            metaball.nwo.material_lighting_attenuation_cutoff *= scale_factor
            
        # for lattice in lattices:
        #     lattice.transform(scale_matrix)
        
        for mesh in meshes:
            mesh.transform(scale_matrix)
            mesh.nwo.material_lighting_attenuation_falloff *= scale_factor
            mesh.nwo.material_lighting_attenuation_cutoff *= scale_factor
            for prop in mesh.nwo.face_props:
                prop.material_lighting_attenuation_cutoff *= scale_factor
                prop.material_lighting_attenuation_falloff *= scale_factor
            
        for camera in cameras:
            camera.display_size *= scale_factor
            
        for light in lights:
            if light.type != 'SUN':
                light.energy *= scale_factor ** 2
            light.nwo.light_far_attenuation_start *= scale_factor
            light.nwo.light_far_attenuation_end *= scale_factor
            light.nwo.light_near_attenuation_start *= scale_factor
            light.nwo.light_near_attenuation_end *= scale_factor
            light.nwo.light_fade_start_distance *= scale_factor
            light.nwo.light_fade_end_distance *= scale_factor
        
        arm_datas = set()
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
                original_collections = arm.users_collection
                unlink(arm)
                scene_coll.link(arm)
                should_be_unlinked = True
                
            set_active_object(arm)
            if data not in arm_datas:
                arm_datas.add(data)
                bpy.ops.object.editmode_toggle()
                
                uses_edit_mirror = bool(arm.data.use_mirror_x)
                if uses_edit_mirror:
                    arm.data.use_mirror_x = False
                
                edit_bones = data.edit_bones
                connected_bones = [b for b in edit_bones if b.use_connect]
                for edit_bone in connected_bones:
                    edit_bone.use_connect = False
                    
                for edit_bone in edit_bones:
                    edit_bone.transform(transform_matrix)
                    edit_bone_children = [child.ob for child in bone_children if child.parent == arm and child.parent_bone == edit_bone.name]
                    for ob in edit_bone_children:
                        correction_matrix = pivot_matrix @ ob.matrix_basis.copy()
                        ob.matrix_parent_inverse.identity()
                        ob.matrix_local = (arm.matrix_world @ Matrix.Translation(edit_bone.tail - edit_bone.head) @ edit_bone.matrix).inverted() @ correction_matrix
                    
                for edit_bone in connected_bones:
                    edit_bone.use_connect = True
            
                if uses_edit_mirror:
                    arm.data.use_mirror_x = True
                
            bpy.ops.object.posemode_toggle()
            
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
                        case 'FOLLOW_PATH':
                            if rotation:
                                con.forward_axis = rotate_follow_path_axis(con.forward_axis, old_forward, new_forward)
                        case 'CHILD_OF':
                            con.inverse_matrix = con.inverse_matrix @ rotation_matrix.inverted()
                            if scale_factor != 1:
                                con_loc, con_rot, con_sca = con.inverse_matrix.decompose()
                                con_loc *= scale_factor
                                con.inverse_matrix = Matrix.LocRotScale(con_loc, con_rot, con_sca)

            if uses_pose_mirror:
                arm.pose.use_mirror_x = True
                
            bpy.ops.object.posemode_toggle()
            
            for bone in data.bones:
                bone.bbone_x *= scale_factor
                bone.bbone_z *= scale_factor
            
            if should_be_hidden:
                arm.hide_set(True)
                
            if should_be_unlinked:
                unlink(arm)
                if original_collections:
                    for coll in original_collections:
                        coll.objects.link(arm)
        
        if armature_parents:
            for item in armature_parents:
                arm_ob = item.ob
                old_matrix = arm_ob.matrix_world.copy()
                arm_ob.parent = item.parent
                arm_ob.parent_type = item.parent_type
                arm_ob.parent_bone = item.parent_bone
                arm_ob.matrix_world = old_matrix
        
        for action in actions:
            fc_quaternions: list[bpy.types.FCurve] = []
            fc_locations: list[bpy.types.FCurve] = []
            for fcurve in action.fcurves:
                if fcurve.data_path == 'location':
                    fc_locations.append(fcurve)
                if fcurve.data_path.endswith('location'):
                    for mod in fcurve.modifiers:
                        if mod.type == 'NOISE':
                            mod.strength *= scale_factor
                    for keyframe_point in fcurve.keyframe_points:
                        keyframe_point.co_ui[1] *= scale_factor
                        
                elif fcurve.data_path.startswith('rotation_euler') and fcurve.array_index == 2:
                    for kfp in fcurve.keyframe_points:
                        kfp.co_ui[1] += rotation
                elif fcurve.data_path.startswith('rotation_quaternion'):
                    fc_quaternions.append(fcurve)
                    
            if fc_locations:
                assert(len(fc_locations) == 3)
                keyframes_x = []
                keyframes_y = []
                keyframes_z = []
                for fc in fc_locations:
                    if fc.array_index == 0:
                        keyframes_x.append(fc.keyframe_points)
                    elif fc.array_index == 1:
                        keyframes_y.append(fc.keyframe_points)
                    elif fc.array_index == 2:
                        keyframes_z.append(fc.keyframe_points)
                        
                for i in range(len(keyframes_x)):
                    for kfpx, kfpy, kfpz in zip(keyframes_x[i], keyframes_y[i], keyframes_z[i]):
                        v = Vector((kfpx.co[1], kfpy.co[1], kfpz.co[1]))
                        mat = Matrix.Translation(v)
                        loc = pivot_matrix @ mat
                        vloc = loc.to_translation()
                        kfpx.co_ui[1], kfpy.co_ui[1], kfpz.co_ui[1] = vloc[0], vloc[1], vloc[2]
                
            if fc_quaternions:
                assert(len(fc_quaternions) == 4)
                keyframes_w = []
                keyframes_x = []
                keyframes_y = []
                keyframes_z = []
                for fc in fc_quaternions:
                    if fc.array_index == 0:
                        keyframes_w.append(fc.keyframe_points)
                    elif fc.array_index == 1:
                        keyframes_x.append(fc.keyframe_points)
                    elif fc.array_index == 2:
                        keyframes_y.append(fc.keyframe_points)
                    elif fc.array_index == 3:
                        keyframes_z.append(fc.keyframe_points)
                        
                for i in range(len(keyframes_w)):
                    for kfpw, kfpx, kfpy, kfpz in zip(keyframes_w[i], keyframes_x[i], keyframes_y[i], keyframes_z[i]):
                        q = Quaternion((kfpw.co[1], kfpx.co[1], kfpy.co[1], kfpz.co[1]))
                        q.rotate(rotation_matrix)
                        kfpw.co_ui[1], kfpx.co_ui[1], kfpy.co_ui[1], kfpz.co_ui[1] = q[0], q[1], q[2], q[3]

            for fc in action.fcurves:
                fc.keyframe_points.handles_recalc()
                
            if apply_rotation:
                with context.temp_override(selected_editable_objects=objects, object=objects[0]):
                    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False, isolate_users=True)
            
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

def blender_rotation_diff(from_direction, to_direction):
    """Returns the rotation (radians) needed to go from the current blender forward to the selected forward"""
    rot = blender_halo_rotation_diff(to_direction)
    match from_direction:
        case "y":
            return rot - radians(-90)
        case "y-":
            return rot - radians(90)
        case "x-":
            return rot - radians(180)
        case "x":
            return rot - 0
            
    return 0

def rotation_diff_from_forward(from_direction, to_direction):
    from_radians = 0
    match from_direction:
        case "y-":
            from_radians = 0
        case "y":
            from_radians = radians(180)
        case "x-":
            from_radians = radians(90)
        case "x":
            from_radians = radians(-90)
        
    to_radians = 0
    match to_direction:
        case "y-":
            to_radians = 0
        case "y":
            to_radians = radians(180)
        case "x-":
            to_radians = radians(90)
        case "x":
            to_radians = radians(-90)
        
    return from_radians - to_radians

def mute_armature_mods():
    muted_arms = []
    for ob in bpy.data.objects:
        for mod in ob.modifiers:
            if mod.type == 'ARMATURE' and mod.use_vertex_groups:
                muted_arms.append(mod)
                mod.use_vertex_groups = False
                
    return muted_arms
                
def unmute_armature_mods(muted_arms):
    for mod in muted_arms:
        mod.use_vertex_groups = True
    
def rig_root_deform_bone(rig: bpy.types.Object, return_name=False) -> None | bpy.types.Bone| str| list:
    """Returns the root deform bone of this rig. If multiple bones are found, returns none"""
    root_bones = [b for b in rig.data.bones if b.use_deform and not b.parent]
    if len(root_bones) == 1:
        root = root_bones[0]
        if return_name:
            return root.name
        else:
            return root
    elif root_bones:
        return root_bones
    
def in_exclude_collection(ob):
    user_collections = ob.users_collection
    if any([coll.nwo.type == 'exclude' for coll in user_collections]):
        return True

def excluded(ob):
    return not ob.nwo.export_this or in_exclude_collection(ob)

def get_camera_track_camera(context: bpy.types.Context) -> bpy.types.Object | None:
    if context.scene.nwo.camera_track_camera:
        return context.scene.nwo.camera_track_camera
    
    cameras = [ob for ob in context.view_layer.objects if ob.type == 'CAMERA']
    animated_cameras = [ob for ob in cameras if ob.animation_data]
    if animated_cameras:
        return animated_cameras[0]
    if cameras:
        return cameras[0]
    
def get_collection_children(collection: bpy.types.Collection):
    child_collections = collection.children
    collections = set()
    for collection in child_collections:
        collections.add(collection)
        if collection.children:
            collections.update(get_collection_children(collection))
            
    return collections
    
def get_exclude_collections():
    '''Gets all collections which are themselves exclude collections or a child of one'''
    direct_exclude_collections = [c for c in bpy.context.scene.collection.children if c.nwo.type == 'exclude']
    all_exclude_collections = set(direct_exclude_collections)
    for collection in direct_exclude_collections:
        if collection.children:
            all_exclude_collections.update(get_collection_children(collection))
    
    return all_exclude_collections
    
def valid_filename(name: str) -> str:
    bad_chars = r'\/:*?"<>'
    for char in bad_chars:
        name = name.replace(char, '_')
        
    return name

def valid_image_name(name: str) -> str:
    for f in BLENDER_IMAGE_FORMATS:
        name = name.replace(f, '')
    
    name = name.replace('.', '_')
    
    return valid_filename(name)

def paths_in_dir(directory: str, valid_extensions: tuple[str] | str = '') -> list[str]:
    '''Returns a list of filepaths from the given directory path. Optionally limited to paths with the given extensions'''
    assert(os.path.exists(directory)), f"Directory not a valid filepath: [{directory}]"
    filepath_list = [] 
    for root, _, files in os.walk(directory):
        for file in files:
            if not valid_extensions or file.endswith(valid_extensions):
                filepath_list.append(os.path.join(root, file))
                
    return filepath_list

class DebugMenuCommand:
    def __init__(self, asset_dir, filename):
        self.path = str(Path(asset_dir, filename)).replace('\\', '\\\\')
        self.tag_type = dot_partition(filename, True).lower()
        self.name = dot_partition(filename).lower()
        
    def __repr__(self):
        return f'<item type = command name = "Foundry: Drop {self.name} [{self.tag_type}]" variable = "drop \\"{self.path}\\"">\n'
    
def update_debug_menu(asset_dir="", asset_name="", for_cubemaps=False):
    menu_commands: list[DebugMenuCommand] = []
    if for_cubemaps:
        menu_commands.append('<item type = command name = "Foundry: Generate Dynamic Cubemaps" variable = "\(cubemap_dynamic_generate\) \(print \\"Dynamic cubemap generation in progress\\"\)">\n')
    else:
        asset_dir = relative_path(asset_dir)
        full_path = Path(get_tags_path(), asset_dir)
        if not full_path.exists():
            return
        for file in full_path.iterdir():
            if file.name.startswith(asset_name) and file.suffix in object_exts:
                menu_commands.append(DebugMenuCommand(asset_dir, file.name))
            
    menu_path = os.path.join(get_project_path(), 'bin', 'debug_menu_user_init.txt')
    valid_lines = None
    # Read first so we can keep the users existing commands
    if os.path.exists(menu_path):
        with open(menu_path, 'r') as menu:
            existing_menu = menu.readlines()
            # Strip out Foundry commands. These get rebuilt in the next step
            valid_lines = [line for line in existing_menu if not line.startswith('<item type = command name = "Foundry: ')]
            
    with open(menu_path, 'w') as menu:
        if valid_lines is not None:
            menu.writelines(valid_lines)
            
        menu.writelines([str(cmd) for cmd in menu_commands])
        
def is_halo_rig(ob):
    '''Returns True if the given object is a halo rig'''
    if ob.type != 'ARMATURE':
        return False
    
def get_object_controls(context: bpy.types.Context) -> list[bpy.types.Object]:
    object_controls = context.scene.nwo.object_controls
    if not object_controls:
        return []
    
    return [control.ob for control in object_controls if control.ob and control.ob.animation_data]

def add_auto_smooth(context: bpy.types.Context, ob: bpy.types.Object, angle=radians(30), apply_mod=False):
    """Applies auto smooth to an object using geometry nodes"""
    mods = ob.modifiers
    auto_smooth = mods.new("foundry_auto_smooth", type="NODES")
    
    node_tree = bpy.data.node_groups.get("foundry_auto_smooth")
    if not node_tree:
        node_tree = bpy.data.node_groups.new("foundry_auto_smooth", "GeometryNodeTree")
        # node_tree.is_modifier = True
        
    # Create input/output sockets
    interface = node_tree.interface
    
    interface.new_socket("Geometry", description="", in_out="INPUT", socket_type="NodeSocketGeometry", parent=None)
    interface.new_socket("Geometry", description="", in_out="OUTPUT", socket_type="NodeSocketGeometry", parent=None)
    
    # Create the nodes! (left to right)
    nodes = node_tree.nodes
    
    edge_angle = nodes.new("GeometryNodeInputMeshEdgeAngle")
    edge_angle.location = Vector((-450, -260))
    face_smooth = nodes.new("GeometryNodeInputShadeSmooth")
    face_smooth.location = Vector((-450, -430))
    
    edge_smooth = nodes.new("GeometryNodeInputEdgeSmooth")
    edge_smooth.location = Vector((-240, -150))
    compare_math = nodes.new("FunctionNodeCompare")
    compare_math.operation = "LESS_EQUAL"
    compare_math.inputs[1].default_value = angle
    compare_math.location = Vector((-245, -225))
    bool_math_a = nodes.new("FunctionNodeBooleanMath")
    bool_math_a.operation = "OR"
    bool_math_a.inputs[1].default_value = True
    bool_math_a.location = Vector((-240, -400))
    
    mesh_input = nodes.new("NodeGroupInput")
    mesh_input.location = Vector((-60, -25))
    node_tree.interface
    bool_math_b = nodes.new("FunctionNodeBooleanMath")
    bool_math_b.operation = "OR"
    bool_math_b.location = Vector((-50, -130))
    bool_math_c = nodes.new("FunctionNodeBooleanMath")
    bool_math_c.operation = "AND"
    bool_math_c.location = Vector((-50, -280))
    
    shade_smooth_a = nodes.new('GeometryNodeSetShadeSmooth')
    shade_smooth_a.domain = 'EDGE'
    shade_smooth_a.location = Vector((145, -50))
    
    shade_smooth_b = nodes.new('GeometryNodeSetShadeSmooth')
    shade_smooth_b.domain = 'FACE'
    shade_smooth_b.inputs[2].default_value = True
    shade_smooth_b.location = Vector((340, -50))
    
    mesh_output = nodes.new("NodeGroupOutput")
    mesh_output.location = Vector((530, -50))
    
    # Link the nodes! (right to left)
    links = node_tree.links
    
    links.new(mesh_output.inputs[0], shade_smooth_b.outputs[0])
    
    links.new(shade_smooth_b.inputs[0], shade_smooth_a.outputs[0])
    
    links.new(shade_smooth_a.inputs[0], mesh_input.outputs[0])
    links.new(shade_smooth_a.inputs[1], bool_math_b.outputs[0])
    links.new(shade_smooth_a.inputs[2], bool_math_c.outputs[0])
    
    links.new(bool_math_b.inputs[0], edge_smooth.outputs[0])
    links.new(bool_math_c.inputs[0], compare_math.outputs[0])
    links.new(bool_math_c.inputs[1], bool_math_a.outputs[0])
    
    links.new(compare_math.inputs[0], edge_angle.outputs[0])
    links.new(bool_math_a.inputs[0], face_smooth.outputs[0])
    
    auto_smooth.node_group = node_tree
    
    if apply_mod:
        with context.temp_override(object=ob):
            bpy.ops.object.modifier_apply(modifier="foundry_auto_smooth", single_user=True)
            
def restart_blender():
    if bpy.data.filepath:
        subprocess.Popen([bpy.app.binary_path, bpy.data.filepath])
    else:
        subprocess.Popen([bpy.app.binary_path])
    bpy.ops.wm.quit_blender()
    
def save_blender():
    bpy.ops.wm.save_mainfile()
    
def human_time(time: float | int, decimal_seconds=False) -> str:
    '''Returns a string of hours, minutes and seconds using the given time input (in seconds)'''
    hours, minutes_remainder = divmod(time, 3600)
    minutes, seconds_remainder = divmod(minutes_remainder, 60)
    seconds, decimals = divmod(seconds_remainder, 1)
    
    hours = int(hours)
    minutes = int(minutes)
    seconds = int(seconds)
    decimals =  int(decimals * 1000)
    
    final_str = ""
    if hours:
        final_str += f"{hours} hours"
        
    if minutes:
        if hours:
            if seconds:
                final_str += ", "
            else:
                final_str += " and "
        final_str += f"{minutes} minutes"
        
    if seconds:
        if hours or minutes:
            final_str += " and "
        if decimals and decimal_seconds:
            final_str += f"{seconds}.{decimals} seconds"
        else:
            final_str += f"{seconds} seconds"
            
    elif decimals:
        if hours or minutes:
            final_str += " and "
        final_str += f"{decimals} milliseconds"
        
    return final_str

def area_light_to_emissive(light_ob: bpy.types.Object):
    """Converts the given area light to a lightmap only emissive plane"""
    light = light_ob.data
    light_nwo = light_ob.data.nwo
    new_name = light_ob.name + "[emissive]"
    points: list[Vector] = []
    if light.shape in ("SQUARE", "RECTANGLE"):
        plane_data = bpy.data.meshes.new(new_name)
        if light.shape == "SQUARE":
            radius = light.size / 2
            points.append(Vector((-radius, -radius, 0)))
            points.append(Vector((-radius, radius, 0)))
            points.append(Vector((radius, radius, 0)))
            points.append(Vector((radius, -radius, 0)))
        else:
            radius_x = light.size / 2
            radius_y = light.size_y / 2
            points.append(Vector((-radius_x, -radius_y, 0)))
            points.append(Vector((-radius_x, radius_y, 0)))
            points.append(Vector((radius_x, radius_y, 0)))
            points.append(Vector((radius_x, -radius_y, 0)))
    else:
        plane_data = bpy.data.curves.new(new_name, type="CURVE")
        plane_data.dimensions = "2D"
        plane_data.fill_mode = "BOTH"
        if light.shape == "DISK":
            radius = light.size / 2
            points.append(Vector((-radius, 0, 0)))
            points.append(Vector((0, radius, 0)))
            points.append(Vector((radius, 0, 0)))
            points.append(Vector((0, -radius, 0)))
        else:
            radius_x = light.size / 2
            radius_y = light.size_y / 2
            points.append(Vector((-radius_x, 0, 0)))
            points.append(Vector((0, radius_y, 0)))
            points.append(Vector((radius_x, 0, 0)))
            points.append(Vector((0, -radius_y, 0)))
            
        
    if isinstance(plane_data, bpy.types.Mesh):
        plane_data.from_pydata(vertices=points, edges=[], faces=[range(len(points))])
    else:
        plane_data: bpy.types.Curve
        spline = plane_data.splines.new("BEZIER")
        spline.bezier_points.add(3)
        for idx, point in enumerate(points):
            spline.bezier_points[idx].co = point
            
        for bezier_point in spline.bezier_points:
            bezier_point.handle_left_type = 'AUTO'
            bezier_point.handle_right_type = 'AUTO'
            
        spline.use_cyclic_u = True
        
        temp_ob = bpy.data.objects.new(new_name + "_temp", plane_data)
        plane_data = temp_ob.to_mesh().copy()
        bm = bmesh.new()
        bm.from_mesh(plane_data)
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
        bm.to_mesh(plane_data)
        bm.free()
    
    plane_ob = bpy.data.objects.new(new_name, plane_data)
    plane_ob.matrix_world = light_ob.matrix_world
    plane_nwo = plane_data.nwo
    plane_nwo.mesh_type = "_connected_geometry_mesh_type_lightmap_only"
    plane_ob.nwo.region_name = true_region(light_ob.nwo)
    plane_ob.nwo.permutation_name = true_permutation(light_ob.nwo)
    plane_nwo.emissive_active = True
    plane_nwo.no_shadow = True
    plane_nwo.material_lighting_attenuation_cutoff = light_nwo.light_far_attenuation_end
    plane_nwo.material_lighting_attenuation_falloff = light_nwo.light_far_attenuation_start
    plane_nwo.material_lighting_emissive_focus = light_nwo.light_focus
    plane_nwo.material_lighting_emissive_color = light.color
    plane_nwo.material_lighting_emissive_per_unit = light_nwo.light_per_unit
    plane_nwo.material_lighting_emissive_power = calc_emissive_intensity(light.energy, 1 if bpy.context.scene.nwo.scale == 'max' else 0.03048)
    plane_nwo.material_lighting_emissive_quality = light_nwo.light_quality
    plane_nwo.material_lighting_use_shader_gel = light_nwo.light_use_shader_gel
    plane_nwo.material_lighting_bounce_ratio = light_nwo.light_bounce_ratio
    
    return plane_ob

def get_asset_animation_graph(full=False):
    if valid_nwo_asset(bpy.context):
        asset_dir, asset_name = get_asset_info()
        tag_path = Path(asset_dir, asset_name).with_suffix(".model_animation_graph")
        full_path = Path(get_tags_path(), tag_path)
        if full_path.exists():
            if full:
                return str(full_path)
            else:
                return str(tag_path)
            
def get_asset_render_model(full=False):
    if valid_nwo_asset(bpy.context):
        asset_dir, asset_name = get_asset_info()
        tag_path = Path(asset_dir, asset_name).with_suffix(".render_model")
        full_path = Path(get_tags_path(), tag_path)
        if full_path.exists():
            if full:
                return str(full_path)
            else:
                return str(tag_path)
            
def get_asset_collision_model(full=False):
    if valid_nwo_asset(bpy.context):
        asset_dir, asset_name = get_asset_info()
        tag_path = Path(asset_dir, asset_name).with_suffix(".collision_model")
        full_path = Path(get_tags_path(), tag_path)
        if full_path.exists():
            if full:
                return str(full_path)
            else:
                return str(tag_path)
            
def get_asset_physics_model(full=False):
    if valid_nwo_asset(bpy.context):
        asset_dir, asset_name = get_asset_info()
        tag_path = Path(asset_dir, asset_name).with_suffix(".physics_model")
        full_path = Path(get_tags_path(), tag_path)
        if full_path.exists():
            if full:
                return str(full_path)
            else:
                return str(tag_path)
            
def get_asset_tag(extension: str, full=False):
    if not extension.startswith('.'):
        extension = '.' + extension
    if valid_nwo_asset(bpy.context):
        asset_dir, asset_name = get_asset_info()
        tag_path = Path(asset_dir, asset_name).with_suffix(extension)
        full_path = Path(get_tags_path(), tag_path)
        if full_path.exists():
            if full:
                return str(full_path)
            else:
                return str(tag_path)
            
def get_asset_tags(extension= "", full=False):
    if extension and not extension.startswith('.'):
        extension = '.' + extension
    if valid_nwo_asset(bpy.context):
        tags_path = Path(get_tags_path())
        matching_tags = set()
        asset_dir, asset_name = get_asset_info()
        full_dir_path = Path(get_tags_path(), asset_dir)
        if not full_dir_path.exists(): return []
        for file in full_dir_path.iterdir():
            if file.suffix == extension:
                if full:
                    matching_tags.add(file)
                else:
                    matching_tags.add(file.relative_to(tags_path))
    
        return sorted(matching_tags)
    
    return []
            
def save_loop_normals(bm: bmesh.types.BMesh, mesh: bpy.types.Mesh):
    layer_names = [f"ln{i}" for i in range(max(len(face.verts) for face in bm.faces))]
    layers = {}

    for name in layer_names:
        if not bm.faces.layers.float_vector.get(name):
            layers[name] = bm.faces.layers.float_vector.new(name)
        else:
            layers[name] = bm.faces.layers.float_vector.get(name)

    bm.faces.ensure_lookup_table()

    for idx, face in enumerate(bm.faces):
        for i in range(len(face.verts)):
            layer = layers[f"ln{i}"]
            face[layer] = mesh.loops[mesh.polygons[idx].loop_indices[i]].normal
            
def save_loop_normals_mesh(mesh: bpy.types.Mesh):
    bm = bmesh.new()
    bm.from_mesh(mesh)
    save_loop_normals(bm, mesh)
    bm.free()
            
def remove_face_layers(bm: bmesh.types.BMesh, layer_prefix="ln"):
    layers_to_remove = [layer for layer in bm.faces.layers.float_vector.keys() if layer.startswith(layer_prefix)]
    
    for layer_name in layers_to_remove:
        layer = bm.faces.layers.float_vector[layer_name]
        bm.faces.layers.float_vector.remove(layer)
            
def apply_loop_normals(mesh: bpy.types.Mesh):        
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        loop_normals = list(yield_loop_normals(bm))
        remove_face_layers(bm)
        bm.to_mesh(mesh)
        if len(mesh.loops) > len(loop_normals):
            diff = len(mesh.loops) - len(loop_normals)
            loop_normals.extend([[0.0,0.0,0.0]]*diff)
        mesh.normals_split_custom_set(loop_normals)
    finally:
        bm.free()
    
def loop_normal_magic(mesh: bpy.types.Mesh, distance=0.01):
    '''Saves current normals, merges vertices, and then restores the normals as loop normals'''
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        save_loop_normals(bm, mesh)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=distance)
        loop_normals = list(yield_loop_normals(bm))
        remove_face_layers(bm)
        bm.to_mesh(mesh)
        if len(mesh.loops) > len(loop_normals):
            diff = len(mesh.loops) - len(loop_normals)
            loop_normals.extend([0,0,0]*diff)
        mesh.normals_split_custom_set(loop_normals)
    finally:
        bm.free()
    
def yield_loop_normals(bm):
    max_verts = max(len(face.verts) for face in bm.faces)
    layers = {i: bm.faces.layers.float_vector.get(f"ln{i}") for i in range(max_verts)}
    for face in bm.faces:
        for i in range(len(face.verts)):
            layer = layers.get(i)
            if layer:
                yield face[layer].copy()
    
def clean_materials(ob: bpy.types.Object) -> list[bpy.types.MaterialSlot]:
    materials = ob.data.materials
    slots = ob.material_slots
    slots_to_remove = set()
    duplicate_slots = {}
    material_indexes = dict.fromkeys(slots)
    for idx, slot in enumerate(slots):
        if not slot.material:
            slots_to_remove.add(idx)
            continue
        slot_name = slot.material.name
        if slot_name not in material_indexes.keys():
            material_indexes[slot_name] = idx
        else:
            slots_to_remove.add(idx)
            duplicate_slots[idx] = material_indexes[slot_name]
    
    if ob.type == 'MESH':
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        bm.faces.ensure_lookup_table()
        used_material_indexes = set()
        for face in bm.faces:
            used_material_indexes.add(face.material_index)
            if duplicate_slots and face.material_index in duplicate_slots.keys():
                face.material_index = duplicate_slots[face.material_index]
                
        bm.to_mesh(ob.data)
        bm.free()
        
        for i in range(len(slots)):
            if i not in used_material_indexes:
                slots_to_remove.add(i)
    
    slots_to_remove = sorted(slots_to_remove, reverse=True)
        
    for idx in slots_to_remove:
        materials.pop(index=idx)
        
    if not ob.data.materials:
        ob.data.materials.clear()
        
    return ob.material_slots

def add_to_collection(objects: list[bpy.types.Object], always_new=False, parent_collection=None, name="collection"):
    if not objects:
        return
    
    for ob in objects: unlink(ob)
    collection = bpy.data.collections.get(name)
    if always_new or not collection:
        collection = bpy.data.collections.new(name)
    
    if parent_collection is None:
        parent_collection = bpy.context.scene.collection
    
    parent_collection.children.link(collection)
    
    [collection.objects.link(ob) for ob in objects]
    
def get_major_vertex_group(ob: bpy.types.Object):
    if not ob.data.vertices or not ob.vertex_groups:
        return
    if len(ob.vertex_groups) == 1:
        return ob.vertex_groups[0].name
    vert_group_indexes = []
    for vert in ob.data.vertices:
        for g in vert.groups:
            vert_group_indexes.append(g.group)
    
    if len(vert_group_indexes) < 2:
        return ob.vertex_groups[0].name
    
    most_common_index = Counter(vert_group_indexes).most_common(1)[0][0]
    
    if len(ob.vertex_groups) > most_common_index: 
        return ob.vertex_groups[most_common_index].name
    
def set_region(ob, region):
    regions_table = bpy.context.scene.nwo.regions_table
    entry = regions_table.get(region, 0)
    if not entry:
        regions_table.add()
        entry = regions_table[-1]
        entry.old = region
        entry.name = region
        
    ob.nwo.region_name = region
    
def add_region(region) -> str:
    regions_table = bpy.context.scene.nwo.regions_table
    entry = regions_table.get(region, 0)
    if not entry:
        regions_table.add()
        entry = regions_table[-1]
        entry.old = region
        entry.name = region
        
    return entry.name

def set_permutation(ob, permutation):
    permutations_table = bpy.context.scene.nwo.permutations_table
    entry = permutations_table.get(permutation, 0)
    if not entry:
        permutations_table.add()
        entry = permutations_table[-1]
        entry.old = permutation
        entry.name = permutation
        
    ob.nwo.permutation_name = permutation
    
def add_permutation(permutation) -> str:
    permutations_table = bpy.context.scene.nwo.permutations_table
    entry = permutations_table.get(permutation, 0)
    if not entry:
        permutations_table.add()
        entry = permutations_table[-1]
        entry.old = permutation
        entry.name = permutation
        
    return entry.name
        
def set_marker_permutations(ob, permutations: list[str]):
    for p in permutations:
        name = add_permutation(p)
        ob.nwo.marker_permutations.add().name = name
        
    
def new_face_prop(data, layer_name, display_name, override_prop, other_props={}) -> str:
    face_props = data.nwo.face_props
    layer = face_props.add()
    layer.layer_name = layer_name
    layer.name = display_name
    layer.layer_color = random_color()
    setattr(layer, override_prop, True)
    for prop, value in other_props.items():
        setattr(layer, prop, value)
        
    return layer_name

def new_face_layer(bm, data, layer_name, display_name, override_prop, other_props={}):
    layer = bm.faces.layers.int.get(layer_name)
    if layer:
        return layer
    else:
        return bm.faces.layers.int.new(new_face_prop(data, layer_name, display_name, override_prop, other_props))
    
def add_face_layer(bm: bmesh.types.BMesh, mesh: bpy.types.Mesh, prop: str, value: object) -> bmesh.types.BMLayerItem:
    match prop:
        case "region":
            layer_name = f"region{str(uuid4())}"
            display_name = f"region::{value}"
            override_prop = "region_name_override"
            other_props = {"region_name": value}
        case "two_sided":
            layer_name = f"face_two_sided{str(uuid4())}"
            display_name = "Two Sided"
            override_prop = "face_two_sided_override"
            other_props = {"face_two_sided": value}
        case "transparent":
            layer_name = f"transparent{str(uuid4())}"
            display_name = "Transparent"
            override_prop = "face_transparent_override"
            other_props = {"face_transparent": value}
        case "draw_distance":
            layer_name = f"{str(uuid4())}"
            display_name = "Draw Distance"
            override_prop = "face_draw_distance_override"
            other_props = {"face_draw_distance": value}
        case "render_only":
            layer_name = f"render_only{str(uuid4())}"
            display_name = "Render Only"
            override_prop = "render_only_override"
            other_props = {"render_only": value}
        case "collision_only":
            layer_name = f"{str(uuid4())}"
            display_name = "Collision Only"
            override_prop = "collision_only_override"
            other_props = {"collision_only": value}
        case "sphere_collision_only":
            layer_name = f"sphere_collision_only{str(uuid4())}"
            display_name = "Sphere Collision Onlu"
            override_prop = "sphere_collision_only_override"
            other_props = {"sphere_collision_only": value}
        case "bullet_collision_only":
            layer_name = f"bullet_collision_only{str(uuid4())}"
            display_name = "Bullet Collision Only"
            override_prop = "bullet_collision_only_override"
            other_props = {"bullet_collision_only": value}
        case "player_collision_only":
            layer_name = f"player_collision_only{str(uuid4())}"
            display_name = "Player Collision Only"
            override_prop = "player_collision_only"
            other_props = {"player_collision_only_override": value}
        case "texcoord_usage":
            layer_name = f"texcoord_usage{str(uuid4())}"
            display_name = "Texcoord Usage"
            override_prop = "texcoord_usage"
            other_props = {"texcoord_usage_override": value}
        case "face_global_material":
            layer_name = f"face_global_material{str(uuid4())}"
            display_name = f"material::{value}"
            override_prop = "face_global_material_override"
            other_props = {"face_global_material": value}
        case "ladder":
            layer_name = f"ladder{str(uuid4())}"
            display_name = "Ladder"
            override_prop = "ladder_override"
            other_props = {"ladder": value}
        case "slip_surface":
            layer_name = f"slip_surface{str(uuid4())}"
            display_name = "Slip Surface"
            override_prop = "slip_surface_override"
            other_props = {"slip_surface": value}
        case "decal_offset":
            layer_name = f"decal_offset{str(uuid4())}"
            display_name = "Decal Override"
            override_prop = "decal_offset_override"
            other_props = {"decal_offset": value}
        case "breakable":
            layer_name = f"breakable{str(uuid4())}"
            display_name = "Breakable"
            override_prop = "breakable_override"
            other_props = {"breakable": value}
        case "no_shadow":
            layer_name = f"no_shadow{str(uuid4())}"
            display_name = "No Shadow"
            override_prop = "no_shadow_override"
            other_props = {"no_shadow": value}
        case "precise_position":
            layer_name = f"precise_position{str(uuid4())}"
            display_name = "Uncompressed"
            override_prop = "precise_position_override"
            other_props = {"precise_position": value}
        case "no_lightmap":
            layer_name = f"no_lightmap{str(uuid4())}"
            display_name = "No Lightmap"
            override_prop = "no_lightmap_override"
            other_props = {"no_lightmap": value}
        case "no_pvs":
            layer_name = f"no_pvs{str(uuid4())}"
            display_name = "No PVS"
            override_prop = "no_pvs_override"
            other_props = {"no_pvs": value}
        case "tessellation":
            layer_name = f"tessellation{str(uuid4())}"
            display_name = "Tessellation Density"
            override_prop = "mesh_tessellation_density_override"
            other_props = {"mesh_tessellation_density": value}
        case "lightmap_additive_transparency":
            layer_name = f"lightmap_additive_transparency{str(uuid4())}"
            display_name = "Lightmap Additive Transparency"
            override_prop = "lightmap_additive_transparency_override"
            other_props = {"lightmap_additive_transparency": value}
        case "":
            layer_name = f"{str(uuid4())}"
            display_name = ""
            override_prop = ""
            other_props = {"": value}
        case _:
            return
            
    return new_face_layer(bm, mesh, layer_name, display_name, override_prop, other_props)
    
class EditArmature:
    ob: bpy.types.Object
    head_vectors: dict
    tail_vectors: dict
    lengths: dict
    matrices: dict[Matrix]
    bones: list[str]
    
    def __init__(self, arm):
        self.ob = arm
        scene_coll = bpy.context.scene
        should_be_hidden = False
        should_be_unlinked = False
        if arm.hide_get():
            arm.hide_set(False)
            should_be_hidden = True
            
        if not arm.visible_get():
            original_collections = arm.users_collection
            unlink(arm)
            scene_coll.link(arm)
            should_be_unlinked = True       
            
        set_active_object(arm)
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        edit_bones = arm.data.edit_bones
        self.head_vectors = {b.name: b.head for b in edit_bones}
        self.tail_vectors = {b.name: b.tail for b in edit_bones}
        self.lengths = {b.name: b.length for b in edit_bones}
        self.matrices = {b.name: b.matrix for b in edit_bones}
        self.bones = [b.name for b in edit_bones]
        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
        
        if should_be_hidden:
            arm.hide_set(True)
            
        if should_be_unlinked:
            unlink(arm)
            if original_collections:
                for coll in original_collections:
                    coll.objects.link(arm)
                    
def disable_excluded_collections(context):
    child_coll = context.view_layer.layer_collection.children
    for layer in child_coll:
        hide_excluded_recursively(layer)

def hide_excluded_recursively(layer):
    if layer.collection.nwo.type == 'exclude' and layer.is_visible:
        layer.exclude = True
    for child_layer in layer.children:
        hide_excluded_recursively(child_layer)
        
def unhide_collections(context):
    layer_collection = context.view_layer.layer_collection
    recursive_unhide_collections(layer_collection)

def recursive_unhide_collections(collections):
    coll_children = collections.children
    for collection in coll_children:
        collection.hide_viewport = False
        if collection.children:
            recursive_unhide_collections(collection)
                
def update_view_layer(context):
    context.view_layer.update()
    
def remove_relative_parenting(armature):
    '''
    Sets bone relative parenting to false for each bone on the given armature\n
    Resolves correct object parent inverses to account for the change
    '''
    relative_bones = set()
    for b in armature.data.bones:
        if b.use_relative_parent:
            relative_bones.add(b)

    relative_bone_names = [b.name for b in relative_bones]
    for ob in bpy.data.objects:
        if ob.parent == armature and ob.parent_type == 'BONE' and ob.parent_bone in relative_bone_names:
            bone = armature.data.bones[ob.parent_bone]
            ob.matrix_parent_inverse = (armature.matrix_world @ Matrix.Translation(bone.tail_local - bone.head_local) @ bone.matrix_local).inverted()

    for b in relative_bones: b.use_relative_parent = False
    
def apply_armature_scale(context, arm: bpy.types.Object):
    '''Applies an armature's scale while scaling animations. Assumes scaling is positive and uniform'''
    old_scale = arm.scale.copy()
    scale_factor = arm.scale.x
    scale_matrix = Matrix.Scale(scale_factor, 4)
    scene_coll = context.scene.collection.objects
    arm_children = {ob: ob.matrix_world.copy() for ob in bpy.data.objects if ob.parent == arm}
    
    arm.scale = Vector.Fill(3, 1)
    
    for ob, world in arm_children.items():
        ob.matrix_world = world

    
    # scale the armature bones
    should_be_hidden = False
    should_be_unlinked = False
    data: bpy.types.Armature = arm.data
    if arm.hide_get():
        arm.hide_set(False)
        should_be_hidden = True
        
    if not arm.visible_get():
        original_collections = arm.users_collection
        unlink(arm)
        scene_coll.link(arm)
        should_be_unlinked = True
        
    set_active_object(arm)
    bpy.ops.object.mode_set(mode='EDIT', toggle=False)
    
    uses_edit_mirror = bool(arm.data.use_mirror_x)
    if uses_edit_mirror: arm.data.use_mirror_x = False
    edit_bones = data.edit_bones
    connected_bones = [b for b in edit_bones if b.use_connect]
    for edit_bone in connected_bones: edit_bone.use_connect = False
    for edit_bone in edit_bones: edit_bone.transform(scale_matrix)
    for edit_bone in connected_bones: edit_bone.use_connect = True
    if uses_edit_mirror: arm.data.use_mirror_x = True
        
    bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
    
    if should_be_hidden:
        arm.hide_set(True)
        
    if should_be_unlinked:
        unlink(arm)
        if original_collections:
            for coll in original_collections:
                coll.objects.link(arm)
    
    # Scale the animations
    for action in bpy.data.actions:
        for fcurve in action.fcurves:
            if fcurve.data_path.endswith('location'):
                for keyframe_point in fcurve.keyframe_points: keyframe_point.co_ui[1] *= scale_factor

        for fc in action.fcurves:
            if fcurve.data_path.endswith('location'):
                fc.keyframe_points.handles_recalc()
                
def project_game_icon(context, project=None):
    if project is None:
        project = get_project(context.scene.nwo.scene_project)
    if not project:
        return get_icon_id('tag_test')
    match project.remote_server_name:
        case 'bngtoolsql':
            return get_icon_id('halo_reach')
        case 'metawins':
            return get_icon_id('halo_4')
        case 'episql.343i.selfhost.corp.microsoft.com':
            return get_icon_id('halo_2amp')
        
def project_icon(context, project=None):
    if project is None:
        project = get_project(context.scene.nwo.scene_project)
    if not project:
        return get_icon_id('tag_test')
    
    thumbnail = Path(project.project_path, project.image_path)
    if thumbnail.exists():
        return get_icon_id_in_directory(str(thumbnail))
    else:
        return project_game_icon(context, project)
    
class Spinner:
    busy = False
    delay = 0.1

    def __init__(self, delay=None):
        if delay and float(delay): self.delay = delay

    def spinner_task(self):
        while self.busy:
            sys.stdout.write(next(spinny))
            sys.stdout.flush()
            time.sleep(self.delay)
            sys.stdout.write('\b')
            sys.stdout.flush()

    def __enter__(self):
        self.busy = True
        threading.Thread(target=self.spinner_task).start()

    def __exit__(self, exception, value, tb):
        self.busy = False
        time.sleep(self.delay)
        if exception is not None:
            return False
        
class TagImportMover():
    def __init__(self, tags_dir, file):
        self.needs_to_move = False
        self.source_file = Path(file)
        name = self.source_file.with_suffix("").name
        self.temp_file = Path(tags_dir, "_temp", name + self.source_file.suffix)
        if not self.source_file.is_relative_to(Path(tags_dir)):
            print_warning(f"Tag [{self.source_file.name}] is from a different project and may fail to load")
            self.needs_to_move = True
            self.tag_path = str(Path("_temp", name + self.source_file.suffix))
            if not self.temp_file.parent.exists():
                self.temp_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.source_file, self.temp_file)
        else:
            self.tag_path = str(self.source_file.relative_to(tags_dir))
    
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_value, traceback):
        if self.needs_to_move and self.temp_file.exists():
            self.temp_file.unlink()
                
def get_foundry_blam_exe():
    bin_dir = Path(get_project_path(), "bin")
    if is_corinth():
        target_exe = Path(bin_dir, "FoundryBlamCorinth.exe")
    else:
        target_exe = Path(bin_dir, "FoundryBlam.exe")
    target_json_dll = Path(bin_dir, "Newtonsoft.Json.dll")
    if False and target_exe.exists() and target_json_dll.exists():
        return str(target_exe)
    else:
        source_dir = Path(addon_root(), "managed_blam", "FoundryBlam")
        if is_corinth():
            source_exe = Path(source_dir, "FoundryBlamCorinth.exe")
        else:
            source_exe = Path(source_dir, "FoundryBlam.exe")
            
        source_json_dll = Path(source_dir, "Newtonsoft.Json.dll")
        try:
            shutil.copyfile(source_exe, target_exe)
            shutil.copyfile(source_json_dll, target_json_dll)
        except:
            pass

    if not target_json_dll.exists():
        raise RuntimeError("Failed to copy Newtonsoft.Json.dll for FoundryBlam")

    if target_exe.exists():
        return str(target_exe)
    
    raise RuntimeError("Failed to copy FoundryBlam.exe")

def mouse_in_object_editor_region(context, x, y):
    for area in context.screen.areas:
        if area.type not in ('VIEW_3D', "PROPERTIES", "OUTLINER"):
            continue
        for region in area.regions:
            if region.type == 'WINDOW':
                if (x >= region.x and
                    y >= region.y and
                    x < region.width + region.x and
                    y < region.height + region.y):
                    return True

    return False

def get_exe(name: str):
    project_dir = Path(get_project_path())
    for file in project_dir.iterdir():
        if file.suffix.lower() != ".exe": continue
        if name in file.name:
            return file
        
def to_convex_hull(ob: bpy.types.Object):
    """Converts the given object to a convex hull"""
    if ob.type not in ("CURVE", "SURFACE", "META", "FONT", "MESH"): return
    mesh = ob.to_mesh()
    new_data = ob.data.copy()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    for edge in bm.edges: bm.edges.remove(edge)
    bm.edges.ensure_lookup_table()
    result = bmesh.ops.convex_hull(bm, input=bm.verts, use_existing_faces=True)
    bmesh.ops.delete(bm, geom=result["geom_interior"], context='VERTS')
    bm.to_mesh(new_data)
    bm.free()
    ob.data = new_data
    

def to_bounding_box(ob: bpy.types.Object):
    """Converts the given object to its bounding box"""
    if ob.type not in ("CURVE", "SURFACE", "META", "FONT", "MESH"): return
    new_data = ob.data.copy()
    bm = bmesh.new()
    bbox = ob.bound_box
    for co in bbox:
        bmesh.ops.create_vert(bm, co=co)

    bm.verts.ensure_lookup_table()
    back_face = [bm.verts[0], bm.verts[1], bm.verts[2], bm.verts[3]]
    front_face = [bm.verts[4], bm.verts[5], bm.verts[6], bm.verts[7]]
    left_face = [bm.verts[0], bm.verts[1], bm.verts[4], bm.verts[5]]
    right_face = [bm.verts[2], bm.verts[3], bm.verts[6], bm.verts[7]]
    bottom_face = [bm.verts[0], bm.verts[3], bm.verts[4], bm.verts[7]]
    top_face = [bm.verts[1], bm.verts[2], bm.verts[5], bm.verts[6]]
    bmesh.ops.contextual_create(bm, geom=back_face, mat_nr=0, use_smooth=False)
    bmesh.ops.contextual_create(bm, geom=front_face, mat_nr=0, use_smooth=False)
    bmesh.ops.contextual_create(bm, geom=left_face, mat_nr=0, use_smooth=False)
    bmesh.ops.contextual_create(bm, geom=right_face, mat_nr=0, use_smooth=False)
    bmesh.ops.contextual_create(bm, geom=bottom_face, mat_nr=0, use_smooth=False)
    bmesh.ops.contextual_create(bm, geom=top_face, mat_nr=0, use_smooth=False)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(new_data)
    bm.free()
    ob.data = new_data
    
def id_from_string(name) -> str:
    rand = random.Random(name)
    return str(rand.randint(-2147483647, 2147483647))

def ijkw_to_wxyz(rot: list[float, float, float, float] | Vector | Quaternion) -> Quaternion:
    i, j, k, w = rot
    return Quaternion((w, i, j, k))

def unsigned_int16(n: int) -> int:
    if n < 0:
        return 65536 + n
    return n

class BoundsDisplay(Enum):
    BOX = auto()
    PILL = auto()
    SPHERE = auto()

def set_bounds_display(ob: bpy.types.Object, display: BoundsDisplay):
    match display:
        case BoundsDisplay.BOX:
            ob.show_bounds = True
            ob.display_bounds_type = 'BOX'
        case BoundsDisplay.PILL:
            ob.show_bounds = True
            ob.display_bounds_type = 'CAPSULE'
        case BoundsDisplay.SPHERE:
            ob.show_bounds = True
            ob.display_bounds_type = 'SPHERE'
            
class MessageBoxType(Enum):
    OK = 0
    OKCXL = 1
    YESNOCXL = 3
    YESNO = 4

class MessageBox:
    mtype: MessageBoxType
    title: str
    message: str
    confirmed: bool
    def __init__(self, mtype: MessageBoxType, title: str, message: str):
        self.mtype = mtype
        self.title = title
        self.message = message
        self.confirmed = False
    
    def show(self):
        result = ctypes.windll.user32.MessageBoxW(0, self.message, self.title, self.mtype.value)
        if (self.mtype == MessageBoxType.YESNO or self.mtype == MessageBoxType.YESNOCXL) and result == 6:
            self.confirmed = True