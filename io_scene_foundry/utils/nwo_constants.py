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

# MESH TYPE GROUPS
# Mesh types which support render properties
RENDER_MESH_TYPES = ("_connected_geometry_mesh_type_structure", "_connected_geometry_mesh_type_default", "_connected_geometry_mesh_type_poop", '_connected_geometry_mesh_type_object_instance')
COLLISION_MESH_TYPES = ("_connected_geometry_mesh_type_default", "_connected_geometry_mesh_type_collision")
# Mesh types which support the two sided flag
TWO_SIDED_MESH_TYPES = ("_connected_geometry_mesh_type_structure", "_connected_geometry_mesh_type_default", "_connected_geometry_mesh_type_collision", '_connected_geometry_mesh_type_lightmap_only', '_connected_geometry_mesh_type_object_instance')

# Blender Halo Mesh Types
VALID_MESHES = {'MESH', 'CURVE', 'META', 'SURFACE', 'FONT'}

# MATERIALS

MATERIAL_SHADERS_DIR = r'shaders\material_shaders'

# Protected material names, we never let the user set shader paths for these
PROTECTED_MATERIALS = (
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
    "+weatherpoly",
    "+override",
    "+slip_surface",
    "+soft_ceiling",
    "+soft_kill",
    "InvisibleSky",
    "Physics",
    "Seam",
    "Portal",
    "Collision",
    "PlayerCollision",
    "WallCollision",
    "BulletCollision",
    "CookieCutter",
    "RainBlocker",
    "WaterVolume",
    "Structure",
    "WeatherPoly",
    "Override",
    "SeamSealer",
    "SlipSurface",
    "SoftCeiling",
    "SoftKill",
    "InvisibleMesh",
)

MAT_SEAMSEALER = '+seamsealer'
MAT_SKY = '+sky'
MAT_INVISIBLE = '+invisible'
MAT_INVALID = "+invalid"

# LEGACY PREFIXES
# Objects
LEGACY_BONE_PREFIXES = ("b ", "b_", "frame ", "frame_", "bip ","bip_", "bone ", "bone_",)
LEGACY_MARKER_PREFIXES = ("#", "?", "$") # marker, game instance, constraint
LEGACY_MESH_PREFIXES = ("@",  "%", "$", "'",) # collision, poop, physics, water surface

# Animation
LEGACY_ANIMATION_TYPES = (
    "JMM",
    "JMA",
    "JMT",
    "JMZ",
    "JMV",
    "JMO",
    "JMR",
    "JMRX",
)

object_asset_validation = {
    # Mesh
    '_connected_geometry_mesh_type_default': ('MODEL', 'SCENARIO', 'SKY', 'PARTICLE MODEL', 'DECORATOR SET', 'FP ANIMATION', 'PREFAB'),
    '_connected_geometry_mesh_type_collision': ('MODEL', 'SCENARIO', 'SKY', 'PREFAB'),
    '_connected_geometry_mesh_type_physics': ('MODEL',),
    '_connected_geometry_mesh_type_object_instance': ('MODEL',),
    '_connected_geometry_mesh_type_structure': ('SCENARIO'),
    '_connected_geometry_mesh_type_poop': ('SCENARIO', 'PREFAB'),
    '_connected_geometry_mesh_type_seam': ('SCENARIO',),
    '_connected_geometry_mesh_type_portal': ('SCENARIO',),
    '_connected_geometry_mesh_type_water_surface': ('SCENARIO',),
    '_connected_geometry_mesh_type_poop_vertical_rain_sheet': ('SCENARIO',),
    '_connected_geometry_mesh_type_planar_fog_volume': ('SCENARIO',),
    '_connected_geometry_mesh_type_soft_ceiling': ('SCENARIO',),
    '_connected_geometry_mesh_type_soft_kill': ('SCENARIO',),
    '_connected_geometry_mesh_type_slip_surface': ('SCENARIO',),
    '_connected_geometry_mesh_type_water_physics_volume': ('SCENARIO',),
    '_connected_geometry_mesh_type_lightmap_only': ('SCENARIO', 'PREFAB'),
    '_connected_geometry_mesh_type_streaming': ('SCENARIO',),
    '_connected_geometry_mesh_type_lightmap_exclude': ('SCENARIO',),
    '_connected_geometry_mesh_type_cookie_cutter': ('SCENARIO',),
    '_connected_geometry_mesh_type_poop_rain_blocker': ('SCENARIO',),
    # Marker
    '_connected_geometry_marker_type_model': ('MODEL', 'SCENARIO', 'SKY', 'FP ANIMATION', 'PREFAB'),
    '_connected_geometry_marker_type_effects': ('MODEL', 'SKY'),
    '_connected_geometry_marker_type_garbage': ('MODEL',),
    '_connected_geometry_marker_type_hint': ('MODEL',),
    '_connected_geometry_marker_type_pathfinding_sphere': ('MODEL',),
    '_connected_geometry_marker_type_physics_constraint': ('MODEL',),
    '_connected_geometry_marker_type_target': ('MODEL',),
    '_connected_geometry_marker_type_game_instance': ('SCENARIO', 'PREFAB'),
    '_connected_geometry_marker_type_airprobe': ('SCENARIO', 'PREFAB'),
    '_connected_geometry_marker_type_envfx': ('SCENARIO', 'PREFAB'),
    '_connected_geometry_marker_type_lightCone': ('SCENARIO', 'PREFAB'),
    }

