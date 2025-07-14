# MESH TYPE GROUPS
# Mesh types which support render properties
from enum import Enum, auto

from mathutils import Matrix

RENDER_MESH_TYPES = ("_connected_geometry_mesh_type_structure", "_connected_geometry_mesh_type_default", "_connected_geometry_mesh_type_poop", '_connected_geometry_mesh_type_object_instance', '_connected_geometry_mesh_type_water_surface')
COLLISION_MESH_TYPES = ("_connected_geometry_mesh_type_default", "_connected_geometry_mesh_type_collision")
# Mesh types which support the two sided flag
TWO_SIDED_MESH_TYPES = ("_connected_geometry_mesh_type_structure", "_connected_geometry_mesh_type_default", "_connected_geometry_mesh_type_collision", '_connected_geometry_mesh_type_object_instance', '_connected_geometry_mesh_type_water_surface')

# Blender Halo Mesh Types
VALID_MESHES = {'MESH', 'CURVE', 'META', 'SURFACE', 'FONT'}
# Object types that we export
VALID_OBJECTS = {'MESH', 'CURVE', 'META', 'SURFACE', 'FONT', 'EMPTY', 'CAMERA', 'LIGHT', 'ARMATURE'}

CG_PROP_PREFIX = "bungie_"

IDENTITY_MATRIX = Matrix.Identity(4)

OBJECT_TAG_EXTS = {'.biped', '.crate', '.creature', '.device_control', '.device_dispenser', '.effect_scenery', '.equipment', '.giant', '.device_machine', '.projectile', '.scenery', '.spawner', '.sound_scenery', '.device_terminal', '.vehicle', '.weapon'}

# IDENTITY_MATRIX = Matrix(((1.0, 2.384185791015625e-07, 0.0, 0.0),
#         (-2.384185791015625e-05, 1.0, 0.0, 0.0),
#         (0.0, 0.0, 1.0, 0.0),
#         (0.0, 0.0, 0.0, 1.0)))

class NormalType:
    OPENGL = 0
    DIRECTX = 1

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
    "+seamsealer",
    "+seam",
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
MAT_SEAM = '+seam'
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

# class FoundryGame:
#     def __init__(self):
#         self.name: str


# class FoundryAssetType:
#     def __init__(self):
#         self.games: tuple[FoundryGame]


# class FoundryMeshType:
#     def __init__(self):
#         self.games: tuple[FoundryGame]
#         self.asset_types = tuple[FoundryAssetType]
#         self.mesh_properties: bool
#         self.face_properties: bool
        

# REACH = FoundryGame()
# REACH.name = "reach"

# CORINTH = FoundryGame()
# CORINTH.name = "corinth"

# MODEL = FoundryAssetType()
# MODEL.games = REACH, CORINTH

# SCENARIO = FoundryAssetType()
# SCENARIO.games = REACH, CORINTH

# MESH_DEFAULT = FoundryMeshType()
# MESH_DEFAULT.games = REACH, CORINTH
# MESH_DEFAULT.asset_types = MODEL, SCENARIO
        

