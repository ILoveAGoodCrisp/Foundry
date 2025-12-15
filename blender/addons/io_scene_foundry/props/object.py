from enum import Enum
from math import radians
import random
import uuid
import bpy

from ..constants import VALID_OBJECTS, face_prop_descriptions

from .. import utils

class IgnoreReason(Enum):
    none = 0
    export_this = 1
    invalid_type = 2
    view_layer = 3
    exclude = 4
    parent = 5

def recursive_parentage(ob):
    if ob.parent:
        return recursive_parentage(ob.parent)
        
    return ob.nwo.ignore_for_export

# MARKER PERM PROPERTIES
# ----------------------------------------------------------
class NWO_MarkerPermutationItems(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Permutation")
    
# CAMERA ACTOR PROPERTIES
# ----------------------------------------------------------
def poll_actor(self, object):
    if object.type == 'ARMATURE' and object.nwo.cinematic_object:
        for item in self.id_data.nwo.actors:
            if item.actor is object:
                return False
        return True

class NWO_ActorItems(bpy.types.PropertyGroup):
    actor: bpy.props.PointerProperty(
        name="Actor",
        type=bpy.types.Object,
        poll=poll_actor,
    )

# OBJECT PROPERTIES
# ----------------------------------------------------------
class NWO_ObjectPropertiesGroup(bpy.types.PropertyGroup):
    scale_model: bpy.props.BoolProperty(options={'HIDDEN'})
    
    export_name: bpy.props.StringProperty(options={'HIDDEN'})
    
    def node_order_source_clean_tag_path(self, context):
        self["node_order_source"] = utils.clean_tag_path(self["node_order_source"], ".render_model").strip('"')
    
    node_order_source: bpy.props.StringProperty(
        name="Original Render Model",
        description="Tag relative path to the render_model tag which provides the bone order for this armature",
        update=node_order_source_clean_tag_path,
        override={'LIBRARY_OVERRIDABLE'},
    )
    
    invert_control_aim: bpy.props.BoolProperty(
        name="Aim Control Toggle",
        description="Inverts the constraint relationship between the Aim Control and aim pitch / aim yaw bones. Allows the aim pitch and aim yaw bones to control the aim control bone"
    )
    
    control_aim: bpy.props.StringProperty(
        name="Aim Control Bone",
        description="Bone used to control the aim yaw and pitch bones on a halo armature",
        options=set(),
    )
    
    invert_control_rig: bpy.props.BoolProperty(
        name="Invert Control Rig",
        description="Inverts the constraint relationship between the control (FK & IK) rig and deform bones"
    )
    
    # CINEMATIC
    
    def cinematic_object_clean_tag_path(self, context):
        self["cinematic_object"] = utils.clean_tag_path(self["cinematic_object"]).strip('"')
    
    cinematic_object: bpy.props.StringProperty(
        name="Cinematic Object",
        description="The object that should represent this actor in cinematic scene tags. This should be any high level object tag such as .scenery or .biped",
        update=cinematic_object_clean_tag_path,
        options=set(),
        override={'LIBRARY_OVERRIDABLE'}
    )
    
    cinematic_variant: bpy.props.StringProperty(
        name="Cinematic Variant",
        options={'HIDDEN'},
    )
    
    ### PROXY
    # proxy_parent: bpy.props.PointerProperty(type=bpy.types.Mesh)
    proxy_type : bpy.props.StringProperty()
    #### MARKER PERM
    marker_permutations: bpy.props.CollectionProperty(
        type=NWO_MarkerPermutationItems,
        override={'LIBRARY_OVERRIDABLE'},
    )

    marker_permutations_index: bpy.props.IntProperty(
        name="Index for Animation Event",
        default=0,
        min=0,
        options=set(),
        override={'LIBRARY_OVERRIDABLE'},
    )

    marker_permutation_type: bpy.props.EnumProperty(
        name="Include/Exclude",
        description="Toggle whether this marker should be included in, or excluded from the below list of permutations. If this is set to include and no permutations are defined, this property will be ignored at export",
        items=[
            ("exclude", "Exclude", ""),
            ("include", "Include", ""),
        ],
        options=set(),
        override={'LIBRARY_OVERRIDABLE'},
    )
    
    # ACTOR SHOTS
    actors: bpy.props.CollectionProperty(
        type=NWO_ActorItems,
        override={'LIBRARY_OVERRIDABLE'},
    )

    active_actor_index: bpy.props.IntProperty(
        name="Index for Actor",
        default=0,
        min=0,
        options=set(),
        override={'LIBRARY_OVERRIDABLE'},
    )

    actors_type: bpy.props.EnumProperty(
        name="Include/Exclude",
        description="Toggle whether actors should be included in, or excluded from the shots covered by this camera",
        items=[
            ("exclude", "Exclude", "Exclude the following actors from this camera's shots"),
            ("include", "Include", "Include only the following actors in this camera's shots, exclude all others"),
        ],
        options=set(),
        override={'LIBRARY_OVERRIDABLE'},
    )
    
    # MAIN
    proxy_instance: bpy.props.BoolProperty(
        name="Proxy Instance",
        description="Duplicates this structure mesh as instanced geometry at export",
        options=set(),
        override={'LIBRARY_OVERRIDABLE'},
    )
    
    marker_instance: bpy.props.BoolProperty(
        name="Instance Collection is a Marker",
        description="Collection instance is a marker, as opposed a mesh. If this option is off, then the visible mesh will be made real at export",
        override={'LIBRARY_OVERRIDABLE'},
    )
    
    collection_region: bpy.props.StringProperty(options={'HIDDEN'})
    collection_permutation: bpy.props.StringProperty(options={'HIDDEN'})
    
    #########################################################################################################################
    # MESH TYPE UI ####################################################################################################
    #########################################################################################################################
    
    def get_mesh_type(self):
        if not utils.is_mesh(self.id_data):
            return '_connected_geometry_mesh_type_none'
        
        return self.id_data.data.nwo.mesh_type

    mesh_type: bpy.props.StringProperty(
        name="Mesh Type",
        default='_connected_geometry_mesh_type_default',
        options={'HIDDEN', 'SKIP_SAVE'},
        get=get_mesh_type,
    )
    
    mesh_type_temp: bpy.props.StringProperty(options={'HIDDEN'})

    #########################################################################################################################
    # MARKER TYPE UI ####################################################################################################
    #########################################################################################################################

    marker_type: bpy.props.StringProperty(
        name="Marker Type",
        options=set(),
        default='_connected_geometry_marker_type_model',
        override={'LIBRARY_OVERRIDABLE'},
    )

    marker_type_help: bpy.props.IntProperty(options=set(), override={'LIBRARY_OVERRIDABLE'})
    
    # frame_override: bpy.props.BoolProperty(
    #     name="Frame Override",
    #     description="Sets this empty as a frame regardless of whether it has children",
    # )

    export_this: bpy.props.BoolProperty(
        name="Export",
        default=True,
        description="Whether this object is exported or not",
        override={'LIBRARY_OVERRIDABLE'},
    )
    
    def get_ignore_for_export(self):
        if not self.export_this:
            return IgnoreReason.export_this.value
        ob = self.id_data
        ob: bpy.types.Object
        if ob.type not in VALID_OBJECTS:
            return IgnoreReason.invalid_type.value
        
        # if not ob.users_collection:
        #     return IgnoreReason.collection.value
        
        if bpy.context.view_layer.objects.get(ob.name) is None:
            return IgnoreReason.view_layer.value
        
        in_exclude_collection = utils.get_prop_from_collection(ob, 'exclude')
        if in_exclude_collection:
            return IgnoreReason.exclude.value

        if ob.parent and recursive_parentage(ob):
            return IgnoreReason.parent.value
        
        return IgnoreReason.none.value
    
    ignore_for_export: bpy.props.IntProperty(
        options={'HIDDEN', 'SKIP_SAVE'},
        get=get_ignore_for_export,
    )


    # def get_ignore_for_export_fast(self):
    #     if not self.export_this:
    #         return IgnoreReason.export_this.value
    #     ob = self.id_data
    #     ob: bpy.types.Object
    #     if ob.type not in VALID_OBJECTS:
    #         return IgnoreReason.invalid_type.value

    #     if ob.parent and recursive_parentage(ob):
    #         return IgnoreReason.parent.value
        
    #     return IgnoreReason.none.value
    
    # ignore_for_export_fast: bpy.props.IntProperty(
    #     options={'HIDDEN', 'SKIP_SAVE'},
    #     get=get_ignore_for_export,
    # )

    # OBJECT LEVEL PROPERTIES

    seam_back: bpy.props.StringProperty(
        name="Seam Back Facing BSP",
        default="default",
        description="The BSP that the normals of this seam are facing away from",
        options=set(),
        override={'LIBRARY_OVERRIDABLE'},
    )
    
    seam_back_manual: bpy.props.BoolProperty(
        name="Manual Seam Backface",
        description="Seam backface is defined by a separate seam object",
        options=set(),
        override={'LIBRARY_OVERRIDABLE'},
    )

    def mesh_primitive_type_items(self, context):
        items = []
        items.append(("_connected_geometry_primitive_type_none", "None", "None", 0))
        items.append(("_connected_geometry_primitive_type_box", "Box", "Box", 1))
        items.append(("_connected_geometry_primitive_type_pill", "Pill", "Pill", 2))
        items.append(
            (
                "_connected_geometry_primitive_type_sphere",
                "Sphere",
                "Sphere",
                3,
            )
        )

        return items
    
    def update_mesh_primitive_type(self, context):
        match self.mesh_primitive_type:
            case "_connected_geometry_primitive_type_box":
                utils.set_bounds_display(self.id_data, utils.BoundsDisplay.BOX)
            case "_connected_geometry_primitive_type_pill":
                utils.set_bounds_display(self.id_data, utils.BoundsDisplay.PILL)
            case "_connected_geometry_primitive_type_sphere":
                utils.set_bounds_display(self.id_data, utils.BoundsDisplay.SPHERE)

    mesh_primitive_type: bpy.props.EnumProperty(
        name="Mesh Primitive Type",
        options=set(),
        description="If this is not none then the in game physics shape will be simplified to the selected primitive, using the objects dimensions",
        items=mesh_primitive_type_items,
        override={'LIBRARY_OVERRIDABLE'},
        # update=update_mesh_primitive_type,
    )
    
    mopp_physics: bpy.props.BoolProperty(
        name="Allow Non-Convex Shape",
        options=set(),
        description="Tells the game to generate a physics representation of this mesh without converting it to a convex hull",
        override={'LIBRARY_OVERRIDABLE'},
    )
    
    global_material: bpy.props.StringProperty(
        name="Global Material",
        options=set(),
        description="Applies the given global material to this object. This affects the sounds and effects that play when objects interact with this mesh",
        override={'LIBRARY_OVERRIDABLE'},
    )

    poop_lighting_items = [
        (
            "per_pixel",
            "Per Pixel",
            "Per pixel provides good fidelity and lighting variation but it takes up resolution in the lightmap bitmap",
        ),
        (
            "per_vertex",
            "Per Vertex",
            "Uses a separate and additional per-vertex lightmap budget. Cost is dependent purely on complexity/vert count of the mesh",
        ),
        (
            "single_probe",
            "Single Probe",
            "Cheap but effective lighting",
        ),
    ]

    # POOP PROPERTIES
    
    poop_global_material: bpy.props.StringProperty(
        name="Collision Material Override",
        description="Override the collision materials for this mesh (which will be derived from the materials) with the given global material",
        options=set(),
        override={'LIBRARY_OVERRIDABLE'},
    )
    
    poop_render_only: bpy.props.BoolProperty(
        name="Render Only",
        options=set(),
        description="Instance is render only regardless of whether the underlying mesh itself has collision",
        override={'LIBRARY_OVERRIDABLE'},
    )
    
    poop_lighting: bpy.props.EnumProperty(
        name="Lighting Policy",
        options=set(),
        description="Determines how this instance is lightmapped",
        default="per_pixel",
        items=poop_lighting_items,
        override={'LIBRARY_OVERRIDABLE'},
    )
    
    poop_ao: bpy.props.BoolProperty(
        name="Ambient Occlusion",
        options=set(),
        description="Per vertex lighting gets ambient occlusion only",
        override={'LIBRARY_OVERRIDABLE'},
    )

    poop_lightmap_resolution_scale: bpy.props.FloatProperty(
        name="Lightmap Resolution",
        options=set(),
        description="Determines how much texel space this instance (if per pixel) will be given on the lightmap bitmap. Higher values do not automatically increase light resolution, instead the resolution is taken away from other instances. This value acts like a weight, deciding how the lightmap bitmap resolution gets divided up between instances",
        default=1,
        min=0,
        override={'LIBRARY_OVERRIDABLE'},
    )
    
    def poop_pathfinding_items(self, context):
        items = []
        if utils.is_corinth(context):
            items.append(("cutout", "Walkable", "AI will be able to pathfind around and on this mesh"))
            items.append(("static", "Force Walkable", "AI will be able to pathfind around and on this mesh"))
        else:
            items.append(("cutout", "Cut-Out", "AI will be able to pathfind around this instance, but not on it"))
            items.append(("static", "Walkable", "AI will be able to pathfind around and on this mesh"))
        items.append(("none", "None", "This mesh will be ignored during pathfinding generation. AI will attempt to walk though it as if it is not there"))
        
        return items

    poop_pathfinding: bpy.props.EnumProperty(
        name="Instanced Geometry Pathfinding",
        options=set(),
        description="How this instanced is assessed when the game builds a pathfinding representation of the map",
        items=poop_pathfinding_items,
        override={'LIBRARY_OVERRIDABLE'},
    )

    poop_imposter_policy: bpy.props.EnumProperty(
        name="Instanced Geometry Imposter Policy",
        options=set(),
        description="Sets what kind of imposter model is assigned to this instance. If any the policy is set to anything other than 'Never', you will need to generate imposters for this to render correctly. See https://c20.reclaimers.net/hr/guides/imposter-generation/ for how to generate these",
        default="never",
        items=[
            (
                "polygon_default",
                "Polygon Default",
                "",
            ),
            (
                "polygon_high",
                "Polygon High",
                "",
            ),
            (
                "card_default",
                "Card Default",
                "",
            ),
            (
                "card_high",
                "Card High",
                "",
            ),
            ("never", "Never", ""),
        ],
    )

    poop_imposter_brightness: bpy.props.FloatProperty(  # h4+
        name="Imposter Brightness",
        options=set(),
        description="The brightness of the imposter variant of this instance",
        default=0.0,
        min=0.0,
        override={'LIBRARY_OVERRIDABLE'},
    )

    poop_imposter_transition_distance: bpy.props.FloatProperty(
        name="Instanced Geometry Imposter Transition Distance",
        options=set(),
        description="The distance at which the instanced geometry transitions to its imposter variant",
        default=utils.wu(50),
        subtype='DISTANCE',
        override={'LIBRARY_OVERRIDABLE'},
    )

    poop_imposter_transition_distance_auto: bpy.props.BoolProperty(
        name="Instanced Geometry Imposter Transition Automatic",
        options=set(),
        description="Enable to let the engine set the imposter transition distance by object size",
        default=True,
        override={'LIBRARY_OVERRIDABLE'},
    )

    poop_streaming_priority: bpy.props.EnumProperty(  # h4+
        name="Streaming Priority",
        options=set(),
        description="When the game loads textures it will prioritise textures on those objects with a higher streaming priority",
        default="_connected_geometry_poop_streamingpriority_default",
        items=[
            (
                "_connected_geometry_poop_streamingpriority_default",
                "Default",
                "",
            ),
            (
                "_connected_geometry_poop_streamingpriority_higher",
                "Higher",
                "",
            ),
            (
                "_connected_geometry_poop_streamingpriority_highest",
                "Highest",
                "",
            ),
        ],
    )

    reach_poop_collision : bpy.props.BoolProperty(options={'HIDDEN'}) # INTERNAL

    poop_chops_portals: bpy.props.BoolProperty(
        name="Chops Portals",
        options=set(),
        description="Lets this instance chop a portal the same way structure geometry does",
        default=False,
        override={'LIBRARY_OVERRIDABLE'},
    )

    poop_does_not_block_aoe: bpy.props.BoolProperty(
        name="Does Not Block AOE",
        options=set(),
        description="Instance does not block area of effect damage",
        default=False,
        override={'LIBRARY_OVERRIDABLE'},
    )

    poop_excluded_from_lightprobe: bpy.props.BoolProperty(
        name="Excluded From Lightprobe",
        options=set(),
        description="Instanced geometry to be excluded from any lightprobes (e.g. placed airprobes)",
        default=False,
        override={'LIBRARY_OVERRIDABLE'},
    )

    poop_decal_spacing: bpy.props.BoolProperty(
        name="Decal Spacing",
        options=set(),
        description="Gives this instance a small offset from its game calculated position, so that it avoids z-fighting with another mesh",
        default=False,
        override={'LIBRARY_OVERRIDABLE'},
    )

    poop_remove_from_shadow_geometry: bpy.props.BoolProperty(  # H4+
        name="Dynamic Sun Shadow",
        options=set(),
        description="Shadows cast by this object are dynamic. Useful for example on tree leaves with foliage materials",
        default=False,
        override={'LIBRARY_OVERRIDABLE'},
    )

    poop_disallow_lighting_samples: bpy.props.BoolProperty(  # H4+
        name="Disallow Lighting Samples",
        options=set(),
        description="",
        default=False,
        override={'LIBRARY_OVERRIDABLE'},
    )

    poop_cinematic_properties: bpy.props.EnumProperty(  # h4+
        name="Cinematic Properties",
        options=set(),
        override={'LIBRARY_OVERRIDABLE'},
        description="Sets whether the instance should render only in cinematics, only outside of cinematics, or in both environments",
        default="_connected_geometry_poop_cinema_default",
        items=[
            (
                "_connected_geometry_poop_cinema_default",
                "Default",
                "Include both in cinematics and outside of them",
            ),
            (
                "_connected_geometry_poop_cinema_only",
                "Cinematic Only",
                "Only render in cinematics",
            ),
            (
                "_connected_geometry_poop_cinema_exclude",
                "Exclude From Cinematics",
                "Do not render in cinematics",
            ),
        ],
    )

    # poop light channel flags. Not included for now

    # portal PROPERTIES
    portal_type: bpy.props.EnumProperty(
        name="Portal Type",
        options=set(),
        override={'LIBRARY_OVERRIDABLE'},
        description="Determines how this portal handles visibilty culling",
        default="_connected_geometry_portal_type_two_way",
        items=[
            (
                "_connected_geometry_portal_type_no_way",
                "No Way",
                "Blocks all visibility",
            ),
            (
                "_connected_geometry_portal_type_one_way",
                "One Way",
                "Allows visibility through the front face (i.e the front facing normal), but culls visibility when viewed from the opposite side",
            ),
            (
                "_connected_geometry_portal_type_two_way",
                "Two Way",
                "Allows visibilty when viewed from either side",
            ),
        ],
    )

    portal_ai_deafening: bpy.props.BoolProperty(
        name="AI Deafening",
        options=set(),
        description="Stops AI hearing through this portal",
        default=False,
        override={'LIBRARY_OVERRIDABLE'},
    )

    portal_blocks_sounds: bpy.props.BoolProperty(
        name="Blocks Sounds",
        options=set(),
        description="Stops sound from travelling past this portal",
        default=False,
        override={'LIBRARY_OVERRIDABLE'},
    )

    portal_is_door: bpy.props.BoolProperty(
        name="Is Door",
        options=set(),
        description="Portal visibility is attached to a device machine state",
        default=False,
        override={'LIBRARY_OVERRIDABLE'},
    )

    # DECORATOR PROPERTIES
    decorator_lod: bpy.props.EnumProperty(
        name="Decorator Level of Detail",
        options=set(),
        override={'LIBRARY_OVERRIDABLE'},
        description="Level of detail of this object. The game will switch to this LOD at the appropriate range",
        items=[
            ("high", "High", ""),
            ("medium", "Medium", ""),
            ("low", "Low", ""),
            ("very_low", "Very Low", ""),
        ]
    )

    # WATER VOLUME PROPERTIES
    water_volume_depth: bpy.props.FloatProperty(  # this something which can probably be automated?
        name="Water Volume Depth",
        options=set(),
        description="How deep the water physics volume extends",
        default=utils.wu(20),
        min=0,
        subtype='DISTANCE',
        override={'LIBRARY_OVERRIDABLE'},
    )
    water_volume_flow_direction: bpy.props.FloatProperty(  # this something which can probably be automated?
        name="Water Volume Flow Direction",
        options=set(),
        description="The flow direction of this water volume mesh. It will carry physics objects in this direction. 0 matches the scene forward direction",
        subtype='ANGLE',
        override={'LIBRARY_OVERRIDABLE'},
    )

    water_volume_flow_velocity: bpy.props.FloatProperty(
        name="Water Volume Flow Velocity",
        options=set(),
        description="Velocity of the water flow physics",
        default=1,
        subtype='FACTOR',
        min=0,
        max=6,
        override={'LIBRARY_OVERRIDABLE'},
    )

    water_volume_fog_color: bpy.props.FloatVectorProperty(
        name="Water Volume Fog Color",
        options=set(),
        description="Color of the fog that renders when below the water surface",
        size=4,
        default=(0.322, 0.379, 0.466, 1.0),
        subtype="COLOR",
        min=0.0,
        max=1.0,
        override={'LIBRARY_OVERRIDABLE'},
    )

    water_volume_fog_murkiness: bpy.props.FloatProperty(
        name="Water Volume Fog Murkiness",
        options=set(),
        description="How murky, i.e. opaque, the underwater fog appears",
        default=0.5,
        min=0.0,
        override={'LIBRARY_OVERRIDABLE'},
    )

    def fog_clean_tag_path(self, context):
        self["fog_appearance_tag"] = utils.clean_tag_path(
            self["fog_appearance_tag"]
        ).strip('"')

    fog_appearance_tag: bpy.props.StringProperty(
        name="Fog Appearance Tag",
        description="Link the planar fog parameters tag that provides settings for this fog volume",
        update=fog_clean_tag_path,
        override={'LIBRARY_OVERRIDABLE'},
    )

    fog_volume_depth: bpy.props.FloatProperty(
        name="Fog Volume Depth",
        options=set(),
        description="How deep the fog volume volume extends",
        min=0,
        default=utils.wu(20),
        override={'LIBRARY_OVERRIDABLE'},
    )

    marker_uses_regions: bpy.props.BoolProperty(
        name="Marker All Regions",
        options=set(),
        description="Link this object to a specific region and consequently, permutation(s)",
        default=False,
        override={'LIBRARY_OVERRIDABLE'},
    )
    
    def get_marker_model_group(self):
        stripped_name = utils.dot_partition(self.id_data.name).strip("#_?$-")
        if self.marker_type == '_connected_geometry_marker_type_effects':
            if not stripped_name.startswith('fx_'):
                return "fx_" + stripped_name
        elif self.marker_type == '_connected_geometry_marker_type_garbage':
            if not stripped_name.startswith('garbage_'):
                return "garbage_" + stripped_name
                
        return stripped_name.lower()
    
    marker_model_group: bpy.props.StringProperty(
        name="Marker Group",
        description="The group this marker is assigned to. Defined by the Blender object name, ignoring any characters after the last period (if any) and legacy object prefix/suffixes [#_?$-]",
        get=get_marker_model_group,
    )

    def game_instance_clean_tag_path(self, context):
        self["marker_game_instance_tag_name"] = utils.clean_tag_path(
            self["marker_game_instance_tag_name"]
        ).strip('"')

    marker_game_instance_tag_name: bpy.props.StringProperty(
        name="Marker Game Instance Tag",
        description="Reference to the tag that should be placed at this marker in your scenario",
        update=game_instance_clean_tag_path,
        override={'LIBRARY_OVERRIDABLE'},
    )

    marker_game_instance_tag_variant_name: bpy.props.StringProperty(
        name="Marker Game Instance Tag Variant",
        description="Setting this will always create the given object variant provided that this name is a valid variant for the object",
        override={'LIBRARY_OVERRIDABLE'},
    )

    marker_always_run_scripts: bpy.props.BoolProperty(
        name="Always Run Scripts",
        options=set(),
        description="Tells this game object to always run scripts if it has any",
        default=True,
        override={'LIBRARY_OVERRIDABLE'},
    )
    
    # Decorators
    
    decorator_motion_scale: bpy.props.FloatProperty(
        name="Motion Scale",
        description="How much this decorator sways in the wind. Limited by the decorator type",
        default=0,
        subtype='FACTOR',
        min=0,
        max=1,
        options=set(),
        override={'LIBRARY_OVERRIDABLE'},
    )
    
    decorator_ground_tint: bpy.props.FloatProperty(
        name="Ground Tint Influence",
        description="How much tint this decorator takes from the diffuse color of the surface its on. The higher this is, the less influence taken from the decorator tint color",
        subtype='FACTOR',
        min=0,
        max=1,
        default=0,
        options=set(),
        override={'LIBRARY_OVERRIDABLE'},
    )
    
    decorator_tint: bpy.props.FloatVectorProperty(
        name="Tint",
        subtype='COLOR',
        size=3,
        default=(1.0, 1.0, 1.0),
        min=0,
        max=1,
        options=set(),
        override={'LIBRARY_OVERRIDABLE'},
    )
    
    # Prefab marker specific props
    
    prefab_lightmap_res: bpy.props.FloatProperty(
        name="Lightmap Resolution",
        options=set(),
        description="0 means override and the default resolution will be used. Determines how much texel space this prefab (if per pixel) will be given on the lightmap. Higher values do not automatically increase light resolution, instead the resolution is taken away from other prefabs. This value acts like a weight, deciding how the lightmap bitmap resolution gets divided up between prefabs",
        default=0,
        min=0,
        override={'LIBRARY_OVERRIDABLE'},
    )
    
    prefab_render_only: bpy.props.BoolProperty(
        name="Render Only",
        description="Prefab instance has no collision",
        options=set(),
        override={'LIBRARY_OVERRIDABLE'},
    )
    prefab_does_not_block_aoe: bpy.props.BoolProperty(
        name="Does Not Block AOE",
        options=set(),
        description="Prefab instance does not block area of effect damage",
        default=False,
        override={'LIBRARY_OVERRIDABLE'},
    )
    prefab_decal_spacing: bpy.props.BoolProperty(
        name="Decal Spacing",
        options=set(),
        description="Prefab instance set to have decal spacing. This gives the mesh a small offset from its game calculated position, so that it avoids z-fighting with another mesh",
        default=False,
        override={'LIBRARY_OVERRIDABLE'},
    )
    prefab_remove_from_shadow_geometry: bpy.props.BoolProperty(
        name="Dynamic Sun Shadow",
        options=set(),
        description="Shadows cast by this prefab instance are dynamic. Useful for example on tree leaves with foliage materials",
        default=False,
        override={'LIBRARY_OVERRIDABLE'},
    )
    prefab_disallow_lighting_samples: bpy.props.BoolProperty(
        name="Disallow Lighting Samples",
        options=set(),
        description="",
        default=False,
        override={'LIBRARY_OVERRIDABLE'},
    )
    
    prefab_excluded_from_lightprobe: bpy.props.BoolProperty(
        name="Excluded From Lightprobe",
        options=set(),
        description="Prefab instance is excluded from any lightprobes",
        default=False,
        override={'LIBRARY_OVERRIDABLE'},
    )
    
    prefab_cinematic_properties: bpy.props.EnumProperty(
        name="Cinematic Properties",
        options=set(),
        override={'LIBRARY_OVERRIDABLE'},
        description="Sets whether the prefab instance should render only in cinematics, only outside of cinematics, or in both environments",
        default="_connected_geometry_poop_cinema_default",
        items=[
            (
                "_connected_geometry_poop_cinema_default",
                "Default",
                "Include both in cinematics and outside of them",
            ),
            (
                "_connected_geometry_poop_cinema_only",
                "Cinematic Only",
                "Only render in cinematics",
            ),
            (
                "_connected_geometry_poop_cinema_exclude",
                "Exclude From Cinematics",
                "Do not render in cinematics",
            ),
        ],
    )
    
    prefab_lighting_items = [
        (
            "no_override",
            "No Override",
            "Does not override the lighting policy for this prefab instance",
        ),
        (
            "per_pixel",
            "Per Pixel",
            "Per pixel provides good fidelity and lighting variation but it takes up resolution in the lightmap bitmap",
        ),
        (
            "per_vertex",
            "Per Vertex",
            "Uses a separate and additional per-vertex lightmap budget. Cost is dependent purely on complexity/vert count of the mesh",
        ),
        (
            "single_probe",
            "Single Probe",
            "Cheap but effective lighting",
        ),
    ]

    prefab_lighting: bpy.props.EnumProperty(
        name="Lighting Policy",
        options=set(),
        description="Sets the lighting policy for this prefab instance",
        default="no_override",
        items=prefab_lighting_items,
        override={'LIBRARY_OVERRIDABLE'},
    )
    
    prefab_ao: bpy.props.BoolProperty(
        name="Ambient Occlusion",
        options=set(),
        description="Per vertex lighting gets ambient occlusion only",
        override={'LIBRARY_OVERRIDABLE'},
    )

    def prefab_pathfinding_items(self, context):
        items = []
        items.append(("no_override", "No Override", "Does not override the pathfinding policy for this prefab instance"))
        items.append(("cutout", "Walkable", "AI will be able to pathfind around and on this mesh"))
        items.append(("static", "Force Walkable", "AI will be able to pathfind around and on this mesh"))
        items.append(("none", "None", "This mesh will be ignored during pathfinding generation. AI will attempt to walk though it as if it is not there"))
        
        return items

    prefab_pathfinding: bpy.props.EnumProperty(
        name="Pathfinding Policy",
        options=set(),
        description="Sets the pathfinding policy for this prefab instance",
        items=prefab_pathfinding_items,
        override={'LIBRARY_OVERRIDABLE'},
    )

    prefab_imposter_policy: bpy.props.EnumProperty(
        name="Imposter Policy",
        options=set(),
        description="Sets the imposter policy for this prefab instance",
        default="no_override",
        override={'LIBRARY_OVERRIDABLE'},
        items=[
            (
                "no_override",
                "No Override",
                "Does not override the imposter policy for this prefab instance",
            ),
            (
                "polygon_default",
                "Polygon Default",
                "",
            ),
            (
                "polygon_high",
                "Polygon High",
                "",
            ),
            (
                "card_default",
                "Card Default",
                "",
            ),
            (
                "card_high",
                "Card High",
                "",
            ),
            ("never", "Never", ""),
        ],
    )

    prefab_imposter_brightness: bpy.props.FloatProperty(
        name="Imposter Brightness",
        options=set(),
        description="Sets the brightness of the imposter variant of this prefab. Leave at zero for no override",
        default=0.0,
        min=0.0,
        override={'LIBRARY_OVERRIDABLE'},
    )

    prefab_imposter_transition_distance: bpy.props.FloatProperty(
        name="Imposter Transition Distance",
        options=set(),
        description="The distance at which the instanced geometry transitions to its imposter variant",
        default=utils.wu(50),
        subtype='DISTANCE',
        override={'LIBRARY_OVERRIDABLE'},
    )

    prefab_imposter_transition_distance_auto: bpy.props.BoolProperty(
        name="Imposter Transition Override",
        options=set(),
        description="Enable to override the imposter transition distance of this prefab instance",
        default=True,
        override={'LIBRARY_OVERRIDABLE'},
    )

    prefab_streaming_priority: bpy.props.EnumProperty(
        name="Streaming Priority",
        options=set(),
        description="Sets the streaming priority for this prefab instance",
        default="no_override",
        override={'LIBRARY_OVERRIDABLE'},
        items=[
            (
                "no_override",
                "No Override",
                "Does not override the streaming priority for this prefab instance",
            ),
            (
                "_connected_geometry_poop_streamingpriority_default",
                "Default",
                "",
            ),
            (
                "_connected_geometry_poop_streamingpriority_higher",
                "Higher",
                "",
            ),
            (
                "_connected_geometry_poop_streamingpriority_highest",
                "Highest",
                "",
            ),
        ],
    )
    
    #####
    
    marker_velocity: bpy.props.FloatVectorProperty(
        name="Marker Velocity",
        options=set(),
        description="Manages the direction and speed with which an object created at this marker is given on spawn",
        subtype="VELOCITY",
        override={'LIBRARY_OVERRIDABLE'},
    )

    marker_pathfinding_sphere_vehicle: bpy.props.BoolProperty(
        name="Vehicle Only Pathfinding Sphere",
        options=set(),
        override={'LIBRARY_OVERRIDABLE'},
        description="This pathfinding sphere only affects vehicle pathfinding",
    )

    pathfinding_sphere_remains_when_open: bpy.props.BoolProperty(
        name="Pathfinding Sphere Remains When Open",
        options=set(),
        description="Pathfinding sphere remains even when a machine is open",
        override={'LIBRARY_OVERRIDABLE'},
    )

    pathfinding_sphere_with_sectors: bpy.props.BoolProperty(
        name="Pathfinding Sphere With Sectors",
        options=set(),
        description="Only active when the pathfinding policy of the object is set to Sectors",
        override={'LIBRARY_OVERRIDABLE'},
    )
    
    def poll_physics_constraint_target(self, object):
        return object.type == 'ARMATURE' or object.nwo.mesh_type == '_connected_geometry_mesh_type_physics'

    physics_constraint_parent: bpy.props.PointerProperty(
        name="Physics Constraint Parent",
        description="The physics object (or armature and bone) this constraint is attached to",
        type=bpy.types.Object,
        poll=poll_physics_constraint_target,
        override={'LIBRARY_OVERRIDABLE'},
    )

    physics_constraint_parent_bone: bpy.props.StringProperty(
        name="Physics Constraint Parent Bone",
        description="The bone that is attached to this constaint. The bone must have atleast one physics object child to be valid",
        override={'LIBRARY_OVERRIDABLE'},
    )

    physics_constraint_child: bpy.props.PointerProperty(
        name="Physics Constraint Child",
        description="The physics object (or armature and bone) this constraint is attached to",
        type=bpy.types.Object,
        poll=poll_physics_constraint_target,
        override={'LIBRARY_OVERRIDABLE'},
    )

    physics_constraint_child_bone: bpy.props.StringProperty(
        name="Physics Constraint Child Bone",
        description="The bone that is attached to this constaint. The bone must have atleast one physics object child to be valid",
        override={'LIBRARY_OVERRIDABLE'},
    )

    physics_constraint_type: bpy.props.EnumProperty(
        name="Constraint Type",
        options=set(),
        description="Whether this is a hinge or socket (i.e ragdoll) constraint",
        default="_connected_geometry_marker_type_physics_hinge_constraint",
        override={'LIBRARY_OVERRIDABLE'},
        items=[
            (
                "_connected_geometry_marker_type_physics_hinge_constraint",
                "Hinge",
                "Constraint that enables rotation around this marker on a single axis",
            ),
            (
                "_connected_geometry_marker_type_physics_socket_constraint",
                "Socket",
                "Constraint that enables rotation around this marker on any axis. For ragdolls",
            ),
        ],
    )

    physics_constraint_uses_limits: bpy.props.BoolProperty(
        name="Physics Constraint Uses Limits",
        options=set(),
        description="Allows setting of constraint limits",
        override={'LIBRARY_OVERRIDABLE'},
    )

    hinge_constraint_minimum: bpy.props.FloatProperty(
        name="Hinge Constraint Minimum",
        options=set(),
        description="Minimum angle of a physics hinge",
        subtype='ANGLE',
        default=radians(-180),
        min=radians(-180),
        max=radians(180),
        override={'LIBRARY_OVERRIDABLE'},
    )

    hinge_constraint_maximum: bpy.props.FloatProperty(
        name="Hinge Constraint Maximum",
        options=set(),
        description="Maximum angle of a physics hinge",
        subtype='ANGLE',
        default=radians(180),
        min=radians(-180),
        max=radians(180),
        override={'LIBRARY_OVERRIDABLE'},
    )

    cone_angle: bpy.props.FloatProperty(
        name="Cone Angle",
        options=set(),
        subtype='ANGLE',
        description="Cone angle",
        default=radians(90),
        min=0,
        max=radians(180),
        override={'LIBRARY_OVERRIDABLE'},
    )

    plane_constraint_minimum: bpy.props.FloatProperty(
        name="Plane Constraint Minimum",
        options=set(),
        description="",
        subtype='ANGLE',
        default=radians(-90),
        min=radians(-90),
        max=0,
        override={'LIBRARY_OVERRIDABLE'},
    )

    plane_constraint_maximum: bpy.props.FloatProperty(
        name="Plane Constraint Maximum",
        options=set(),
        description="",
        subtype='ANGLE',
        default=radians(90),
        min=0,
        max=radians(90),
        override={'LIBRARY_OVERRIDABLE'},
    )

    twist_constraint_start: bpy.props.FloatProperty(
        name="Twist Constraint Minimum",
        options=set(),
        subtype='ANGLE',
        description="Starting angle of a twist constraint",
        default=radians(-180),
        min=radians(-180),
        max=radians(180),
        override={'LIBRARY_OVERRIDABLE'},
    )

    twist_constraint_end: bpy.props.FloatProperty(
        name="Twist Constraint Maximum",
        options=set(),
        description="Ending angle of a twist constraint",
        default=radians(180),
        subtype='ANGLE',
        min=radians(-180),
        max=radians(180),
        override={'LIBRARY_OVERRIDABLE'},
    )

    def effect_clean_tag_path(self, context):
        self["marker_looping_effect"] = utils.clean_tag_path(
            self["marker_looping_effect"]
        ).strip('"')

    marker_looping_effect: bpy.props.StringProperty(
        name="Effect Path",
        description="Tag path to an effect tag",
        update=effect_clean_tag_path,
        override={'LIBRARY_OVERRIDABLE'},
    )

    def light_cone_clean_tag_path(self, context):
        self["marker_light_cone_tag"] = utils.clean_tag_path(
            self["marker_light_cone_tag"]
        ).strip('"')

    marker_light_cone_tag: bpy.props.StringProperty(
        name="Light Cone Tag Path",
        description="Tag path to a light cone tag",
        update=light_cone_clean_tag_path,
        override={'LIBRARY_OVERRIDABLE'},
    )

    marker_light_cone_color: bpy.props.FloatVectorProperty(
        name="Light Cone Color",
        options=set(),
        description="",
        subtype="COLOR",
        default=(1, 1, 1, 1),
        size=4,
        min=0.0,
        max=1.0,
        override={'LIBRARY_OVERRIDABLE'},
    )

    # marker_light_cone_alpha: bpy.props.FloatProperty(
    #     name="Light Cone Alpha",
    #     options=set(),
    #     description="",
    #     default=1.0,
    #     subtype="FACTOR",
    #     min=0.0,
    #     max=1.0,
    # )

    marker_light_cone_width: bpy.props.FloatProperty(
        name="Light Cone Width",
        options=set(),
        description="",
        default=5,
        min=0,
        override={'LIBRARY_OVERRIDABLE'},
    )

    marker_light_cone_length: bpy.props.FloatProperty(
        name="Light Cone Length",
        options=set(),
        description="",
        default=10,
        min=0,
        override={'LIBRARY_OVERRIDABLE'},
    )

    marker_light_cone_intensity: bpy.props.FloatProperty(
        name="Light Cone Intensity",
        options=set(),
        description="",
        default=1,
        min=0,
        override={'LIBRARY_OVERRIDABLE'},
    )

    def light_cone_curve_clean_tag_path(self, context):
        self["marker_light_cone_curve"] = utils.clean_tag_path(
            self["marker_light_cone_curve"]
        ).strip('"')

    marker_light_cone_curve: bpy.props.StringProperty(
        name="Light Cone Curve Tag Path",
        description="Tag path to a curve scalar tag",
        update=light_cone_curve_clean_tag_path,
        override={'LIBRARY_OVERRIDABLE'},
    )

    def get_region_name(self):
        scene_nwo = utils.get_scene_props()
        regions = scene_nwo.regions_table
        name = self.get("region_name", "")
        if not regions:
            return "default"
        region_names = [r.name for r in regions]
        old_region_names = [r.old for r in regions]
        if name not in region_names and name not in old_region_names:
            name = scene_nwo.regions_table[0].name
        # self['region_name'] = name
        return name

    def set_region_name(self, value):
        self['region_name'] = value

    region_name: bpy.props.StringProperty(
        name="Face Region",
        description="",
        get=get_region_name,
        set=set_region_name,
        override={'LIBRARY_OVERRIDABLE'},
    )

    def get_region_from_collection(self):
        region = utils.get_prop_from_collection(self.id_data, 'region')
        return region

    region_name_locked: bpy.props.StringProperty(
        name="Face Region",
        description="",
        get=get_region_from_collection,
    )

    def get_permutation_name(self):
        scene_nwo = utils.get_scene_props()
        permutations = scene_nwo.permutations_table
        name = self.get("permutation_name", "")
        if not permutations:
            return "default"
        permutation_names = [p.name for p in permutations]
        old_permutation_names = [p.old for p in permutations]
        if name not in permutation_names and name not in old_permutation_names:
            name = scene_nwo.permutations_table[0].name
        # self['permutation_name'] = name
        return name

    def set_permutation_name(self, value):
        self['permutation_name'] = value

    permutation_name: bpy.props.StringProperty(
        name="Permutation",
        default="default",
        description="The permutation of this object. Permutations get exported to separate files in scenario exports, or in model exports if the mesh type is one of render/collision/physics",
        get=get_permutation_name,
        set=set_permutation_name,
        override={'LIBRARY_OVERRIDABLE'},
    )

    def get_permutation_from_collection(self):
        permutation = utils.get_prop_from_collection(self.id_data, 'permutation')
        return permutation

    permutation_name_locked: bpy.props.StringProperty(
        name="Permutation",
        description="The permutation of this object",
        get=get_permutation_from_collection,
    )

    is_pca: bpy.props.BoolProperty(
        name="Frame PCA",
        options=set(),
        description="",
        default=False,
        override={'LIBRARY_OVERRIDABLE'},
    )
    
    export_collection: bpy.props.StringProperty(options={'HIDDEN'})
    
    # # GETTER PROPS
    # def get_object_id(self):
    #     current_id = self.get('object_id', 0)
    #     if current_id:
    #         return current_id
        
    #     rnd = random.Random()
    #     id = str(uuid.UUID(int=rnd.getrandbits(128)))
    #     self['object_id'] = id
    #     return id
    
    # ObjectID: bpy.props.StringProperty(
    #     get=get_object_id,
    # )

    # INSTANCED GEOMETRY ONLY

    instanced_collision: bpy.props.BoolProperty(
        name="Bullet Collision",
        override={'LIBRARY_OVERRIDABLE'},
    )
    instanced_physics: bpy.props.BoolProperty(
        name="Player Collision",
        override={'LIBRARY_OVERRIDABLE'},
    )

    cookie_cutter: bpy.props.BoolProperty(
        name="Cookie Cutter",
        override={'LIBRARY_OVERRIDABLE'},
    )

    #########

    toggle_face_defaults: bpy.props.BoolProperty(override={'LIBRARY_OVERRIDABLE'},)

    # MARKER PERMS
    marker_exclude_permutations : bpy.props.StringProperty(override={'LIBRARY_OVERRIDABLE'},)
    marker_include_permutations : bpy.props.StringProperty(override={'LIBRARY_OVERRIDABLE'},)
    
    # LIGHT OBJECT LEVEL PROPS
    
    # Reach
    
    light_game_type: bpy.props.EnumProperty(
        name="Light Type",
        options=set(),
        description="Determines how this light renders and whether it is dynamic (i.e. casts light without lightmapping) or static",
        default="_connected_geometry_bungie_light_type_default",
        items=[
            ("_connected_geometry_bungie_light_type_default", "Default", "Lightmap light. Requires lightmapping to complete for this light appear"),
            ("_connected_geometry_bungie_light_type_inlined", "Inlined", "For large lights"),
            ("_connected_geometry_bungie_light_type_rerender", "Rerender", "High quality shadowing light"),
            (
                "_connected_geometry_bungie_light_type_screen_space",
                "Screen Space",
                "Cheap low quality dynamic light",
            ),
            ("_connected_geometry_bungie_light_type_uber", "Uber", "High quality light"),
        ],
    )
    
    light_screenspace_has_specular: bpy.props.BoolProperty(
        name="Screenspace Light Has Specular",
        options=set(),
        description="",
        default=False,
    )
    
    light_bounce_ratio: bpy.props.FloatProperty(
        name="Light Bounce Ratio",
        options=set(),
        description="",
        default=1,
        min=0.0,
    )
    
    light_volume_distance: bpy.props.FloatProperty(
        name="Light Volume Distance",
        options=set(),
        description="",
    )

    light_volume_intensity: bpy.props.FloatProperty(
        name="Light Volume Intensity",
        options=set(),
        description="",
        default=1.0,
        min=0.0,
        soft_max=10.0,
        subtype="FACTOR",
    )

    light_fade_start_distance: bpy.props.FloatProperty(
        name="Light Fade Out Start",
        options=set(),
        description="The light starts to fade out when the camera is x units away",
        default=utils.wu(1),
        subtype='DISTANCE',
        unit='LENGTH',
    )

    light_fade_end_distance: bpy.props.FloatProperty(
        name="Light Fade Out End",
        options=set(),
        description="The light completely fades out when the camera is x units away",
        default=utils.wu(1.5),
        subtype='DISTANCE',
        unit='LENGTH',
    )
    
    def light_tag_clean_tag_path(self, context):
        self["light_tag_override"] = utils.clean_tag_path(self["light_tag_override"]).strip(
            '"'
        )

    light_tag_override: bpy.props.StringProperty(
        name="Light Tag Override",
        options=set(),
        description="",
        update=light_tag_clean_tag_path,
    )

    def light_shader_clean_tag_path(self, context):
        self["light_shader_reference"] = utils.clean_tag_path(
            self["light_shader_reference"]
        ).strip('"')

    light_shader_reference: bpy.props.StringProperty(
        name="Light Shader Reference",
        options=set(),
        description="",
        update=light_shader_clean_tag_path,
    )

    def light_gel_clean_tag_path(self, context):
        self["light_gel_reference"] = utils.clean_tag_path(self["light_gel_reference"]).strip(
            '"'
        )

    light_gel_reference: bpy.props.StringProperty(
        name="Light Gel Reference",
        options=set(),
        description="",
        update=light_gel_clean_tag_path,
    )

    def light_lens_flare_clean_tag_path(self, context):
        self["light_lens_flare_reference"] = utils.clean_tag_path(
            self["light_lens_flare_reference"]
        ).strip('"')

    light_lens_flare_reference: bpy.props.StringProperty(
        name="Light Lens Flare Reference",
        options=set(),
        description="",
        update=light_lens_flare_clean_tag_path,
    )
    
    light_mode: bpy.props.EnumProperty(
        name="Light Mode",
        options=set(),
        description="Type of light to export. Static and Analytic must be lightmapped to be visible, dynamic is always visible",
        default="_connected_geometry_light_mode_static",
        items=[
            (
                "_connected_geometry_light_mode_static",
                "Static",
                "Lights used in lightmapping",
            ),
            (
                "_connected_geometry_light_mode_dynamic",
                "Dynamic",
                "Lights that appear regardless of whether the map has been lightmapped",
            ),
            ("_connected_geometry_light_mode_analytic", "Analytic", "Similar to static lights but provides better results, however only one analytic light should ever light an object at a time"),
        ],
    )