object_game_validation = {
    # Mesh
    '_connected_geometry_mesh_type_default': ('reach', 'corinth'),
    '_connected_geometry_mesh_type_poop': ('reach', 'corinth'),
    '_connected_geometry_mesh_type_collision': ('reach', 'corinth'),
    '_connected_geometry_mesh_type_physics': ('reach', 'corinth'),
    '_connected_geometry_mesh_type_object_instance': ('reach', 'corinth'),
    '_connected_geometry_mesh_type_structure': ('reach', 'corinth'),
    '_connected_geometry_mesh_type_seam': ('reach', 'corinth'),
    '_connected_geometry_mesh_type_portal': ('reach', 'corinth'),
    '_connected_geometry_mesh_type_water_surface': ('reach', 'corinth'),
    '_connected_geometry_mesh_type_poop_vertical_rain_sheet': ('reach',),
    '_connected_geometry_mesh_type_planar_fog_volume': ('reach',),
    '_connected_geometry_mesh_type_soft_ceiling': ('reach', 'corinth'),
    '_connected_geometry_mesh_type_soft_kill': ('reach', 'corinth'),
    '_connected_geometry_mesh_type_slip_surface': ('reach', 'corinth'),
    '_connected_geometry_mesh_type_water_physics_volume': ('reach', 'corinth'),
    '_connected_geometry_mesh_type_lightmap_only': ('reach', 'corinth'),
    '_connected_geometry_mesh_type_streaming': ('corinth',),
    '_connected_geometry_mesh_type_lightmap_exclude': ('corinth',),
    '_connected_geometry_mesh_type_cookie_cutter': ('reach',),
    '_connected_geometry_mesh_type_poop_rain_blocker': ('reach',),
    # Marker
    '_connected_geometry_marker_type_model': ('reach', 'corinth'),
    '_connected_geometry_marker_type_effects': ('reach', 'corinth'),
    '_connected_geometry_marker_type_garbage': ('reach', 'corinth'),
    '_connected_geometry_marker_type_hint': ('reach', 'corinth'),
    '_connected_geometry_marker_type_pathfinding_sphere': ('reach', 'corinth'),
    '_connected_geometry_marker_type_physics_constraint': ('reach', 'corinth'),
    '_connected_geometry_marker_type_target': ('reach', 'corinth'),
    '_connected_geometry_marker_type_game_instance': ('reach', 'corinth'),
    '_connected_geometry_marker_type_airprobe': ('corinth',),
    '_connected_geometry_marker_type_envfx': ('corinth',),
    '_connected_geometry_marker_type_lightCone': ('corinth',),
    }