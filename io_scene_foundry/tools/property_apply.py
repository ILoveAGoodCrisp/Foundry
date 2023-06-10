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

from io_scene_foundry.utils.nwo_utils import dot_partition
import bpy

special_materials = (
    "InvisibleSky",
    "Physics",
    "Seam",
    "Portal",
    "Collision",
    "PlayCollision",
    "WallCollision",
    "BulletCollision",
    "CookieCutter",
    "RainBlocker",
    "RainSheet",
    "WaterVolume",
    "Structure",
    "Fog",
    "SoftCeiling",
    "SoftKill",
    "SlipSurface",
)
# face_prop_types = ()


def clear_special_mats(materials):
    """Removes special materials from an objects material slots i.e. ones that are not used as Halo shaders/materials"""
    for idx, mat in enumerate(materials):
        if mat.name in special_materials:
            remove_idx = idx
            materials.pop(index=remove_idx)
            break


def halo_material_color(material, color):
    """Sets the material to the specifier colour in both viewport and shader, setting alpha if appropriate"""
    material.use_nodes = True
    # viewport
    material.diffuse_color = color
    # shader
    material.node_tree.nodes[0].inputs[0].default_value = color
    if color[3] < 1.0:
        material.blend_method = "BLEND"

    material.use_nodes = False


def halo_material(mat_name):
    """Adds a halo material to the blend if it doesn't exist and applies settings, then returning the material"""
    # first check if the material already exists
    materials = bpy.data.materials
    material_names = (mat.name for mat in materials)
    if mat_name in material_names:
        return materials[mat_name]
    # if not, make it, apply settings, and return it
    new_material = materials.new(mat_name)
    match mat_name:
        case "InvisibleSky":
            halo_material_color(
                new_material, (0.8, 0.8, 0.8, 0.0)
            )  # light turqouise with 90% opacity

        case "Physics":
            halo_material_color(
                new_material, (0.0, 1.0, 0.0, 0.2)
            )  # green with 20% opacity

        case "Seam":
            halo_material_color(
                new_material, (0.39, 1.0, 0.39, 0.4)
            )  # light green with 40% opacity

        case "Portal":
            halo_material_color(
                new_material, (0.78, 0.69, 0.15, 0.4)
            )  # yellow with 40% opacity

        case "Collision":
            halo_material_color(
                new_material, (0.0, 0.0, 1.0, 0.2)
            )  # medium blue with 20% opacity

        case "PlayCollision":
            halo_material_color(
                new_material, (1.0, 0.5, 0.0, 0.2)
            )  # orange with 20% opacity

        case "WallCollision":
            halo_material_color(
                new_material, (0.0, 0.8, 0.0, 0.2)
            )  # green with 20% opacity

        case "BulletCollision":
            halo_material_color(
                new_material, (0.0, 0.8, 0.8, 0.2)
            )  # cyan with 20% opacity

        case "CookieCutter":
            halo_material_color(
                new_material, (0.3, 0.3, 1.0, 0.2)
            )  # purply-blue with 20% opacity

        case "Fog":
            halo_material_color(
                new_material, (0.3, 0.3, 1.0, 0.2)
            )  # purply-blue with 20% opacity

        case "RainBlocker":
            halo_material_color(
                new_material, (0.3, 0.3, 1.0, 1.0)
            )  # blue with 100% opacity

        case "RainSheet":
            halo_material_color(
                new_material, (0.3, 0.3, 1.0, 1.0)
            )  # blue with 100% opacity

        case "WaterVolume":
            halo_material_color(
                new_material, (0.0, 0.0, 1.0, 0.9)
            )  # deep blue with 90% opacity

        case "Structure":
            halo_material_color(
                new_material, (0.0, 0.0, 1.0, 0.9)
            )  # champion orange with 90% opacity

        case "SoftCeiling":
            halo_material_color(
                new_material, (0.51, 0.02, 0.06, 0.9)
            )  # blood red with 90% opacity

        case "SoftKill":
            halo_material_color(
                new_material, (0.51, 0.02, 0.06, 0.9)
            )  # blood red with 90% opacity

        case "SlipSurface":
            halo_material_color(
                new_material, (0.51, 0.02, 0.06, 0.9)
            )  # blood red with 90% opacity

    return new_material

def apply_props_material(ob, mat_name):
    if mat_name != "":
        ob.data.materials.clear()
        ob.data.materials.append(halo_material(mat_name))
    else:
        clear_special_mats(ob.data.materials)
