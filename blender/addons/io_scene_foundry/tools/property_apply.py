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
io = {'full': 'io:', 'legacy': ''}
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

for dictionary in [render, decorator, collision, physics, io, structure, instance, seam, portal, water_surface, soft_ceiling, soft_kill, slip_surface, water_physics, rain_blocker, rain_sheet, cookie_cutter, fog, lightmap, streaming, model, game_instance, envfx, lightcone, airprobe, effects, garbage, hint, pathfinding_sphere, physics_constraint, target]:
    all_prefixes.extend(list(dictionary.values()))

all_prefixes = [p for p in all_prefixes if p != '']
all_prefixes = set(all_prefixes)

import bpy
from io_scene_foundry.utils.nwo_utils import is_corinth
from io_scene_foundry.utils.nwo_materials import convention_materials

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

def halo_material(mat_name):
    """Adds a halo material to the blend if it doesn't exist and applies settings, then returning the material"""
    # first check if the material already exists
    mat = bpy.data.materials.get(mat_name)
    if mat: return mat
    # if not, make it, apply settings, and return it
    for m in convention_materials:
        if m.name == mat_name:
            convention = m
            break
    else:
        raise ValueError(f"halo material of name {mat_name} does not exist in nwo_materials.py")
    
    new_material = bpy.data.materials.new(mat_name)
    new_material.diffuse_color = convention.color
    new_material.use_nodes = True
    bsdf = new_material.node_tree.nodes[0]
    bsdf.inputs[0].default_value = convention.color
    bsdf.inputs[4].default_value = convention.color[3]
    new_material.blend_method = 'BLEND'
    new_material.shadow_method = 'NONE'

    return new_material

def cleanup_empty_slots(slots):
    materials = bpy.data.materials
    h4 = is_corinth()
    for slot in slots:
        slot_mat = slot.material
        if slot_mat:
            continue
        
        invalid_mat = materials.get('+invalid')
        if not invalid_mat:
            invalid_mat = materials.new("+invalid")

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
    
    