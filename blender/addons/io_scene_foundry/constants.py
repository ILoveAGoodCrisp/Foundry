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
LIGHTMAP_TRANSLUCENCY_TINT_COLOR = 0
LIGHTMAP_ANALYTICAL_LIGHT_ABSORB = 9999
LIGHTMAP_NORMAL_LIGHT_ABSORD = 9999
LIGHTMAP_IGNORE_DEFAULT_RESOLUTION_SCALE = False
LIGHTMAP_TRANSPARENCY_OVERRIDE = False
LIGHTMAP_LIGHTING_FROM_BOTH_SIDES = False
LIGHTMAP_CHART_GROUP_INDEX = 0

face_mode_items = (
    'render_only',
    'collision_only',
    'sphere_collision_only',
    'shadow_only',
    'breakable',
    'lightmap_only',
)

face_prop_type_items = [
            ('face_mode', "Face Mode", ":"),
            ('render_only', "Render Only", "reach,corinth:scenario,prefab"), 
            ('collision_only', "Collision Only", "reach,corinth:scenario,prefab"), 
            ('sphere_collision_only', "Sphere Collision Only", "reach,corinth:scenario,prefab"), 
            ('shadow_only', "Shadow Only", "reach,corinth:model,sky"), 
            ('breakable', "Breakable", "reach:scenario"), 
            ('lightmap_only', "Lightmap Only", "reach,corinth:model,sky,scenario,prefab"), 
            ('collision_type', "Collision Type", "corinth:scenario,prefab"), 
            ('face_sides', "Two-Sided", "reach,corinth:model,scenario,prefab,sky"), # face_two_sided & face_two_sided_type
            ('transparent', "Transparent", "reach,corinth:model,scenario,prefab,sky"),
            ('region', "Region", "reach,corinth:model,sky"),
            ('draw_distance', "Draw Distance", "reach,corinth:model,scenario,prefab,sky"),
            ('global_material', "Collision Material", "reach,corinth:model,scenario,prefab"),
            ('ladder', "Ladder", "reach:model,scenario"),
            ('slip_surface', "Slip Surface", "reach:model,scenario"),
            ('decal_offset', "Decal Offset", "reach,corinth:model,scenario,prefab,sky"),
            ('no_shadow', "No Shadow", "reach,corinth:model,scenario,prefab,sky"),
            ('precise_position', "Precise", "reach,corinth:model,scenario,prefab,sky"),
            ('uncompressed', "Uncompressed", "corinth:model,scenario,prefab,sky"),
            ('additional_compression', "Additional Compression", "reach,corinth:model,scenario,prefab,sky"),
            ('no_lightmap', "No Lightmap", "corinth:model,scenario,prefab,sky"),
            ('no_pvs', "No PVS", "corinth:model,scenario,prefab,sky"),
            ('mesh_tessellation_density', "Tessellation Density", "reach,corinth:model,scenario,prefab,sky"),
            ('lightmap_resolution_scale', "Lightmap Resolution", "reach:model,scenario,sky"),
            ('lightmap_ignore_default_resolution_scale', "Lightmap Resolution Ignore Default", "reach,corinth:model,scenario,prefab,sky"),
            ('lightmap_chart_group', "Lightmap Chart Group", "reach,corinth:model,scenario,prefab,sky"),
            ('lightmap_type', "Lightmap Type", "reach,corinth:model,scenario,prefab,sky"),
            ('lightmap_additive_transparency', "Lightmap Additive Transparency", "reach,corinth:model,scenario,prefab,sky"),
            ('lightmap_transparency_override', "Lightmap Transparency Override", "reach,corinth:model,scenario,prefab,sky"),
            ('lightmap_analytical_bounce_modifier', "Sunlight Bounce", "reach,corinth:model,scenario,prefab,sky"),
            ('lightmap_general_bounce_modifier', "Light Bounce", "reach,corinth:model,scenario,prefab,sky"),
            ('lightmap_translucency_tint_color', "Lightmap Translucency", "reach,corinth:model,scenario,prefab,sky"),
            ('lightmap_lighting_from_both_sides', "Light Both Sides", "reach,corinth:model,scenario,prefab,sky"),
            ('emissive', "Emissive", "reach,corinth:scenario,prefab"), # all emissive props
        ]

