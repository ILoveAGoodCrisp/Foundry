import bpy
from ..utils import get_scene_props

class NWO_CollectionPropertiesGroup(bpy.types.PropertyGroup):
    def type_items(self, context):
        items = []
        r_name = "Region"
        p_name = "Permutation"
        if get_scene_props().asset_type == "scenario":
            r_name = "BSP"
            p_name = "BSP Category"

        items.append(("none", "None", ""))
        items.append(("region", r_name, ""))
        items.append(("permutation", p_name, ""))
        items.append(("exclude", "Exclude", ""))

        return items
    
    def update_color(self, context):
        match self.type:
            case 'none':
                self.id_data.color_tag = 'NONE'
            case 'region':
                self.id_data.color_tag = 'COLOR_05'
            case 'permutation':
                self.id_data.color_tag = 'COLOR_04'
            case 'exclude':
                self.id_data.color_tag = 'COLOR_01'

    type: bpy.props.EnumProperty(
        name="Collection Type",
        items=type_items,
        update=update_color,
        )

    region: bpy.props.StringProperty(
        name="Region",
    )

    permutation: bpy.props.StringProperty(
        name="Permutation",
    )
    
    game_object_path: bpy.props.StringProperty(options={'HIDDEN'})
    game_object_variant: bpy.props.StringProperty(options={'HIDDEN'})
    