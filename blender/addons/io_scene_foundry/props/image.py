import os
import bpy

from ..utils import clean_tag_path, get_asset_path, is_corinth, valid_nwo_asset

class NWO_ImagePropertiesGroup(bpy.types.PropertyGroup):
    bitmap_name: bpy.props.StringProperty(
        name="Name",
    )
    def bitmap_type_items(self, context):
        h4 = is_corinth(context)
        items = []
        items.append(("default", "Default", "Usage is defined by the suffix of the bitmap name"))
        items.append(("Diffuse Map", "Diffuse Map", ""))
        items.append(("Specular Map", "Specular Map", ""))
        items.append(("Bump Map (from Height Map)", "Bump Map (from Height Map)", ""))
        items.append(("Detail Bump Map (from Height Map - fades out)", "Detail Bump Map (from Height Map - fades out)", ""))
        items.append(("Detail Map", "Detail Map", ""))
        items.append(("Self-Illum Map", "Self-Illum Map", ""))
        items.append(("Change Color Map", "Change Color Map", ""))
        items.append(("Cube Map (Reflection Map)", "Cube Map (Reflection Map)", ""))
        items.append(("Sprite (Additive, Black Background)", "Sprite (Additive, Black Background)", ""))
        items.append(("Sprite (Blend, White Background)", "Sprite (Blend, White Background)", ""))
        items.append(("Sprite (Double Multiply, Gray Background)", "Sprite (Double Multiply, Gray Background)", ""))
        items.append(("Interface Bitmap", "Interface Bitmap", ""))
        items.append(("Warp Map (EMBM)", "Warp Map (EMBM)", ""))
        items.append(("Vector Map", "Vector Map", ""))
        items.append(("3D Texture", "3D Texture", ""))
        items.append(("Float Map (WARNING)", "Float Map (WARNING)", ""))
        items.append(("Half float Map (HALF HUGE)", "Half float Map (HALF HUGE)", ""))
        items.append(("Height Map (for Parallax)", "Height Map (for Parallax)", ""))
        items.append(("ZBrush Bump Map (from Bump Map)", "ZBrush Bump Map (from Bump Map)", ""))
        items.append(("Normal Map (aka zbump)", "Normal Map (aka zbump)", ""))
        items.append(("Detail ZBrush Bump Map", "Detail ZBrush Bump Map", ""))
        items.append(("Detail Normal Map", "Detail Normal Map", ""))
        items.append(("Blend Map (linear for terrains)", "Blend Map (linear for terrains)", ""))
        items.append(("Palettized --- effects only", "Palettized --- effects only", ""))
        items.append(("CHUD related bitmap", "CHUD related bitmap", ""))
        items.append(("Lightmap Array", "Lightmap Array", ""))
        items.append(("Water Array", "Water Array", ""))
        items.append(("Interface Sprite", "Interface Sprite", ""))
        items.append(("Interface Gradient", "Interface Gradient", ""))
        items.append(("Material Map", "Material Map", ""))
        items.append(("Smoke Warp", "Smoke Warp", ""))
        items.append(("Mux Material Blend Map", "Mux Material Blend Map", ""))
        items.append(("Cubemap Gel", "Cubemap Gel", ""))
        items.append(("Lens Flare gamma 2.2 -- effects only", "Lens Flare gamma 2.2 -- effects only", ""))
        items.append(("Signed Noise", "Signed Noise", ""))
        items.append(("Roughness Map (auto)", "Roughness Map (auto)", ""))
        if h4:
            items.append(("Normal Map (from Standard Orientation of Maya, Modo, Zbrush)", "Normal Map (from Standard Orientation of Maya, Modo, Zbrush)", ""))
            items.append(("Color Grading", "Color Grading", ""))
            items.append(("Detail Normal Map (from Standard Orientation with distance face)", "Detail Normal Map (from Standard Orientation with distance face)", ""))
            items.append(("Diffuse Texture Array", "Diffuse Texture Array", ""))
            items.append(("Palettized Texture Array", "Palettized Texture Array", ""))
        
        return items


    bitmap_type: bpy.props.EnumProperty(
        name="Type",
        items=bitmap_type_items,
    )
    append_type: bpy.props.BoolProperty(
        name="Append Type",
        description="Appends the type of this bitmap to its exported name",
    )

    bitmap_path : bpy.props.StringProperty()

    export : bpy.props.BoolProperty(
        name="Export",
        description="Toggles whether this image should be exported as a bitmap",
        default=True,
    )

    use_image_path : bpy.props.BoolProperty(
        name="Use Image Path",
        description="Toggles whether this image should be exported as a bitmap",
    )

    reexport_tiff : bpy.props.BoolProperty(
        name="Re-Export TIFF",
        description="Forces this bitmap's source file (TIFF) to be re-exported. By default the Bitmap exporter will skip exporting a new TIFF file provided the following conditions are met: a TIFF file already exists, is not packed data in this blend, and is located within the data directory",
    )

    filepath : bpy.props.StringProperty()
    source_name : bpy.props.StringProperty()

    def update_bitmap_dir(self, context):

        self["bitmap_dir"] = clean_tag_path(self["bitmap_dir"]).strip('"')

    def get_bitmap_dir(self):
        context = bpy.context
        is_asset = valid_nwo_asset(context)
        if is_asset:
            return self.get("bitmap_dir", os.path.join(get_asset_path(), "bitmaps"))
        return self.get("bitmap_dir", "")
    
    def set_bitmap_dir(self, value):
        self['bitmap_dir'] = value

    bitmap_dir : bpy.props.StringProperty(
        name="Tiff Directory",
        description="Specifies where the exported tiff should be saved (if it is not externally linked). Defaults to the asset bitmaps folder",
        update=update_bitmap_dir,
        get=get_bitmap_dir,
        set=set_bitmap_dir,
    )