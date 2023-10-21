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
import subprocess
import sys
import winreg
import bpy
import platform
from math import radians
from mathutils import Matrix, Vector
import os
from os.path import exists as file_exists
from subprocess import Popen, check_call
import shutil
import random
import xml.etree.ElementTree as ET

from io_scene_foundry.utils import nwo_globals
from io_scene_foundry.utils.nwo_constants import PROTECTED_MATERIALS, VALID_MESHES

from ..icons import get_icon_id
import requests


###########
##GLOBALS##
###########

# Material Prefixes #
special_materials = (
    "+collision",
    "+physics",
    "+portal",
    "+seamsealer",
    "+sky",
    "+slip_surface",
    "+soft_ceiling",
    "+soft_kill",
    "+weatherpoly",
    "+override",
)
special_materials_h4 = (
    "+sky",
    "+physics",
    "+seam",
    "+portal",
    "+collision",
    "+player_collision",
    "+wall_collision",
    "+bullet_collision",
    "+cookie_cutter",
    "+rain_blocker",
    "+water_volume",
    "+structure",
)

# Enums #
special_mesh_types = (
    "_connected_geometry_mesh_type_boundary_surface",
    "_connected_geometry_mesh_type_collision",
    "_connected_geometry_mesh_type_decorator",
    "_connected_geometry_mesh_type_poop",
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

def object_valid(ob, export_hidden, valid_perm="", evaluated_perm=""):
    return (
        ob in tuple(bpy.context.scene.view_layers[0].objects)
        and (ob.visible_get() or export_hidden)
        and valid_perm == evaluated_perm
    )


def export_perm(perm, export_all_perms, selected_perms):
    return export_all_perms == "all" or perm in selected_perms


def export_bsp(bsp, export_all_bsps, selected_bsps):
    return export_all_bsps == "all" or bsp in selected_bsps


def get_prefix(string, prefix_list):  # gets a prefix from a list of prefixes
    prefix = ""
    for p in prefix_list:
        if string.startswith(p):
            prefix = p
            break

    return prefix


def select_halo_objects(select_func, selected_asset_type, valid_asset_types):
    deselect_all_objects()
    select_func = getattr(CheckType, select_func)
    halo_objects = []
    if selected_asset_type in valid_asset_types:
        for ob in bpy.context.view_layer.objects:
            if select_func(ob):
                halo_objects.append(ob)

    return halo_objects


def select_model_objects(
    halo_objects, perm, arm, export_hidden, export_all_perms, selected_perms
):
    deselect_all_objects()
    boolean = False
    if arm is not None:
        arm.select_set(True)
    for ob in halo_objects:
        halo = ob.nwo
        if object_valid(ob, export_hidden, perm, halo.permutation_name) and export_perm(
            perm, export_all_perms, selected_perms
        ):
            ob.select_set(True)
            boolean = True

    return boolean


def select_model_objects_no_perm(halo_objects, arm, export_hidden):
    deselect_all_objects()
    boolean = False
    if arm is not None:
        arm.select_set(True)
    for ob in halo_objects:
        if object_valid(ob, export_hidden):
            ob.select_set(True)
            boolean = True

    return boolean


def select_bsp_objects(
    halo_objects,
    bsp,
    arm,
    perm,
    export_hidden,
    export_all_perms,
    selected_perms,
    export_all_bsps,
    selected_bsps,
):
    deselect_all_objects()
    boolean = False
    if arm is not None:
        arm.select_set(True)
    for ob in halo_objects:
        halo = ob.nwo
        bsp_value = ob.nwo.bsp_name
        if bsp_value == bsp:
            if (
                object_valid(ob, export_hidden, perm, halo.permutation_name)
                and export_perm(perm, export_all_perms, selected_perms)
                and export_bsp(bsp, export_all_bsps, selected_bsps)
            ):
                ob.select_set(True)
                boolean = True

    return boolean


def get_shared_objects(halo_objects):
    new_objects = []
    for ob in halo_objects:
        if true_region(ob.nwo) == "shared":
            new_objects.append(ob)

    return new_objects


def select_prefab_objects(halo_objects, arm, export_hidden):
    deselect_all_objects()
    boolean = False
    if arm is not None:
        arm.select_set(True)
    for ob in halo_objects:
        if ob in tuple(bpy.context.scene.view_layers[0].objects) and (
            ob.visible_get() or export_hidden
        ):
            ob.select_set(True)
            boolean = True

    return boolean


def deselect_all_objects():
    bpy.ops.object.select_all(action="DESELECT")


def select_all_objects():
    bpy.ops.object.select_all(action="SELECT")


def set_active_object(ob):
    bpy.context.view_layer.objects.active = ob


def get_active_object():
    return bpy.context.view_layer.objects.active


def get_asset_info(filepath):
    asset_path = os.path.dirname(filepath).lower()
    asset = os_sep_partition(asset_path, True)

    return asset_path, asset


def get_asset_path():
    """Returns the path to the asset folder."""
    asset_path = bpy.context.scene.nwo_halo_launcher.sidecar_path.rpartition(os.sep)[0].lower()
    return asset_path


def get_asset_path_full(tags=False):
    """Returns the full system path to the asset folder. For tags, add a True arg to the function call"""
    asset_path = bpy.context.scene.nwo_halo_launcher.sidecar_path.rpartition(os.sep)[0].lower()
    if tags:
        return get_tags_path() + asset_path
    else:
        return get_data_path() + asset_path


# -------------------------------------------------------------------------------------------------------------------


def mesh_type(ob, types):
    if (
        ob is not None
    ):  # temp work around for 'ob' not being passed between functions correctly, and resolving to a NoneType
        return is_mesh(ob) and ob.nwo.mesh_type in types


def marker_type(ob, types):
    if (
        ob is not None
    ):  # temp work around for 'ob' not being passed between functions correctly, and resolving to a NoneType
        return is_marker(ob) and ob.nwo.marker_type in types


def object_type(ob, types=()):
    if (
        ob != None
    ):  # temp work around for 'ob' not being passed between functions correctly, and resolving to a NoneType
        if ob.type == "MESH":
            return ob.nwo.object_type in types
        elif ob.type == "EMPTY":
            return ob.nwo.object_type in types or len(ob.children) > 0
        elif ob.type == "LIGHT" and types != "MARKER":
            return True
        elif ob.nwo.object_type in types:
            return True
        else:
            return False


def object_prefix(ob, prefixes):
    return ob.name.startswith(prefixes)


def not_parented_to_poop(ob):
    return not mesh_type(ob.parent, "_connected_geometry_mesh_type_poop")


def is_design(ob):
    nwo = ob.nwo
    mesh_type = nwo.mesh_type
    return (
        CheckType.fog(ob)
        or CheckType.boundary_surface(ob)
        or CheckType.water_physics(ob)
        or CheckType.poop_rain_blocker(ob)
    )


def is_marker(ob):
    if ob.type == "MESH":
        return ob.nwo.object_type == "_connected_geometry_object_type_marker"
    elif ob.type == "EMPTY":
        return ob.nwo.object_type == "_connected_geometry_object_type_marker"
    else:
        return False


def is_frame(ob):
    if ob.type == "MESH":
        return ob.nwo.object_type == "_connected_geometry_object_type_frame"
    elif ob.type == "EMPTY":
        return ob.nwo.object_type == "_connected_geometry_object_type_frame"
    else:
        return False


def is_mesh(ob):
    return (
        ob.type in blender_object_types_mesh
        and ob.nwo.object_type == "_connected_geometry_object_type_mesh"
    )


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
    return str(round(number, 6))

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
        path = path.replace(get_tags_path().lower(), "")
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


class CheckType:
    @staticmethod
    def get(ob):
        if CheckType.animation_control(ob):
            return "_connected_geometry_object_type_animation_control"
        elif CheckType.animation_event(ob):
            return "_connected_geometry_object_type_animation_event"
        elif CheckType.animation_camera(ob):
            return "_connected_geometry_object_type_animation_camera"
        elif CheckType.light(ob):
            return "_connected_geometry_object_type_light"
        elif CheckType.frame_pca(ob):
            return "_connected_geometry_object_type_frame_pca"
        elif CheckType.frame(ob):
            return "_connected_geometry_object_type_frame"
        elif CheckType.marker(ob):
            return "_connected_geometry_object_type_marker"
        else:
            return "_connected_geometry_object_type_mesh"

    @staticmethod
    def render(ob):
        return mesh_type(ob, ("_connected_geometry_mesh_type_default",))

    @staticmethod
    def collision(ob):
        return mesh_type(ob, ("_connected_geometry_mesh_type_collision",))

    @staticmethod
    def physics(ob):
        return mesh_type(ob, ("_connected_geometry_mesh_type_physics",))

    @staticmethod
    def default(ob):
        return mesh_type(ob, ("_connected_geometry_mesh_type_default",))

    @staticmethod
    def marker(ob):
        return object_type(ob, ("_connected_geometry_object_type_marker",))

    @staticmethod
    def structure(ob):
        return mesh_type(ob, ("_connected_geometry_mesh_type_default",))

    @staticmethod
    def poop(ob):
        return mesh_type(ob, ("_connected_geometry_mesh_type_poop",))

    @staticmethod
    def poop_all(ob):
        return mesh_type(
            ob,
            (
                "_connected_geometry_mesh_type_poop",
                "_connected_geometry_mesh_type_poop_collision",
                "_connected_geometry_mesh_type_poop_physics",
            ),
        )

    @staticmethod
    def poop_marker(ob):
        return mesh_type(ob, ("_connected_geometry_mesh_type_poop_marker",))

    @staticmethod
    def object_instance(ob):
        return mesh_type(ob, ("_connected_geometry_mesh_type_object_instance",))

    @staticmethod
    def poop_collision_physics(ob):
        return mesh_type(
            ob,
            (
                "_connected_geometry_mesh_type_poop_collision",
                "_connected_geometry_mesh_type_poop_physics",
            ),
        )

    @staticmethod
    def light(ob):
        return ob.type == "LIGHT"

    @staticmethod
    def portal(ob):
        return mesh_type(ob, ("_connected_geometry_mesh_type_portal",))

    @staticmethod
    def seam(ob):
        return mesh_type(ob, ("_connected_geometry_mesh_type_seam",))

    @staticmethod
    def water_surface(ob):
        return mesh_type(ob, ("_connected_geometry_mesh_type_water_surface",))

    @staticmethod
    def misc(ob):
        return mesh_type(
            ob,
            (
                "_connected_geometry_mesh_type_lightmap_region",
                "_connected_geometry_mesh_type_obb_volume",
            ),
        )

    @staticmethod
    def lightmap_region(ob):
        return mesh_type(ob, ("_connected_geometry_mesh_type_lightmap_region",))

    @staticmethod
    def fog(ob):
        return mesh_type(ob, ("_connected_geometry_mesh_type_planar_fog_volume",))

    @staticmethod
    def boundary_surface(ob):
        return mesh_type(ob, ("_connected_geometry_mesh_type_boundary_surface",))

    @staticmethod
    def water_physics(ob):
        return mesh_type(ob, ("_connected_geometry_mesh_type_water_physics_volume",))

    @staticmethod
    def poop_rain_blocker(ob):
        return mesh_type(
            ob,
            tuple(
                "_connected_geometry_mesh_type_poop_rain_blocker",
            ),
        )

    @staticmethod
    def poop_rain_sheet(ob):
        return mesh_type(
            ob, ("_connected_geometry_mesh_type_poop_vertical_rain_sheet",)
        )

    @staticmethod
    def frame(ob):
        return (
            object_type(ob, ("_connected_geometry_object_type_frame",))
            and not ob.type == "LIGHT"
            and not ob.type == "ARMATURE"
        )  # ignores objects we know must be frames (like bones / armatures) as these are handled seperately

    @staticmethod
    def decorator(ob):
        return mesh_type(ob, ("_connected_geometry_mesh_type_decorator",))

    @staticmethod
    def poop_collision(ob):
        return mesh_type(ob, ("_connected_geometry_mesh_type_poop_collision",))

    @staticmethod
    def poop_physics(ob):
        return mesh_type(ob, ("_connected_geometry_mesh_type_poop_physics",))

    @staticmethod
    def cookie_cutter(ob):
        return mesh_type(ob, ("_connected_geometry_mesh_type_cookie_cutter",))

    @staticmethod
    def obb_volume(ob):
        return mesh_type(ob, ("_connected_geometry_mesh_type_obb_volume",))

    @staticmethod
    def mesh(ob):
        return (
            ob.type == "MESH"
            and ob.nwo.object_type in "_connected_geometry_object_type_mesh"
        )

    @staticmethod
    def model(ob):
        return marker_type(ob, ("_connected_geometry_marker_type_model",))

    @staticmethod
    def effects(ob):
        return marker_type(ob, ("_connected_geometry_marker_type_effects",))

    @staticmethod
    def game_instance(ob):
        return marker_type(ob, ("_connected_geometry_marker_type_game_instance",))

    @staticmethod
    def garbage(ob):
        return marker_type(ob, ("_connected_geometry_marker_type_garbage",))

    @staticmethod
    def hint(ob):
        return marker_type(ob, ("_connected_geometry_marker_type_hint",))

    @staticmethod
    def pathfinding_sphere(ob):
        return marker_type(ob, ("_connected_geometry_marker_type_pathfinding_sphere",))

    @staticmethod
    def physics_constraint(ob):
        return marker_type(ob, ("_connected_geometry_marker_type_physics_constraint",))

    @staticmethod
    def target(ob):
        return marker_type(ob, ("_connected_geometry_marker_type_target",))

    @staticmethod
    def water_volume_flow(ob):
        return marker_type(ob, ("_connected_geometry_marker_type_water_volume_flow",))

    @staticmethod
    def airprobe(ob):  # H4+ ONLY
        return marker_type(ob, ("_connected_geometry_marker_type_airprobe",))

    @staticmethod
    def envfx(ob):  # H4+ ONLY
        return marker_type(ob, ("_connected_geometry_marker_type_envfx",))

    @staticmethod
    def lightCone(ob):  # H4+ ONLY
        return marker_type(ob, ("_connected_geometry_marker_type_lightCone",))

    @staticmethod
    def animation_event(ob):
        return ob.nwo.is_animation_event

    @staticmethod
    def animation_control(ob):
        return False

    @staticmethod
    def animation_camera(ob):
        return ob.type == "CAMERA"

    @staticmethod
    def frame_pca(ob):  # H4+ ONLY
        return False

    @staticmethod
    def override(material):
        if is_corinth():
            return (
                material.name.startswith("+")
                or material.nwo.material_override_h4 != "none"
            )
        else:
            return (
                material.name.startswith("+")
                or material.nwo.material_override != "none"
            )


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


def rename_file(file_path, new_file_path=""):
    os.replace(file_path, new_file_path)


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

def comma_partition(target_string):
    """Returns a string after partitioning it using comma. If the returned string will be empty, the function will instead return the argument passed"""
    return shortest_string(target_string.rpartition(",")[0], target_string)


def write_error_report(asset_path, report_text, file_1=None, file_2=None, file_3=None):
    errors_folder = os.path.join(asset_path, "errors")

    if not file_exists(errors_folder):
        os.makedirs(errors_folder)

    with open(os.path.join(errors_folder, "output.txt"), "a+") as f:
        f.write(report_text)
        f.write("\n")

    if file_1 is not None and file_exists(file_1):
        shutil.copy(file_1, errors_folder)
    if file_2 is not None and file_exists(file_2):
        shutil.copy(file_2, errors_folder)
    if file_3 is not None and file_exists(file_3):
        shutil.copy(file_3, errors_folder)

    clean_files(file_1, file_2, file_3)


def clean_files(file_1, file_2, file_3):
    if file_1 is not None and file_exists(file_1):
        os.remove(file_1)
    if file_2 is not None and file_exists(file_2):
        os.remove(file_2)
    if file_3 != "" and file_3 is not None and file_exists(file_3):
        os.remove(file_3)


def get_structure_from_halo_objects(halo_objects, include_frames=True):
    """Gets structure objects when passed a HaloObjects instance"""
    objects = (
        halo_objects.lights
        + halo_objects.default
        + halo_objects.collision
        + halo_objects.physics
        + halo_objects.markers
        + halo_objects.cookie_cutters
        + halo_objects.poops
        + halo_objects.poop_markers
        + halo_objects.misc
        + halo_objects.seams
        + halo_objects.portals
        + halo_objects.water_surfaces
    )
    if include_frames:
        objects += halo_objects.frame
    return objects


def get_prefab_from_halo_objects(halo_objects):
    """Gets structure objects when passed a HaloObjects instance"""
    return (
        halo_objects.lights
        + halo_objects.collision
        + halo_objects.markers
        + halo_objects.cookie_cutters
        + halo_objects.poops
        + halo_objects.water_surfaces
        + halo_objects.frame
    )


def get_design_from_halo_objects(halo_objects, include_frames=True):
    """Gets structure design objects when passed a HaloObjects instance"""
    objects = (
        halo_objects.boundary_surfaces
        + halo_objects.fog
        + halo_objects.water_physics
        + halo_objects.poop_rain_blockers
    )
    if include_frames:
        objects += halo_objects.frame
    return objects


def get_render_from_halo_objects(halo_objects):
    """Gets render objects when passed a HaloObjects instance"""
    return halo_objects.default + halo_objects.object_instances + halo_objects.lights


def select_all_lights(halo_objects):
    for ob in halo_objects.lights:
        ob.select_set(True)


# def get_skeleton_from_halo_objects(halo_objects, model_armature=None):
#     """Gets skeleton objects when passed a HaloObjects instance"""
#     return halo_objects.frame + model_armature + model_armature.data.bones


def SetBoneJSONValues(bones):
    print("tbd")


def HaloBoner(bones, model_armature, context):
    objects_in_scope = context.view_layer.objects
    ob_matrix = create_ob_matric_dict(objects_in_scope)
    set_active_object(model_armature)
    bpy.ops.object.mode_set(mode="EDIT", toggle=False)
    for b in bones:
        pivot = b.head
        angle_x = radians(-90)
        axis_x = (1, 0, 0)
        M = (
            Matrix.Translation(pivot)
            @ Matrix.Rotation(angle_x, 4, axis_x)
            @ Matrix.Translation(-pivot)
        )
        b.matrix = M @ b.matrix

    bpy.ops.object.mode_set(mode="OBJECT", toggle=False)

    for ob in objects_in_scope:
        for key, value in ob_matrix.items():
            if key == ob:
                ob.matrix_world = value
                break


def halo_deboner(bones, model_armature, context):
    objects_in_scope = context.view_layer.objects
    ob_matrix = create_ob_matric_dict(objects_in_scope)
    set_active_object(model_armature)
    bpy.ops.object.mode_set(mode="EDIT", toggle=False)
    for b in bones:
        pivot = b.head
        angle_x = radians(90)
        axis_x = (1, 0, 0)
        M = (
            Matrix.Translation(pivot)
            @ Matrix.Rotation(angle_x, 4, axis_x)
            @ Matrix.Translation(-pivot)
        )
        b.matrix = M @ b.matrix

    bpy.ops.object.mode_set(mode="OBJECT", toggle=False)

    for ob in objects_in_scope:
        for key, value in ob_matrix.items():
            if key == ob:
                ob.matrix_world = value
                break


def halo_noder(nodes, model_armature):
    set_active_object(model_armature)
    for n in nodes:
        pivot = model_armature.location
        angle_x = radians(-90)
        angle_z = radians(-180)
        axis_x = (1, 0, 0)
        axis_z = (0, 0, 1)
        M = (
            Matrix.Translation(pivot)
            @ Matrix.Rotation(angle_x, 4, axis_x)
            @ Matrix.Rotation(angle_z, 4, axis_z)
            @ Matrix.Translation(-pivot)
        )
        n.matrix_world = M @ n.matrix_world


def halo_denoder(nodes, model_armature):
    set_active_object(model_armature)
    for n in nodes:
        pivot = model_armature.location
        angle_x = radians(90)
        angle_z = radians(180)
        axis_x = (1, 0, 0)
        axis_z = (0, 0, 1)
        M = (
            Matrix.Translation(pivot)
            @ Matrix.Rotation(angle_z, 4, axis_z)
            @ Matrix.Rotation(angle_x, 4, axis_x)
            @ Matrix.Translation(-pivot)
        )
        n.matrix_world = M @ n.matrix_world


def create_ob_matric_dict(objects_in_scope):
    ob_matrix = {}
    for ob in objects_in_scope:
        mtrx = Matrix(ob.matrix_world)
        ob_matrix.update({ob: mtrx})

    return ob_matrix


def check_path(filePath):
    return filePath.lower().startswith(os.path.join(get_project_path().lower(), "data"))


#################################

################################################
# EXTRA
################################################


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


# returns true if this material is a halo shader
def is_shader(mat):
    halo_mat = mat.nwo
    shader_path_not_empty = True if halo_mat.shader_path != "" else False
    no_material_override = True if halo_mat.material_override == "NONE" else False
    no_special_material_name = (
        True if not mat.name.lower().startswith(special_materials) else False
    )

    return shader_path_not_empty and no_material_override and no_special_material_name


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
                coll.name.startswith("+exclude") for coll in ob.users_collection
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


def data_relative(path: str) -> str:
    """
    Takes a full system path to a location within
    the data folder and returns the data relative path
    """
    return path.replace(get_data_path(), "")


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
        "_connected_geometry_mesh_type_structure",
        "_connected_geometry_mesh_type_render",
        "_connected_geometry_mesh_type_poop",
        "_connected_geometry_mesh_type_poop_collision",
    )
    nwo = ob.nwo
    return (
        ob
        and nwo.export_this
        and nwo.object_type_ui == "_connected_geometry_object_type_mesh"
        and nwo.mesh_type_ui in valid_mesh_types
    )