object_asset_validation = {
    # Mesh
    '_connected_geometry_mesh_type_default': ('model', 'scenario', 'sky', 'particle_model', 'decorator_set', 'animation', 'prefab', 'resource'),
    '_connected_geometry_mesh_type_collision': ('model', 'resource'),
    '_connected_geometry_mesh_type_physics': ('model', 'resource'),
    '_connected_geometry_mesh_type_object_instance': ('model', 'resource'),
    '_connected_geometry_mesh_type_structure': ('scenario', 'resource'),
    '_connected_geometry_mesh_type_poop': ('scenario', 'prefab', 'resource'),
    '_connected_geometry_mesh_type_seam': ('scenario', 'resource'),
    '_connected_geometry_mesh_type_portal': ('scenario', 'resource'),
    '_connected_geometry_mesh_type_water_surface': ('scenario', 'resource'),
    '_connected_geometry_mesh_type_poop_vertical_rain_sheet': ('scenario', 'resource'),
    '_connected_geometry_mesh_type_planar_fog_volume': ('scenario', 'resource'),
    '_connected_geometry_mesh_type_boundary_surface': ('scenario', 'resource'),
    '_connected_geometry_mesh_type_obb_volume': ('scenario', 'resource'),
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
    '_connected_geometry_mesh_type_boundary_surface': ('reach', 'corinth'),
    '_connected_geometry_mesh_type_obb_volume': ('corinth',),
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
    
    
# Material prop defaults
EMISSIVE_POWER = 0
EMISSIVE_COLOR = 0, 0, 0
EMISSIVE_QUALITY = 1
EMISSIVE_FOCUS = 0
EMISSIVE_POWER_PER_UNIT_AREA = False
EMISSIVE_USE_SHADER_GEL = False

LIGHTMAP_RESOLUTION_SCALE = 3
LIGHTMAP_ADDITIVE_TRANSPARENCY_COLOR = 0
LIGHTMAP_ADDITIVE_TRANSPARENCY_COLOR = 0
LIGHTMAP_TRANSLUCENCY_TINT_COLOR = 0
LIGHTMAP_ANALYTICAL_LIGHT_ABSORB = 9999
LIGHTMAP_NORMAL_LIGHT_ABSORD = 9999
LIGHTMAP_IGNORE_DEFAULT_RESOLUTION_SCALE = False
LIGHTMAP_TRANSPARENCY_OVERRIDE = False
LIGHTMAP_LIGHTING_FROM_BOTH_SIDES = False
LIGHTMAP_CHART_GROUP_INDEX = 0

CSS_COLORS = {
    # Grayscales
    "black": (0, 0, 0), "dimgray": (105, 105, 105), "gray": (128, 128, 128),
    "darkgray": (169, 169, 169), "silver": (192, 192, 192),
    "lightgray": (211, 211, 211), "gainsboro": (220, 220, 220),
    "whitesmoke": (245, 245, 245), "white": (255, 255, 255),

    # Reds & pinks
    "maroon": (128, 0, 0), "darkred": (139, 0, 0), "firebrick": (178, 34, 34),
    "red": (255, 0, 0), "salmon": (250, 128, 114), "lightsalmon": (255, 160, 122),
    "crimson": (220, 20, 60), "deeppink": (255, 20, 147), "hotpink": (255, 105, 180),
    "pink": (255, 192, 203), "lightpink": (255, 182, 193),

    # Oranges & browns
    "darkorange": (255, 140, 0), "coral": (255, 127, 80), "tomato": (255, 99, 71),
    "orange": (255, 165, 0), "lightsalmon": (255, 160, 122), "sienna": (160, 82, 45),
    "saddlebrown": (139, 69, 19), "chocolate": (210, 105, 30), "peru": (205, 133, 63),
    "sandybrown": (244, 164, 96), "burlywood": (222, 184, 135), "tan": (210, 180, 140),

    # Yellows & golds
    "gold": (255, 215, 0), "goldenrod": (218, 165, 32), "khaki": (240, 230, 140),
    "darkkhaki": (189, 183, 107), "yellow": (255, 255, 0), "lightyellow": (255, 255, 224),

    # Greens
    "darkgreen": (0, 100, 0), "green": (0, 128, 0), "forestgreen": (34, 139, 34),
    "lime": (0, 255, 0), "limegreen": (50, 205, 50), "springgreen": (0, 255, 127),
    "mediumseagreen": (60, 179, 113), "seagreen": (46, 139, 87),

    # Cyans & teals
    "teal": (0, 128, 128), "darkcyan": (0, 139, 139), "cyan": (0, 255, 255),
    "aqua": (0, 255, 255), "turquoise": (64, 224, 208), "mediumturquoise": (72, 209, 204),

    # Blues
    "navy": (0, 0, 128), "midnightblue": (25, 25, 112), "blue": (0, 0, 255),
    "mediumblue": (0, 0, 205), "royalblue": (65, 105, 225), "dodgerblue": (30, 144, 255),
    "deepskyblue": (0, 191, 255), "skyblue": (135, 206, 235), "lightskyblue": (135, 206, 250),

    # Purples & magentas
    "purple": (128, 0, 128), "indigo": (75, 0, 130), "darkviolet": (148, 0, 211),
    "darkorchid": (153, 50, 204), "mediumorchid": (186, 85, 211),
    "magenta": (255, 0, 255), "violet": (238, 130, 238), "plum": (221, 160, 221),
    "orchid": (218, 112, 214), "thistle": (216, 191, 216),
}