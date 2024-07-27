import bpy

class NWO_CollectionPropertiesGroup(bpy.types.PropertyGroup):

    def type_items(self, context):
        items = []
        r_name = "Region"
        p_name = "Permutation"
        if context.scene.nwo.asset_type == "scenario":
            r_name = "BSP"
            p_name = "BSP Category"

        items.append(("none", "None", ""))
        items.append(("region", r_name, ""))
        items.append(("permutation", p_name, ""))
        items.append(("exclude", "Exclude", ""))

        return items

    type: bpy.props.EnumProperty(
        name="Collection Type",
        items=type_items,
        )

    region: bpy.props.StringProperty(
        name="Region",
    )

    permutation: bpy.props.StringProperty(
        name="Permutation",
    )