face_prop_descriptions = {
    'face_mode': "By default the game will build multiple versions of this geometry for different uses, such as building the visible mesh and the collision mesh. You can use this to specify a specific type of geometry only to be built",
    'collision_type': "The type of havok collision to generate from this mesh",
    'face_sides': "Render the backfacing normal of this mesh if it has render geometry. Collision geometry will be two-sided and will not result in open edges, but will be more expensive",
    'transparent': "Game treats this mesh as being transparent. If you're using a shader/material which has transparency, set this flag. Transparency is used in lightmapping and for allowing AI to see through a mesh",
    'region': "The name of the region these faces should be associated with",
    'draw_distance': "Controls the distance at which the assigned faces will stop rendering",
    'global_material': "The global material used for collision and physics meshes to control material responses to projectiles and physics objects, and separates a model for the purpose of damage regions. If the name matches a valid material defined in tags\globals\globals.globals then this mesh will automatically take the correct material response type, otherwise, the material override can be manually defined in the .model tag in materials tag block",
    'ladder': "Makes faces climbable",
    'slip_surface': "Assigned faces will be non traversable by the player. Used to ensure the player can not climb a surface regardless of slope angle",
    'decal_offset': "Provides a Z bias to the faces that will not be overridden by the plane build.  If placing a face coplanar against another surface, this flag will prevent Z fighting",
    'no_shadow': "Prevents faces from casting shadows",
    'precise_position': "Lowers the level of compression of vertices during export, resulting in more accurate (and expensive) meshes in game. Only use this when you need to, for example on smaller meshes like weapons where vertex detail is lost on in game",
    'uncompressed': "Mesh vertex data is stored in an uncompressed format",
    'additional_compression': "Additional level of compression to apply to this mesh",
    'no_lightmap': "The lightmapper will ignore these faces when building lightmap data",
    'no_pvs': "Makes these faces always render even if they aren't currently in a loaded potentially visible set (this is the geometry visible based on portal culling)",
    'mesh_tessellation_density': "Not sure this actually does anything",
    'lightmap_resolution_scale': "Determines how much texel space the faces will be given on the lightmap. Lowest means less space for the faces, while highest means more space for the faces. The resolutions can be tweaked in the .scenario tag under the bsp tag block, by default the lowest represents 1, and the highest 512. The default is 16. This is balance, you can't just give everything the highest resolution as there's only so much resolution to go around. Prioritise resolution in areas you want the best quality, and take it away from places where it matters less (such as a non-playable space)",
    'lightmap_ignore_default_resolution_scale': "Different render mesh types can have different default lightmap resolutions. Enabling this prevents the default for a given type being used",
    'lightmap_chart_group': "Per-face lightmap chart ID (0 to 31). Faces with the same value bake into one lightmap chart/UV island; different values force separate charts (controls seams & packing)",
    'lightmap_type': "Whether to add faces to the lightmap bitmap or store their lightmap data in the per-vertex lightmap budget",
    'lightmap_additive_transparency': "Overrides the amount and color of light that will pass through the surface. Tint color will override the alpha blend settings in the shader",
    'lightmap_transparency_override': "Disables the transparency of any mesh faces this property is applied to for the purposes of lightmapping. For example on a mesh using an invisible shader/material, shadow will still be cast",
    'lightmap_analytical_bounce_modifier': "For analytical lights such as the sun. 0 will bounce no energy. 1 will bounce full energy",
    'lightmap_general_bounce_modifier': "For general lights, such as placed spot lights. 0 will bounce no energy. 1 will bounce full energy",
    'lightmap_translucency_tint_color': "Overrides the color of the shadow and color of light after it passes through a translucent surface",
    'lightmap_lighting_from_both_sides': "Determines whether light should be cast at both sides of a single sided face",
    'emissive': "Makes surfaces emit light during lightmapping",
}

