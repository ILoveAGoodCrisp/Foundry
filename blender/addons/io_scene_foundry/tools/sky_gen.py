import bpy

class NWO_OT_SkyGenerate(bpy.types.Operator):
    bl_idname = "nwo.sky_generate"
    bl_label = "Generate Sky"
    bl_description = "Generates a skydome and skylights ready for export to the game"
    bl_options = {'REGISTER', 'UNDO'}
    
    # Main params
    build_sky_from_map: bpy.props.BoolProperty()
    input_sky_map_name: bpy.props.StringProperty()
    generate_type: bpy.props.EnumProperty(
        name="Type",
        items=[
            ('BOTH', "Skylights & Skydome", ""),
            ('SKYLIGHT', "Skylights Only", ""),
            ('SKYDOME', "Skydome Only", ""),
        ]
    )
    
    lit_objects_by_sky: bpy.props.BoolProperty()
    generate_light_count: bpy.props.IntProperty()
    
    # Dome Params
    lattitude_slices: bpy.props.IntProperty()
    longitude_slices: bpy.props.IntProperty()
    horizontal_fov: bpy.props.FloatProperty()
    vertical_fov: bpy.props.FloatProperty()
    
    # Light params
    sun_theta: bpy.props.FloatProperty()
    sun_phi: bpy.props.FloatProperty()
    turpidity: bpy.props.FloatProperty()
    sky_type: bpy.props.EnumProperty()
    cie_sky_number: bpy.props.IntProperty()
    sky_intensity: bpy.props.FloatProperty()
    sun_intensity: bpy.props.FloatProperty()
    luminance_only: bpy.props.IntProperty()
    exposure: bpy.props.FloatProperty()
    sun_cone_angle: bpy.props.FloatProperty()
    custom_sun_color_override: bpy.props.BoolProperty()
    
    

    def execute(self, context):
        
        return {"FINISHED"}




class SkyGen:
    pass