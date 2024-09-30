# MESH TYPE GROUPS
# Mesh types which support render properties
from enum import Enum, auto

from mathutils import Matrix

RENDER_MESH_TYPES = ("_connected_geometry_mesh_type_structure", "_connected_geometry_mesh_type_default", "_connected_geometry_mesh_type_poop", '_connected_geometry_mesh_type_object_instance', '_connected_geometry_mesh_type_water_surface')
COLLISION_MESH_TYPES = ("_connected_geometry_mesh_type_default", "_connected_geometry_mesh_type_collision")
# Mesh types which support the two sided flag
TWO_SIDED_MESH_TYPES = ("_connected_geometry_mesh_type_structure", "_connected_geometry_mesh_type_default", "_connected_geometry_mesh_type_collision", '_connected_geometry_mesh_type_lightmap_only', '_connected_geometry_mesh_type_object_instance', '_connected_geometry_mesh_type_water_surface')

# Blender Halo Mesh Types
VALID_MESHES = {'MESH', 'CURVE', 'META', 'SURFACE', 'FONT'}
# Object types that we export
VALID_OBJECTS = {'MESH', 'CURVE', 'META', 'SURFACE', 'FONT', 'EMPTY', 'CAMERA', 'LIGHT', 'ARMATURE'}

CG_PROP_PREFIX = "bungie_"

IDENTITY_MATRIX = Matrix.Identity(4)

# IDENTITY_MATRIX = Matrix(((1.0, 2.384185791015625e-07, 0.0, 0.0),
#         (-2.384185791015625e-05, 1.0, 0.0, 0.0),
#         (0.0, 0.0, 1.0, 0.0),
#         (0.0, 0.0, 0.0, 1.0)))

class object_type(Enum):
    _connected_geometry_object_type_none = auto()
    _connected_geometry_object_type_frame = auto()
    _connected_geometry_object_type_marker = auto()
    _connected_geometry_object_type_mesh = auto()
    _connected_geometry_object_type_light = auto()
    _connected_geometry_object_type_animation_control = auto()
    _connected_geometry_object_type_animation_camera = auto()
    _connected_geometry_object_type_animation_event = auto()
    _connected_geometry_object_type_debug = auto()
    _connected_geometry_object_type_frame_pca = auto()
    

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
    '_connected_geometry_mesh_type_default': ('model', 'scenario', 'sky', 'particle_model', 'decorator_set', 'animation', 'prefab', 'resource'),
    '_connected_geometry_mesh_type_collision': ('model', 'scenario', 'sky', 'prefab', 'resource'),
    '_connected_geometry_mesh_type_physics': ('model', 'resource'),
    '_connected_geometry_mesh_type_object_instance': ('model', 'resource'),
    '_connected_geometry_mesh_type_structure': ('scenario', 'resource'),
    '_connected_geometry_mesh_type_poop': ('scenario', 'prefab', 'resource'),
    '_connected_geometry_mesh_type_seam': ('scenario', 'resource'),
    '_connected_geometry_mesh_type_portal': ('scenario', 'resource'),
    '_connected_geometry_mesh_type_water_surface': ('scenario', 'resource'),
    '_connected_geometry_mesh_type_poop_vertical_rain_sheet': ('scenario', 'resource'),
    '_connected_geometry_mesh_type_planar_fog_volume': ('scenario', 'resource'),
    '_connected_geometry_mesh_type_soft_ceiling': ('scenario', 'resource'),
    '_connected_geometry_mesh_type_soft_kill': ('scenario', 'resource'),
    '_connected_geometry_mesh_type_slip_surface': ('scenario', 'resource'),
    '_connected_geometry_mesh_type_water_physics_volume': ('scenario', 'resource'),
    '_connected_geometry_mesh_type_lightmap_only': ('scenario', 'prefab', 'resource'),
    '_connected_geometry_mesh_type_streaming': ('scenario', 'resource'),
    '_connected_geometry_mesh_type_lightmap_exclude': ('scenario', 'resource'),
    '_connected_geometry_mesh_type_cookie_cutter': ('scenario', 'resource'),
    '_connected_geometry_mesh_type_poop_rain_blocker': ('scenario', 'resource'),
    # Marker
    '_connected_geometry_marker_type_model': ('model', 'scenario', 'sky', 'animation', 'prefab', 'resource'),
    '_connected_geometry_marker_type_effects': ('model', 'sky', 'resource'),
    '_connected_geometry_marker_type_garbage': ('model', 'resource'),
    '_connected_geometry_marker_type_hint': ('model', 'resource'),
    '_connected_geometry_marker_type_pathfinding_sphere': ('model', 'resource'),
    '_connected_geometry_marker_type_physics_constraint': ('model', 'resource'),
    '_connected_geometry_marker_type_target': ('model', 'resource'),
    '_connected_geometry_marker_type_game_instance': ('scenario', 'prefab', 'resource'),
    '_connected_geometry_marker_type_airprobe': ('scenario', 'prefab', 'resource'),
    '_connected_geometry_marker_type_envfx': ('scenario', 'prefab', 'resource'),
    '_connected_geometry_marker_type_lightCone': ('scenario', 'prefab', 'resource'),
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

WU_SCALAR = 0.328084

class GameVersion(Enum):
    REACH = 0
    CORINTH = 1