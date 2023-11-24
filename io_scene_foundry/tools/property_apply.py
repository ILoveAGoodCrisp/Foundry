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

# Full Prefixes:

render = {'full': 'render:', 'legacy': ''}
decorator = {'full': 'decorator:', 'legacy': ''}
collision = {'full': 'collision:', 'legacy': '@'}
physics = {'full': 'physics:', 'legacy': '$'}
flair = {'full': 'flair:', 'legacy': ''}
structure = {'full': 'structure:', 'legacy': ''}
instance = {'full': 'instance:', 'legacy': '%'}
seam = {'full': 'seam:', 'legacy': ''}
portal = {'full': 'portal:', 'legacy': ''}
water_surface = {'full': 'water_surface:', 'legacy': ''}
soft_ceiling = {'full': 'soft_ceiling:', 'legacy': ''}
soft_kill = {'full': 'soft_kill:', 'legacy': ''}
slip_surface = {'full': 'slip_surface:', 'legacy': ''}
lightmap_only = {'full': 'lightmap_only:', 'legacy': ''}
water_physics = {'full': 'water_physics:', 'legacy': ''}
rain_blocker = {'full': 'rain_blocker:', 'legacy': ''}
rain_sheet = {'full': 'rain_sheet:', 'legacy': ''}
cookie_cutter = {'full': 'cookie_cutter:', 'legacy': ''}
fog = {'full': 'fog:', 'legacy': ''}
lightmap = {'full': 'lightmap_exclude:', 'legacy': ''}
streaming = {'full': 'streaming_volume:', 'legacy': ''}

model = {'full': 'marker:', 'legacy': '#'}
game_instance = {'full': 'tag:', 'legacy': '?'}
envfx = {'full': 'env_fx:', 'legacy': '#'}
lightcone = {'full': 'light_cone:', 'legacy': '#'}
airprobe = {'full': 'airprobe:', 'legacy': '#'}
effects = {'full': 'fx:', 'legacy': '#'}
garbage = {'full': 'garbage:', 'legacy': '#'}
hint = {'full': 'hint:', 'legacy': '#'}
pathfinding_sphere = {'full': 'pathfinding_sphere:', 'legacy': '#'}
physics_constraint = {'full': 'constraint:', 'legacy': '$'}
target = {'full': 'target:', 'legacy': '#'}

all_prefixes = []

for dictionary in [render, decorator, collision, physics, flair, structure, instance, seam, portal, water_surface, soft_ceiling, soft_kill, slip_surface, water_physics, rain_blocker, rain_sheet, cookie_cutter, fog, lightmap, streaming, model, game_instance, envfx, lightcone, airprobe, effects, garbage, hint, pathfinding_sphere, physics_constraint, target]:
    all_prefixes.extend(list(dictionary.values()))

all_prefixes = [p for p in all_prefixes if p != '']
all_prefixes = set(all_prefixes)

import bpy
from io_scene_foundry.utils.nwo_utils import is_corinth

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
    "Volume",
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
            materials.pop(index=idx)
            clear_special_mats(materials)


def halo_material_color(material, color):
    """Sets the material to the specifier color in both viewport and shader, setting alpha if appropriate"""
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
                new_material, (0.0, 0.0, 1.0, 0.2)
            )  # medium blue with 20% opacity

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
                new_material, (0.0, 1.0, 0.0, 0.2)
            )  # green with 20% opacity

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
                new_material, (1.0, 0.1, 0.9, 0.2)
            )  # pink with 20% opacity

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
        case "Volume":
            halo_material_color(
                new_material, (0.0, 0.0, 1.0, 0.9)
            )  # champion orange with 90% opacity

        case "SoftCeiling":
            halo_material_color(
                new_material, (0.51, 0.364, 0.118, 0.9)
            )  # orange with 90% opacity

        case "SoftKill":
            halo_material_color(
                new_material, (0.51, 0.02, 0.06, 0.9)
            )  # blood red with 90% opacity

        case "SlipSurface":
            halo_material_color(
                new_material, (0.317, 0.51, 0.226, 0.9)
            )  # dull green with 90% opacity

    new_material.nwo.rendered = False

    return new_material

def cleanup_empty_slots(slots):
    materials = bpy.data.materials
    h4 = is_corinth()
    for slot in slots:
        slot_mat = slot.material
        if slot_mat:
            continue

        if "invalid" not in materials:
            invalid_mat = materials.new("invalid")
            if h4:
                invalid_mat.nwo.shader_path = r"shaders\invalid.material"
            else:
                invalid_mat.nwo.shader_path = r"shaders\invalid.shader"
        else:
            invalid_mat = materials.get("invalid")

        slot.material = invalid_mat



def apply_props_material(ob, mat_name):
    if mat_name != "":
        ob.data.materials.clear()
        ob.data.materials.append(halo_material(mat_name))
    else:
        clear_special_mats(ob.data.materials)
        cleanup_empty_slots(ob.material_slots)

def apply_prefix(ob, type, setting):
    original_name = ob.name
    no_prefix = original_name
    # Match start of string
    for p in all_prefixes:
        if original_name.startswith(p):
            no_prefix = original_name[len(p):]
            if no_prefix: break
    type_dict = globals()[type]
    if setting != 'none':
        prefix = type_dict[setting]
        ob.name = prefix + no_prefix
    else:
        ob.name = no_prefix
    
    