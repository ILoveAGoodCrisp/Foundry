import bpy
from ... import utils

class NWO_OT_HaloLightToggle(bpy.types.Operator):
    bl_idname = "nwo.halo_light_toggle"
    bl_label = "Halo Light Toggle"
    bl_description = "Toggles whether this light is a Halo light. A halo light works like a standard light in 3DS Max, with the ability to set custom light falloff and cutoff. This will apply to all selected lights. You will need to use Cycles to correctly render this light"
    bl_options = {"UNDO", "REGISTER"}

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'LIGHT' and context.object.data.type != 'SUN'
    
    toggle_on: bpy.props.BoolProperty(
        name="On",
        default=True,
    )

    def execute(self, context):
        
        light_data = {ob.data for ob in context.selected_objects if ob.type == 'LIGHT' and ob.data.type != 'SUN'}
        
        if self.toggle_on:
            for light in light_data:
                utils.make_halo_light(light, intensity_from_power=True)
            self.report({'INFO'}, f"Converted {len(light_data)} light{'' if len(light_data) == 1 else 's'}")
        else:
            for light in light_data:
                light.use_nodes = False
                light.use_custom_distance = False
                light.energy = utils.calc_light_energy(light, light.nwo.light_intensity)
            self.report({'INFO'}, f"Disabled Halo light properties for {len(light_data)} light{'' if len(light_data) == 1 else 's'}")
        
        return {"FINISHED"}
