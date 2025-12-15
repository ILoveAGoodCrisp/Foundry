"""Mesh and face level properties"""

from enum import Enum
from math import radians
import bpy

from .. import utils
from ..constants import face_prop_type_items, face_prop_descriptions

from ..tools.property_apply import apply_props_material_data

from ..icons import get_icon_id

class LightmapResolution(Enum):
    lowest = 1
    very_low = 2
    low = 3
    medium = 4
    high = 5
    very_high = 6
    highest = 7

class NWO_FaceProperties_ListItems(bpy.types.PropertyGroup):
    attribute_name: bpy.props.StringProperty(options={'HIDDEN'})
    
    face_count: bpy.props.IntProperty(options={'HIDDEN'})
    
    color: bpy.props.FloatVectorProperty(
        subtype="COLOR_GAMMA",
        size=3,
        default=(1.0, 1.0, 1.0),
        min=0,
        max=1,
        options=set(),
    )
    
    type: bpy.props.EnumProperty(
        options={'HIDDEN'},
        items=face_prop_type_items,
    )
    
    def get_all_faces(self):
        if not self.attribute_name:
            return True
        
        attribute = self.id_data.attributes.get(self.attribute_name)
        
        return attribute is None
    
    def get_name(self):
        match self.type:
            case 'face_mode':
                return f"{self.face_mode.replace('_', ' ').title()}"
            case 'collision_type':
                return f"{self.collision_type.replace('_', ' ').title()}"
            case 'face_sides':
                return "Two-Sided" if self.two_sided else "One-Sided"
            case 'transparent':
                return "Transparent" if self.transparent else "Opaque"
            case 'region':
                return f"region::{self.region}"
            case 'draw_distance':
                return f"Draw Distance {self.draw_distance.replace('detail_', '').title()}"
            case 'global_material':
                return f"material::{self.global_material}"
            case 'ladder':
                return "Ladder" if self.ladder else "No Ladder"
            case 'slip_surface':
                return "Slip Surface" if self.slip_surface else "No Slip Surface"
            case 'decal_offset':
                return "Decal Offset" if self.decal_offset else "No Decal Offset"
            case 'no_shadow':
                return "No Shadow" if self.no_shadow else "Shadow"
            case 'precise_position':
                return "Precise" if self.precise_position else "Not Precise"
            case 'uncompressed':
                return "Uncompressed" if self.uncompressed else "Compressed"
            case 'additional_compression':
                return "Additional Compression On" if self.additional_compression == 'force_on' else "Additional Compression Off"
            case 'no_lightmap':
                return "Exclude From Lightmap" if self.no_lightmap else "Include In Lightmap"
            case 'no_pvs':
                return "No PVS" if self.no_pvs else "PVS"
            case 'mesh_tessellation_density':
                return f"{self.mesh_tessellation_density[1:]} Tessellation"
            case 'lightmap_resolution_scale':
                return f"Lightmap Resolution: {LightmapResolution(int(self.lightmap_resolution_scale)).name.replace('_', ' ').title()}"
            case 'lightmap_ignore_default_resolution_scale':
                return "Default Lightmap Rez Ignored" if  self.lightmap_ignore_default_resolution_scale else "Using Default Lightmap Rez"
            case 'lightmap_chart_group':
                return f"Lightmap Chart Group {self.lightmap_chart_group}"
            case 'lightmap_type':
                return f"Lightmap Type {self.lightmap_type.replace('_', ' ').title()}"
            case 'lightmap_additive_transparency':
                return "Lightmap Transparency"
            case 'lightmap_transparency_override':
                return "Lightmap Transparency Overridden" if self.lightmap_transparency_override else "Lightmap Transparency Using Material"
            case 'lightmap_analytical_bounce_modifier':
                return f"Sunlight Bounce {round(self.lightmap_analytical_bounce_modifier, 2)}"
            case 'lightmap_general_bounce_modifier':
                return f"Light Bounce {round(self.lightmap_general_bounce_modifier, 2)}"
            case 'lightmap_translucency_tint_color':
                return "Lightmap Translucency Tint Color"
            case 'lightmap_lighting_from_both_sides':
                return "Lightmap Lighting Two-Sided" if self.lightmap_lighting_from_both_sides else "Lightmap Lighting One-Sided" 
            case 'emissive':
                return f"Emissive: Intensity {round(self.light_intensity, 2)}"
            case _:
                return "Something went wrong"
    
    name: bpy.props.StringProperty(get=get_name)
    
    face_mode: bpy.props.EnumProperty(
        name="Face Mode",
        description=face_prop_descriptions['face_mode'],
        options=set(),
        items=[
            ('normal', "Render & Collision", "Mesh will be used to build both render geometry and collision"),
            ('render_only', "Render Only", "Mesh will be visible but the game will not build a collision representation of this mesh. It will not be collidable to either objects or projectiles"),
            ('collision_only', "Collision Only", "Objects and projectiles will collide with this mesh but it will not be visible"),
            ('sphere_collision_only', "Sphere Collision Only", "Only physics objects collide with this mesh. Projectiles will pass through it. Invisible"),
            ('shadow_only', "Shadow Only", "Model only, invisible except to cast shadows"),
            ('lightmap_only', "Lightmap Only", "Mesh will be invisible and uncollidable. It will only be used by the lightmapper"),
            ('breakable', "Breakable", "Allows collision geometry to be destroyed. Mesh will be used to build both render geometry and collision. This type is non-functional in Halo 4 and Halo 2AMP"),
        ]
    )
    
    collision_type: bpy.props.EnumProperty(
        name="Collision Type",
        options=set(),
        description=face_prop_descriptions['collision_type'],
        items=[
            ("default", "Full", "Collision mesh that interacts with the physics objects and with projectiles"),
            ("invisible_wall", "Invisible Wall Collision", "Collision mesh that interacts with the physics objects only"),
            ("play_collision", "Player Collision", "Collision mesh that affects physics objects and physical projectiles, such as grenades"),
            ("bullet_collision", "Bullet Collision", "Collision mesh that only interacts with simple projectiles, such as bullets")
        ]
    )

    two_sided: bpy.props.BoolProperty(
        name="Two Sided",
        description=face_prop_descriptions['face_sides'],
        options=set(),
        default=True,
    )

    transparent: bpy.props.BoolProperty(
        name="Transparent",
        description=face_prop_descriptions['transparent'],
        options=set(),
        default=True,
    )

    face_sides_type: bpy.props.EnumProperty(
        name="Two Sided Policy",
        description="Set how the game should render the backfacing side of two-sided mesh faces",
        options=set(),
        items=[
            ("two_sided", "Default", "No special properties"),
            ("mirror", "Mirror", "Mirror backside normals from the frontside"),
            ("keep", "Keep", "Keep the same normal on each face side"),
        ]
    )

    region: bpy.props.StringProperty(
        name="Region",
        default="default",
        description=face_prop_descriptions['region'],
    )
    
    draw_distance: bpy.props.EnumProperty(
        name="Draw Distance",
        options=set(),
        description=face_prop_descriptions['draw_distance'],
        items=[
            ('normal', 'Default', ''),
            ('detail_mid', 'Medium', ''),
            ('detail_close', 'Close', ''),
        ]
    )

    global_material: bpy.props.StringProperty(
        name="Collision Material",
        default="",
        description=face_prop_descriptions['global_material'],
    )

    ladder: bpy.props.BoolProperty(
        name="Ladder",
        options=set(),
        description=face_prop_descriptions['ladder'],
        default=True,
    )

    slip_surface: bpy.props.BoolProperty(
        name="Slip Surface",
        options=set(),
        description=face_prop_descriptions['slip_surface'],
        default=True,
    )

    decal_offset: bpy.props.BoolProperty(
        name="Decal Offset",
        options=set(),
        description=face_prop_descriptions['decal_offset'],
        default=True,
    )
    
    no_shadow: bpy.props.BoolProperty(
        name="No Shadow",
        options=set(),
        description=face_prop_descriptions['no_shadow'],
        default=True,
    )

    precise_position: bpy.props.BoolProperty(
        name="Precise Position",
        options=set(),
        description=face_prop_descriptions['precise_position'],
        default=True,
    )
    
    uncompressed: bpy.props.BoolProperty(
        name="Uncompressed",
        options=set(),
        default=True,
        description=face_prop_descriptions['uncompressed'],
    )
    
    additional_compression: bpy.props.EnumProperty(
        name="Additional Compression",
        options=set(),
        description=face_prop_descriptions['additional_compression'],
        items=[
            ('force_on', "Force On", ""),
            ('force_off', "Force Off", ""),
        ]
    )

    no_lightmap: bpy.props.BoolProperty(
        name="Exclude From Lightmap",
        options=set(),
        description=face_prop_descriptions['no_lightmap'],
        default=True,
    )

    no_pvs: bpy.props.BoolProperty(
        name="Invisible To PVS",
        options=set(),
        description=face_prop_descriptions['no_pvs'],
        default=True,
    )
    
    def update_mesh_tessellation_density(self, context):
        if self.name.startswith("Tesselation::"):
            self.name = "Tesselation::" + self.mesh_tessellation_density.rpartition("_")[2]
    
    mesh_tessellation_density: bpy.props.EnumProperty(
        name="Mesh Tessellation Density",
        update=update_mesh_tessellation_density,
        options=set(),
        description=face_prop_descriptions['mesh_tessellation_density'],
        items=[
            (
                "_4x",
                "4x",
                "4 times",
            ),
            (
                "_9x",
                "9x",
                "9 times",
            ),
            (
                "_36x",
                "36x",
                "36 times",
            ),
        ],
    )

    #########

    # LIGHTMAP

    lightmap_resolution_scale: bpy.props.EnumProperty(
        name="Lightmap Resolution",
        options=set(),
        description=face_prop_descriptions['lightmap_resolution_scale'],
        default='3',
        items=[
            ('1', "Lowest", "Default resolution = 1"),
            ('2', "Very Low", "Default resolution = 4"),
            ('3', "Low", "Default resolution = 16"),
            ('4', "Medium", "Default resolution = 64"),
            ('5', "High", "Default resolution = 128"),
            ('6', "Very High", "Default resolution = 256"),
            ('7', "Highest", "Default resolution = 512"),
        ]
    )
    
    lightmap_ignore_default_resolution_scale: bpy.props.BoolProperty(
        name="Ignore Default Lightmap Resolution Scale",
        options=set(),
        description=face_prop_descriptions['lightmap_ignore_default_resolution_scale'],
        default=True,
    )
    
    lightmap_chart_group: bpy.props.IntProperty(
        name="Lightmap Chart Group",
        options=set(),
        description=face_prop_descriptions['lightmap_chart_group'],
        min=0,
        max=31,
    )

    lightmap_type: bpy.props.EnumProperty(
        name="Lightmap Type",
        options=set(),
        description=face_prop_descriptions['lightmap_type'],
        default="per_vertex",
        items=[
            ("per_pixel", "Per Pixel", "Per pixel provides good fidelity and lighting variation but it takes up resolution in the lightmap bitmap"),
            ("per_vertex", "Per Vertex", "Uses a separate and additional per-vertex lightmap budget. Cost is dependent purely on complexity/vert count of the mesh"),
        ],
    )
    
    lightmap_additive_transparency: bpy.props.FloatVectorProperty(
        name="Lightmap Additive Transparency",
        options=set(),
        description=face_prop_descriptions['lightmap_additive_transparency'],
        default=(1.0, 1.0, 1.0),
        subtype="COLOR",
        min=0.0,
        max=1.0,
    )

    lightmap_transparency_override: bpy.props.BoolProperty(
        name="Disable Lightmap Transparency",
        options=set(),
        description=face_prop_descriptions['lightmap_transparency_override'],
        default=True,
    )

    lightmap_analytical_bounce_modifier: bpy.props.FloatProperty(
        name="Sunlight Bounce Modifier",
        options=set(),
        description=face_prop_descriptions['lightmap_analytical_bounce_modifier'],
        default=1,
        max=1,
        min=0,
        subtype='FACTOR',
    )

    lightmap_general_bounce_modifier: bpy.props.FloatProperty(
        name="Light Bounce Modifier",
        options=set(),
        description=face_prop_descriptions['lightmap_general_bounce_modifier'],
        default=1,
        max=1,
        min=0,
        subtype='FACTOR',
    )

    lightmap_translucency_tint_color: bpy.props.FloatVectorProperty(
        name="Lightmap Translucency Tint Color",
        options=set(),
        description=face_prop_descriptions['lightmap_translucency_tint_color'],
        default=(1.0, 1.0, 1.0),
        subtype="COLOR",
        min=0.0,
        max=1.0,
    )

    lightmap_lighting_from_both_sides: bpy.props.BoolProperty(
        name="Lightmap Lighting From Both Sides",
        options=set(),
        description=face_prop_descriptions['lightmap_lighting_from_both_sides'],
        default=True,
    )

    # MATERIAL LIGHTING PROPERTIES
      
    def update_lighting_attenuation_falloff(self, context):
        if not utils.get_scene_props().transforming:
            if self.material_lighting_attenuation_falloff > self.material_lighting_attenuation_cutoff:
                self.material_lighting_attenuation_cutoff = self.material_lighting_attenuation_falloff
            
    def update_lighting_attenuation_cutoff(self, context):
        if not utils.get_scene_props().transforming:
            if self.material_lighting_attenuation_cutoff < self.material_lighting_attenuation_falloff:
                self.material_lighting_attenuation_falloff = self.material_lighting_attenuation_cutoff
    
    material_lighting_attenuation_cutoff: bpy.props.FloatProperty(
        name="Material Lighting Attenuation Cutoff",
        options=set(),
        description="Determines how far light travels before it stops. Leave this at 0 to for realistic light falloff/cutoff",
        min=0,
        default=0,
        update=update_lighting_attenuation_cutoff,
        subtype='DISTANCE',
        unit='LENGTH',
    )

    material_lighting_attenuation_falloff: bpy.props.FloatProperty(
        name="Material Lighting Attenuation Falloff",
        options=set(),
        description="Determines how far light travels before its power begins to falloff",
        min=0,
        default=0,
        update=update_lighting_attenuation_falloff,
        subtype='DISTANCE',
        unit='LENGTH',
    )

    material_lighting_emissive_focus: bpy.props.FloatProperty(
        name="Material Lighting Emissive Focus",
        options=set(),
        description="Controls the spread of the light. 180 degrees will emit light in a hemisphere from each point, 0 degrees will emit light nearly perpendicular to the surface",
        min=0,
        default=radians(180), 
        max=radians(180),
        subtype="ANGLE",
    )

    material_lighting_emissive_color: bpy.props.FloatVectorProperty(
        name="Material Lighting Emissive Color",
        options=set(),
        description="The RGB value of the emitted light",
        default=(1.0, 1.0, 1.0),
        subtype="COLOR",
        min=0.0,
        max=1.0,
    )

    material_lighting_emissive_per_unit: bpy.props.BoolProperty(
        name="Normalize",
        options=set(),
        description="When an emissive surface is scaled, determines if the amount of emitted light should be spread out across the surface or increased/decreased to keep a regular amount of light emission per unit area",
        default=False,
    )

    material_lighting_emissive_power: bpy.props.FloatProperty(
        name="Material Lighting Emissive Quality",
        options=set(),
        description="The power of the emissive surface",
        min=0,
        default=10,
        subtype='POWER',
        unit='POWER',
    )
    
    def get_light_intensity(self):
        return utils.calc_emissive_intensity(self.material_lighting_emissive_power, utils.get_export_scale(bpy.context) ** 2)
    
    def set_light_intensity(self, value):
        self['light_intensity_value'] = value
        
    def update_light_intensity(self, context):
        self.material_lighting_emissive_power = utils.calc_emissive_energy(self.material_lighting_emissive_power, utils.get_export_scale(context) ** -2 * self.light_intensity_value)

    light_intensity: bpy.props.FloatProperty(
        name="Light Intensity",
        options=set(),
        description="The intensity of this light expressed in the units the game uses",
        get=get_light_intensity,
        set=set_light_intensity,
        update=update_light_intensity,
        min=0,
        default=1,
    )
    
    light_intensity_value: bpy.props.FloatProperty(options={'HIDDEN'})
    
    debug_emissive_index: bpy.props.IntProperty(options={'HIDDEN'})

    material_lighting_emissive_quality: bpy.props.FloatProperty(
        name="Material Lighting Emissive Quality",
        options=set(),
        description="Controls the quality of the shadows cast by a complex occluder. For instance, a light casting shadows of tree branches on a wall would require a higher quality to get smooth shadows",
        default=1,
        min=0,
    )

    material_lighting_use_shader_gel: bpy.props.BoolProperty(
        name="Material Lighting Use Shader Gel",
        options=set(),
        description="",
        default=False,
    )

    material_lighting_bounce_ratio: bpy.props.FloatProperty(
        name="Material Lighting Bounce Ratio",
        options=set(),
        description="0 will bounce no energy. 1 will bounce full energy. Any value greater than 1 will exaggerate the amount of bounced light. Affects 1st bounce only",
        default=1,
        min=0,
    )