def has_face_props(ob) -> bool:
    valid_mesh_types = (
        "_connected_geometry_mesh_type_collision",
        "_connected_geometry_mesh_type_structure",
        "_connected_geometry_mesh_type_render",
        "_connected_geometry_mesh_type_poop",
        "_connected_geometry_mesh_type_poop_collision",
    )
    return (
        ob
        and ob.nwo.export_this
        and ob.type == "MESH"
        and ob.nwo.object_type_ui == "_connected_geometry_object_type_mesh"
        and ob.nwo.mesh_type_ui in valid_mesh_types
    )


def get_halo_material_count() -> tuple:
    count = 0
    total = 0
    for mat in bpy.data.materials:
        nwo = mat.nwo
        if mat.grease_pencil or not nwo.rendered:
            continue
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
            response = requests.get(update_url, timeout=6)
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

def is_halo_node(node: bpy.types.Node, valid_inputs: list) -> bool:
    """Given a Node and a list of valid inputs (each a string), checks if the given Node has exactly the inputs supplied"""
    inputs = node.inputs
    if len(inputs) != len(valid_inputs):
        return False
    for i in node.inputs:
        if i.name in valid_inputs: continue
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
    region_names = {e.name for e in regions_table}
    permutations_table = context.scene.nwo.permutations_table
    permutation_names = {e.name for e in permutations_table}
    scene_obs = context.scene.objects
    for ob in scene_obs:
        ob_region = true_region(ob.nwo)
        if ob_region not in region_names:
            new_region = regions_table.add()
            new_region.name = ob_region
            region_names.add(ob_region)
            ob.nwo.region_name_ui = ob_region

        ob_permutation = true_permutation(ob.nwo)
        if ob_permutation not in permutation_names:
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

