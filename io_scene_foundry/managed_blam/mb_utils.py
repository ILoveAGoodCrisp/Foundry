import os
import bpy
from io_scene_foundry.utils.nwo_utils import get_ek_path

##### UTIL FUNCTIONS


def get_bungie(report=None):
    """Get a reference to Bungie"""
    mb_path = os.path.join(get_ek_path(), "bin", "managedblam")
    try:
        import clr

        try:
            clr.AddReference(mb_path)
            print(mb_path)
            if bpy.context.scene.nwo.game_version == "reach":
                import Bungie
            else:
                import Corinth as Bungie
        except:
            print("Failed to add reference to ManagedBlam")
            # return({'CANCELLED'})
    except:
        print("Failed to import clr")
        report(
            {
                "ERROR",
                "Failed to import modules to connect to ManagedBlam. Process aborted",
            }
        )

    return Bungie


def get_tag_and_path(Bungie, user_path):
    """Return the tag and bungie tag path for tag creation"""
    relative_path, tag_ext = get_path_and_ext(user_path)
    tag = Bungie.Tags.TagFile()
    tag_path = Bungie.Tags.TagPath.FromPathAndExtension(relative_path, tag_ext)

    return tag, tag_path

def get_tag_path(Bungie, user_path):
    """Return the bungie tag path for tag creation"""
    relative_path, tag_ext = get_path_and_ext(user_path)
    tag_path = Bungie.Tags.TagPath.FromPathAndExtension(relative_path, tag_ext)

    return tag_path


def get_path_and_ext(user_path):
    """Splits a file path into path and extension"""
    return user_path.rpartition(".")[0], user_path.rpartition(".")[2]


# ELMENTS

def block_new_element(block):
    """Create a new tag element in the given block and returns the element"""
    block.AddElement()
    index = len(block.Elements) - 1
    return block[index]

def block_new_element_by_name(parent, block_name):
    """Create a new tag element in the given block and returns the element"""
    block = parent.SelectField(block_name)
    block.AddElement()
    index = block.Elements.Count - 1
    return block.Elements[index]

# Set Values
def field_set_value(field, value):
    """Sets the string value of the given field - Supports StringIDs"""
    return

def field_set_value_by_name(element, field_name: str, value):
    """Sets the string value of the given field - Supports StringIDs"""
    field = element.SelectField(field_name)
    field_type_str = str(field.FieldType)
    match field_type_str:
        case "StringId":
            field.SetStringData(value)
        case "LongEnum":
            field.SetValue(value)
        case "Reference":
            field.Path = get_tag_path(get_bungie(), value)
        case "WordInteger":
            field.SetStringData(value)

# Tag Field Types ENUMs
# 0 String
# 1 LongString
# 2 StringId
# 3 OldStringId
# 4 CharInteger
# 5 ShortInteger
# 6 LongInteger
# 7 Int64Integer
# 8 Angle
# 9 Tag
# 10 CharEnum
# 11 ShortEnum
# 12 LongEnum
# 13 Flags
# 14 WordFlags
# 15 ByteFlags
# 16 Point2d
# 17 Rectangle2d
# 18 RgbPixel32
# 19 ArgbPixel32
# 20 Real
# 21 RealSlider
# 22 RealFraction
# 23 RealPoint2d
# 24 RealPoint3d
# 25 RealVector2d
# 26 RealVector3d
# 27 RealQuaternion
# 28 RealEulerAngles2d
# 29 RealEulerAngles3d
# 30 RealPlane2d
# 31 RealPlane3d
# 32 RealRgbColor
# 33 RealArgbColor
# 34 RealHsvColor
# 35 RealAhsvColor
# 36 ShortIntegerBounds
# 37 AngleBounds
# 38 RealBounds
# 39 RealFractionBounds
# 40 Reference
# 41 Block
# 42 BlockFlags
# 43 WordBlockFlags
# 44 ByteBlockFlags
# 45 CharBlockIndex
# 46 CharBlockIndexCustomSearch
# 47 ShortBlockIndex
# 48 ShortBlockIndexCustomSearch
# 49 LongBlockIndex
# 50 LongBlockIndexCustomSearch
# 51 Data
# 52 VertexBuffer
# 53 Pad
# 54 UselessPad
# 55 Skip
# 56 Explanation
# 57 Custom
# 58 Struct
# 59 Array
# 60 Resource
# 61 Interop
# 62 Terminator