class NWO_MeshPropertiesGroup(bpy.types.PropertyGroup):
    proxy_collision: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_cookie_cutter: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics0: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics1: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics2: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics3: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics4: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics5: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics6: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics7: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics8: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics9: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics10: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics11: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics12: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics13: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics14: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics15: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics16: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics17: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics18: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics19: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics20: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics21: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics22: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics23: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics24: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics25: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics26: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics27: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics28: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics29: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics30: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics31: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics32: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics33: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics34: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics35: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics36: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics37: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics38: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics39: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics40: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics41: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics42: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics43: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics44: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics45: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics46: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics47: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics48: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics49: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics50: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics51: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics52: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics53: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics54: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics55: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics56: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics57: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics58: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics59: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics60: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics61: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics62: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics63: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics64: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics65: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics66: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics67: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics68: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics69: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics70: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics71: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics72: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics73: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics74: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics75: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics76: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics77: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics78: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics79: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics80: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics81: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics82: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics83: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics84: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics85: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics86: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics87: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics88: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics89: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics90: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics91: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics92: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics93: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics94: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics95: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics96: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics97: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics98: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics99: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics100: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics101: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics102: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics103: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics104: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics105: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics106: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics107: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics108: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics109: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics110: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics111: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics112: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics113: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics114: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics115: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics116: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics117: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics118: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics119: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics120: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics121: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics122: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics123: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics124: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics125: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics126: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics127: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics128: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics129: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics130: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics131: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics132: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics133: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics134: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics135: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics136: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics137: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics138: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics139: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics140: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics141: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics142: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics143: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics144: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics145: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics146: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics147: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics148: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics149: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics150: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics151: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics152: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics153: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics154: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics155: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics156: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics157: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics158: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics159: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics160: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics161: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics162: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics163: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics164: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics165: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics166: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics167: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics168: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics169: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics170: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics171: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics172: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics173: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics174: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics175: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics176: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics177: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics178: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics179: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics180: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics181: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics182: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics183: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics184: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics185: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics186: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics187: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics188: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics189: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics190: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics191: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics192: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics193: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics194: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics195: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics196: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics197: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics198: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics199: bpy.props.PointerProperty(type=bpy.types.Object)

    
    from_vert_normals: bpy.props.BoolProperty(
        name="Uses Custom Vertex Normals",
        description="True if this mesh uses vertex custom normals. This will only take effect if the mesh has custom normals. Only set this manually if you know what you are doing"
    )
    
    def update_obb_volume_type(self, context):
        if utils.get_prefs().apply_materials:
            _, material = utils.mesh_and_material(self.obb_volume_type.lower(), context)
            apply_props_material_data(self.id_data, material)
    
    def obb_volume_types(self, context) -> list:
        return [
            ('LIGHTMAP_EXCLUSION', "Lightmap Exclusion", "", get_icon_id("lightmap_exclude"), 0),
            ('STREAMING_VOLUME', "Texture Streaming", "", get_icon_id("streaming"), 1),
        ]
    
    obb_volume_type: bpy.props.EnumProperty(
        name="Type",
        items=obb_volume_types,
        update=update_obb_volume_type,
        default=0,
        options=set(),
    )
    
    def update_boundary_surface_types(self, context):
        if utils.get_prefs().apply_materials:
            _, material = utils.mesh_and_material(self.boundary_surface_type.lower(), context)
            apply_props_material_data(self.id_data, material)
            
    
    def boundary_surface_types(self, context) -> list:
        return [
            ('SOFT_CEILING', "Soft Ceiling", "", get_icon_id("soft_ceiling"), 0),
            ('SOFT_KILL', "Kill Timer", "", get_icon_id("soft_kill"), 1),
            ('SLIP_SURFACE', "Slip Surface", "", get_icon_id("slip_surface"), 2)
        ]
    
    boundary_surface_type: bpy.props.EnumProperty(
        name="Type",
        items=boundary_surface_types,
        update=update_boundary_surface_types,
        default=0,
        options=set(),
    )
    
    mesh_type: bpy.props.StringProperty(
        name="Mesh Type",
        default='_connected_geometry_mesh_type_default',
        options=set(),
    )

    face_props: bpy.props.CollectionProperty(
        type=NWO_FaceProperties_ListItems, override={"USE_INSERTION"}
    )

    face_props_active_index: bpy.props.IntProperty(
        name="Index for Face Property",
        options=set(),
    )

    highlight: bpy.props.BoolProperty(
        options=set(),
        name="Highlight",
    )
    
    def poop_collision_type_items(self, context):
        items = []
        items.append(("default", "Full", "Collision mesh that interacts with the physics objects and with projectiles"))
        items.append(("invisible_wall", "Sphere Collision", "Collision mesh that interacts with the physics objects only"))
        items.append(("play_collision", "Player Collision", "Collision mesh that affects physics objects and physical projectiles, such as grenades"))
        items.append(("bullet_collision", "Bullet Collision", "Collision mesh that only interacts with simple projectiles, such as bullets"))
        
        return items