css_colors = { # Commented out some very light / dark colors here for better viewport vis
    # 'aliceblue': (0.941, 0.973, 1.000),
    # 'antiquewhite': (0.980, 0.922, 0.843),
    'aqua': (0.000, 1.000, 1.000),
    'aquamarine': (0.498, 1.000, 0.831),
    # 'azure': (0.941, 1.000, 1.000),
    'beige': (0.961, 0.961, 0.863),
    'bisque': (1.000, 0.894, 0.769),
    # 'black': (0.000, 0.000, 0.000),
    # 'blanchedalmond': (1.000, 0.922, 0.804),
    'blue': (0.000, 0.000, 1.000),
    'blueviolet': (0.541, 0.169, 0.886),
    'brown': (0.647, 0.165, 0.165),
    'burlywood': (0.871, 0.722, 0.529),
    'cadetblue': (0.373, 0.620, 0.627),
    'chartreuse': (0.498, 1.000, 0.000),
    'chocolate': (0.824, 0.412, 0.118),
    'coral': (1.000, 0.498, 0.314),
    'cornflowerblue': (0.392, 0.584, 0.929),
    'cornsilk': (1.000, 0.973, 0.863),
    'crimson': (0.863, 0.078, 0.235),
    'cyan': (0.000, 1.000, 1.000),
    'darkblue': (0.000, 0.000, 0.545),
    'darkcyan': (0.000, 0.545, 0.545),
    'darkgoldenrod': (0.722, 0.525, 0.043),
    # 'darkgray': (0.663, 0.663, 0.663),
    'darkgreen': (0.000, 0.392, 0.000),
    'darkgrey': (0.663, 0.663, 0.663),
    'darkkhaki': (0.741, 0.718, 0.420),
    'darkmagenta': (0.545, 0.000, 0.545),
    'darkolivegreen': (0.333, 0.420, 0.184),
    'darkorange': (1.000, 0.549, 0.000),
    'darkorchid': (0.600, 0.196, 0.800),
    'darkred': (0.545, 0.000, 0.000),
    'darksalmon': (0.914, 0.588, 0.478),
    'darkseagreen': (0.561, 0.737, 0.561),
    'darkslateblue': (0.282, 0.239, 0.545),
    'darkslategray': (0.184, 0.310, 0.310),
    'darkslategrey': (0.184, 0.310, 0.310),
    'darkturquoise': (0.000, 0.808, 0.820),
    'darkviolet': (0.580, 0.000, 0.827),
    'deeppink': (1.000, 0.078, 0.576),
    'deepskyblue': (0.000, 0.749, 1.000),
    'dimgray': (0.412, 0.412, 0.412),
    'dimgrey': (0.412, 0.412, 0.412),
    'dodgerblue': (0.118, 0.565, 1.000),
    'firebrick': (0.698, 0.133, 0.133),
    # 'floralwhite': (1.000, 0.980, 0.941),
    'forestgreen': (0.133, 0.545, 0.133),
    'fuchsia': (1.000, 0.000, 1.000),
    'gainsboro': (0.863, 0.863, 0.863),
    'ghostwhite': (0.973, 0.973, 1.000),
    'gold': (1.000, 0.843, 0.000),
    'goldenrod': (0.855, 0.647, 0.125),
    'gray': (0.502, 0.502, 0.502),
    'green': (0.000, 0.502, 0.000),
    'greenyellow': (0.678, 1.000, 0.184),
    'grey': (0.502, 0.502, 0.502),
    # 'honeydew': (0.941, 1.000, 0.941),
    'hotpink': (1.000, 0.412, 0.706),
    'indianred': (0.804, 0.361, 0.361),
    'indigo': (0.294, 0.000, 0.510),
    'ivory': (1.000, 1.000, 0.941),
    'khaki': (0.941, 0.902, 0.549),
    'lavender': (0.902, 0.902, 0.980),
    # 'lavenderblush': (1.000, 0.941, 0.961),
    'lawngreen': (0.486, 0.988, 0.000),
    'lemonchiffon': (1.000, 0.980, 0.804),
    'lightblue': (0.678, 0.847, 0.902),
    'lightcoral': (0.941, 0.502, 0.502),
    'lightcyan': (0.878, 1.000, 1.000),
    'lightgoldenrodyellow': (0.980, 0.980, 0.824),
    # 'lightgray': (0.827, 0.827, 0.827),
    'lightgreen': (0.565, 0.933, 0.565),
    # 'lightgrey': (0.827, 0.827, 0.827),
    'lightpink': (1.000, 0.714, 0.757),
    'lightsalmon': (1.000, 0.627, 0.478),
    'lightseagreen': (0.125, 0.698, 0.667),
    'lightskyblue': (0.529, 0.808, 0.980),
    # 'lightslategray': (0.467, 0.533, 0.600),
    # 'lightslategrey': (0.467, 0.533, 0.600),
    # 'lightsteelblue': (0.690, 0.769, 0.871),
    'lightyellow': (1.000, 1.000, 0.878),
    'lime': (0.000, 1.000, 0.000),
    'limegreen': (0.196, 0.804, 0.196),
    'linen': (0.980, 0.941, 0.902),
    'magenta': (1.000, 0.000, 1.000),
    'maroon': (0.502, 0.000, 0.000),
    'mediumaquamarine': (0.400, 0.804, 0.667),
    'mediumblue': (0.000, 0.000, 0.804),
    'mediumorchid': (0.729, 0.333, 0.827),
    'mediumpurple': (0.576, 0.439, 0.859),
    'mediumseagreen': (0.235, 0.702, 0.443),
    'mediumslateblue': (0.482, 0.408, 0.933),
    'mediumspringgreen': (0.000, 0.980, 0.604),
    'mediumturquoise': (0.282, 0.820, 0.800),
    'mediumvioletred': (0.780, 0.082, 0.522),
    'midnightblue': (0.098, 0.098, 0.439),
    'mintcream': (0.961, 1.000, 0.980),
    'mistyrose': (1.000, 0.894, 0.882),
    'moccasin': (1.000, 0.894, 0.710),
    # 'navajowhite': (1.000, 0.871, 0.678),
    'navy': (0.000, 0.000, 0.502),
    'oldlace': (0.992, 0.961, 0.902),
    'olive': (0.502, 0.502, 0.000),
    'olivedrab': (0.420, 0.557, 0.137),
    'orange': (1.000, 0.647, 0.000),
    'orangered': (1.000, 0.271, 0.000),
    'orchid': (0.855, 0.439, 0.839),
    'palegoldenrod': (0.933, 0.910, 0.667),
    'palegreen': (0.596, 0.984, 0.596),
    'paleturquoise': (0.686, 0.933, 0.933),
    'palevioletred': (0.859, 0.439, 0.576),
    'papayawhip': (1.000, 0.937, 0.835),
    'peachpuff': (1.000, 0.855, 0.725),
    'peru': (0.804, 0.522, 0.247),
    'pink': (1.000, 0.753, 0.796),
    'plum': (0.867, 0.627, 0.867),
    'powderblue': (0.690, 0.878, 0.902),
    'purple': (0.502, 0.000, 0.502),
    'rebeccapurple': (0.400, 0.200, 0.600),
    'red': (1.000, 0.000, 0.000),
    'rosybrown': (0.737, 0.561, 0.561),
    'royalblue': (0.255, 0.412, 0.882),
    'saddlebrown': (0.545, 0.271, 0.075),
    'salmon': (0.980, 0.502, 0.447),
    'sandybrown': (0.957, 0.643, 0.376),
    'seagreen': (0.180, 0.545, 0.341),
    'seashell': (1.000, 0.961, 0.933),
    'sienna': (0.627, 0.322, 0.176),
    'silver': (0.753, 0.753, 0.753),
    'skyblue': (0.529, 0.808, 0.922),
    'slateblue': (0.416, 0.353, 0.804),
    'slategray': (0.439, 0.502, 0.565),
    'slategrey': (0.439, 0.502, 0.565),
    'snow': (1.000, 0.980, 0.980),
    'springgreen': (0.000, 1.000, 0.498),
    'steelblue': (0.275, 0.510, 0.706),
    'tan': (0.824, 0.706, 0.549),
    'teal': (0.000, 0.502, 0.502),
    'thistle': (0.847, 0.749, 0.847),
    'tomato': (1.000, 0.388, 0.278),
    'turquoise': (0.251, 0.878, 0.816),
    'violet': (0.933, 0.510, 0.933),
    'wheat': (0.961, 0.871, 0.702),
    'white': (1.000, 1.000, 1.000),
    # 'whitesmoke': (0.961, 0.961, 0.961),
    'yellow': (1.000, 1.000, 0.000),
    'yellowgreen': (0.604, 0.804, 0.196),
}
