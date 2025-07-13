from math import radians
from pathlib import Path
import bpy
from bpy.types import PropertyGroup
from bpy.props import StringProperty, BoolProperty
from .. import utils
from ..tools.materials import special_materials, convention_materials


class NWO_MaterialPropertiesGroup(PropertyGroup):
    def update_shader(self, context):
        self["shader_path"] = utils.clean_tag_path(self["shader_path"])
        shader_path = self.shader_path
        full_path = Path(utils.get_tags_path(), shader_path)
        if utils.get_prefs().update_materials_on_shader_path and self.prev_shader_path != self.shader_path and full_path.exists() and bpy.ops.nwo.shader_to_nodes.poll():
            bpy.ops.nwo.shader_to_nodes(mat_name=self.id_data.name)
            
        self.prev_shader_path = self.shader_path

    shader_path: StringProperty(
        name="Shader Path",
        description="The path to a shader. This can either be a relative path, or if you have added your Editing Kit Path to add on preferences, the full path. Include the file extension as this will set the shader/material type",
        update=update_shader,
        options=set(),
    )
    
    prev_shader_path: StringProperty(options={'HIDDEN'})

    def recursive_image_search_object(self, tree_owner, object):
        nodes = tree_owner.node_tree.nodes
        for n in nodes:
            if getattr(n, "image", 0):
                if n.image == object:
                    return True
            elif n.type == 'GROUP':
                image_found = self.recursive_image_search_object(n, object)
                if image_found:
                    return True

    def poll_active_image(self, object):
        mat = bpy.context.object.active_material
        return self.recursive_image_search_object(mat, object)

    active_image : bpy.props.PointerProperty(
        type=bpy.types.Image,
        poll=poll_active_image,
        )
    
    def update_material_shader(self, context):
        self["material_shader"] = utils.clean_tag_path(self["material_shader"]).strip('"')

    material_shader : StringProperty(
        name="Material Shader",
        description="Tag relative path to a material shader. Generated material tag will use this material shader. Leave blank to let the material exporter choose the best material_shader based on the current material node setup",
        options=set(),
        update=update_material_shader,
    )

    shader_type_items = [
        (".shader", "Default", ""),
        (".shader_cortana", "Cortana", ""),
        (".shader_custom", "Custom", ""),
        (".shader_decal", "Decal", ""),
        (".shader_foliage", "Foliage", ""),
        (".shader_fur", "Fur", ""),
        (".shader_fur_stencil", "Fur Stencil", ""),
        (".shader_glass", "Glass", ""),
        (".shader_halogram", "Halogram", ""),
        (".shader_mux", "Mux", ""),
        (".shader_mux_material", "Mux Material", ""),
        (".shader_screen", "Screen", ""),
        (".shader_skin", "Skin", ""),
        (".shader_terrain", "Terrain", ""),
        (".shader_water", "Water", ""),
    ]

    shader_type : bpy.props.EnumProperty(
        name="Shader Type",
        description="Type of shader to generate",
        items=shader_type_items,
        options=set(),
    )

    uses_blender_nodes : BoolProperty(
        name="Uses Blender Nodes",
        description="Allow tag to be updated from Blender Shader nodes",
        options=set(),
    )
    
    
    game_functions: bpy.props.StringProperty(options={'HIDDEN'}) # comma delimited list of functions for this shader
    object_functions: bpy.props.StringProperty(options={'HIDDEN'})
    sequence_drivers: bpy.props.StringProperty(options={'HIDDEN'})
    
    def get_special_material(self):
        material_name: str = self.id_data.name
        return material_name.startswith(tuple([m.name for m in special_materials]))
    
    SpecialMaterial: BoolProperty(
        options={'HIDDEN', 'SKIP_SAVE'},
        get=get_special_material,
    )
    
    def get_convention_material(self):
        material_name: str = self.id_data.name
        return material_name.startswith(tuple([m.name for m in convention_materials]))
    
    ConventionMaterial: BoolProperty(
        options={'HIDDEN', 'SKIP_SAVE'},
        get=get_convention_material,
    )
    
    def get_render_material(self):
        return not (self.id_data.is_grease_pencil or self.SpecialMaterial or self.ConventionMaterial)
    
    RenderMaterial: BoolProperty(
        options={'HIDDEN', 'SKIP_SAVE'},
        get=get_render_material,
    )
    
    # MATERIAL PROPERTIES
    
    def get_has_lightmap_props(self):
        return (
            self.lightmap_additive_transparency_active or
            self.lightmap_ignore_default_resolution_scale_active or
            self.lightmap_resolution_scale_active or
            self.lightmap_type_active or
            self.lightmap_transparency_override_active or
            self.lightmap_analytical_bounce_modifier_active or
            self.lightmap_general_bounce_modifier_active or
            self.lightmap_translucency_tint_color_active or
            self.lightmap_lighting_from_both_sides_active or
            (self.emissive_active and self.material_lighting_emissive_power > 0)
        )
    
    has_lightmap_props: bpy.props.BoolProperty(
        options={'HIDDEN'},
        get=get_has_lightmap_props,
    )
    
    def update_lightmap_additive_transparency(self, context):
        self.lightmap_additive_transparency_active = True

    lightmap_additive_transparency_active: bpy.props.BoolProperty()
    lightmap_additive_transparency: bpy.props.FloatVectorProperty(
        name="lightmap Additive Transparency",
        options=set(),
        description="Overrides the amount and color of light that will pass through the surface. Tint color will override the alpha blend settings in the shader",
        default=(1.0, 1.0, 1.0),
        subtype="COLOR",
        min=0.0,
        max=1.0,
        update=update_lightmap_additive_transparency,
    )

    def update_lightmap_ignore_default_resolution_scale(self, context):
        self.lightmap_ignore_default_resolution_scale_active = True

    lightmap_ignore_default_resolution_scale_active: bpy.props.BoolProperty()
    lightmap_ignore_default_resolution_scale: bpy.props.BoolProperty(
        name="Ignore Default Lightmap Resolution Scale",
        options=set(),
        description="Different render mesh types can have different default lightmap resolutions. Enabling this prevents the default for a given type being used",
        default=True,
        update=update_lightmap_ignore_default_resolution_scale,
    )

    def update_lightmap_resolution_scale(self, context):
        self.lightmap_resolution_scale_active = True

    lightmap_resolution_scale_active: bpy.props.BoolProperty()
    lightmap_resolution_scale: bpy.props.IntProperty(
        name="Resolution Scale",
        options=set(),
        default=3,
        min=1,
        max=7,
        description="Determines how much texel space the faces will be given on the lightmap. 1 means less space for the faces, while 7 means more space for the faces. The relationships can be tweaked in the .scenario tag under the bsp tag block",
        update=update_lightmap_resolution_scale,
    )

    # def update_lightmap_photon_fidelity(self, context):
    #     self.lightmap_photon_fidelity_active = True

    # lightmap_photon_fidelity_active: bpy.props.BoolProperty()
    # lightmap_photon_fidelity: bpy.props.EnumProperty(
    #     name="Photon Fidelity",
    #     options=set(),
    #     update=update_lightmap_photon_fidelity,
    #     description="H4+ only",
    #     default="_connected_material_lightmap_photon_fidelity_normal",
    #     items=[
    #         (
    #             "_connected_material_lightmap_photon_fidelity_normal",
    #             "Normal",
    #             "",
    #         ),
    #         (
    #             "_connected_material_lightmap_photon_fidelity_medium",
    #             "Medium",
    #             "",
    #         ),
    #         ("_connected_material_lightmap_photon_fidelity_high", "High", ""),
    #         ("_connected_material_lightmap_photon_fidelity_none", "None", ""),
    #     ],
    # )

    def update_lightmap_type(self, context):
        self.lightmap_type_active = True

    lightmap_type_active: bpy.props.BoolProperty()
    lightmap_type: bpy.props.EnumProperty(
        name="Lightmap Type",
        options=set(),
        update=update_lightmap_type,
        description="How this should be lit while lightmapping",
        default="_connected_material_lightmap_type_per_pixel",
        items=[
            ("_connected_material_lightmap_type_per_pixel", "Per Pixel", "Per pixel provides good fidelity and lighting variation but it takes up resolution in the lightmap bitmap"),
            ("_connected_material_lightmap_type_per_vertex", "Per Vertex", "Uses a separate and additional per-vertex lightmap budget. Cost is dependent purely on complexity/vert count of the mesh"),
        ],
    )
    
    def update_lightmap_transparency_override(self, context):
        self.lightmap_transparency_override_active = True

    lightmap_transparency_override_active: bpy.props.BoolProperty()
    lightmap_transparency_override: bpy.props.BoolProperty(
        name="Disable Lightmap Transparency",
        options=set(),
        description="Disables the transparency of any mesh faces this property is applied for the purposes of lightmapping. For example on a mesh using an invisible shader/material, shadow will still be cast",
        default=True,
        update=update_lightmap_transparency_override,
    )

    def update_lightmap_analytical_bounce_modifier(self, context):
        self.lightmap_analytical_bounce_modifier_active = True

    lightmap_analytical_bounce_modifier_active: bpy.props.BoolProperty()
    lightmap_analytical_bounce_modifier: bpy.props.FloatProperty(
        name="Lightmap Analytical Bounce Modifier",
        options=set(),
        description="For analytical lights such as the sun. 0 will bounce no energy. 1 will bounce full energy",
        default=1,
        max=1,
        min=0,
        subtype='FACTOR',
        update=update_lightmap_analytical_bounce_modifier,
    )

    def update_lightmap_general_bounce_modifier(self, context):
        self.lightmap_general_bounce_modifier_active = True

    lightmap_general_bounce_modifier_active: bpy.props.BoolProperty()
    lightmap_general_bounce_modifier: bpy.props.FloatProperty(
        name="Lightmap General Bounce Modifier",
        options=set(),
        description="For general lights, such as placed spot lights. 0 will bounce no energy. 1 will bounce full energy",
        default=1,
        max=1,
        min=0,
        subtype='FACTOR',
        update=update_lightmap_general_bounce_modifier,
    )

    def update_lightmap_translucency_tint_color(self, context):
        self.lightmap_translucency_tint_color_active = True

    lightmap_translucency_tint_color_active: bpy.props.BoolProperty()
    lightmap_translucency_tint_color: bpy.props.FloatVectorProperty(
        name="Lightmap Translucency Tint Color",
        options=set(),
        description="Overrides the color of the shadow and color of light after it passes through a surface",
        default=(1.0, 1.0, 1.0),
        subtype="COLOR",
        min=0.0,
        max=1.0,
        update=update_lightmap_translucency_tint_color,
    )

    def update_lightmap_lighting_from_both_sides(self, context):
        self.lightmap_lighting_from_both_sides_active = True

    lightmap_lighting_from_both_sides_active: bpy.props.BoolProperty()
    lightmap_lighting_from_both_sides: bpy.props.BoolProperty(
        name="Lightmap Lighting From Both Sides",
        options=set(),
        description="",
        default=True,
        update=update_lightmap_lighting_from_both_sides,
    )

    # MATERIAL LIGHTING PROPERTIES

    emissive_active: bpy.props.BoolProperty()
            
    def update_lighting_attenuation_falloff(self, context):
        if not context.scene.nwo.transforming:
            if self.material_lighting_attenuation_falloff > self.material_lighting_attenuation_cutoff:
                self.material_lighting_attenuation_cutoff = self.material_lighting_attenuation_falloff
            
    def update_lighting_attenuation_cutoff(self, context):
        if not context.scene.nwo.transforming:
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
        name="Material Lighting Emissive Per Unit",
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
    )
    
    light_intensity_value: bpy.props.FloatProperty(options={'HIDDEN'})

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