import bpy

from ..utils import get_game
from ..bitmap_usage import bitmap_type_items

class NWO_ImagePropertiesGroup(bpy.types.PropertyGroup):
    bitmap_name: bpy.props.StringProperty(
        name="Name",
    )
    def bitmap_type_items(self, context):
        return bitmap_type_items(get_game(use_external=False))

    bitmap_type: bpy.props.EnumProperty(
        name="Type",
        options=set(),
        items=bitmap_type_items,
    )
    bitmap_shape: bpy.props.EnumProperty(
        name="Texture Shape",
        description="Halo CE and Halo 2 store texture shape separately from usage",
        items=[('auto', 'Automatic', 'Infer shape from the image name; preserve existing tags', 0),
               ('2d', '2D Texture', '', 1), ('3d', '3D Texture', '', 2),
               ('cube', 'Cube Map', '', 3), ('sprites', 'Sprites', '', 4),
               ('interface', 'Interface Bitmap', '', 5)],
        default='auto',
        options=set(),
    )
    append_type: bpy.props.BoolProperty(
        name="Append Type",
        options=set(),
        description="Appends the type of this bitmap to its exported name",
    )

    export : bpy.props.BoolProperty(
        name="Export",
        description="Toggles whether this image should be exported as a bitmap",
        default=True,
        options=set(),
    )

    use_image_path : bpy.props.BoolProperty(
        name="Use Image Path",
        description="Toggles whether this image should be exported as a bitmap",
        options=set(),
    )

    reexport_tiff : bpy.props.BoolProperty(
        name="Re-Export Image",
        options=set(),
        default=False,
        description="Forces this bitmap's source file to be re-exported from Blender. By default the Bitmap exporter will skip exporting a new file provided the following conditions are met: a TIFF file already exists, is not packed data in this blend, and is located within the project data directory",
    )

    filepath : bpy.props.StringProperty()
    source_name : bpy.props.StringProperty()
